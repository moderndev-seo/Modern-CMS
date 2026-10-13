from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction

from common.testing import rls_org
from patients.models import (
    AttributionConnection,
    AttributionEvent,
    AttributionIdentity,
)
from patients.tests.test_journey import BASE, DATE, create, report

URL = BASE + "attribution/"


@pytest.fixture
def sandbox(org_a, org_b):
    for org in (org_a, org_b):
        org.name = "TEST - Fictional attribution"
        org.save(update_fields=["name"])


def stream(client):
    response = client.post(
        URL, {"name": "TEST connector", "request_id": str(uuid4())}, format="json"
    )
    assert response.status_code == 201, response.data
    return response.data["id"]


def send(
    client, connection_id, kind, facts=None, event_id=None, subject="test-patient"
):
    data = {"occurred_at": DATE} if facts is None else facts
    return client.post(
        f"{URL}{connection_id}/events/",
        {
            "event_id": event_id or kind,
            "subject_id": subject,
            "kind": kind,
            "data": data,
        },
        format="json",
    )


def lead(client, connection_id, **overrides):
    return send(
        client,
        connection_id,
        "lead",
        {
            "first_name": "Fictional",
            "lead_at": DATE,
            "original_source": "google_ads",
            "original_campaign": "TEST Campaign",
            "original_at": "2026-09-01T12:00:00Z",
            **overrides,
        },
    )


def cash(
    client,
    connection_id,
    kind="payment",
    event_id=None,
    subject="test-patient",
    **overrides,
):
    return send(
        client,
        connection_id,
        kind,
        {
            "amount": "1200.00",
            "currency": "USD",
            "occurred_at": DATE,
            **overrides,
        },
        event_id=event_id,
        subject=subject,
    )


def test_complete_loop_retries_first_touch_and_cash(sandbox, admin_client):
    key = stream(admin_client)
    patient = lead(admin_client, key)
    assert patient.status_code == 201, patient.data
    assert lead(admin_client, key).status_code == 200
    for kind in ("booked", "attended", "consultation", "treated"):
        assert send(admin_client, key, kind).status_code == 201
        assert send(admin_client, key, kind).status_code == 200
    assert (
        send(
            admin_client,
            key,
            "touch",
            {"source": "email", "campaign": "Later", "occurred_at": DATE},
        ).status_code
        == 201
    )
    assert cash(admin_client, key).status_code == 201
    assert cash(admin_client, key).status_code == 200
    assert (
        cash(
            admin_client, key, "refund", amount="100.00", payment_event_id="payment"
        ).status_code
        == 201
    )
    assert (
        cash(
            admin_client, key, "refund", amount="100.00", payment_event_id="payment"
        ).status_code
        == 200
    )
    data = report(admin_client)
    assert data["totals"]["net_revenue"] == Decimal("1100")
    assert (
        data["totals"]["leads"]
        == data["totals"]["booked"]
        == data["totals"]["treated"]
        == 1
    )
    assert data["totals"]["roas"] is None
    google = next(row for row in data["sources"] if row["source"] == "google_ads")
    assert google["net_revenue"] == Decimal("1100")
    detail = admin_client.get(f"{BASE}{patient.data['patient_id']}/").data
    assert (
        detail["original_source"] == "google_ads"
        and detail["original_campaign"] == "TEST Campaign"
    )
    history = admin_client.get(f"{URL}{key}/events/").data
    assert history["count"] == 8
    assert all(row["evidence"] == "sandbox" for row in history["results"])


def test_conflicting_retries_and_unmatched_events_never_create_cash(
    sandbox, admin_client
):
    key = stream(admin_client)
    assert send(admin_client, key, "treated").status_code == 409
    assert lead(admin_client, key).status_code == 201
    assert lead(admin_client, key, original_source="email").status_code == 409
    assert (
        cash(admin_client, key, "refund", payment_event_id="missing").status_code == 409
    )
    assert cash(admin_client, key).status_code == 201
    assert cash(admin_client, key, amount="1300.00").status_code == 409
    assert (
        cash(
            admin_client, key, "refund", amount="1300.00", payment_event_id="payment"
        ).status_code
        == 400
    )
    assert (
        cash(
            admin_client,
            key,
            "refund",
            amount="100.00",
            payment_event_id="payment",
            occurred_at="2026-09-01T12:00:00Z",
        ).status_code
        == 400
    )
    assert report(admin_client)["totals"]["net_revenue"] == Decimal("1200")
    assert admin_client.get(f"{URL}{key}/events/").data["count"] == 2


def test_unknown_currency_timestamps_and_forged_fields(sandbox, admin_client):
    key = stream(admin_client)
    assert lead(admin_client, key, original_source="unknown").status_code == 201
    for override in (
        {"currency": "EUR"},
        {"currency": ""},
        {"status": "pending"},
        {"reference": "forged"},
        {"payment": str(uuid4())},
        {"amount": "0"},
        {"occurred_at": "2099-01-01T00:00:00Z"},
    ):
        assert cash(admin_client, key, **override).status_code == 400
    assert send(admin_client, key, "treated", {}).status_code == 400
    response = admin_client.post(
        f"{URL}{key}/events/",
        {
            "event_id": "x",
            "subject_id": "p",
            "kind": "treated",
            "data": {},
            "org": str(uuid4()),
        },
        format="json",
    )
    assert response.status_code == 400
    assert cash(admin_client, key).status_code == 201
    unknown = next(
        row for row in report(admin_client)["sources"] if row["source"] == "unknown"
    )
    assert unknown["net_revenue"] == Decimal("1200") and unknown["roas"] is None


def test_api_permissions_isolation_and_foreign_refund(
    sandbox, admin_client, org_b_client, user_client, unauthenticated_client
):
    key = stream(admin_client)
    other = stream(org_b_client)
    lead(admin_client, key)
    lead(org_b_client, other)
    cash(org_b_client, other)
    for client in (user_client, unauthenticated_client):
        assert client.get(URL).status_code in (401, 403)
        assert client.get(f"{URL}{key}/events/").status_code in (401, 403)
        assert send(client, key, "treated").status_code in (401, 403)
    assert org_b_client.get(f"{URL}{key}/events/").status_code == 404
    assert send(org_b_client, key, "treated").status_code == 404
    assert (
        cash(admin_client, key, "refund", payment_event_id="payment").status_code == 409
    )
    assert not any(
        str(item["id"]) == key for item in org_b_client.get(URL).data["connections"]
    )


def test_non_test_practice_rejected(admin_client):
    assert (
        admin_client.post(
            URL, {"name": "x", "request_id": str(uuid4())}, format="json"
        ).status_code
        == 403
    )


def test_existing_identity_is_not_guessed_or_overwritten(sandbox, admin_client):
    key = stream(admin_client)
    existing = create(admin_client, email="fictional@example.com")
    assert lead(admin_client, key, email="fictional@example.com").status_code == 400
    assert lead(admin_client, key, contact=existing["contact"]).status_code == 400
    assert admin_client.get(f"{URL}{key}/events/").data["count"] == 0


@pytest.mark.postgres_only
def test_database_guards_and_forced_rls(
    sandbox, admin_client, org_b_client, org_a, org_b, admin_user, user_b
):
    key = stream(admin_client)
    other = stream(org_b_client)
    a = lead(admin_client, key).data
    b = lead(org_b_client, other).data
    with rls_org(org_a):
        for model in (AttributionConnection, AttributionIdentity, AttributionEvent):
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname=%s",
                    [model._meta.db_table],
                )
                assert cursor.fetchone() == (True, True)
            assert not model.objects.filter(org=org_b).exists()
        with pytest.raises(IntegrityError), transaction.atomic():
            AttributionIdentity.objects.create(
                org=org_a,
                created_by=admin_user,
                connection_id=key,
                external_id="foreign",
                patient_id=b["patient_id"],
            )
        with pytest.raises(IntegrityError), transaction.atomic():
            AttributionIdentity.objects.create(
                org=org_a,
                created_by=admin_user,
                connection_id=other,
                external_id="foreign",
                patient_id=a["patient_id"],
            )
        identity = AttributionIdentity.objects.get(connection_id=key)
        with pytest.raises(IntegrityError), transaction.atomic():
            AttributionEvent.objects.create(
                org=org_a,
                created_by=admin_user,
                connection_id=key,
                identity=identity,
                external_id="forged",
                kind="payment",
                payload_hash="a" * 64,
            )
        with pytest.raises(IntegrityError), transaction.atomic():
            AttributionConnection.objects.create(
                org=org_a, created_by=user_b, name="foreign actor", request_id=uuid4()
            )
        for model in (AttributionConnection, AttributionIdentity, AttributionEvent):
            with pytest.raises(IntegrityError), transaction.atomic():
                model.objects.filter(org=org_a).update(created_by=user_b)
        with pytest.raises(IntegrityError), transaction.atomic():
            AttributionEvent.objects.filter(org=org_a).delete()


@pytest.mark.django_db(transaction=True)
@pytest.mark.postgres_only
@pytest.mark.parametrize("second_amount", ["1200.00", "1400.00"])
def test_competing_imports_create_only_one_receipt(
    sandbox, admin_client, org_a, admin_user, admin_profile, second_amount
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from types import SimpleNamespace

    from django.db import connections
    from rest_framework.exceptions import APIException

    from patients.intake import ingest

    key = stream(admin_client)
    assert lead(admin_client, key).status_code == 201
    barrier = Barrier(2)

    def attempt(amount):
        try:
            with transaction.atomic():
                with connections["default"].cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.current_org',%s,true)", [str(org_a.id)]
                    )
                    cursor.execute("SET LOCAL lock_timeout='5s'")
                barrier.wait(timeout=10)
                result = ingest(
                    SimpleNamespace(profile=admin_profile, user=admin_user),
                    key,
                    {
                        "event_id": "payment",
                        "subject_id": "test-patient",
                        "kind": "payment",
                        "data": {
                            "amount": amount,
                            "currency": "USD",
                            "occurred_at": DATE,
                        },
                    },
                )
            return 200 if result["replayed"] else 201
        except APIException as error:
            return error.status_code
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(attempt, amount) for amount in ("1200.00", second_amount)
        ]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(results) == ([200, 201] if second_amount == "1200.00" else [201, 409])
    with rls_org(org_a):
        from patients.models import Receipt

        assert Receipt.objects.count() == 1
        assert AttributionEvent.objects.filter(connection_id=key).count() == 2


def test_connection_retry_and_pagination(sandbox, admin_client):
    body = {"name": "TEST connector", "request_id": str(uuid4())}
    first = admin_client.post(URL, body, format="json")
    assert first.status_code == 201
    assert admin_client.post(URL, body, format="json").data["id"] == first.data["id"]
    assert (
        admin_client.post(URL, {**body, "name": "Different"}, format="json").status_code
        == 409
    )
    key = first.data["id"]
    lead(admin_client, key)
    for index in range(51):
        assert (
            send(admin_client, key, "touch", event_id=f"touch-{index}").status_code
            == 201
        )
    page1 = admin_client.get(f"{URL}{key}/events/").data
    page2 = admin_client.get(f"{URL}{key}/events/?page=2").data
    assert (
        page1["count"] == 52
        and len(page1["results"]) == 50
        and len(page2["results"]) == 2
    )
    assert not {row["id"] for row in page1["results"]} & {
        row["id"] for row in page2["results"]
    }
    assert admin_client.get(f"{URL}{key}/events/?page=0").status_code == 400
