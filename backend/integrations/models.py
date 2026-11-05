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


class IntegrationEventInbox(PracticeMetadata):
    """Immutable delivery evidence; not a canonical patient observation."""

    namespace = models.ForeignKey(ProviderNamespace, on_delete=models.PROTECT)
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.PROTECT)
    credential = models.ForeignKey(IntegrationCredential, on_delete=models.PROTECT)
    delivery_id = models.UUIDField()
    schema_version = models.CharField(max_length=32, default="fixture.ingress/1")
    manifest_digest = models.CharField(max_length=64)
    authorization_generation = models.PositiveBigIntegerField()
    semantic_digest = models.CharField(max_length=64)
    transport_digest = models.CharField(max_length=64)
    replay_key_version = models.CharField(max_length=32)
    replay_ciphertext = models.TextField()
    replay_retention_policy = models.CharField(max_length=32, default="fixture-24h-v1")
    replay_purged_at = models.DateTimeField(null=True)

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_inbox"
        constraints = [
            models.UniqueConstraint(
                fields=["namespace", "delivery_id"],
                name="mp_ingress_delivery_unique",
            )
        ]


class IntegrationPendingWork(PracticeMetadata):
    """Durable pending marker only; worker lease/state belongs to Phase 2C."""

    inbox = models.OneToOneField(IntegrationEventInbox, on_delete=models.PROTECT)

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_pending"


class IntegrationDeliveryConflict(PracticeMetadata):
    inbox = models.ForeignKey(IntegrationEventInbox, on_delete=models.PROTECT)
    credential = models.ForeignKey(IntegrationCredential, on_delete=models.PROTECT)
    attempted_digest = models.CharField(max_length=64)

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_delivery_conflict"
        constraints = [
            models.UniqueConstraint(
                fields=["inbox", "credential", "attempted_digest"],
                name="mp_ingress_conflict_unique",
            )
        ]


class IntegrationProcessingWork(PracticeMetadata):
    """Mutable scheduling companion; never replaces durable receipt evidence."""

    pending = models.OneToOneField(IntegrationPendingWork, on_delete=models.PROTECT)
    state = models.CharField(max_length=24, default="accepted")
    next_attempt_at = models.DateTimeField(default=timezone.now)
    attempt_count = models.PositiveIntegerField(default=0)
    lease_token = models.UUIDField(null=True)
    lease_expires_at = models.DateTimeField(null=True)
    reason_code = models.CharField(max_length=32, default="")

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_work"
        indexes = [models.Index(fields=["org", "state", "next_attempt_at"])]


class IntegrationProcessingAttempt(PracticeMetadata):
    """Append-only claim evidence; completion is a later processing concern."""

    work = models.ForeignKey(IntegrationProcessingWork, on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    lease_token = models.UUIDField(unique=True)
    lease_expires_at = models.DateTimeField()

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_attempt"
        constraints = [
            models.UniqueConstraint(
                fields=["work", "number"], name="mp_processing_attempt_unique"
            )
        ]


class IntegrationObservation(PracticeMetadata):
    """Immutable fictional observation, not a patient link or verified outcome."""

    work = models.OneToOneField(IntegrationProcessingWork, on_delete=models.PROTECT)
    lease_token = models.UUIDField()
    mapping_version = models.CharField(max_length=32, default="fixture.normalized/1")
    event_type = models.CharField(max_length=64)
    source_id = models.UUIDField()
    occurred_at = models.DateTimeField(null=True)
    semantic_digest = models.CharField(max_length=64)

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_observation"


class IntegrationStreamPage(PracticeMetadata):
    """Immutable fictional page accepted only after all its receipts persist."""

    connection = models.ForeignKey(IntegrationConnection, on_delete=models.PROTECT)
    stream = models.CharField(max_length=32, default="acquisition")
    position = models.PositiveBigIntegerField(default=1)
    cursor = models.UUIDField()
    previous_cursor = models.UUIDField(null=True)
    receipt_ids = models.JSONField()
    authorization_generation = models.PositiveBigIntegerField()

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_stream_page"
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "stream", "position"],
                name="mp_stream_position_unique",
            ),
            models.UniqueConstraint(
                fields=["connection", "stream", "cursor"],
                name="mp_stream_cursor_unique",
            ),
            models.UniqueConstraint(
                fields=["connection", "stream", "previous_cursor"],
                name="mp_stream_successor_unique",
            ),
            models.UniqueConstraint(
                fields=["connection", "stream"],
                condition=models.Q(previous_cursor__isnull=True),
                name="mp_stream_root_unique",
            ),
        ]


class IntegrationAppliedPrefix(PracticeMetadata):
    """Verified acquisition prefix cache over immutable pages and observations."""

    connection = models.OneToOneField(IntegrationConnection, on_delete=models.PROTECT)
    position = models.PositiveBigIntegerField(default=0)

    class Meta(PracticeMetadata.Meta):
        db_table = "mp_integration_applied_prefix"
