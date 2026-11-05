"""Fictional durable page ordering and conservative applied progress."""

from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction

from common.testing import rls_org
from integrations import pages, processing
from integrations.models import IntegrationAppliedPrefix as AppliedPrefix
from integrations.models import IntegrationConnection as Connection
from integrations.models import IntegrationEventInbox as Inbox
from integrations.models import IntegrationStreamPage as Page
from integrations.tests import test_processing as scheduling

fictional = scheduling.fictional
replay_keys = scheduling.replay_keys
receiver = scheduling.receiver
receive_enabled = scheduling.receive_enabled
processing_enabled = scheduling.processing_enabled
accepted = scheduling.accepted


def accept(org, receiver, ids, previous=None, cursor=None):
    cursor = cursor or uuid4()
    return pages.accept_page(
        org, receiver[0], cursor=cursor, previous_cursor=previous, receipt_ids=ids
    ), cursor


def test_empty_stream_and_empty_page_keep_unknown(receiver, org_a):
    assert pages.page_progress(org_a.id, receiver[0])["accepted_pages"] == 0
    _, cursor = accept(org_a.id, receiver, [])
    result = pages.page_progress(org_a.id, receiver[0])
    assert result["ingestion_cursor"] == result["applied_cursor"] == str(cursor)
    assert result["source_coverage"] == "unknown"


def test_missing_receipt_does_not_advance(accepted, receiver):
    _, cursor = accept(accepted, receiver, [])
    with pytest.raises(ValueError, match="durable"):
        accept(accepted, receiver, [uuid4()], previous=cursor)
    assert pages.page_progress(accepted, receiver[0])["ingestion_cursor"] == str(cursor)


def test_applied_prefix_stops_at_unfinished_page(accepted, receiver):
    receipt = str(Inbox.objects.get().id)
    _, first = accept(accepted, receiver, [])
    _, second = accept(accepted, receiver, [receipt], previous=first)
    _, third = accept(accepted, receiver, [], previous=second)
    result = pages.page_progress(accepted, receiver[0])
    assert result["ingestion_cursor"] == str(third)
    assert result["applied_cursor"] == str(first)
    processing.apply_work(accepted, *scheduling.get_claim(accepted))
    assert pages.page_progress(accepted, receiver[0])["applied_cursor"] == str(third)


def test_replay_is_idempotent_but_changed_content_conflicts(accepted, receiver):
    receipt = str(Inbox.objects.get().id)
    row, cursor = accept(accepted, receiver, [receipt])
    assert accept(accepted, receiver, [receipt], cursor=cursor)[0] == row
    with pytest.raises(ValueError, match="conflicts"):
        accept(accepted, receiver, [], cursor=cursor)
    assert Page.objects.count() == 1


def test_out_of_order_and_duplicate_receipts_rejected(accepted, receiver):
    receipt = str(Inbox.objects.get().id)
    with pytest.raises(ValueError, match="unique"):
        accept(accepted, receiver, [receipt, receipt])
    with pytest.raises(ValueError, match="extend"):
        accept(accepted, receiver, [], previous=uuid4())
    accept(accepted, receiver, [])
    with pytest.raises(ValueError, match="extend"):
        accept(accepted, receiver, [])


def test_foreign_practice_cannot_read_or_append(accepted, receiver, org_b):
    accept(accepted, receiver, [])
    with pytest.raises(ValueError, match="unavailable"):
        accept(org_b.id, receiver, [])
    with pytest.raises(ValueError, match="unavailable"):
        pages.page_progress(org_b.id, receiver[0])
    with rls_org(org_b):
        assert not Page.objects.exists()


def test_sql_cannot_bypass_receipt_or_order_guards(accepted, receiver):
    for ids, previous in [([str(uuid4())], None), ([], uuid4())]:
        with pytest.raises(IntegrityError), transaction.atomic():
            Page.objects.create(
                org_id=accepted,
                connection_id=receiver[0],
                cursor=uuid4(),
                previous_cursor=previous,
                receipt_ids=ids,
                authorization_generation=Connection.objects.get(
                    pk=receiver[0]
                ).authorization_generation,
            )
    assert not Page.objects.exists()


def test_page_is_immutable_and_position_is_database_owned(accepted, receiver):
    row, cursor = accept(accepted, receiver, [])
    with pytest.raises(IntegrityError), transaction.atomic():
        Page.objects.filter(pk=row).update(receipt_ids=[])
    with pytest.raises(IntegrityError), transaction.atomic():
        Page.objects.all()._raw_delete(Page.objects.db)
    second = Page.objects.create(
        org_id=accepted,
        connection_id=receiver[0],
        position=999,
        cursor=uuid4(),
        previous_cursor=cursor,
        receipt_ids=[],
        authorization_generation=Connection.objects.get(
            pk=receiver[0]
        ).authorization_generation,
    )
    second.refresh_from_db()
    assert second.position == 2


def test_transaction_rollback_preserves_cursor(accepted, receiver):
    _, cursor = accept(accepted, receiver, [])
    with pytest.raises(RuntimeError), transaction.atomic():
        accept(accepted, receiver, [], previous=cursor)
        raise RuntimeError("synthetic rollback")
    assert pages.page_progress(accepted, receiver[0])["ingestion_cursor"] == str(cursor)


def test_scan_limit_is_explicit(receiver, org_a):
    previous = None
    cursors = []
    for _ in range(101):
        _, previous = accept(org_a.id, receiver, [], previous=previous)
        cursors.append(previous)
    result = pages.page_progress(org_a.id, receiver[0])
    assert result["accepted_pages"] == 101
    assert result["pages_examined"] == 100 and not result["scan_complete"]
    assert result["applied_cursor"] == str(cursors[99])
    assert result["ingestion_cursor"] == str(cursors[100])
    assert result["source_coverage"] == "unknown"

    resumed = pages.page_progress(org_a.id, receiver[0])
    assert resumed["pages_examined"] == 1 and resumed["scan_complete"]
    assert resumed["applied_cursor"] == str(cursors[100])
    assert pages.page_progress(org_a.id, receiver[0])["pages_examined"] == 0


def test_prefix_cannot_skip_gap_via_sql(accepted, receiver):
    receipt = str(Inbox.objects.get().id)
    accept(accepted, receiver, [receipt])
    pages.page_progress(accepted, receiver[0])
    with pytest.raises(IntegrityError, match="unfinished"), transaction.atomic():
        AppliedPrefix.objects.update(position=1)
    processing.apply_work(accepted, *scheduling.get_claim(accepted))
    pages.page_progress(accepted, receiver[0])
    assert AppliedPrefix.objects.get().position == 1


def test_prefix_rejects_regression_missing_pages_and_deletion(accepted, receiver):
    accept(accepted, receiver, [])
    pages.page_progress(accepted, receiver[0])
    for position in [0, 2, 102]:
        with pytest.raises(IntegrityError), transaction.atomic():
            AppliedPrefix.objects.update(position=position)
    with pytest.raises(IntegrityError), transaction.atomic():
        AppliedPrefix.objects.all()._raw_delete(AppliedPrefix.objects.db)


def test_prefix_creation_cannot_assert_unverified_progress(accepted, receiver):
    accept(accepted, receiver, [])
    with pytest.raises(IntegrityError, match="starts at zero"), transaction.atomic():
        AppliedPrefix.objects.create(
            org_id=accepted, connection_id=receiver[0], position=1
        )


def test_prefix_rollback_resumes_safely(accepted, receiver):
    _, cursor = accept(accepted, receiver, [])
    with pytest.raises(RuntimeError), transaction.atomic():
        pages.page_progress(accepted, receiver[0])
        raise RuntimeError("synthetic rollback")
    assert not AppliedPrefix.objects.exists()
    assert pages.page_progress(accepted, receiver[0])["applied_cursor"] == str(cursor)


def test_prefix_is_hidden_from_other_practice(accepted, receiver, org_b):
    pages.page_progress(accepted, receiver[0])
    with rls_org(org_b):
        assert not AppliedPrefix.objects.exists()
        with pytest.raises(IntegrityError), transaction.atomic():
            AppliedPrefix.objects.create(org_id=org_b.id, connection_id=receiver[0])


def test_gap_after_first_batch_blocks_until_receipt_applied(accepted, receiver):
    previous = None
    for _ in range(100):
        _, previous = accept(accepted, receiver, [], previous=previous)
    first_batch_end = previous
    _, gap = accept(
        accepted, receiver, [str(Inbox.objects.get().id)], previous=previous
    )
    _, end = accept(accepted, receiver, [], previous=gap)
    assert pages.page_progress(accepted, receiver[0])["applied_cursor"] == str(
        first_batch_end
    )
    blocked = pages.page_progress(accepted, receiver[0])
    assert blocked["applied_cursor"] == str(first_batch_end)
    assert blocked["pages_examined"] == 2
    processing.apply_work(accepted, *scheduling.get_claim(accepted))
    assert pages.page_progress(accepted, receiver[0])["applied_cursor"] == str(end)


@pytest.mark.django_db(transaction=True)
def test_concurrent_scans_share_verified_prefix(accepted, receiver, org_a):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import connection

    previous = None
    for _ in range(101):
        _, previous = accept(accepted, receiver, [], previous=previous)
    barrier = Barrier(2)

    def run():
        try:
            barrier.wait(timeout=10)
            return pages.page_progress(accepted, receiver[0])
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(result["pages_examined"] for result in results) == [1, 100]
    with rls_org(org_a):
        assert AppliedPrefix.objects.get().position == 101
