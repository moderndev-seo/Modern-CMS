"""Fictional page checkpoints only; no vendor polling or completeness claims."""

from uuid import UUID

from integrations.models import IntegrationAppliedPrefix as AppliedPrefix
from integrations.models import IntegrationConnection as Connection
from integrations.models import IntegrationEventInbox as Inbox
from integrations.models import IntegrationObservation as Observation
from integrations.models import IntegrationStreamPage as Page
from integrations.processing import _locked_practice, _practice


def accept_page(org_id, connection_id, *, cursor, previous_cursor, receipt_ids):
    """Persist an immutable page after all listed receipts are accepted.

    Tokens are UUIDs for this fictional contract, not arbitrary provider secrets.
    Empty pages are valid transport checkpoints, not evidence of zero outcomes.
    """
    org_id = _practice(org_id)
    cursor = UUID(str(cursor))
    previous_cursor = (
        UUID(str(previous_cursor)) if previous_cursor is not None else None
    )
    if not isinstance(receipt_ids, list) or len(receipt_ids) > 100:
        raise ValueError("Page requires at most 100 receipt references.")
    ids = sorted(str(UUID(str(value))) for value in receipt_ids)
    if len(set(ids)) != len(ids):
        raise ValueError("Page receipt references must be unique.")
    with _locked_practice(org_id):
        conn = (
            Connection.objects.select_for_update()
            .filter(pk=connection_id, org_id=org_id)
            .first()
        )
        if (
            conn is None
            or conn.status != "active"
            or conn.mode != "fictional"
            or conn.capabilities.get("ingress") != "fixture.ingress/1"
        ):
            raise ValueError("Fictional stream unavailable.")
        prior = Page.objects.filter(
            org_id=org_id, connection=conn, cursor=cursor
        ).first()
        if prior:
            if prior.previous_cursor != previous_cursor or prior.receipt_ids != ids:
                raise ValueError("Page cursor conflicts with accepted content.")
            return str(prior.id)
        if Inbox.objects.filter(
            org_id=org_id,
            connection=conn,
            id__in=ids,
            authorization_generation=conn.authorization_generation,
        ).count() != len(ids):
            raise ValueError("Page requires durable same-stream receipts.")
        head = (
            Page.objects.filter(org_id=org_id, connection=conn)
            .order_by("-position")
            .first()
        )
        if (
            previous_cursor != (head.cursor if head else None)
            or cursor == previous_cursor
        ):
            raise ValueError("Page must extend current cursor.")
        row = Page.objects.create(
            org_id=org_id,
            connection=conn,
            cursor=cursor,
            previous_cursor=previous_cursor,
            receipt_ids=ids,
            authorization_generation=conn.authorization_generation,
        )
        return str(row.id)


def page_progress(org_id, connection_id):
    """Advance a durable prefix by at most 100 pages and report local progress.

    This internal operation writes a verified cache; repeated calls resume from
    it. Immutable pages/observations make previously verified progress stable.
    """
    org_id = _practice(org_id)
    with _locked_practice(org_id):
        if not Connection.objects.filter(pk=connection_id, org_id=org_id).exists():
            raise ValueError("Fictional stream unavailable.")
        pages = Page.objects.filter(org_id=org_id, connection_id=connection_id)
        head = pages.order_by("-position").first()
        checkpoint, _ = AppliedPrefix.objects.get_or_create(
            org_id=org_id, connection_id=connection_id
        )
        batch = list(
            pages.filter(position__gt=checkpoint.position).order_by("position")[:100]
        )
        ids = {value for page in batch for value in page.receipt_ids}
        applied = {
            str(value)
            for value in Observation.objects.filter(
                org_id=org_id, work__pending__inbox_id__in=ids
            ).values_list("work__pending__inbox_id", flat=True)
        }
        prefix = pages.filter(position=checkpoint.position).first()
        for page in batch:
            if not set(page.receipt_ids).issubset(applied):
                break
            prefix = page
        if prefix and prefix.position > checkpoint.position:
            checkpoint.position = prefix.position
            checkpoint.save(update_fields=["position"])
        return {
            "ingestion_cursor": str(head.cursor) if head else None,
            "applied_cursor": str(prefix.cursor) if prefix else None,
            "accepted_pages": head.position if head else 0,
            "pages_examined": len(batch),
            "scan_complete": head is None
            or not batch
            or batch[-1].position == head.position,
            "source_coverage": "unknown",
        }
