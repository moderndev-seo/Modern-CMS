"""Fictional claim/recovery without any patient or cash projection."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import DatabaseError, connection
from django.utils import timezone

from common.testing import rls_org
from integrations import processing
from integrations.models import IntegrationConnection as Connection
from integrations.models import IntegrationProcessingAttempt as Attempt
from integrations.models import IntegrationProcessingWork as Work
from integrations.tests import test_acceptance as acceptance
from integrations.tests import test_foundation as foundation
from integrations.tests import test_ingress_storage as storage

fictional = foundation.fictional
replay_keys = storage.replay_keys
receiver = acceptance.receiver
receive_enabled = acceptance.receive_enabled


@pytest.fixture(autouse=True)
def processing_enabled(settings):
    settings.INTEGRATION_PROCESSING_ENABLED = True


@pytest.fixture
def accepted(receiver, org_a):
    result = acceptance.send(receiver[1], storage.raw())
    assert result.status_code == 202, result.content
    return str(org_a.id)


def get_claim(org):
    processing.prepare_work(org)
    claims = processing.claim_work(org)
    assert len(claims) == 1
    return claims[0]


def test_prepare_claim_and_bounded_retry(accepted):
    assert processing.prepare_work(accepted) == 1
    assert processing.prepare_work(accepted) == 0
    work_id, token = get_claim(accepted)
    assert processing.claim_work(accepted) == []
    assert Attempt.objects.count() == 1
    now = timezone.now()
    assert processing.retry_work(accepted, work_id, token, retry_after_seconds=120)
    row = Work.objects.get(pk=work_id)
    assert row.state == "retry_due" and row.lease_token is None
    assert row.next_attempt_at >= now + timedelta(seconds=120)
    assert processing.claim_work(accepted) == []
    with patch(
        "integrations.processing.timezone.now", return_value=row.next_attempt_at
    ):
        second = processing.claim_work(accepted)
    assert len(second) == 1 and second[0][1] != token
    assert Attempt.objects.count() == 2
    assert not processing.retry_work(accepted, work_id, token)


def test_expiry_recovery_and_stale_owner(accepted):
    work_id, token = get_claim(accepted)
    row = Work.objects.get(pk=work_id)
    with patch(
        "integrations.processing.timezone.now", return_value=row.lease_expires_at
    ):
        assert not processing.retry_work(accepted, work_id, token)
        assert processing.recover_work(accepted) == 1
        assert processing.recover_work(accepted) == 0
        second = processing.claim_work(accepted)
    assert second[0][1] != token
    assert not processing.retry_work(accepted, work_id, token)


def test_six_claim_ceiling_survives_repeated_crashes(accepted):
    work_id, _ = get_claim(accepted)
    for count in range(1, 7):
        row = Work.objects.get(pk=work_id)
        assert row.attempt_count == count
        with patch(
            "integrations.processing.timezone.now", return_value=row.lease_expires_at
        ):
            assert processing.recover_work(accepted) == 1
            claims = processing.claim_work(accepted)
        assert bool(claims) == (count < 6)
    assert Work.objects.get(pk=work_id).state == "terminal_failure"
    assert Attempt.objects.count() == 6


def test_expired_evidence_is_quarantined(accepted):
    processing.prepare_work(accepted)
    row = Work.objects.select_related("pending__inbox").get()
    with patch(
        "integrations.processing.timezone.now",
        return_value=row.pending.inbox.created_at + timedelta(hours=24),
    ):
        assert processing.claim_work(accepted) == []
    row.refresh_from_db()
    assert row.state == "quarantined" and row.reason_code == "evidence_unavailable"


def test_revocation_quarantines_without_automatic_resume(
    accepted, receiver, admin_client
):
    work_id, token = get_claim(accepted)
    conn = Connection.objects.get(pk=receiver[0])
    result = foundation.post(
        admin_client,
        f"connections/{conn.id}/state/",
        expected_revision=conn.revision,
        target="revoked",
        reason_code="operator_revoke",
    )
    assert result.status_code == 200
    assert processing.retry_work(accepted, work_id, token)
    row = Work.objects.get(pk=work_id)
    assert row.state == "quarantined" and row.reason_code == "revoked"
    assert processing.claim_work(accepted) == []


def test_claim_rolls_back_if_attempt_insert_fails(accepted):
    processing.prepare_work(accepted)
    with patch.object(
        Attempt.objects, "create", side_effect=DatabaseError("synthetic")
    ):
        with pytest.raises(DatabaseError):
            processing.claim_work(accepted)
    row = Work.objects.get()
    assert (
        row.state == "accepted" and row.attempt_count == 0 and row.lease_token is None
    )
    assert Attempt.objects.count() == 0
    assert len(processing.claim_work(accepted)) == 1


@pytest.mark.parametrize("limit", [0, 101, True, "1"])
def test_batch_bounds(accepted, limit):
    with pytest.raises(ValueError):
        processing.prepare_work(accepted, limit)
    with pytest.raises(ValueError):
        processing.claim_work(accepted, limit)
    with pytest.raises(ValueError):
        processing.recover_work(accepted, limit)


def test_disabled_and_foreign_practice(accepted, org_b, settings):
    work_id, token = get_claim(accepted)
    assert processing.prepare_work(org_b.id) == 0
    assert processing.claim_work(org_b.id) == []
    assert not processing.retry_work(org_b.id, work_id, token)
    settings.INTEGRATION_PROCESSING_ENABLED = False
    with pytest.raises(ValueError):
        processing.claim_work(accepted)
    settings.INTEGRATION_PROCESSING_ENABLED = True
    settings.INTEGRATION_TEST_ORGS = []
    with pytest.raises(ValueError):
        processing.claim_work(accepted)


def test_retry_cannot_outlive_retained_evidence(accepted):
    work_id, token = get_claim(accepted)
    assert processing.retry_work(accepted, work_id, token, retry_after_seconds=86400)
    row = Work.objects.get(pk=work_id)
    assert row.state == "terminal_failure" and row.reason_code == "evidence_unavailable"


def test_context_restored_on_success_and_failure(accepted):
    def current():
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org',true)")
            return cursor.fetchone()[0]

    before = current()
    processing.prepare_work(accepted)
    assert current() == before
    with patch.object(
        Attempt.objects, "create", side_effect=DatabaseError("synthetic")
    ):
        with pytest.raises(DatabaseError):
            processing.claim_work(accepted)
    assert current() == before


@pytest.mark.django_db(transaction=True)
def test_concurrent_claims_have_one_owner(accepted, org_a):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    processing.prepare_work(accepted)
    barrier = Barrier(2)

    def run():
        try:
            barrier.wait(timeout=10)
            return processing.claim_work(accepted)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(run) for _ in range(2)]
        claims = [claim for future in results for claim in future.result(timeout=20)]
    assert len(claims) == 1
    with rls_org(org_a):
        assert Attempt.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_commit_failure_leaves_work_claimable(accepted):
    processing.prepare_work(accepted)
    with patch.object(connection, "commit", side_effect=DatabaseError("synthetic")):
        with pytest.raises(DatabaseError):
            processing.claim_work(accepted)
    assert len(processing.claim_work(accepted)) == 1


@pytest.mark.django_db(transaction=True)
def test_revocation_wins_waiting_claim(accepted, receiver, org_a, admin_profile):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from uuid import uuid4

    from common.models import Org
    from integrations.authentication import tenant_transaction
    from integrations.services import command

    processing.prepare_work(accepted)
    waiting = Event()

    def run():
        def observe(execute, sql, params, many, context):
            if '"organization"' in sql and "FOR UPDATE" in sql:
                waiting.set()
            return execute(sql, params, many, context)

        try:
            with connection.execute_wrapper(observe):
                return processing.claim_work(accepted)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with tenant_transaction(org_a.id):
            Org.objects.select_for_update().get(pk=org_a.id)
            conn = Connection.objects.select_for_update().get(pk=receiver[0])
            future = pool.submit(run)
            assert waiting.wait(timeout=10)
            assert not future.done()
            command(
                admin_profile,
                "state",
                {
                    "request_id": uuid4(),
                    "expected_revision": conn.revision,
                    "target": "revoked",
                    "reason_code": "compromise",
                },
                connection_id=conn.id,
            )
        assert future.result(timeout=20) == []
    with rls_org(org_a):
        assert Work.objects.get().state == "quarantined"
        assert Attempt.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_locked_practice_does_not_block_other_practice(
    accepted, org_a, org_b, org_b_client
):
    from concurrent.futures import ThreadPoolExecutor

    from common.models import Org
    from integrations.authentication import tenant_transaction

    conn = acceptance.make_receiver(org_b_client)
    with rls_org(org_b):
        key = foundation.issue(org_b_client, conn, scopes=["integration.receive"])
    assert acceptance.send(key, storage.raw()).status_code == 202
    processing.prepare_work(org_b.id)

    def run():
        try:
            return processing.claim_work(org_b.id)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with tenant_transaction(org_a.id):
            Org.objects.select_for_update().get(pk=org_a.id)
            assert len(pool.submit(run).result(timeout=10)) == 1


@pytest.mark.django_db(transaction=True)
def test_committed_claim_survives_reconnect_and_recovers(accepted, org_a):
    work_id, token = get_claim(accepted)
    with rls_org(org_a):
        expiry = Work.objects.get(pk=work_id).lease_expires_at
    connection.close()
    with patch("integrations.processing.timezone.now", return_value=expiry):
        assert processing.recover_work(accepted) == 1
        next_claim = processing.claim_work(accepted)
    assert next_claim[0][1] != token
    with rls_org(org_a):
        assert Attempt.objects.count() == 2


def test_batch_limit_preserves_remaining_markers(accepted, receiver):
    for _ in range(3):
        assert acceptance.send(receiver[1], storage.raw()).status_code == 202
    assert processing.prepare_work(accepted, limit=2) == 2
    assert len(processing.claim_work(accepted, limit=1)) == 1
    assert len(processing.claim_work(accepted, limit=1)) == 1
    assert processing.claim_work(accepted, limit=1) == []
    assert processing.prepare_work(accepted, limit=2) == 2
    assert len(processing.claim_work(accepted, limit=2)) == 2


def test_released_token_cannot_be_restored_or_apply(accepted):
    from django.db import IntegrityError, transaction

    work_id, token = get_claim(accepted)
    original = Work.objects.get(pk=work_id)
    assert processing.retry_work(accepted, work_id, token)
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.filter(pk=work_id).update(
            state="processing",
            lease_token=token,
            lease_expires_at=original.lease_expires_at,
        )
    assert not processing.apply_work(accepted, work_id, token)
    due = Work.objects.get(pk=work_id).next_attempt_at
    with patch("integrations.processing.timezone.now", return_value=due):
        fresh = processing.claim_work(accepted)[0]
    assert fresh[1] != token
    assert not processing.apply_work(accepted, work_id, token)
    assert processing.apply_work(accepted, *fresh)
