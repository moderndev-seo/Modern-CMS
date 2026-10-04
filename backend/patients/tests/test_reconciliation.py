from decimal import Decimal

from common.testing import rls_org
from invoices.models import Payment
from patients.models import PaymentMatch, Receipt
from patients.tests.test_billing import invoice
from patients.tests.test_journey import BASE, create, report
from patients.tests.test_matching import match, pair, reverse


def coverage(client, patient, **params):
    response = client.get(f"{BASE}{patient['id']}/billing/", params)
    assert response.status_code == 200, response.data
    return response.data["receipt_coverage"]


def test_refunds_partition_and_follow_only_valid_current_matches(admin_client, org_a):
    patient, payment, receipt = pair(admin_client, org_a)
    with rls_org(org_a):
        Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="refund",
            payment=receipt,
            amount=5,
            reference="matched-refund",
        )
        extra = Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="payment",
            amount=20,
            reference="extra",
        )
        Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="refund",
            payment=extra,
            amount=2,
            reference="extra-refund",
        )
    before = report(admin_client)
    original = match(admin_client, patient, payment, receipt).data["id"]
    data = coverage(admin_client, patient)
    assert data["linked"] == {
        "payments": Decimal("75.25"),
        "refunds": 5,
        "net_collected": Decimal("70.25"),
        "payment_count": 1,
    }
    assert data["unmatched"]["net_collected"] == 18
    assert data["by_invoice"][str(payment.invoice_id)] == data["linked"]
    assert reverse(admin_client, patient, original).status_code == 201
    data = coverage(admin_client, patient)
    assert data["linked"]["payment_count"] == 0 and data["by_invoice"] == {}
    assert data["unmatched"]["net_collected"] == Decimal("88.25")
    assert match(admin_client, patient, payment, receipt).status_code == 201
    assert coverage(admin_client, patient)["linked"]["payment_count"] == 1
    with rls_org(org_a):
        Payment.objects.filter(pk=payment.id).update(
            reference_number="Changed evidence"
        )
    data = coverage(admin_client, patient)
    assert data["linked"]["net_collected"] == 0 and data["by_invoice"] == {}
    assert data["needs_review"]["net_collected"] == Decimal("70.25")
    assert sum(
        data[key]["net_collected"] for key in ("linked", "unmatched", "needs_review")
    ) == Decimal("88.25")
    assert report(admin_client) == before


def test_coverage_uses_all_records_not_history_or_invoice_page(admin_client, org_a):
    patient = create(admin_client)
    with rls_org(org_a):
        bill = invoice(org_a, patient, status="Sent")
        for index in range(101):
            receipt = Receipt.objects.create(
                org=org_a,
                patient_id=patient["id"],
                kind="payment",
                amount=1,
                reference=f"coverage-{index}",
            )
            payment = Payment.objects.create(
                org=org_a,
                invoice=bill,
                amount=1,
                payment_date="2026-09-02",
                payment_method="CASH",
            )
            PaymentMatch.objects.create(
                org=org_a,
                receipt=receipt,
                invoice_payment=payment,
                reason="Fictional verified pair",
            )
        for _ in range(20):
            invoice(org_a, patient, status="Sent")
    first = coverage(admin_client, patient)
    second = coverage(admin_client, patient, page=2)
    assert first == second
    assert first["linked"]["payments"] == first["linked"]["net_collected"] == 101
    assert first["linked"]["payment_count"] == 101
    assert first["by_invoice"][str(bill.id)]["payments"] == 101


def test_coverage_permissions_tenant_scope_empty_and_foreign_currency(
    admin_client, user_client, org_b_client, org_a, org_b
):
    patient, payment, receipt = pair(admin_client, org_a)
    foreign, foreign_payment, foreign_receipt = pair(org_b_client, org_b)
    assert (
        match(org_b_client, foreign, foreign_payment, foreign_receipt).status_code
        == 201
    )
    assert admin_client.get(f"{BASE}{foreign['id']}/billing/").status_code == 404
    assert user_client.get(f"{BASE}{patient['id']}/billing/").status_code == 403
    data = coverage(
        admin_client, patient, org=str(org_b.id), contact=foreign["contact"]
    )
    assert data["linked"]["payments"] == 0 and data["by_invoice"] == {}
    assert data["unmatched"]["payments"] == Decimal("75.25")
    empty = create(admin_client)
    assert coverage(admin_client, empty)["unmatched"]["payment_count"] == 0
    assert match(admin_client, patient, payment, receipt).status_code == 201
    with rls_org(org_a):
        from invoices.models import Invoice

        Invoice.objects.filter(pk=payment.invoice_id).update(currency="EUR")
    data = coverage(admin_client, patient)
    assert data["linked"]["payment_count"] == 0
    assert data["needs_review"]["payment_count"] == 1
    assert data["by_invoice"] == {}
