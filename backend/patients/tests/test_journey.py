from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import IntegrityError, ProgrammingError, connection, transaction

from common.testing import rls_org
from contacts.models import Contact
from patients.models import JourneyEvent, MarketingSpend, Patient, Receipt

BASE = "/api/patients/"
DATE = "2026-09-02T12:00:00Z"


def create(client, **overrides):
    response = client.post(
        BASE,
        {
            "first_name": "Fictional",
            "last_name": "Patient",
            "lead_at": DATE,
            "original_source": "google_ads",
            "original_campaign": "Care",
            "original_at": "2026-09-01T12:00:00Z",
            **overrides,
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    return response.data


def record(client, patient_record, path, **data):
    return client.post(f"{BASE}{patient_record['id']}/{path}/", data, format="json")


def report(client, start="2026-09-01", end="2026-09-30"):
    response = client.get(f"{BASE}growth/?start={start}&end={end}")
    assert response.status_code == 200, response.data
    return response.data


def test_full_journey_attribution_and_cash_reconcile(admin_client):
    patient = create(admin_client)
    for kind in ("booked", "attended", "consultation", "treated"):
        assert (
            record(
                admin_client,
                patient,
                "events",
                kind=kind,
                occurred_at="2026-09-03T12:00:00Z",
            ).status_code
            == 201
        )
    assert (
        record(
            admin_client,
            patient,
            "events",
            kind="booked",
            occurred_at="2026-09-04T12:00:00Z",
        ).status_code
        == 201
    )
    assert (
        record(
            admin_client,
            patient,
            "events",
            kind="touch",
            source="email",
            campaign="Later channel",
            occurred_at="2026-09-05T12:00:00Z",
        ).status_code
        == 201
    )
    payment = record(
        admin_client,
        patient,
        "receipts",
        kind="payment",
        amount="1200.00",
        reference="cash-001",
        occurred_at="2026-09-10T12:00:00Z",
    )
    assert payment.status_code == 201, payment.data
    refund = record(
        admin_client,
        patient,
        "receipts",
        kind="refund",
        payment=payment.data["id"],
        amount="100.00",
        reference="refund-001",
        occurred_at="2026-09-12T12:00:00Z",
    )
    assert refund.status_code == 201, refund.data
    assert (
        admin_client.put(
            BASE + "spend/",
            {"source": "google_ads", "date": "2026-09-01", "amount": "200.00"},
            format="json",
        ).status_code
        == 200
    )
    data = report(admin_client)
    assert (
        data["totals"]["leads"]
        == data["totals"]["booked"]
        == data["totals"]["treated"]
        == 1
    )
    assert data["totals"]["payments"] == Decimal("1200")
    assert data["totals"]["refunds"] == Decimal("100")
    assert data["totals"]["net_revenue"] == Decimal("1100")
    assert data["totals"]["roas"] == Decimal("5.50")
    detail = admin_client.get(f"{BASE}{patient['id']}/").data
    assert detail["original_source"] == "google_ads"
    assert detail["original_campaign"] == "Care"
    assert detail["net_revenue"] == data["totals"]["net_revenue"]
    assert len(detail["events"]) == 6
    assert (
        next(r for r in data["sources"] if r["source"] == "email")["net_revenue"] == 0
    )
    refund_period = report(admin_client, "2026-09-12", "2026-09-12")
    assert refund_period["totals"]["net_revenue"] == -100
    assert refund_period["totals"]["leads"] == 0


def test_unknown_missing_zero_spend_and_daily_replacement(admin_client):
    patient = create(admin_client, original_source="unknown", original_at=None)
    assert (
        record(
            admin_client,
            patient,
            "receipts",
            kind="payment",
            amount="25.25",
            reference="unknown",
            occurred_at=DATE,
        ).status_code
        == 201
    )
    totals = report(admin_client)["totals"]
    assert totals["spend"] is None and totals["roas"] is None
    assert totals["missing_spend_sources"] == ["Unknown"]
    for amount in ("0.00", "10.00", "20.00"):
        assert (
            admin_client.put(
                BASE + "spend/",
                {"source": "unknown", "date": "2026-09-02", "amount": amount},
                format="json",
            ).status_code
            == 200
        )
        totals = report(admin_client)["totals"]
        assert totals["spend"] == Decimal(amount)
        if amount == "0.00":
            assert totals["roas"] is None
    assert MarketingSpend.objects.count() == 1
    assert totals["net_revenue"] == Decimal("25.25")
    assert totals["roas"] == Decimal("1.26")


def test_utc_boundaries_and_distinct_patients(admin_client):
    p = create(admin_client, lead_at="2026-09-02T00:00:00Z")
    for i, timestamp in enumerate(
        ("2026-09-02T00:00:00Z", "2026-09-02T23:59:59Z", "2026-09-03T00:00:00Z")
    ):
        assert (
            record(
                admin_client,
                p,
                "receipts",
                kind="payment",
                amount="10.00",
                reference=f"boundary-{i}",
                occurred_at=timestamp,
            ).status_code
            == 201
        )
    data = report(admin_client, "2026-09-02", "2026-09-02")
    assert data["totals"]["net_revenue"] == 20
    assert data["totals"]["leads"] == 1
    assert (
        report(admin_client, "2026-09-03", "2026-09-03")["totals"]["net_revenue"] == 10
    )


def test_cross_practice_api_reads_writes_and_links(admin_client, org_b_client):
    a = create(admin_client)
    b = create(org_b_client)
    for path in ("", "events/", "receipts/"):
        assert org_b_client.get(f"{BASE}{a['id']}/{path}").status_code == 404
        assert admin_client.get(f"{BASE}{b['id']}/{path}").status_code == 404
    assert org_b_client.get(BASE).data["count"] == 1
    assert (
        record(org_b_client, a, "events", kind="treated", occurred_at=DATE).status_code
        == 404
    )
    assert (
        record(
            org_b_client,
            a,
            "receipts",
            kind="payment",
            amount="1",
            reference="bad",
            occurred_at=DATE,
        ).status_code
        == 404
    )
    assert (
        org_b_client.post(BASE, {"contact": a["contact"]}, format="json").status_code
        == 400
    )
    payment = record(
        admin_client,
        a,
        "receipts",
        kind="payment",
        amount="100",
        reference="a-only",
        occurred_at=DATE,
    )
    assert payment.status_code == 201
    assert (
        record(
            org_b_client,
            b,
            "receipts",
            kind="refund",
            amount="10",
            payment=payment.data["id"],
            reference="bad-refund",
            occurred_at=DATE,
        ).status_code
        == 404
    )
    assert report(org_b_client)["totals"]["net_revenue"] == 0
    assert report(admin_client)["totals"]["net_revenue"] == 100


def test_forged_server_fields_and_immutable_source(admin_client, org_b):
    assert (
        admin_client.post(
            BASE, {"first_name": "X", "org": str(org_b.id)}, format="json"
        ).status_code
        == 400
    )
    patient = create(admin_client)
    assert (
        admin_client.patch(
            f"{BASE}{patient['id']}/", {"original_source": "email"}, format="json"
        ).status_code
        == 405
    )
    assert (
        record(
            admin_client, patient, "events", kind="touch", org=str(org_b.id)
        ).status_code
        == 400
    )
    assert (
        record(
            admin_client, patient, "events", kind="touch", patient=patient["id"]
        ).status_code
        == 400
    )
    assert admin_client.delete(f"{BASE}{patient['id']}/").status_code == 405


def test_permissions_and_revoked_membership(
    admin_client, user_client, user_profile, unauthenticated_client
):
    patient = create(user_client)
    assert user_client.get(f"{BASE}{patient['id']}/").status_code == 200
    assert (
        record(
            user_client, patient, "events", kind="booked", occurred_at=DATE
        ).status_code
        == 201
    )
    assert (
        record(
            user_client,
            patient,
            "receipts",
            kind="payment",
            amount="1",
            reference="no",
            occurred_at=DATE,
        ).status_code
        == 403
    )
    assert (
        user_client.put(
            BASE + "spend/",
            {"source": "email", "date": "2026-09-02", "amount": "1"},
            format="json",
        ).status_code
        == 403
    )
    assert unauthenticated_client.get(BASE).status_code in (401, 403)
    user_profile.is_active = False
    user_profile.save()
    assert user_client.get(BASE).status_code == 403


def test_refund_limits_wrong_patient_duplicate_reference_and_validation(admin_client):
    patient = create(admin_client)
    other = create(admin_client)
    payment = record(
        admin_client,
        patient,
        "receipts",
        kind="payment",
        amount="100",
        reference="original",
        occurred_at=DATE,
    ).data

    def refund(**kwargs):
        return record(
            admin_client,
            patient,
            "receipts",
            **{
                "kind": "refund",
                "amount": "60",
                "reference": "r1",
                "payment": payment["id"],
                "occurred_at": DATE,
                **kwargs,
            },
        )

    assert refund().status_code == 201
    assert refund(reference="r2").status_code == 400
    assert refund(reference="r3", amount="40").status_code == 201
    assert refund(reference="r4", amount="0.01").status_code == 400
    assert (
        record(
            admin_client,
            other,
            "receipts",
            kind="refund",
            amount="1",
            reference="wrong",
            payment=payment["id"],
            occurred_at=DATE,
        ).status_code
        == 404
    )
    assert (
        record(
            admin_client,
            patient,
            "receipts",
            kind="payment",
            amount="100",
            reference="original",
            occurred_at=DATE,
        ).status_code
        == 400
    )
    for amount in ("0", "-1", "NaN", "1.001"):
        assert (
            record(
                admin_client,
                patient,
                "receipts",
                kind="payment",
                amount=amount,
                reference="invalid",
                occurred_at=DATE,
            ).status_code
            == 400
        )
    assert (
        record(
            admin_client,
            patient,
            "events",
            kind="treated",
            occurred_at="2099-01-01T00:00:00Z",
        ).status_code
        == 400
    )
    assert (
        record(
            admin_client,
            patient,
            "events",
            kind="treated",
            occurred_at="2026-01-01T00:00:00Z",
        ).status_code
        == 400
    )
    assert admin_client.get(BASE + "growth/?start=oops").status_code == 400
    assert (
        admin_client.get(BASE + "growth/?start=2026-09-10&end=2026-09-01").status_code
        == 400
    )


def test_existing_contact_reused_and_duplicates_rejected(admin_client, org_a):
    contact = Contact.objects.create(
        org=org_a,
        first_name="Existing",
        last_name="Person",
        email="existing@example.invalid",
    )
    response = admin_client.post(BASE, {"contact": str(contact.id)}, format="json")
    assert response.status_code == 201
    assert Contact.objects.filter(org=org_a).count() == 1
    assert (
        admin_client.post(BASE, {"contact": str(contact.id)}, format="json").status_code
        == 400
    )
    assert (
        admin_client.post(
            BASE, {"first_name": "Duplicate", "email": contact.email}, format="json"
        ).status_code
        == 400
    )


def test_demo_seed_is_idempotent_and_preserves_existing(org_a, admin_user):
    from patients.management.commands.seed_modern_practice import demo_id

    original = Contact.objects.create(org=org_a, first_name="Keep", last_name="Me")
    call_command("seed_modern_practice", member_email=admin_user.email)
    call_command("seed_modern_practice", member_email=admin_user.email)
    assert Contact.objects.get(id=original.id).first_name == "Keep"
    from common.models import Org, Profile

    for key in ("harbor", "cedar"):
        demo = Org.objects.get(id=demo_id(key))
        with rls_org(demo):
            assert Contact.objects.filter(org=demo).count() == 4
            assert Contact.objects.filter(
                id=demo_id(f"{key}:intake:contact"), org=demo
            ).exists()
            assert Patient.objects.filter(org=demo).count() == 3
            assert Receipt.objects.filter(org=demo).count() == 2
            assert JourneyEvent.objects.filter(org=demo).count() == 6
            assert MarketingSpend.objects.filter(org=demo).count() == 2
            assert Profile.objects.filter(org=demo, user=admin_user).count() == 1


@pytest.mark.postgres_only
def test_postgres_rls_and_relationship_constraints(
    admin_client, org_b_client, org_a, org_b
):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )
        assert cursor.fetchone() == (False, False), (
            "RLS tests must run as a non-bypass role"
        )
        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('mp_patient','mp_journey_event','mp_receipt','mp_marketing_spend')"
        )
        policies = cursor.fetchall()
        assert len(policies) == 4 and all(
            enabled and forced for _, enabled, forced in policies
        )
    a = create(admin_client)
    b = create(org_b_client)
    with rls_org(org_b):
        assert not Patient.objects.filter(id=a["id"]).exists()
        with pytest.raises(IntegrityError), transaction.atomic():
            Patient.objects.create(org=org_b, contact_id=a["contact"])
        with pytest.raises(IntegrityError), transaction.atomic():
            JourneyEvent.objects.create(org=org_b, patient_id=a["id"], kind="treated")
        with pytest.raises(IntegrityError), transaction.atomic():
            Receipt.objects.create(
                org=org_b,
                patient_id=a["id"],
                kind="payment",
                amount=10,
                reference="cross",
            )
        with (
            pytest.raises(ProgrammingError, match="row-level security"),
            transaction.atomic(),
        ):
            MarketingSpend.objects.create(
                org=org_a, source="email", date="2026-09-01", amount=10
            )
    with rls_org(org_a):
        assert not Patient.objects.filter(id=b["id"]).exists()
        with pytest.raises(IntegrityError), transaction.atomic():
            Patient.objects.filter(id=a["id"]).update(original_source="email")
