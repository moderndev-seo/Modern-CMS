"""Scheduling storage only; no worker, normalized observation or domain writes."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from common.testing import rls_org
from integrations.models import IntegrationPendingWork as Pending
from integrations.models import IntegrationProcessingAttempt as Attempt
from integrations.models import IntegrationProcessingWork as Work
from integrations.tests import test_ingress_storage as storage

fictional = storage.fictional
registry = storage.registry
replay_keys = storage.replay_keys
receipt_fields = storage.receipt_fields


def flush_claim_guard():
    with connection.cursor() as cursor:
        cursor.execute(
            "SET CONSTRAINTS mp_processing_claim_required, mp_work_observation_required IMMEDIATE"
        )
        cursor.execute(
            "SET CONSTRAINTS mp_processing_claim_required, mp_work_observation_required DEFERRED"
        )


@pytest.fixture
def work(receipt_fields):
    inbox = storage.create_pair(receipt_fields)
    row = Work.objects.create(
        org_id=inbox.org_id, pending=Pending.objects.get(inbox=inbox)
    )
    flush_claim_guard()
    return row


def test_one_companion_preserves_pending_marker(work):
    assert work.state == "accepted" and work.attempt_count == 0
    original = Pending.objects.filter(pk=work.pending_id).values().get()
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.create(org_id=work.org_id, pending_id=work.pending_id)
    assert Pending.objects.filter(pk=work.pending_id).values().get() == original


@pytest.mark.parametrize(
    "changes",
    [
        {"state": "unknown"},
        {"state": "processing"},
        {"lease_token": uuid4()},
        {"attempt_count": 7},
        {"reason_code": "unsafe free text"},
        {"pending_id": uuid4()},
        {"org_id": uuid4()},
        {"created_at": timezone.now()},
    ],
)
def test_invalid_work_changes_fail(work, changes):
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.filter(pk=work.pk).update(**changes)


def test_foreign_tenant_cannot_read_or_change(work, org_b):
    with rls_org(org_b):
        assert not Work.objects.filter(pk=work.pk).exists()
        assert Work.objects.filter(pk=work.pk).update(reason_code="transient") == 0
        with pytest.raises(IntegrityError), transaction.atomic():
            Work.objects.create(org_id=org_b.id, pending_id=work.pending_id)


def claim(work):
    work.state = "processing"
    work.attempt_count = 1
    work.lease_token = uuid4()
    work.lease_expires_at = timezone.now() + timedelta(minutes=1)
    work.save()
    attempt = Attempt.objects.create(
        org_id=work.org_id,
        work=work,
        number=1,
        lease_token=work.lease_token,
        lease_expires_at=work.lease_expires_at,
    )
    flush_claim_guard()
    return attempt


def test_claim_evidence_is_immutable(work):
    attempt = claim(work)
    with pytest.raises(IntegrityError), transaction.atomic():
        Attempt.objects.filter(pk=attempt.pk).update(number=2)
    with pytest.raises(IntegrityError), transaction.atomic():
        Attempt.objects.filter(pk=attempt.pk)._raw_delete(Attempt.objects.db)
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.filter(pk=work.pk)._raw_delete(Work.objects.db)


def test_claim_must_match_active_lease(work):
    with pytest.raises(IntegrityError), transaction.atomic():
        Attempt.objects.create(
            org_id=work.org_id,
            work=work,
            number=1,
            lease_token=uuid4(),
            lease_expires_at=timezone.now() + timedelta(minutes=1),
        )


def test_forced_rls_catalog(work):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('mp_integration_work','mp_integration_attempt')"
        )
        assert cursor.fetchall() == [(True, True), (True, True)]


def test_processing_without_claim_evidence_cannot_commit(work):
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.filter(pk=work.pk).update(
            state="processing",
            attempt_count=1,
            lease_token=uuid4(),
            lease_expires_at=timezone.now() + timedelta(minutes=1),
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SET CONSTRAINTS mp_processing_claim_required, mp_work_observation_required IMMEDIATE"
            )


def test_terminal_work_cannot_be_reactivated(work):
    work.state = "quarantined"
    work.reason_code = "revoked"
    work.save()
    flush_claim_guard()
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.filter(pk=work.pk).update(state="accepted", reason_code="")


def test_released_claim_token_cannot_be_resurrected(work):
    attempt = claim(work)
    Work.objects.filter(pk=work.pk).update(
        state="retry_due", lease_token=None, lease_expires_at=None
    )
    flush_claim_guard()
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.filter(pk=work.pk).update(
            state="processing",
            lease_token=attempt.lease_token,
            lease_expires_at=attempt.lease_expires_at,
        )
        flush_claim_guard()


def test_active_claim_cannot_be_replaced(work):
    claim(work)
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.filter(pk=work.pk).update(
            attempt_count=2,
            lease_token=uuid4(),
            lease_expires_at=timezone.now() + timedelta(minutes=2),
        )


def test_attempt_count_cannot_change_while_releasing_claim(work):
    claim(work)
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.filter(pk=work.pk).update(
            state="retry_due",
            attempt_count=2,
            lease_token=None,
            lease_expires_at=None,
        )
