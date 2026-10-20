"""Strict fictional input and receipt-bound encrypted replay primitives."""

import hashlib
import json
import re
from datetime import datetime, timezone
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from integrations.manifests import OBSERVATIONS, canonical

MAX_BYTES = 16384
SCHEMA = "fixture.ingress/1"
FORBIDDEN = {
    "org",
    "org_id",
    "organization",
    "organization_id",
    "tenant",
    "tenant_id",
    "patient_id",
    "verified",
    "verification",
    "actor",
    "actor_id",
    "reconciled",
    "financial_sign",
}
FIELDS = {"schema", "delivery_id", "event_type", "source_id", "occurred_at"}


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def validate_envelope(raw, source_class):
    """No free text, demographics, money or raw vendor bodies in this slice.

    A source UUID is synthetic evidence, not a Patient UUID or a resolved link.
    Unknown occurrence time is explicit null; known time must include an offset.
    """
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES or not raw:
        raise ValidationError("Invalid fictional envelope.")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        if not isinstance(data, dict):
            raise ValueError
        if set(data) & FORBIDDEN:
            raise PermissionDenied("Caller authority fields are not permitted.")
        if set(data) != FIELDS or data["schema"] != SCHEMA:
            raise ValueError
        event = data["event_type"]
        if not isinstance(event, str) or event not in OBSERVATIONS.get(
            source_class, ()
        ):
            raise PermissionDenied("Source cannot assert this event type.")
        for name in ("delivery_id", "source_id"):
            if not isinstance(data[name], str):
                raise ValueError
            data[name] = str(UUID(data[name]))
        occurred = data["occurred_at"]
        if occurred is not None:
            if not isinstance(occurred, str) or len(occurred) > 40:
                raise ValueError
            instant = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
            if instant.tzinfo is None or instant.utcoffset() is None:
                raise ValueError
            data["occurred_at"] = instant.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
        raise ValidationError("Invalid fictional envelope.") from None
    encoded = canonical(data).encode()
    return data, hashlib.sha256(encoded).hexdigest(), hashlib.sha256(raw).hexdigest()


def _fernet(version):
    # Dedicated replay keys, never a fallback to Django signing credentials.
    keyring = getattr(settings, "INTEGRATION_REPLAY_KEYS", {})
    if (
        not isinstance(version, str)
        or re.fullmatch(r"[A-Za-z0-9_-]{1,32}", version) is None
        or not isinstance(keyring, dict)
    ):
        raise ValueError("Replay encryption unavailable.")
    try:
        return Fernet(keyring[version])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Replay encryption unavailable.") from None


def seal_envelope(envelope, *, receipt_id, org_id, semantic_digest):
    version = getattr(settings, "INTEGRATION_REPLAY_KEY_VERSION", None)
    cipher = _fernet(version)
    bound = {
        "receipt": str(receipt_id),
        "org": str(org_id),
        "digest": semantic_digest,
        "envelope": envelope,
    }
    return version, cipher.encrypt(canonical(bound).encode()).decode("ascii")


def open_envelope(ciphertext, *, key_version, receipt_id, org_id, semantic_digest):
    try:
        if not isinstance(ciphertext, str) or len(ciphertext) > 32768:
            raise ValueError
        bound = json.loads(_fernet(key_version).decrypt(ciphertext.encode("ascii")))
        if (
            not isinstance(bound, dict)
            or set(bound) != {"receipt", "org", "digest", "envelope"}
            or bound["receipt"] != str(receipt_id)
            or bound["org"] != str(org_id)
            or bound["digest"] != semantic_digest
            or hashlib.sha256(canonical(bound["envelope"]).encode()).hexdigest()
            != semantic_digest
        ):
            raise ValueError
        return bound["envelope"]
    except (InvalidToken, ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError("Replay evidence unavailable.") from None
