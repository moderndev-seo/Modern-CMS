"""Serialized metadata commands, idempotent audit, and one-time secrets."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, ValidationError

from integrations.authentication import issue_token, token_digest
from integrations.manifests import ALL_MANIFESTS, digest
from integrations.models import IntegrationAuditEvent as Audit
from integrations.models import IntegrationConnection as Connection
from integrations.models import IntegrationCredential as Credential
from integrations.models import ProviderNamespace as Namespace


class Conflict(APIException):
    status_code = 409
    default_detail = "Stale revision or conflicting command."


def namespace_data(row, detail=False):
    data = {
        "id": str(row.id),
        "provider_key": row.provider_key,
        "environment": row.environment,
    }
    if detail:
        data["account_key"] = row.account_key
    return data


def connection_data(row, audit=None):
    return {
        "id": str(row.id),
        "namespace_id": str(row.namespace_id),
        "label": row.label,
        "mode": row.mode,
        "manifest_id": row.capabilities["id"],
        "manifest_version": row.manifest_version,
        "status": audit.details.get("status", "active") if audit else row.status,
        "revision": audit.new_generation if audit else row.revision,
        "authorization_generation": audit.new_generation
        if audit
        else row.authorization_generation,
    }


def credential_data(row):
    return {
        "id": str(row.id),
        "issued_by_profile": str(row.issued_by_profile_id),
        "scopes": row.scopes,
        "issued_at": row.issued_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
        "retire_at": row.retire_at.isoformat() if row.retire_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "secret_available": False,
    }


def replay_result(audit):
    if audit.action == "namespace.created":
        return namespace_data(audit.namespace, detail=True)
    if audit.action.startswith("credential."):
        data = credential_data(audit.credential)
        # Reconstruct the original nonsecret result, not later retirement/revocation.
        data["retire_at"] = (
            audit.details.get("retire_at")
            if audit.action == "credential.revoked"
            else None
        )
        data["revoked_at"] = (
            audit.occurred_at.isoformat()
            if audit.action == "credential.revoked"
            else None
        )
        data["revision"] = audit.new_generation
        return data
    return connection_data(audit.connection, audit)


def command(profile, kind, data, connection_id=None, credential_id=None):
    # Middleware locks the practice and active admin for the full request. This
    # also serializes namespace commands and same request_id across connections.
    with transaction.atomic():
        fingerprint = digest(
            {
                "kind": kind,
                "connection": str(connection_id) if connection_id else None,
                "credential": str(credential_id) if credential_id else None,
                "data": {
                    k: v.isoformat()
                    if hasattr(v, "isoformat")
                    else str(v)
                    if k.endswith("id")
                    else v
                    for k, v in data.items()
                },
            }
        )
        prior = Audit.objects.filter(
            org=profile.org, request_id=data["request_id"]
        ).first()
        if prior:
            if (
                prior.request_fingerprint != fingerprint
                or prior.actor_profile_id != profile.id
            ):
                raise Conflict()
            return replay_result(prior), 200
        now = timezone.now()
        conn = None
        key = None
        previous = None
        details = {}
        created = False
        reason = data.get("reason_code", "fixture_setup")
        if connection_id:
            conn = (
                Connection.objects.select_for_update()
                .filter(org=profile.org, id=connection_id)
                .first()
            )
            if not conn:
                raise NotFound()
            if conn.revision != data["expected_revision"]:
                raise Conflict()
            previous = conn.revision
            namespace = conn.namespace
        if kind == "namespace":
            namespace, created = Namespace.objects.get_or_create(
                org=profile.org,
                provider_key=data["provider_key"],
                account_key=data["account_key"],
                environment="fictional",
                defaults={"created_by_profile": profile},
            )
            action = "namespace.created"
        elif kind == "connection":
            namespace = Namespace.objects.filter(
                org=profile.org, id=data["namespace_id"]
            ).first()
            if not namespace:
                raise NotFound()
            selected = ALL_MANIFESTS[data["manifest_id"]]
            if namespace.provider_key != data["manifest_id"].split(":")[0]:
                raise ValidationError("Manifest provider must match namespace.")
            if (
                Connection.objects.filter(namespace=namespace)
                .exclude(status="revoked")
                .exists()
            ):
                raise Conflict("A non-revoked connection already exists.")
            conn = Connection.objects.create(
                org=profile.org,
                namespace=namespace,
                label=data["label"],
                adapter_key=namespace.provider_key,
                manifest_version=selected["version"],
                manifest_digest=digest(selected),
                capabilities=selected,
                created_by_profile=profile,
            )
            action = "connection.created"
            details = {"status": "active"}
        elif kind == "state":
            target = data["target"]
            allowed = {
                ("active", "paused"): "maintenance",
                ("paused", "active"): "resume",
            }
            if target == "revoked" and reason in (
                "compromise",
                "retired",
                "operator_revoke",
            ):
                if conn.status == "revoked":
                    raise Conflict(
                        "Connection already revoked; retry original command."
                    )
                conn.revoked_at = now
                for old in Credential.objects.filter(
                    connection=conn, revoked_at__isnull=True
                ):
                    (
                        old.revoked_at,
                        old.revoked_by_profile,
                        old.revocation_reason_code,
                    ) = now, profile, reason
                    old.save(
                        update_fields=[
                            "revoked_at",
                            "revoked_by_profile",
                            "revocation_reason_code",
                        ]
                    )
            elif allowed.get((conn.status, target)) != reason:
                raise ValidationError("Invalid lifecycle transition or reason.")
            conn.status = target
            action = {
                "active": "connection.resumed",
                "paused": "connection.paused",
                "revoked": "connection.revoked",
            }[target]
            details = {"status": target}
        elif kind == "issue":
            if conn.status != "active":
                raise Conflict("Active connection required.")
            if (
                data["scopes"] == ["integration.receive"]
                and conn.capabilities.get("ingress") != "fixture.ingress/1"
            ):
                raise ValidationError("Receive scope requires a receive manifest.")
            expires = data["expires_at"]
            if not now < expires <= now + timedelta(days=30):
                raise ValidationError("Expiry must be in the next 30 days.")
            old = None
            if data.get("replaces_id"):
                old = Credential.objects.filter(
                    org=profile.org,
                    connection=conn,
                    id=data["replaces_id"],
                    revoked_at__isnull=True,
                ).first()
                if not old:
                    raise NotFound()
                overlap = data.get("overlap_seconds", 0)
                if overlap:
                    cutoff = min(now + timedelta(seconds=overlap), old.expires_at)
                    old.retire_at = (
                        min(old.retire_at, cutoff) if old.retire_at else cutoff
                    )
                    old.save(update_fields=["retire_at"])
                else:
                    (
                        old.revoked_at,
                        old.revoked_by_profile,
                        old.revocation_reason_code,
                    ) = now, profile, "rotation"
                    old.save(
                        update_fields=[
                            "revoked_at",
                            "revoked_by_profile",
                            "revocation_reason_code",
                        ]
                    )
            elif data.get("overlap_seconds", 0):
                raise ValidationError("Overlap requires a replacement credential.")
            if (
                Credential.objects.filter(
                    connection=conn, revoked_at__isnull=True
                ).count()
                >= 2
            ):
                raise Conflict("Revoke a credential before issuing another.")
            key = Credential(
                org=profile.org,
                connection=conn,
                issued_by_profile=profile,
                issued_at=now,
                expires_at=expires,
                scopes=data["scopes"],
                replaces_credential=old,
                locator_key_version=str(
                    getattr(settings, "INTEGRATION_SIGNING_KEY_VERSION", "1")
                ),
            )
            raw = issue_token(key)
            key.token_digest = token_digest(raw)
            key.save()
            action = "credential.rotated" if old else "credential.issued"
            reason = "rotation" if old else "fixture_setup"
            details = {
                "scopes": key.scopes,
                "expires_at": expires.isoformat(),
                "replaces_credential_id": str(old.id) if old else None,
                "retire_at": old.retire_at.isoformat()
                if old and old.retire_at
                else None,
            }
        elif kind == "revoke":
            key = Credential.objects.filter(
                org=profile.org, connection=conn, id=credential_id
            ).first()
            if not key:
                raise NotFound()
            if key.revoked_at is not None:
                raise Conflict("Credential already revoked; retry original command.")
            if reason not in ("compromise", "retired", "operator_revoke"):
                raise ValidationError("Invalid revocation reason.")
            if reason == "compromise":
                raise ValidationError(
                    "Revoke the connection to revoke all compromised credentials."
                )
            key.revoked_at, key.revoked_by_profile, key.revocation_reason_code = (
                now,
                profile,
                reason,
            )
            key.save(
                update_fields=[
                    "revoked_at",
                    "revoked_by_profile",
                    "revocation_reason_code",
                ]
            )
            action = "credential.revoked"
            details = {
                "retire_at": key.retire_at.isoformat() if key.retire_at else None
            }
        else:
            raise ValidationError("Unknown command.")
        if previous is not None:
            conn.revision += 1
            conn.authorization_generation += 1
            conn.save(
                update_fields=[
                    "revision",
                    "authorization_generation",
                    "status",
                    "revoked_at",
                ]
            )
        audit = Audit.objects.create(
            org=profile.org,
            namespace=namespace,
            connection=conn,
            credential=key,
            actor_profile=profile,
            action=action,
            reason_code=reason,
            request_id=data["request_id"],
            request_fingerprint=fingerprint,
            previous_generation=previous,
            new_generation=conn.revision if conn else None,
            occurred_at=now,
            details=details,
        )
        result = replay_result(audit)
        if kind == "issue":
            result.update(secret_available=True, credential=raw)
        return result, (201 if kind in ("connection", "issue") or created else 200)
