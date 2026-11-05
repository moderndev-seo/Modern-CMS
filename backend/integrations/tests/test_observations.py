"""Atomic fictional normalization and bounded task orchestration."""

from unittest.mock import patch

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from common.testing import rls_org
from integrations import processing, tasks
from integrations.models import IntegrationObservation as Observation
from integrations.models import IntegrationProcessingWork as Work
from integrations.tests import test_processing as scheduling

fictional = scheduling.fictional
replay_keys = scheduling.replay_keys
receiver = scheduling.receiver
receive_enabled = scheduling.receive_enabled
processing_enabled = scheduling.processing_enabled
accepted = scheduling.accepted


def test_apply_once_preserves_unknown_time(accepted):
    work_id, token = scheduling.get_claim(accepted)
    assert processing.apply_work(accepted, work_id, token)
    assert not processing.apply_work(accepted, work_id, token)
    row = Observation.objects.get()
    assert row.event_type == "inquiry.created" and row.occurred_at is None
    assert row.mapping_version == "fixture.normalized/1"
    assert Work.objects.get(pk=work_id).state == "applied"


def test_apply_failure_rolls_back_observation_and_state(accepted):
    work_id, token = scheduling.get_claim(accepted)
    with patch(
        "integrations.processing._release", side_effect=DatabaseError("synthetic")
    ):
        with pytest.raises(DatabaseError):
            processing.apply_work(accepted, work_id, token)
    assert not Observation.objects.exists()
    assert Work.objects.get(pk=work_id).state == "processing"
    assert processing.apply_work(accepted, work_id, token)


def test_stale_lease_cannot_apply(accepted):
    work_id, token = scheduling.get_claim(accepted)
    expiry = Work.objects.get(pk=work_id).lease_expires_at
    with patch("integrations.processing.timezone.now", return_value=expiry):
        assert not processing.apply_work(accepted, work_id, token)
        processing.recover_work(accepted)
        next_claim = processing.claim_work(accepted)[0]
    assert not processing.apply_work(accepted, work_id, token)
    assert processing.apply_work(accepted, *next_claim)
    assert Observation.objects.count() == 1


def test_missing_key_quarantines_without_fact(accepted, settings):
    claim = scheduling.get_claim(accepted)
    settings.INTEGRATION_REPLAY_KEYS = {}
    assert not processing.apply_work(accepted, *claim)
    assert Work.objects.get().state == "quarantined"
    assert not Observation.objects.exists()


def test_foreign_practice_cannot_apply_or_read(accepted, org_b):
    claim = scheduling.get_claim(accepted)
    assert not processing.apply_work(org_b.id, *claim)
    assert processing.apply_work(accepted, *claim)
    with rls_org(org_b):
        assert not Observation.objects.exists()


def test_observation_is_immutable(accepted):
    claim = scheduling.get_claim(accepted)
    processing.apply_work(accepted, *claim)
    with pytest.raises(IntegrityError), transaction.atomic():
        Observation.objects.update(event_type="inquiry.qualified")
    with pytest.raises(IntegrityError), transaction.atomic():
        Observation.objects.all()._raw_delete(Observation.objects.db)


def test_applied_without_observation_is_rejected(accepted):
    work_id, _ = scheduling.get_claim(accepted)
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.filter(pk=work_id).update(
            state="applied", lease_token=None, lease_expires_at=None
        )
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS mp_work_observation_required IMMEDIATE")


def test_task_processes_fictional_path_idempotently(accepted):
    result = tasks.process_practice.run(accepted)
    assert result == {
        "prepared": 1,
        "recovered": 0,
        "claimed": 1,
        "applied": 1,
        "failed": 0,
    }
    assert tasks.process_practice.run(accepted)["applied"] == 0
    assert Observation.objects.count() == 1


def test_task_failure_schedules_retry_without_sensitive_error(accepted):
    with patch(
        "integrations.tasks.apply_work", side_effect=DatabaseError("private-detail")
    ):
        result = tasks.process_practice.run(accepted)
    assert result["failed"] == 1 and "private-detail" not in str(result)
    row = Work.objects.get()
    assert row.state == "retry_due"
    with patch(
        "integrations.processing.timezone.now", return_value=row.next_attempt_at
    ):
        assert tasks.process_practice.run(accepted)["applied"] == 1


def test_dispatch_disabled_and_publish_failure(settings, org_a, org_b):
    settings.INTEGRATION_PROCESSING_ENABLED = False
    with patch("integrations.tasks.process_practice.delay") as delay:
        assert tasks.dispatch_practices.run() == {"queued": 0, "failed": 0}
        delay.assert_not_called()
    settings.INTEGRATION_PROCESSING_ENABLED = True
    with patch(
        "integrations.tasks.process_practice.delay",
        side_effect=[RuntimeError("private"), None],
    ) as delay:
        assert tasks.dispatch_practices.run() == {"queued": 1, "failed": 1}
        assert {call.args for call in delay.call_args_list} == {
            (str(org_a.id),),
            (str(org_b.id),),
        }


@pytest.mark.django_db(transaction=True)
def test_apply_commit_failure_is_recoverable(accepted, org_a):
    claim = scheduling.get_claim(accepted)
    with patch.object(connection, "commit", side_effect=DatabaseError("synthetic")):
        with pytest.raises(DatabaseError):
            processing.apply_work(accepted, *claim)
    with rls_org(org_a):
        assert not Observation.objects.exists()
    assert processing.apply_work(accepted, *claim)


def test_revocation_before_apply_prevents_observation(accepted, receiver, admin_client):
    from integrations.models import IntegrationConnection
    from integrations.tests import test_foundation as foundation

    claim = scheduling.get_claim(accepted)
    conn = IntegrationConnection.objects.get(pk=receiver[0])
    result = foundation.post(
        admin_client,
        f"connections/{conn.id}/state/",
        expected_revision=conn.revision,
        target="revoked",
        reason_code="operator_revoke",
    )
    assert result.status_code == 200
    assert not processing.apply_work(accepted, *claim)
    assert not Observation.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_apply_has_one_observation(accepted, org_a):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    claim = scheduling.get_claim(accepted)
    barrier = Barrier(2)

    def run():
        try:
            barrier.wait(timeout=10)
            return processing.apply_work(accepted, *claim)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(run) for _ in range(2)]
        assert sorted(job.result(timeout=20) for job in jobs) == [False, True]
    with rls_org(org_a):
        assert Observation.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_enabled_worker_consumes_queued_fictional_receipt(accepted, org_a, monkeypatch):
    import time
    from uuid import uuid4

    from celery.contrib.testing.worker import start_worker

    from crm.celery import app

    # Dedicated queue and in-memory transport: never consume the demo's jobs.
    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "cache+memory://")
    assert app.conf.broker_url == "memory://"
    queue = "fictional-test-" + uuid4().hex
    with start_worker(
        app,
        pool="solo",
        concurrency=1,
        perform_ping_check=False,
        queues=[queue],
        shutdown_timeout=10,
    ):
        tasks.process_practice.apply_async(args=[accepted], queue=queue)
        for _ in range(80):
            with rls_org(org_a):
                if Observation.objects.count() == 1:
                    break
            time.sleep(0.1)
        else:
            pytest.fail("Enabled test worker did not produce an observation")
    with rls_org(org_a):
        assert Work.objects.get().state == "applied"
