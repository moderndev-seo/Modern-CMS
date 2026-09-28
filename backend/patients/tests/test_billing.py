from decimal import Decimal
from uuid import uuid4

from common.testing import rls_org
from invoices.models import Invoice, Payment
from patients.models import Receipt
from patients.tests.test_journey import BASE, create, report


def invoice(org, patient, **overrides):
    item = Invoice.objects.create(
        org=org,
        contact_id=patient["contact"],
        invoice_title="Fictional review invoice",
        invoice_number=f"TEST-{uuid4().hex[:10]}",
        **overrides,
    )
    # Avoid line-item recalculation: fixture represents already-issued documents.
    Invoice.objects.filter(pk=item.id).update(
        total_amount=Decimal("200"), amount_due=Decimal("200")
    )
    item.refresh_from_db()
    return item


def test_billing_separates_receipts_currencies_statuses_and_ledger_drift(
    admin_client, org_a
):
    patient = create(admin_client)
    with rls_org(org_a):
        usd = invoice(org_a, patient, status="Sent")
        invoice(org_a, patient, status="Sent", currency="EUR")
        for status in ("Draft", "Pending", "Cancelled"):
            invoice(org_a, patient, status=status)
        Payment.objects.create(
            org=org_a,
            invoice=usd,
            amount=Decimal("75.25"),
            payment_date="2026-09-02",
            payment_method="CASH",
        )
        Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="payment",
            amount=Decimal("90"),
            reference="patient-payment",
        )
        payment = Receipt.objects.get(reference="patient-payment")
        Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="refund",
            payment=payment,
            amount=Decimal("10"),
            reference="patient-refund",
        )
        Invoice.objects.filter(pk=usd.id).update(amount_paid=Decimal("70"))
    before = report(admin_client)
    result = admin_client.get(f"{BASE}{patient['id']}/billing/")
    assert result.status_code == 200, result.data
    data = result.data
    assert (
        data["payments"] == 90 and data["refunds"] == 10 and data["net_collected"] == 80
    )
    assert data["count"] == 5 and data["excluded_from_billed_count"] == 3
    assert data["currencies"] == [
        {"currency": "EUR", "billed": Decimal("200"), "invoice_payments": 0},
        {
            "currency": "USD",
            "billed": Decimal("200"),
            "invoice_payments": Decimal("75.25"),
        },
    ]
    row = next(row for row in data["results"] if row["id"] == str(usd.id))
    assert row["stored_paid"] == 70 and row["invoice_payments"] == Decimal("75.25")
    assert not row["ledger_matches_stored_paid"]
    assert report(admin_client) == before
    with rls_org(org_a):
        usd.refresh_from_db()
        assert (
            usd.amount_paid == 70
        )  # Review never silently repairs accounting records.


def test_billing_admin_only_tenant_scoped_and_read_only(
    admin_client, user_client, org_b_client, org_a, org_b, unauthenticated_client
):
    patient = create(admin_client)
    own = create(user_client)
    foreign = create(org_b_client)
    with rls_org(org_b):
        invoice(org_b, foreign, status="Sent")
    url = f"{BASE}{patient['id']}/billing/"
    assert user_client.get(f"{BASE}{own['id']}/billing/").status_code == 403
    assert org_b_client.get(url).status_code == 404
    assert unauthenticated_client.get(url).status_code in (401, 403)
    response = admin_client.get(url, {"org": str(org_b), "contact": foreign["contact"]})
    assert response.status_code == 200 and response.data["results"] == []
    for method in (admin_client.post, admin_client.patch, admin_client.delete):
        assert method(url, {}, format="json").status_code == 405
    assert (
        admin_client.get(f"{BASE}{patient['id']}/").data["can_review_billing"] is True
    )
    assert user_client.get(f"{BASE}{own['id']}/").data["can_review_billing"] is False


def test_billing_pagination_does_not_change_currency_totals(admin_client, org_a):
    patient = create(admin_client)
    with rls_org(org_a):
        for _ in range(21):
            invoice(org_a, patient, status="Sent")
        other = create(admin_client)
        invoice(org_a, other, status="Sent")
    url = f"{BASE}{patient['id']}/billing/"
    first = admin_client.get(url).data
    second = admin_client.get(url, {"page": 2}).data
    assert len(first["results"]) == 20 and len(second["results"]) == 1
    assert first["count"] == second["count"] == 21
    assert (
        first["currencies"]
        == second["currencies"]
        == [{"currency": "USD", "billed": Decimal("4200"), "invoice_payments": 0}]
    )
    for invalid in ("bad", "0", "-1"):
        assert admin_client.get(url, {"page": invalid}).status_code == 400
