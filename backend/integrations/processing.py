"""Opt-in fictional scheduling and observations; no patient or cash effects."""

from contextlib import contextmanager
from datetime import datetime, timedelta
from random import SystemRandom
from uuid import UUID, uuid4

from django.conf import settings
from django.db import connection
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from common.models import Org
from integrations.authentication import enabled, tenant_transaction
from integrations.ingress import validate_envelope
from integrations.manifests import ALL_MANIFESTS, canonical, digest
from integrations.models import IntegrationConnection as Connection
from integrations.models import IntegrationObservation as Observation
from integrations.models import IntegrationPendingWork as Pending
from integrations.models import IntegrationProcessingAttempt as Attempt
from integrations.models import IntegrationProcessingWork as Work
from integrations.retention import REPLAY_WINDOW, open_receipt

LEASE = timedelta(minutes=2)
MAX_ATTEMPTS = 6
_RANDOM = SystemRandom()


def _practice(org_id):
    org_id = str(UUID(str(org_id)))
    if not getattr(settings, "INTEGRATION_PROCESSING_ENABLED", False) or not enabled(
        org_id
    ):
        raise ValueError("Fictional processing is disabled for this practice.")
    return org_id


def _limit(limit):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("Batch limit must be between 1 and 100.")
    return limit


@contextmanager
def _locked_practice(org_id):
    with tenant_transaction(org_id):
        # Same order as receive/lifecycle: Org, connection, then work. Bounded
        # batches serialize within one practice, never across all practices.
        if not Org.objects.select_for_update().filter(pk=org_id).exists():
            raise ValueError("Practice unavailable.")
        yield
        # Flush our deferred evidence invariant before tenant context restoration.
        with connection.cursor() as cursor:
            cursor.execute(
                "SET CONSTRAINTS mp_processing_claim_required, mp_work_observation_required, mp_observation_result_required IMMEDIATE"
            )
            cursor.execute(
                "SET CONSTRAINTS mp_processing_claim_required, mp_work_observation_required, mp_observation_result_required DEFERRED"
            )


def _blocked(row, conn, now):
    receipt = row.pending.inbox
    manifest = ALL_MANIFESTS.get(conn.capabilities.get("id"))
    if (
        conn.status != "active"
        or conn.mode != "fictional"
        or conn.authorization_generation != receipt.authorization_generation
        or conn.manifest_digest != receipt.manifest_digest
        or not manifest
        or digest(manifest) != conn.manifest_digest
        or conn.capabilities.get("ingress") != "fixture.ingress/1"
    ):
        return "revoked"
    if (
        receipt.replay_purged_at is not None
        or now >= receipt.created_at + REPLAY_WINDOW
    ):
        return "evidence_unavailable"
    return None


def _release(row, state, reason, *, due=None):
    row.state, row.reason_code = state, reason
    row.lease_token = row.lease_expires_at = None
    if due is not None:
        row.next_attempt_at = due
    row.save()


def _locked_work(org_id, work_id):
    candidate = (
        Work.objects.filter(pk=work_id, org_id=org_id)
        .select_related("pending__inbox")
        .first()
    )
    if candidate is None:
        return None, None
    conn = Connection.objects.select_for_update().get(
        pk=candidate.pending.inbox.connection_id, org_id=org_id
    )
    row = (
        Work.objects.select_for_update()
        .select_related("pending__inbox")
        .get(pk=work_id, org_id=org_id)
    )
    return row, conn


def prepare_work(org_id, limit=25):
    """Recover missing companions from durable markers, without broker reliance."""
    org_id, limit = _practice(org_id), _limit(limit)
    with _locked_practice(org_id):
        markers = list(
            Pending.objects.filter(
                org_id=org_id, integrationprocessingwork__isnull=True
            ).order_by("created_at", "id")[:limit]
        )
        for marker in markers:
            Work.objects.create(org_id=org_id, pending=marker)
        return len(markers)


def claim_work(org_id, limit=25):
    """Return opaque work/token pairs only after atomic claim evidence writes."""
    org_id, limit = _practice(org_id), _limit(limit)
    claims = []
    with _locked_practice(org_id):
        now = timezone.now()
        ids = list(
            Work.objects.filter(
                org_id=org_id,
                state__in=("accepted", "retry_due"),
                next_attempt_at__lte=now,
            )
            .order_by("next_attempt_at", "id")
            .values_list("id", flat=True)[:limit]
        )
        for work_id in ids:
            row, conn = _locked_work(org_id, work_id)
            reason = _blocked(row, conn, now)
            if reason:
                _release(row, "quarantined", reason)
                continue
            if row.attempt_count >= MAX_ATTEMPTS:
                _release(row, "terminal_failure", "attempts_exhausted")
                continue
            row.state, row.reason_code = "processing", ""
            row.attempt_count += 1
            row.lease_token = uuid4()
            row.lease_expires_at = min(
                now + LEASE, row.pending.inbox.created_at + REPLAY_WINDOW
            )
            row.save()
            Attempt.objects.create(
                org_id=org_id,
                work=row,
                number=row.attempt_count,
                lease_token=row.lease_token,
                lease_expires_at=row.lease_expires_at,
                created_at=now,
            )
            claims.append((str(row.id), str(row.lease_token)))
    return claims


def retry_work(org_id, work_id, lease_token, *, retry_after_seconds=0):
    """Release a current claim with bounded exponential jitter; stale tokens do nothing."""
    org_id = _practice(org_id)
    if (
        isinstance(retry_after_seconds, bool)
        or not isinstance(retry_after_seconds, int)
        or not 0 <= retry_after_seconds <= 86400
    ):
        raise ValueError("Retry delay must be an integer from 0 to 86400 seconds.")
    with _locked_practice(org_id):
        row, conn = _locked_work(org_id, work_id)
        now = timezone.now()
        if (
            row is None
            or row.state != "processing"
            or str(row.lease_token) != str(lease_token)
            or now >= row.lease_expires_at
        ):
            return False
        reason = _blocked(row, conn, now)
        if reason:
            _release(row, "quarantined", reason)
        elif row.attempt_count >= MAX_ATTEMPTS:
            _release(row, "terminal_failure", "attempts_exhausted")
        else:
            delay = max(
                retry_after_seconds,
                _RANDOM.randint(1, min(3600, 30 * 2 ** (row.attempt_count - 1))),
            )
            due = now + timedelta(seconds=delay)
            if due >= row.pending.inbox.created_at + REPLAY_WINDOW:
                _release(row, "terminal_failure", "evidence_unavailable")
            else:
                _release(row, "retry_due", "transient", due=due)
        return True


def recover_work(org_id, limit=25):
    """Bounded sweep of expired claims; authorization is checked before retry."""
    org_id, limit = _practice(org_id), _limit(limit)
    changed = 0
    with _locked_practice(org_id):
        now = timezone.now()
        # Expired leases are prioritized. Queued authority is also checked by
        # claim_work, so a backlog cannot prevent their denial at claim time.
        ids = list(
            Work.objects.filter(
                org_id=org_id, state="processing", lease_expires_at__lte=now
            )
            .order_by("lease_expires_at", "id")
            .values_list("id", flat=True)[:limit]
        )
        for work_id in ids:
            row, conn = _locked_work(org_id, work_id)
            reason = _blocked(row, conn, now)
            if reason:
                _release(row, "quarantined", reason)
            elif row.attempt_count >= MAX_ATTEMPTS:
                _release(row, "terminal_failure", "attempts_exhausted")
            else:
                _release(row, "retry_due", "lease_expired", due=now)
            changed += 1
    return changed


def apply_work(org_id, work_id, lease_token):
    """Normalize one fictional receipt and atomically commit its shadow observation.

    Repeated/stale delivery returns False. No patient matching or economic effect
    is inferred from a source UUID. Null occurrence time remains null.
    """
    org_id = _practice(org_id)
    with _locked_practice(org_id):
        row, conn = _locked_work(org_id, work_id)
        now = timezone.now()
        if (
            row is None
            or row.state != "processing"
            or str(row.lease_token) != str(lease_token)
            or now >= row.lease_expires_at
        ):
            return False
        reason = _blocked(row, conn, now)
        if reason:
            _release(row, "quarantined", reason)
            return False
        receipt = row.pending.inbox
        try:
            envelope = open_receipt(receipt)
            normalized, semantic, _ = validate_envelope(
                canonical(envelope).encode(), conn.capabilities["source_class"]
            )
            if semantic != receipt.semantic_digest or normalized["delivery_id"] != str(
                receipt.delivery_id
            ):
                raise ValueError("Invalid receipt evidence.")
        except (ValueError, PermissionDenied, ValidationError):
            # Missing/wrong keys or corrupt evidence never invent a fact.
            # Authorized replay after repair belongs to the later review phase.
            _release(row, "quarantined", "evidence_unavailable")
            return False
        Observation.objects.create(
            org_id=org_id,
            work=row,
            lease_token=row.lease_token,
            event_type=normalized["event_type"],
            source_id=normalized["source_id"],
            occurred_at=(
                datetime.fromisoformat(normalized["occurred_at"])
                if normalized["occurred_at"] is not None
                else None
            ),
            semantic_digest=semantic,
        )
        _release(row, "applied", "")
        return True
