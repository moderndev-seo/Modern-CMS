"""Bounded fictional retention; no receipt deletion or automatic event replay."""

from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.utils import timezone

from common.models import Org
from integrations.authentication import tenant_transaction
from integrations.ingress import open_envelope
from integrations.models import IntegrationEventInbox as Inbox

POLICY = "fixture-24h-v1"
REPLAY_WINDOW = timedelta(hours=24)


def open_receipt(row):
    """Policy-enforcing entry point for a future authorized replay consumer."""
    try:
        # Do not trust a cached pre-purge row, or an object from another context.
        row = Inbox.objects.get(pk=row.pk, org_id=row.org_id)
    except Inbox.DoesNotExist:
        raise ValueError("Replay evidence unavailable.") from None
    if (
        row.replay_retention_policy != POLICY
        or row.replay_purged_at is not None
        or timezone.now() >= row.created_at + REPLAY_WINDOW
    ):
        raise ValueError("Replay evidence unavailable.")
    return open_envelope(
        row.replay_ciphertext,
        key_version=row.replay_key_version,
        receipt_id=row.id,
        org_id=row.org_id,
        semantic_digest=row.semantic_digest,
    )


def purge_expired(org_id, limit=100):
    """Explicit operator maintenance, including when intake is disabled.

    No public API and no service credential authority. Only explicit fictional
    TEST allowlist entries are eligible; this is not a real-data retention policy.
    """
    org_id = str(UUID(str(org_id)))
    if org_id not in {
        str(value) for value in getattr(settings, "INTEGRATION_TEST_ORGS", ())
    }:
        raise ValueError("Practice is not allowlisted for fictional maintenance.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("Batch limit must be between 1 and 1000.")
    with tenant_transaction(org_id):
        if not Org.objects.select_for_update().filter(pk=org_id).exists():
            raise ValueError("Practice unavailable.")
        rows = list(
            Inbox.objects.select_for_update()
            .filter(
                org_id=org_id,
                replay_retention_policy=POLICY,
                replay_purged_at__isnull=True,
                created_at__lte=timezone.now() - REPLAY_WINDOW,
            )
            .order_by("created_at", "id")[:limit]
        )
        for row in rows:
            # The SQL guard validates expiration using database time and stamps
            # the permanent purge fact. All other receipt fields stay immutable.
            row.replay_ciphertext = ""
            row.replay_purged_at = timezone.now()
            row.save(update_fields=["replay_ciphertext", "replay_purged_at"])
        return len(rows)
