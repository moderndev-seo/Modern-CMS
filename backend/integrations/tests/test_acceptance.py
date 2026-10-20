"""Fictional HTTP acceptance, grants, idempotency and transaction failures."""

import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from common.testing import rls_org
from integrations.models import IntegrationConnection as Connection
from integrations.models import IntegrationDeliveryConflict as Conflict
from integrations.models import IntegrationEventInbox as Inbox
from integrations.models import IntegrationPendingWork as Pending
from integrations.tests import test_foundation as foundation
from integrations.tests import test_ingress_storage as storage

fictional = foundation.fictional
replay_keys = storage.replay_keys
registry = foundation.registry
ROOT = foundation.ROOT


@pytest.fixture(autouse=True)
def receive_enabled(settings):
    settings.INTEGRATION_RECEIVE_ENABLED = True


def make_receiver(admin_client):
    ns = foundation.post(
        admin_client,
        "namespaces/",
        provider_key="fixture_a",
        account_key="test_receive",
    )
    assert ns.status_code in (200, 201), ns.content
    conn = foundation.post(
        admin_client,
        "connections/",
        namespace_id=ns.json()["id"],
        label="TEST receive",
        manifest_id="fixture_a:acquisition:ingress-v1",
    )
    assert conn.status_code == 201, conn.content
    return conn.json()["id"]


@pytest.fixture
def receiver(admin_client, replay_keys):
    conn_id = make_receiver(admin_client)
    key = foundation.issue(admin_client, conn_id, scopes=["integration.receive"])
    return conn_id, key


def send(key, body):
    return foundation.service(key["credential"]).generic(
        "POST", ROOT + "service/events/", body, content_type="application/json"
    )


def test_accept_retry_conflict_audit_and_no_new_work(receiver):
    _, key = receiver
    body = storage.raw()
    first = send(key, body)
    assert first.status_code == 202, first.content
    second = send(key, json.dumps(json.loads(body), indent=2).encode())
    assert second.status_code == 200
    assert first.json() == second.json()
    changed = json.loads(body)
    changed["source_id"] = str(uuid4())
    for _ in range(2):
        assert send(key, json.dumps(changed).encode()).status_code == 409
    assert (
        Inbox.objects.count()
        == Pending.objects.count()
        == Conflict.objects.count()
        == 1
    )
    assert b"source_id" not in first.content
    assert first["Cache-Control"] == "private, no-store"


def test_legacy_manifest_cannot_issue_receive(admin_client, registry):
    from datetime import timedelta

    from django.utils import timezone

    result = foundation.post(
        admin_client,
        f"connections/{registry}/credentials/",
        expected_revision=1,
        expires_at=(timezone.now() + timedelta(days=1)).isoformat(),
        scopes=["integration.receive"],
    )
    assert result.status_code == 400
    assert Connection.objects.get(id=registry).revision == 1


def test_receive_cannot_probe_or_impersonate_human(receiver, admin_client):
    _, key = receiver
    client = foundation.service(key["credential"])
    assert client.get(ROOT + "service/probe/").status_code == 403
    assert client.get(ROOT + "namespaces/").status_code == 403
    assert client.get("/api/patients/").status_code == 403
    assert (
        admin_client.generic(
            "POST",
            ROOT + "service/events/",
            storage.raw(),
            content_type="application/json",
        ).status_code
        == 403
    )


def test_disabled_receiver_fails_closed(receiver, settings):
    settings.INTEGRATION_RECEIVE_ENABLED = False
    assert send(receiver[1], storage.raw()).status_code == 404
    assert Inbox.objects.count() == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"event_type": "treatment.completed"},
        {"event_type": "payment.settled"},
        {"org_id": str(uuid4())},
        {"verified": True},
    ],
)
def test_forbidden_authority_never_persists(receiver, changes):
    assert send(receiver[1], storage.raw(**changes)).status_code == 403
    assert Inbox.objects.count() == Pending.objects.count() == 0


@pytest.mark.parametrize(
    "body",
    [
        b"{}",
        b"[" * 1500,
        b" " * 16385,
        b'{"schema":"fixture.ingress/1","schema":"ignored"}',
    ],
)
def test_invalid_input_rejected_without_effect(receiver, body):
    assert send(receiver[1], body).status_code == 400
    assert Inbox.objects.count() == Pending.objects.count() == 0


@pytest.mark.parametrize("failure", ["encryption", "pending", "deferred"])
def test_failure_rolls_back_receipt_and_retry_is_safe(receiver, settings, failure):
    body = storage.raw()
    if failure == "encryption":
        target = "integrations.acceptance.seal_envelope"
    elif failure == "pending":
        target = "integrations.acceptance.Pending.objects.create"
    else:
        target = None
    if target:
        with patch(target, side_effect=RuntimeError("fictional failure canary")):
            assert send(receiver[1], body).status_code == 503
    else:

        def fail(execute, sql, params, many, context):
            if (
                sql.startswith("SET CONSTRAINTS")
                and "mp_ingress_pending_required" in sql
                and "IMMEDIATE" in sql
            ):
                raise DatabaseError("fictional deferred failure")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(fail):
            assert send(receiver[1], body).status_code == 503
    assert Inbox.objects.count() == Pending.objects.count() == 0
    assert send(receiver[1], body).status_code == 202


def test_receipt_and_conflicts_hidden_from_other_practice(receiver, org_b):
    body = storage.raw()
    assert send(receiver[1], body).status_code == 202
    changed = json.loads(body)
    changed["source_id"] = str(uuid4())
    assert send(receiver[1], json.dumps(changed).encode()).status_code == 409
    row = Inbox.objects.get()
    with rls_org(org_b):
        assert (
            Inbox.objects.count()
            == Pending.objects.count()
            == Conflict.objects.count()
            == 0
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            Conflict.objects.create(
                org=org_b,
                inbox_id=row.id,
                credential_id=row.credential_id,
                attempted_digest="a" * 64,
            )
    for action in ("update", "delete"):
        with pytest.raises(IntegrityError), transaction.atomic():
            if action == "update":
                Conflict.objects.update(attempted_digest="b" * 64)
            else:
                Conflict.objects.all()._raw_delete(Conflict.objects.db)


@pytest.mark.django_db(transaction=True)
def test_commit_failure_never_acknowledges(receiver, org_a):
    body = storage.raw()
    with patch.object(
        connection, "commit", side_effect=DatabaseError("fictional commit failure")
    ):
        assert send(receiver[1], body).status_code == 503
    with rls_org(org_a):
        assert Inbox.objects.count() == Pending.objects.count() == 0
    assert send(receiver[1], body).status_code == 202


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("conflicting", [False, True])
def test_concurrent_deliveries_one_receipt(receiver, org_a, conflicting):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    body = storage.raw()
    changed = json.loads(body)
    if conflicting:
        changed["source_id"] = str(uuid4())
    barrier = Barrier(2)

    def attempt(payload):
        try:
            barrier.wait(timeout=10)
            return send(receiver[1], payload).status_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(attempt, payload)
            for payload in (body, json.dumps(changed).encode())
        ]
        assert sorted(job.result(timeout=20) for job in jobs) == (
            [202, 409] if conflicting else [200, 202]
        )
    with rls_org(org_a):
        assert Inbox.objects.count() == Pending.objects.count() == 1
        assert Conflict.objects.count() == int(conflicting)


def test_rotation_preserves_delivery_identity_and_revocation_denies(
    receiver, admin_client
):
    conn_id, old = receiver
    body = storage.raw()
    first = send(old, body)
    assert first.status_code == 202
    new = foundation.issue(
        admin_client,
        conn_id,
        scopes=["integration.receive"],
        replaces_id=old["id"],
        overlap_seconds=0,
    )
    assert send(old, body).status_code == 401
    replay = send(new, body)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert Inbox.objects.count() == Pending.objects.count() == 1
    result = foundation.post(
        admin_client,
        f"connections/{conn_id}/state/",
        expected_revision=3,
        target="revoked",
        reason_code="compromise",
    )
    assert result.status_code == 200
    assert send(new, body).status_code == 401
    assert send(new, storage.raw()).status_code == 401
    assert Inbox.objects.count() == 1


def test_missing_key_never_acknowledges(receiver, settings):
    settings.INTEGRATION_REPLAY_KEYS = {}
    assert send(receiver[1], storage.raw()).status_code == 503
    assert Inbox.objects.count() == Pending.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_receipt_survives_database_reconnect(receiver, org_a):
    body = storage.raw()
    first = send(receiver[1], body)
    assert first.status_code == 202
    connection.close()
    replay = send(receiver[1], body)
    assert replay.status_code == 200 and replay.json() == first.json()
    with rls_org(org_a):
        assert Inbox.objects.count() == Pending.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_revocation_wins_against_waiting_receive(receiver, org_a, admin_profile):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from common.models import Org
    from integrations.authentication import tenant_transaction
    from integrations.services import command

    waiting = Event()

    def attempt():
        def observe(execute, sql, params, many, context):
            if '"organization"' in sql and "FOR UPDATE" in sql:
                waiting.set()
            return execute(sql, params, many, context)

        try:
            with connection.execute_wrapper(observe):
                return send(receiver[1], storage.raw()).status_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with tenant_transaction(org_a.id):
            Org.objects.select_for_update().get(id=org_a.id)
            Connection.objects.select_for_update().get(id=receiver[0])
            future = pool.submit(attempt)
            assert waiting.wait(timeout=10)
            assert not future.done()
            command(
                admin_profile,
                "state",
                {
                    "request_id": uuid4(),
                    "expected_revision": 2,
                    "target": "revoked",
                    "reason_code": "compromise",
                },
                connection_id=receiver[0],
            )
        assert future.result(timeout=20) == 401
    with rls_org(org_a):
        assert Inbox.objects.count() == Pending.objects.count() == 0


def test_same_delivery_id_is_independent_between_practices(
    receiver, org_b_client, org_a, org_b
):
    body = storage.raw()
    first = send(receiver[1], body)
    assert first.status_code == 202
    other_conn = make_receiver(org_b_client)
    with rls_org(org_b):
        other_key = foundation.issue(
            org_b_client, other_conn, scopes=["integration.receive"]
        )
    second = send(other_key, body)
    assert second.status_code == 202
    assert second.json()["receipt_id"] != first.json()["receipt_id"]
    for org, own, other in ((org_a, first, second), (org_b, second, first)):
        with rls_org(org):
            assert Inbox.objects.count() == Pending.objects.count() == 1
            assert Inbox.objects.filter(id=own.json()["receipt_id"]).exists()
            assert not Inbox.objects.filter(id=other.json()["receipt_id"]).exists()


def test_sql_rejects_receive_scope_on_legacy_manifest(admin_client, registry):
    from datetime import timedelta

    from django.utils import timezone

    from integrations.models import IntegrationCredential

    conn = Connection.objects.get(id=registry)
    with pytest.raises(IntegrityError), transaction.atomic():
        IntegrationCredential.objects.create(
            org=conn.org,
            connection=conn,
            token_digest="a" * 64,
            scopes=["integration.receive"],
            issued_by_profile=conn.created_by_profile,
            expires_at=timezone.now() + timedelta(days=1),
        )
