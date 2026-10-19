"""Additive, practice-local metadata; no patient or financial domain effects."""

import uuid

from django.db import models
from django.utils import timezone


class PracticeMetadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey("common.Org", on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["org", "created_at"])]


class ProviderNamespace(PracticeMetadata):
    provider_key = models.CharField(max_length=64)
    account_key = models.CharField(max_length=128)
    environment = models.CharField(max_length=16, default="fictional")
    created_by_profile = models.ForeignKey("common.Profile", on_delete=models.PROTECT)

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_namespace"
        constraints = [
            models.UniqueConstraint(
                fields=["org", "provider_key", "account_key", "environment"],
                name="mp_namespace_binding_unique",
            )
        ]


class IntegrationConnection(PracticeMetadata):
    namespace = models.ForeignKey(ProviderNamespace, on_delete=models.PROTECT)
    label = models.CharField(max_length=100)
    adapter_key = models.CharField(max_length=64)
    manifest_version = models.CharField(max_length=32)
    manifest_digest = models.CharField(max_length=64)
    capabilities = models.JSONField()
    mode = models.CharField(max_length=16, default="fictional")
    status = models.CharField(max_length=16, default="active")
    authorization_generation = models.PositiveBigIntegerField(default=1)
    revision = models.PositiveBigIntegerField(default=1)
    created_by_profile = models.ForeignKey("common.Profile", on_delete=models.PROTECT)
    revoked_at = models.DateTimeField(null=True)

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_connection"
        constraints = [
            models.UniqueConstraint(
                fields=["namespace"],
                condition=~models.Q(status="revoked"),
                name="mp_one_live_connection",
            )
        ]


class IntegrationCredential(PracticeMetadata):
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.PROTECT)
    token_digest = models.CharField(max_length=64, unique=True)
    digest_version = models.CharField(max_length=32, default="sha256-v1")
    locator_key_version = models.CharField(max_length=32, default="1")
    scopes = models.JSONField()
    issued_by_profile = models.ForeignKey(
        "common.Profile",
        on_delete=models.PROTECT,
        related_name="issued_integration_credentials",
    )
    issued_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    retire_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    revoked_by_profile = models.ForeignKey(
        "common.Profile",
        null=True,
        on_delete=models.PROTECT,
        related_name="revoked_integration_credentials",
    )
    revocation_reason_code = models.CharField(max_length=32, null=True)
    replaces_credential = models.ForeignKey("self", null=True, on_delete=models.PROTECT)

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_credential"


class IntegrationAuditEvent(PracticeMetadata):
    namespace = models.ForeignKey(ProviderNamespace, on_delete=models.PROTECT)
    connection = models.ForeignKey(
        IntegrationConnection, null=True, on_delete=models.PROTECT
    )
    credential = models.ForeignKey(
        IntegrationCredential, null=True, on_delete=models.PROTECT
    )
    actor_kind = models.CharField(max_length=16, default="human")
    actor_profile = models.ForeignKey(
        "common.Profile", null=True, on_delete=models.PROTECT
    )
    actor_credential = models.ForeignKey(
        IntegrationCredential,
        null=True,
        on_delete=models.PROTECT,
        related_name="actor_events",
    )
    action = models.CharField(max_length=32)
    reason_code = models.CharField(max_length=32)
    request_id = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    previous_generation = models.PositiveBigIntegerField(null=True)
    new_generation = models.PositiveBigIntegerField(null=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    details = models.JSONField(default=dict)

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_audit"
        constraints = [
            models.UniqueConstraint(
                fields=["org", "request_id"], name="mp_integration_command_unique"
            )
        ]
