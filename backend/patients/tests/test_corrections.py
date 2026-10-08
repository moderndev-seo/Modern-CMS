from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction

from common.testing import rls_org
from invoices.models import Payment
from patients.models import Receipt, ReceiptCorrection
from patients.tests.test_allocations import allocate, line
from patients.tests.test_journey import BASE, DATE, create, record, report
from patients.tests.test_matching import match, pair

pytestmark = [
    pytest.mark.postgres_only,
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="Requires audit triggers"
    ),
]


def correct(client, patient, receipt, **overrides):
    return client.post(
        f"{BASE}{patient['id']}/corrections/",
        {
            "receipt": str(receipt.id),
            "amount": "80.00",
            "revision": 0,
            "request_id": str(uuid4()),
            "reason": "Fictional entry typo",
            **overrides,
        },
        format="json",
    )


def cash(client, org, **overrides):
    patient = create(client, **overrides)
    result = record(
        client,
        patient,
        "receipts",
        kind="payment",
        amount="100.00",
        reference=str(uuid4()),
        occurred_at=DATE,
    )
    assert result.status_code == 201
    with rls_org(org):
        receipt = Receipt.objects.get(id=result.data["id"])
    return patient, receipt


def test_amount_correction_and_restoration_recalculate_original_period(
    admin_client, org_a
):
    patient, receipt = cash(admin_client, org_a)
    original = Receipt.objects.values().get(id=receipt.id)
    assert correct(admin_client, patient, receipt).status_code == 201
    receipt.refresh_from_db()
    assert receipt.amount == 80
    assert report(admin_client)["totals"]["net_revenue"] == 80
    assert (
        report(admin_client, "2026-09-03", "2026-09-30")["totals"]["net_revenue"] == 0
    )
    assert (
        correct(admin_client, patient, receipt, amount="100.00", revision=1).status_code
        == 201
    )
    assert report(admin_client)["totals"]["net_revenue"] == 100
    current = Receipt.objects.values().get(id=receipt.id)
    for field in original.keys() - {"amount", "updated_at", "updated_by_id"}:
        assert current[field] == original[field]
    entries = list(ReceiptCorrection.objects.order_by("revision"))
    assert Decimal(str(entries[0].snapshot["amount"])) == 100
    assert Decimal(str(entries[1].snapshot["amount"])) == 80
    assert len(entries) == 2 and Receipt.objects.count() == 1
    detail = admin_client.get(f"{BASE}{patient['id']}/").data
    assert len(detail["corrections"]) == 2 and detail["original_source"] == "google_ads"
    assert detail["net_revenue"] == 100


def test_retry_stale_revision_and_invalid_input(admin_client, org_a):
    patient, receipt = cash(admin_client, org_a)
    request_id = str(uuid4())
    assert (
        correct(admin_client, patient, receipt, request_id=request_id).status_code
        == 201
    )
    assert (
        correct(admin_client, patient, receipt, request_id=request_id).status_code
        == 200
    )
    assert (
        correct(
            admin_client, patient, receipt, request_id=request_id, amount="90.00"
        ).status_code
        == 409
    )
    assert correct(admin_client, patient, receipt, amount="90.00").status_code == 409
    assert correct(admin_client, patient, receipt, revision=1).status_code == 409
    for extra in (
        {"amount": "0"},
        {"amount": "-1"},
        {"amount": "1.001"},
        {"reason": "  "},
        {"snapshot": {}},
        {"org": str(org_a.id)},
    ):
        assert (
            correct(admin_client, patient, receipt, revision=1, **extra).status_code
            == 400
        )
    assert (
        correct(admin_client, patient, receipt, revision=1, amount="100.00").status_code
        == 201
    )
    # A late retry acknowledges its own entry and cannot restore its old amount.
    assert (
        correct(admin_client, patient, receipt, request_id=request_id).status_code
        == 200
    )
    receipt.refresh_from_db()
    assert receipt.amount == 100 and ReceiptCorrection.objects.count() == 2


def test_refund_corrections_caps_and_atomic_failure(admin_client, org_a):
    patient, payment = cash(admin_client, org_a)
    refunded = Receipt.objects.create(
        org=org_a,
        patient_id=patient["id"],
        kind="refund",
        payment=payment,
        amount=20,
        reference="refund",
        occurred_at=DATE,
    )
    assert correct(admin_client, patient, refunded, amount="30.00").status_code == 201
    assert report(admin_client)["totals"]["net_revenue"] == 70
    assert (
        correct(
            admin_client, patient, refunded, amount="100.01", revision=1
        ).status_code
        == 409
    )
    assert correct(admin_client, patient, payment, amount="29.99").status_code == 409
    assert ReceiptCorrection.objects.count() == 1
    payment.refresh_from_db()
    refunded.refresh_from_db()
    assert payment.amount == 100 and refunded.amount == 30
    assert correct(admin_client, patient, payment, amount="30.00").status_code == 201
    assert report(admin_client)["totals"]["net_revenue"] == 0


def test_matching_and_allocation_must_be_explicitly_released(
    admin_client, org_a, admin_user
):
    patient, legacy, receipt = pair(admin_client, org_a, "100.00")
    before = list(Payment.objects.values())
    matched = match(admin_client, patient, legacy, receipt)
    assert matched.status_code == 201
    assert correct(admin_client, patient, receipt).status_code == 409
    with (
        pytest.raises(IntegrityError, match="Reverse the active match"),
        transaction.atomic(),
    ):
        ReceiptCorrection.objects.create(
            org=org_a,
            patient_id=patient["id"],
            receipt=receipt,
            revision=1,
            amount=80,
            reason="Bypass test",
            request_id=uuid4(),
            created_by=admin_user,
        )
    state = admin_client.get(f"{BASE}{patient['id']}/corrections/").data
    assert state["receipts"][0]["blockers"]
    from patients.models import PaymentMatch

    match_id = PaymentMatch.objects.get(receipt=receipt).id
    result = admin_client.post(
        f"{BASE}{patient['id']}/billing/reversals/",
        {"match": str(match_id), "reason": "Fictional correction review"},
        format="json",
    )
    assert result.status_code in (200, 201), result.data
    assert (
        allocate(
            admin_client, patient, receipt, [line(legacy.invoice, "100.00")]
        ).status_code
        == 201
    )
    assert correct(admin_client, patient, receipt).status_code == 409
    with pytest.raises(IntegrityError, match="Clear allocations"), transaction.atomic():
        ReceiptCorrection.objects.create(
            org=org_a,
            patient_id=patient["id"],
            receipt=receipt,
            revision=1,
            amount=80,
            reason="Bypass test",
            request_id=uuid4(),
            created_by=admin_user,
        )
    assert allocate(admin_client, patient, receipt, [], revision=1).status_code == 201
    assert correct(admin_client, patient, receipt).status_code == 201
    assert list(Payment.objects.values()) == before
    assert not PaymentMatch.objects.filter(active=True).exists()


def test_admin_tenant_and_foreign_receipt_guards(
    admin_client, user_client, org_b_client, org_a, org_b
):
    a, receipt = cash(admin_client, org_a)
    b, foreign = cash(org_b_client, org_b)
    assert user_client.get(f"{BASE}{a['id']}/corrections/").status_code == 403
    assert correct(user_client, a, receipt).status_code == 403
    assert org_b_client.get(f"{BASE}{a['id']}/corrections/").status_code == 404
    assert correct(org_b_client, a, receipt).status_code == 404
    assert correct(org_b_client, b, receipt).status_code == 404
    other = create(admin_client)
    assert correct(admin_client, other, receipt).status_code == 404
    with rls_org(org_b):
        with pytest.raises(IntegrityError), transaction.atomic():
            ReceiptCorrection.objects.create(
                org=org_b,
                patient_id=b["id"],
                receipt=receipt,
                revision=1,
                amount=10,
                request_id=uuid4(),
                reason="Foreign link",
                created_by_id=foreign.created_by_id,
            )
    with rls_org(org_a):
        assert not ReceiptCorrection.objects.exists()


def test_database_audit_immutability_and_forced_rls(
    admin_client, org_a, org_b, admin_user
):
    patient, receipt = cash(admin_client, org_a)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='mp_receipt_correction'"
        )
        assert cursor.fetchone() == (True, True)
        cursor.execute(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )
        assert cursor.fetchone() == (False, False)
    entry = ReceiptCorrection.objects.create(
        org=org_a,
        patient_id=patient["id"],
        receipt=receipt,
        revision=1,
        amount=80,
        reason="Direct audited correction",
        request_id=uuid4(),
        created_by=admin_user,
        snapshot={"amount": "forged"},
    )
    entry.refresh_from_db()
    receipt.refresh_from_db()
    assert Decimal(str(entry.snapshot["amount"])) == 100 and receipt.amount == 80
    for changes in (
        {"amount": 90},
        {"reference": "changed"},
        {"occurred_at": "2026-09-03T12:00:00Z"},
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            Receipt.objects.filter(id=receipt.id).update(**changes)
    with pytest.raises(IntegrityError), transaction.atomic():
        ReceiptCorrection.objects.filter(id=entry.id).update(reason="rewrite")
    with pytest.raises(IntegrityError), transaction.atomic():
        ReceiptCorrection.objects.filter(id=entry.id).delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        ReceiptCorrection.objects.create(
            org=org_a,
            patient_id=patient["id"],
            receipt=receipt,
            revision=3,
            amount=90,
            reason="Stale",
            request_id=uuid4(),
            created_by=admin_user,
        )
    with rls_org(org_b):
        assert not ReceiptCorrection.objects.filter(id=entry.id).exists()


@pytest.mark.django_db(transaction=True)
def test_competing_corrections_keep_one_current_revision(
    admin_client, org_a, admin_user
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import DatabaseError, connections

    patient, receipt = cash(admin_client, org_a)
    start = Barrier(2)

    def attempt(amount):
        try:
            with transaction.atomic():
                with connections["default"].cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.current_org', %s, true)",
                        [str(org_a.id)],
                    )
                    cursor.execute("SET LOCAL lock_timeout = '5s'")
                start.wait(timeout=10)
                ReceiptCorrection.objects.create(
                    org_id=org_a.id,
                    patient_id=patient["id"],
                    receipt_id=receipt.id,
                    revision=1,
                    request_id=uuid4(),
                    amount=amount,
                    reason="Fictional simultaneous correction",
                    created_by_id=admin_user.id,
                )
            return "accepted"
        except DatabaseError as exc:
            return exc.__cause__.sqlstate
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, amount) for amount in (80, 90)]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(results) == ["23514", "accepted"]
    with rls_org(org_a):
        receipt.refresh_from_db()
        entry = ReceiptCorrection.objects.get(receipt=receipt)
        assert receipt.amount == entry.amount and entry.revision == 1


def test_unknown_source_missing_spend_and_cash_deletion_guard(admin_client, org_a):
    patient, receipt = cash(
        admin_client, org_a, original_source="unknown", original_at=None
    )
    assert correct(admin_client, patient, receipt, amount="80.25").status_code == 201
    data = report(admin_client)
    unknown = next(row for row in data["sources"] if row["source"] == "unknown")
    assert unknown["net_revenue"] == Decimal("80.25")
    assert unknown["roas"] is None and data["totals"]["roas"] is None
    with pytest.raises(IntegrityError, match="cannot be deleted"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM mp_receipt WHERE id=%s", [receipt.id])
    assert Receipt.objects.get(id=receipt.id).amount == Decimal("80.25")
