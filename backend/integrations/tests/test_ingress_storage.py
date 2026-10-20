"""Storage/input primitives only: no receive endpoint or widened credentials."""

import json
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.db import IntegrityError, connection, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from common.testing import rls_org
from integrations.ingress import open_envelope, seal_envelope, validate_envelope
from integrations.models import IntegrationConnection as Connection
from integrations.models import IntegrationEventInbox as Inbox
from integrations.models import IntegrationPendingWork as Pending
from integrations.tests import test_foundation as foundation
from integrations.tests.test_foundation import (
    ROOT,
    issue,
    service,
)

# Reuse the existing fictional registry fixtures without collecting tests twice.
fictional = foundation.fictional
registry = foundation.registry


def raw(**changes):
    return json.dumps(
        {
            "schema": "fixture.ingress/1",
            "delivery_id": str(uuid4()),
            "event_type": "inquiry.created",
            "source_id": str(uuid4()),
            "occurred_at": None,
            **changes,
        }
    ).encode()


@pytest.fixture
def replay_keys(settings):
    settings.INTEGRATION_REPLAY_KEYS = {"test-v1": Fernet.generate_key()}
    settings.INTEGRATION_REPLAY_KEY_VERSION = "test-v1"


@pytest.fixture
def receipt_fields(admin_client, registry, replay_keys):
    key = issue(admin_client, registry)
    conn = Connection.objects.get(id=registry)
    envelope, semantic, transport = validate_envelope(raw(), "acquisition")
    receipt_id = uuid4()
    version, encrypted = seal_envelope(
        envelope, receipt_id=receipt_id, org_id=conn.org_id, semantic_digest=semantic
    )
    return dict(
        id=receipt_id,
        org_id=conn.org_id,
        namespace_id=conn.namespace_id,
        connection=conn,
        credential_id=key["id"],
        delivery_id=envelope["delivery_id"],
        manifest_digest=conn.manifest_digest,
        authorization_generation=conn.authorization_generation,
        semantic_digest=semantic,
        transport_digest=transport,
        replay_key_version=version,
        replay_ciphertext=encrypted,
    )


def flush_pair_guard():
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS mp_ingress_pending_required IMMEDIATE")
        cursor.execute("SET CONSTRAINTS mp_ingress_pending_required DEFERRED")


def create_pair(fields):
    with transaction.atomic():
        inbox = Inbox.objects.create(**fields)
        Pending.objects.create(org_id=inbox.org_id, inbox=inbox)
        flush_pair_guard()
    return inbox


def test_canonical_retry_hash_retains_transport_difference():
    first = raw(occurred_at="2026-10-19T00:00:00-05:00")
    decoded = json.loads(first)
    decoded["occurred_at"] = "2026-10-19T05:00:00Z"
    second = json.dumps(decoded, sort_keys=True, indent=2).encode()
    a, semantic_a, transport_a = validate_envelope(first, "acquisition")
    b, semantic_b, transport_b = validate_envelope(second, "acquisition")
    assert a == b and semantic_a == semantic_b
    assert transport_a != transport_b
    assert validate_envelope(raw(), "acquisition")[0]["occurred_at"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"schema": "unsupported"},
        {"note": "not retained"},
        {"source_id": "name"},
        {"occurred_at": "2026-10-19"},
        {"occurred_at": "2026-10-19T05:00:00"},
        {"delivery_id": 1},
        {"occurred_at": 1},
    ],
)
def test_reject_unbounded_or_ambiguous_input(changes):
    with pytest.raises(ValidationError):
        validate_envelope(raw(**changes), "acquisition")


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"[]",
        b"null",
        b"{",
        b"\xff",
        b" " * 16385,
        b'{"schema":"x","schema":"y"}',
        b"[" * 1500,
    ],
)
def test_reject_invalid_wire_data(body):
    with pytest.raises(ValidationError):
        validate_envelope(body, "acquisition")


@pytest.mark.parametrize(
    "changes",
    [
        {"org_id": str(uuid4())},
        {"patient_id": str(uuid4())},
        {"verified": True},
        {"event_type": "treatment.completed"},
        {"event_type": "payment.settled"},
        {"event_type": "patient.identity_linked"},
    ],
)
def test_external_authority_denied(changes):
    with pytest.raises(PermissionDenied):
        validate_envelope(raw(**changes), "acquisition")


def test_replay_ciphertext_binding_and_key_rotation(replay_keys, settings):
    envelope, digest, _ = validate_envelope(raw(), "acquisition")
    binding = dict(receipt_id=uuid4(), org_id=uuid4(), semantic_digest=digest)
    version, ciphertext = seal_envelope(envelope, **binding)
    assert envelope["source_id"] not in ciphertext
    assert open_envelope(ciphertext, key_version=version, **binding) == envelope
    for override in (
        {"org_id": uuid4()},
        {"receipt_id": uuid4()},
        {"semantic_digest": "0" * 64},
    ):
        with pytest.raises(ValueError, match="Replay evidence unavailable"):
            open_envelope(ciphertext, key_version=version, **{**binding, **override})
    with pytest.raises(ValueError):
        open_envelope("invalid", key_version=version, **binding)
    settings.INTEGRATION_REPLAY_KEYS["test-v2"] = Fernet.generate_key()
    settings.INTEGRATION_REPLAY_KEY_VERSION = "test-v2"
    assert open_envelope(ciphertext, key_version=version, **binding) == envelope
    del settings.INTEGRATION_REPLAY_KEYS[version]
    with pytest.raises(ValueError):
        open_envelope(ciphertext, key_version=version, **binding)


def test_missing_replay_key_fails_closed(settings):
    settings.INTEGRATION_REPLAY_KEYS = {}
    settings.INTEGRATION_REPLAY_KEY_VERSION = "test-v1"
    with pytest.raises(ValueError, match="Replay encryption unavailable"):
        seal_envelope({}, receipt_id=uuid4(), org_id=uuid4(), semantic_digest="0" * 64)


def test_storage_encrypted_pair_unique_and_forced_rls(receipt_fields, org_b):
    row = create_pair(receipt_fields)
    assert Pending.objects.filter(inbox=row).count() == 1
    assert open_envelope(
        row.replay_ciphertext,
        key_version=row.replay_key_version,
        receipt_id=row.id,
        org_id=row.org_id,
        semantic_digest=row.semantic_digest,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        create_pair({**receipt_fields, "id": uuid4()})
    with rls_org(org_b):
        assert not Inbox.objects.filter(id=row.id).exists()
        assert not Pending.objects.filter(inbox_id=row.id).exists()
        with pytest.raises(IntegrityError), transaction.atomic():
            Pending.objects.create(org=org_b, inbox_id=row.id)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('mp_integration_inbox','mp_integration_pending')"
        )
        assert cursor.fetchall() == [(True, True), (True, True)]


def test_receipt_requires_atomic_work_marker(receipt_fields):
    with pytest.raises(IntegrityError), transaction.atomic():
        Inbox.objects.create(**receipt_fields)
        flush_pair_guard()
    assert not Inbox.objects.filter(id=receipt_fields["id"]).exists()
    create_pair(receipt_fields)


@pytest.mark.parametrize(
    "field,value",
    [
        ("semantic_digest", "invalid"),
        ("schema_version", "unknown"),
        ("authorization_generation", 999),
        ("replay_key_version", "invalid key"),
        ("replay_ciphertext", "plaintext"),
        ("manifest_digest", "0" * 64),
    ],
)
def test_sql_receipt_shape_guards(receipt_fields, field, value):
    with pytest.raises(IntegrityError), transaction.atomic():
        create_pair({**receipt_fields, field: value})


def test_cross_practice_receipt_links_rejected(receipt_fields, org_b):
    with rls_org(org_b):
        with pytest.raises(IntegrityError), transaction.atomic():
            create_pair({**receipt_fields, "org_id": org_b.id})


def test_immutable_evidence_and_pending_marker(receipt_fields):
    row = create_pair(receipt_fields)
    for model, change in [
        (Inbox, {"semantic_digest": "0" * 64}),
        (Pending, {"created_at": row.created_at}),
    ]:
        with pytest.raises(IntegrityError), transaction.atomic():
            model.objects.all().update(**change)
        with pytest.raises(IntegrityError), transaction.atomic():
            model.objects.all()._raw_delete(model.objects.db)


def test_probe_credentials_still_cannot_receive(admin_client, registry, settings):
    settings.INTEGRATION_RECEIVE_ENABLED = True
    credential = issue(admin_client, registry)
    result = service(credential["credential"]).post(
        ROOT + "service/events/", json.loads(raw()), format="json"
    )
    assert result.status_code == 403
    assert Inbox.objects.count() == Pending.objects.count() == 0


@pytest.mark.parametrize("field", ["namespace_id", "connection_id", "credential_id"])
def test_foreign_receipt_parent_is_rejected(receipt_fields, org_b_client, org_b, field):
    other_namespace = foundation.post(
        org_b_client, "namespaces/", provider_key="fixture_a", account_key="test_other"
    )
    assert other_namespace.status_code == 201
    other_connection = foundation.post(
        org_b_client,
        "connections/",
        namespace_id=other_namespace.json()["id"],
        label="TEST other",
        manifest_id="fixture_a:acquisition",
    )
    assert other_connection.status_code == 201
    with rls_org(org_b):
        other_key = issue(org_b_client, other_connection.json()["id"])
    parent_ids = {
        "namespace_id": other_namespace.json()["id"],
        "connection_id": other_connection.json()["id"],
        "credential_id": other_key["id"],
    }
    fields = {**receipt_fields, field: parent_ids[field]}
    if field == "connection_id":
        del fields["connection"]
    with pytest.raises(IntegrityError), transaction.atomic():
        create_pair(fields)


def test_no_context_hides_receipt_and_rejects_write(receipt_fields):
    row = create_pair(receipt_fields)
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org',true)")
        original = cursor.fetchone()[0] or ""
        cursor.execute("SELECT set_config('app.current_org','',true)")
    try:
        assert Inbox.objects.count() == Pending.objects.count() == 0
        with pytest.raises(IntegrityError), transaction.atomic():
            Pending.objects.create(org_id=row.org_id, inbox=row)
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_org',%s,true)", [original])
