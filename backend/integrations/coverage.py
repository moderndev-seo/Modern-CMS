"""Internal fictional ingestion checkpoints; never assert provider completeness."""

from django.db.models import Exists, OuterRef, Q

from integrations.models import IntegrationConnection as Connection
from integrations.models import IntegrationEventInbox as Inbox
from integrations.models import IntegrationObservation as Observation
from integrations.processing import _locked_practice, _practice


def _checkpoint(row):
    if row is None:
        return None
    return {"receipt_id": str(row.id), "received_at": row.created_at.isoformat()}


def stream_progress(org_id, connection_id):
    """Consistent local acceptance/application progress for one acquisition stream.

    The local tuple (received_at, receipt_id) is a snapshot ordering, not a vendor
    cursor or proof of historical inventory. A gap blocks the applied checkpoint.
    No payload, source identity or patient data is returned.
    """
    org_id = _practice(org_id)
    with _locked_practice(org_id):
        conn = (
            Connection.objects.select_for_update()
            .filter(pk=connection_id, org_id=org_id)
            .first()
        )
        if (
            conn is None
            or conn.mode != "fictional"
            or conn.capabilities.get("ingress") != "fixture.ingress/1"
        ):
            raise ValueError("Fictional stream unavailable.")
        applied = Observation.objects.filter(
            org_id=org_id, work__pending__inbox_id=OuterRef("pk")
        )
        receipts = Inbox.objects.filter(org_id=org_id, connection_id=conn.id).annotate(
            is_applied=Exists(applied)
        )
        count = receipts.count()
        applied_count = receipts.filter(is_applied=True).count()
        latest = receipts.order_by("-created_at", "-id").first()
        gap = receipts.filter(is_applied=False).order_by("created_at", "id").first()
        prefix = receipts.filter(is_applied=True)
        if gap is not None:
            prefix = prefix.filter(
                Q(created_at__lt=gap.created_at)
                | Q(created_at=gap.created_at, id__lt=gap.id)
            )
        contiguous = prefix.order_by("-created_at", "-id").first()
        return {
            "stream": "acquisition",
            "accepted_count": count,
            "applied_count": applied_count,
            "unresolved_count": count - applied_count,
            "ingestion_checkpoint": _checkpoint(latest),
            "applied_checkpoint": _checkpoint(contiguous),
            "processing_status": "no_data"
            if not count
            else "caught_up"
            if count == applied_count
            else "partial",
            "source_coverage": "unknown",
            "provider_cursor": None,
        }
