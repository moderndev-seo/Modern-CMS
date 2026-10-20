"""Expired evidence is unavailable without forgetting delivery identity."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from common.testing import rls_org
from integrations.models import IntegrationEventInbox as Inbox
from integrations.models import IntegrationPendingWork as Pending
from integrations.retention import open_receipt, purge_expired
from integrations.tests import test_acceptance as acceptance
from integrations.tests import test_foundation as foundation
from integrations.tests import test_ingress_storage as storage

fictional = foundation.fictional
registry = foundation.registry
replay_keys = storage.replay_keys
receipt_fields = storage.receipt_fields
receiver = acceptance.receiver
receive_enabled = acceptance.receive_enabled


@pytest.mark.parametrize("offset,available", [(-1, True), (0, False), (1, False)])
def test_exact_expiry_boundary(receipt_fields, offset, available):
    row = storage.create_pair(receipt_fields)
    boundary = row.created_at + timedelta(hours=24, seconds=offset)
    with patch("integrations.retention.timezone.now", return_value=boundary):
        if available:
            assert open_receipt(row)["delivery_id"] == str(row.delivery_id)
        else:
            with pytest.raises(ValueError, match="Replay evidence unavailable"):
                open_receipt(row)


def expired_pair(fields):
    return storage.create_pair(
        {**fields, "created_at": timezone.now() - timedelta(days=2)}
    )


def test_purge_keeps_identity_and_cannot_be_reversed(receipt_fields):
    row = expired_pair(receipt_fields)
    original = Inbox.objects.filter(pk=row.pk).values().get()
    assert purge_expired(row.org_id) == 1
    row.refresh_from_db()
    assert row.replay_ciphertext == "" and row.replay_purged_at is not None
    after = Inbox.objects.filter(pk=row.pk).values().get()
    for key in original.keys() - {"replay_ciphertext", "replay_purged_at"}:
        assert after[key] == original[key]
    assert Pending.objects.filter(inbox=row).count() == 1
    assert purge_expired(row.org_id) == 0
    with pytest.raises(ValueError):
        open_receipt(row)
    for change in (
        {"replay_ciphertext": original["replay_ciphertext"]},
        {"replay_purged_at": None},
        {"semantic_digest": "a" * 64},
        {"created_at": timezone.now()},
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            Inbox.objects.filter(pk=row.pk).update(**change)
    with pytest.raises(IntegrityError), transaction.atomic():
        Inbox.objects.filter(pk=row.pk)._raw_delete(Inbox.objects.db)


def test_sql_forbids_early_or_partial_purge(receipt_fields):
    row = storage.create_pair(receipt_fields)
    for change in (
        {"replay_ciphertext": "", "replay_purged_at": timezone.now()},
        {"replay_purged_at": timezone.now()},
        {"replay_ciphertext": ""},
        {"replay_retention_policy": "extended"},
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            Inbox.objects.filter(pk=row.pk).update(**change)
    assert purge_expired(row.org_id) == 0
    assert open_receipt(row)


def test_purge_server_stamps_fact(receipt_fields):
    row = expired_pair(receipt_fields)
    start = timezone.now()
    Inbox.objects.filter(pk=row.pk).update(
        replay_ciphertext="", replay_purged_at=row.created_at
    )
    row.refresh_from_db()
    assert row.replay_purged_at >= start


def test_purge_does_not_require_encryption_key_or_active_receive(
    receipt_fields, settings
):
    row = expired_pair(receipt_fields)
    settings.INTEGRATION_REPLAY_KEYS = {}
    settings.INTEGRATION_RECEIVE_ENABLED = False
    settings.INTEGRATION_FOUNDATION_ENABLED = False
    assert purge_expired(row.org_id) == 1


def test_cross_practice_cannot_open_or_purge_foreign_row(receipt_fields, org_b):
    row = expired_pair(receipt_fields)
    with rls_org(org_b):
        with pytest.raises(ValueError):
            open_receipt(row)
        with pytest.raises(IntegrityError), transaction.atomic():
            # Raw SQL sees zero rows, so use INSERT to prove foreign row writes
            # are denied rather than treating a no-op UPDATE as authorization.
            Inbox.objects.create(
                **{**receipt_fields, "id": uuid4(), "org_id": org_b.id}
            )
    assert purge_expired(org_b.id) == 0
    row.refresh_from_db()
    assert row.replay_purged_at is None


@pytest.mark.parametrize("limit", [0, -1, 1001, True, "100"])
def test_invalid_batch_limit_fails_closed(org_a, limit):
    with pytest.raises(ValueError):
        purge_expired(org_a.id, limit)


def test_nonallowlisted_maintenance_denied(org_a, settings):
    settings.INTEGRATION_TEST_ORGS = []
    with pytest.raises(ValueError, match="not allowlisted"):
        purge_expired(org_a.id)
    with pytest.raises(CommandError):
        call_command("purge_integration_evidence", org=str(org_a.id), stdout=StringIO())


def test_bounded_command_is_rerunnable(receipt_fields):
    first = expired_pair(receipt_fields)
    second = expired_pair({**receipt_fields, "id": uuid4(), "delivery_id": uuid4()})
    output = StringIO()
    call_command(
        "purge_integration_evidence", org=str(first.org_id), limit=1, stdout=output
    )
    assert "Purged 1" in output.getvalue()
    assert Inbox.objects.filter(replay_purged_at__isnull=False).count() == 1
    assert purge_expired(first.org_id, 1) == 1
    assert purge_expired(first.org_id, 1) == 0
    assert Inbox.objects.filter(pk=second.pk).exists()


def test_expired_purged_delivery_never_becomes_new_work(receiver):
    body = storage.raw()
    create = Inbox.objects.create

    def historical(**kwargs):
        return create(**{**kwargs, "created_at": timezone.now() - timedelta(days=2)})

    with patch("integrations.acceptance.Inbox.objects.create", side_effect=historical):
        first = acceptance.send(receiver[1], body)
    assert first.status_code == 202
    row = Inbox.objects.get()
    assert purge_expired(row.org_id) == 1
    retry = acceptance.send(receiver[1], body)
    assert retry.status_code == 200 and retry.json() == first.json()
    assert Inbox.objects.count() == Pending.objects.count() == 1


def test_purge_batch_rolls_back_on_failure(receipt_fields):
    row = expired_pair(receipt_fields)

    def fail(execute, sql, params, many, context):
        result = execute(sql, params, many, context)
        if sql.startswith('UPDATE "mp_integration_inbox"'):
            raise RuntimeError("fictional purge failure")
        return result

    with pytest.raises(RuntimeError), connection.execute_wrapper(fail):
        purge_expired(row.org_id)
    row.refresh_from_db()
    assert row.replay_purged_at is None and row.replay_ciphertext


def test_versioned_key_rotation_and_recovery_preserve_receipts(
    receipt_fields, settings
):
    old = storage.create_pair(receipt_fields)
    old_key = settings.INTEGRATION_REPLAY_KEYS["test-v1"]
    new_key = Fernet.generate_key()
    settings.INTEGRATION_REPLAY_KEYS = {"test-v1": old_key, "test-v2": new_key}
    settings.INTEGRATION_REPLAY_KEY_VERSION = "test-v2"
    envelope, semantic, transport = storage.validate_envelope(
        storage.raw(), "acquisition"
    )
    new_id = uuid4()
    version, ciphertext = storage.seal_envelope(
        envelope, receipt_id=new_id, org_id=old.org_id, semantic_digest=semantic
    )
    new = storage.create_pair(
        {
            **receipt_fields,
            "id": new_id,
            "delivery_id": envelope["delivery_id"],
            "semantic_digest": semantic,
            "transport_digest": transport,
            "replay_key_version": version,
            "replay_ciphertext": ciphertext,
        }
    )
    assert new.replay_key_version == "test-v2"
    assert open_receipt(old) and open_receipt(new)
    settings.INTEGRATION_REPLAY_KEYS = {"test-v2": new_key}
    with pytest.raises(ValueError):
        open_receipt(old)
    assert open_receipt(new)
    settings.INTEGRATION_REPLAY_KEYS = {"test-v1": new_key, "test-v2": new_key}
    with pytest.raises(ValueError):
        open_receipt(old)
    settings.INTEGRATION_REPLAY_KEYS = {"test-v1": old_key, "test-v2": new_key}
    assert open_receipt(old) and open_receipt(new)
    assert Inbox.objects.count() == Pending.objects.count() == 2


def test_cached_row_does_not_bypass_purge(receipt_fields):
    row = expired_pair(receipt_fields)
    assert row.replay_purged_at is None and row.replay_ciphertext
    assert purge_expired(row.org_id) == 1
    # A stale object still holds the old ciphertext; the policy entry point
    # re-reads authoritative storage rather than using that cached evidence.
    with patch("integrations.retention.timezone.now", return_value=row.created_at):
        with pytest.raises(ValueError):
            open_receipt(row)
