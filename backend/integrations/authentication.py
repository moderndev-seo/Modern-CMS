"""Bounded signed tenant bootstrap and hash-only service credentials."""

import hashlib
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone as dt_timezone
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from integrations.models import IntegrationConnection, IntegrationCredential

SALT = "modern-practice.fictional-integration.v1"


def enabled(org_id):
    return bool(getattr(settings, "INTEGRATION_FOUNDATION_ENABLED", False)) and str(
        org_id
    ) in {str(v) for v in getattr(settings, "INTEGRATION_TEST_ORGS", ())}


def token_digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def keys():
    return getattr(settings, "INTEGRATION_SIGNING_KEYS", {"1": settings.SECRET_KEY})


def issue_token(credential):
    version = str(getattr(settings, "INTEGRATION_SIGNING_KEY_VERSION", "1"))
    claims = {
        "org": str(credential.org_id),
        "connection": str(credential.connection_id),
        "credential": str(credential.id),
        "version": version,
        "iat": credential.issued_at.timestamp(),
        "exp": credential.expires_at.timestamp(),
        "aud": settings.INTEGRATION_AUDIENCE,
    }
    locator = signing.dumps(claims, key=keys()[version], salt=SALT)
    return f"mpis1.{version}.{locator}.{secrets.token_urlsafe(32)}"


def decode(raw):
    try:
        if len(raw) > 2048:
            raise ValueError
        prefix, version, locator, secret = raw.split(".")
        if prefix != "mpis1" or len(secret) != 43 or version not in keys():
            raise ValueError
        claims = signing.loads(
            locator, key=keys()[version], fallback_keys=[], salt=SALT
        )
        if (
            set(claims)
            != {"org", "connection", "credential", "version", "iat", "exp", "aud"}
            or claims["version"] != version
            or claims["aud"] != settings.INTEGRATION_AUDIENCE
        ):
            raise ValueError
        now = timezone.now().timestamp()
        if (
            not claims["iat"] <= now < claims["exp"]
            or claims["exp"] - claims["iat"] > 30 * 86400
        ):
            raise ValueError
        for name in ("org", "connection", "credential"):
            claims[name] = str(UUID(claims[name]))
        return claims
    except (ValueError, TypeError, KeyError, signing.BadSignature, OverflowError):
        raise AuthenticationFailed("Invalid integration credential.") from None


@contextmanager
def tenant_transaction(org_id):
    """Validate deferred audit guards before restoring the tenant context."""
    if connection.vendor != "postgresql":
        raise RuntimeError("Integration foundation requires PostgreSQL")
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org', true)")
            previous = cursor.fetchone()[0] or ""
            cursor.execute(
                "SELECT set_config('app.current_org', %s, true)", [str(org_id)]
            )
        try:
            yield
            if not connection.needs_rollback:
                # Deferred guards query audit rows under forced RLS. They must
                # run while the authenticated practice is still selected, even
                # when this block is nested inside another transaction.
                guards = (
                    "mp_integration_namespace_audit_required, "
                    "mp_integration_connection_audit_required, "
                    "mp_integration_credential_audit_required, "
                    "mp_ingress_pending_required"
                )
                with connection.cursor() as cursor:
                    cursor.execute(f"SET CONSTRAINTS {guards} IMMEDIATE")
                    cursor.execute(f"SET CONSTRAINTS {guards} DEFERRED")
        except BaseException:
            # Raw SQL errors do not always mark Django's transaction as broken.
            # Roll back before any context-reset query can mask the cause.
            transaction.set_rollback(True)
            raise
        finally:
            if not connection.needs_rollback:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT set_config('app.current_org', %s, true)", [previous]
                        )
                except Exception:
                    connection.close()
                    raise
            # A failed transaction rolls LOCAL context back with the transaction.


@dataclass(frozen=True)
class ServicePrincipal:
    id: str
    credential_id: str
    is_authenticated: bool = True
    is_anonymous: bool = False


def resolve_service(raw, claims, required_scope="integration.probe"):
    conn = (
        IntegrationConnection.objects.select_for_update()
        .filter(id=claims["connection"], org_id=claims["org"])
        .first()
    )
    credential = (
        IntegrationCredential.objects.filter(
            id=claims["credential"], connection=conn, org_id=claims["org"]
        ).first()
        if conn
        else None
    )
    now = timezone.now()
    if (
        not credential
        or conn.status != "active"
        or conn.mode != "fictional"
        or credential.revoked_at is not None
        or now >= credential.expires_at
        or (credential.retire_at is not None and now >= credential.retire_at)
        or credential.scopes not in (["integration.probe"], ["integration.receive"])
        or not secrets.compare_digest(credential.token_digest, token_digest(raw))
        or credential.locator_key_version != claims["version"]
        or credential.expires_at
        != datetime.fromtimestamp(claims["exp"], dt_timezone.utc)
    ):
        raise AuthenticationFailed("Invalid integration credential.")
    if credential.scopes != [required_scope] or (
        required_scope == "integration.receive"
        and conn.capabilities.get("ingress") != "fixture.ingress/1"
    ):
        raise PermissionDenied("Credential scope does not permit this action.")
    return conn, credential


class IntegrationAuthentication(BaseAuthentication):
    def authenticate(self, request):
        if not getattr(request, "_integration_verified", False):
            raise AuthenticationFailed("Verified integration context required.")
        principal = getattr(request, "integration_principal", None)
        return (principal or request.profile.user, None)

    def authenticate_header(self, request):
        return "Bearer"
