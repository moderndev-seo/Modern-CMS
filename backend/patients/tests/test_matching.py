from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from common.testing import rls_org
from invoices.models import Invoice, Payment
from patients.models import PaymentMatch, Receipt
from patients.tests.test_billing import invoice
from patients.tests.test_journey import BASE, create, report


def pair(client, org, amount="75.25"):
    patient = create(client)
    with rls_org(org):
        bill = invoice(org, patient, status="Sent")
        payment = Payment.objects.create(
            org=org,
            invoice=bill,
            amount=Decimal(amount),
            payment_date="2026-09-02",
            payment_method="CASH",
            reference_number="DEMO-PAY",
        )
        receipt = Receipt.objects.create(
            org=org,
            patient_id=patient["id"],
            kind="payment",
            amount=Decimal(amount),
            reference=f"receipt-{payment.id}",
        )
    return patient, payment, receipt


def match(client, patient, payment, receipt, **overrides):
    return client.post(
        f"{BASE}{patient['id']}/billing/matches/",
        {
            "receipt": str(receipt.id),
            "invoice_payment": str(payment.id),
            "reason": "Verified fictional bank reference",
            **overrides,
        },
        format="json",
    )


def test_match_retry_history_and_no_cash_changes(admin_client, org_a):
    patient, payment, receipt = pair(admin_client, org_a)
    before = report(admin_client)
    result = match(admin_client, patient, payment, receipt)
    assert result.status_code == 201, result.data
    assert match(admin_client, patient, payment, receipt).status_code == 200
    with rls_org(org_a):
        assert PaymentMatch.objects.count() == 1
        assert Payment.objects.count() == Receipt.objects.count() == 1
    data = admin_client.get(f"{BASE}{patient['id']}/billing/").data["matching"]
    assert (
        data["match_count"] == 1 and data["receipt_count"] == data["payment_count"] == 0
    )
    assert data["matches"][0]["consistent"] is True
    assert report(admin_client) == before
    with rls_org(org_a):
        Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="refund",
            amount=Decimal("5"),
            payment=receipt,
            reference="refund-after-match",
        )
    assert admin_client.get(f"{BASE}{patient['id']}/billing/").data[
        "net_collected"
    ] == Decimal("70.25")
    with rls_org(org_a):
        Invoice.objects.filter(pk=payment.invoice_id).update(currency="EUR")
    assert (
        admin_client.get(f"{BASE}{patient['id']}/billing/").data["matching"]["matches"][
            0
        ]["consistent"]
        is False
    )


def test_match_permissions_foreign_links_and_validation(
    admin_client, user_client, org_b_client, org_a, org_b
):
    patient, payment, receipt = pair(admin_client, org_a)
    foreign, foreign_payment, foreign_receipt = pair(org_b_client, org_b)
    assert match(user_client, patient, payment, receipt).status_code == 403
    assert match(org_b_client, patient, payment, receipt).status_code == 404
    assert match(admin_client, patient, foreign_payment, receipt).status_code == 404
    assert match(admin_client, patient, payment, foreign_receipt).status_code == 404
    assert match(admin_client, patient, payment, receipt, reason=" ").status_code == 400
    assert (
        match(admin_client, patient, payment, receipt, org=str(org_b.id)).status_code
        == 400
    )
    with rls_org(org_a):
        Payment.objects.filter(pk=payment.id).update(amount=Decimal("1"))
    assert match(admin_client, patient, payment, receipt).status_code == 400
    with rls_org(org_a):
        Payment.objects.filter(pk=payment.id).update(amount=receipt.amount)
        Invoice.objects.filter(pk=payment.invoice_id).update(currency="EUR")
    assert match(admin_client, patient, payment, receipt).status_code == 400
    with rls_org(org_a):
        Invoice.objects.filter(pk=payment.invoice_id).update(
            currency="USD", status="Cancelled"
        )
    assert match(admin_client, patient, payment, receipt).status_code == 400
    with rls_org(org_a):
        assert PaymentMatch.objects.count() == 0


def test_match_duplicate_records_and_refund_rejected(admin_client, org_a):
    patient, payment, receipt = pair(admin_client, org_a)
    with rls_org(org_a):
        second = Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="payment",
            amount=receipt.amount,
            reference="second",
        )
        refund = Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="refund",
            amount=receipt.amount,
            reference="refund",
            payment=receipt,
        )
    assert match(admin_client, patient, payment, refund).status_code == 400
    assert match(admin_client, patient, payment, receipt).status_code == 201
    assert match(admin_client, patient, payment, second).status_code == 409
    with rls_org(org_a):
        other_payment = Payment.objects.create(
            org=org_a,
            invoice=payment.invoice,
            amount=receipt.amount,
            payment_date="2026-09-02",
            payment_method="CASH",
        )
    assert match(admin_client, patient, other_payment, receipt).status_code == 409


@pytest.mark.postgres_only
def test_match_database_isolation_and_append_only(
    admin_client, org_b_client, org_a, org_b
):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    patient, payment, receipt = pair(admin_client, org_a)
    foreign, foreign_payment, foreign_receipt = pair(org_b_client, org_b)
    with rls_org(org_a):
        with pytest.raises(IntegrityError), transaction.atomic():
            PaymentMatch.objects.create(
                org=org_a,
                receipt=receipt,
                invoice_payment=foreign_payment,
                reason="Forged",
            )
    assert match(admin_client, patient, payment, receipt).status_code == 201
    with rls_org(org_b):
        assert not PaymentMatch.objects.exists()
    with rls_org(org_a):
        stored = PaymentMatch.objects.get()
        with pytest.raises(IntegrityError, match="append-only"), transaction.atomic():
            PaymentMatch.objects.filter(pk=stored.id).update(reason="Rewrite")
        with pytest.raises(IntegrityError, match="append-only"), transaction.atomic():
            stored.delete()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='mp_payment_match'"
            )
            assert cursor.fetchone() == (True, True)


def test_billing_seed_is_rerunnable_and_payment_delete_is_protected(
    admin_client, org_a
):
    from django.core.management import call_command

    from common.models import Org
    from patients.management.commands.seed_modern_practice import demo_id

    call_command("seed_modern_practice")
    call_command("seed_modern_practice_billing")
    demo = Org.objects.get(id=demo_id("harbor"))
    with rls_org(demo):
        before = list(Invoice.objects.values())
        receipts = list(Receipt.objects.values())
    call_command("seed_modern_practice_billing")
    with rls_org(demo):
        assert list(Invoice.objects.values()) == before
        assert list(Receipt.objects.values()) == receipts
        assert Payment.objects.count() == 1
        assert (
            Invoice.objects.get().total_amount
            == Receipt.objects.get(kind="payment").amount
        )
    patient, payment, receipt = pair(admin_client, org_a)
    assert match(admin_client, patient, payment, receipt).status_code == 201
    response = admin_client.delete(
        f"/api/invoices/{payment.invoice_id}/payments/{payment.id}/"
    )
    assert response.status_code == 409, response.data
    with rls_org(org_a):
        assert Payment.objects.filter(pk=payment.id).exists()


def reverse(client, patient, match_id, **overrides):
    return client.post(
        f"{BASE}{patient['id']}/billing/reversals/",
        {
            "match": match_id,
            "reason": "Wrong fictional reference; reviewed correction",
            **overrides,
        },
        format="json",
    )


def test_reversal_retry_rematch_retains_history_and_cash(admin_client, org_a):
    from patients.models import PaymentMatchReversal

    patient, payment, receipt = pair(admin_client, org_a)
    before = report(admin_client)
    original = match(admin_client, patient, payment, receipt).data["id"]
    assert reverse(admin_client, patient, original).status_code == 201
    assert (
        reverse(
            admin_client, patient, original, reason="Retry must not rewrite reason"
        ).status_code
        == 200
    )
    billing = admin_client.get(f"{BASE}{patient['id']}/billing/").data
    assert (
        billing["matching"]["receipt_count"]
        == billing["matching"]["payment_count"]
        == 1
    )
    history = billing["matching"]["matches"][0]
    assert history["active"] is False
    assert history["consistent"] is None
    assert (
        history["reversal"]["reason"]
        == "Wrong fictional reference; reviewed correction"
    )
    assert history["reversal"]["actor"] != "Not recorded"
    second = match(admin_client, patient, payment, receipt)
    assert second.status_code == 201 and second.data["id"] != original
    # An old retry must not reverse the newer match.
    assert reverse(admin_client, patient, original).status_code == 200
    with rls_org(org_a):
        assert PaymentMatch.objects.filter(active=True).count() == 1
        assert PaymentMatch.objects.count() == 2
        assert PaymentMatchReversal.objects.count() == 1
        assert Payment.objects.count() == Receipt.objects.count() == 1
        assert (
            PaymentMatch.objects.get(pk=original).reason
            == "Verified fictional bank reference"
        )
    assert report(admin_client) == before
    assert (
        admin_client.delete(
            f"/api/invoices/{payment.invoice_id}/payments/{payment.id}/"
        ).status_code
        == 409
    )


def test_reversal_permissions_scope_and_input(
    admin_client, user_client, org_b_client, org_a, org_b
):
    from patients.models import PaymentMatchReversal

    patient, payment, receipt = pair(admin_client, org_a)
    original = match(admin_client, patient, payment, receipt).data["id"]
    foreign, foreign_payment, foreign_receipt = pair(org_b_client, org_b)
    foreign_match = match(org_b_client, foreign, foreign_payment, foreign_receipt).data[
        "id"
    ]
    other = create(admin_client)
    assert reverse(user_client, patient, original).status_code == 403
    assert reverse(org_b_client, patient, original).status_code == 404
    assert reverse(admin_client, patient, foreign_match).status_code == 404
    assert reverse(admin_client, other, original).status_code == 404
    assert reverse(admin_client, patient, original, reason=" ").status_code == 400
    assert (
        reverse(admin_client, patient, original, reason="x" * 1001).status_code == 400
    )
    assert (
        reverse(admin_client, patient, original, org=str(org_b.id)).status_code == 400
    )
    assert reverse(admin_client, patient, "bad-id").status_code == 400
    with rls_org(org_a):
        assert not PaymentMatchReversal.objects.exists()
        assert PaymentMatch.objects.get(pk=original).active


@pytest.mark.postgres_only
def test_reversal_database_guards_and_rollback(
    admin_client, org_b_client, org_a, org_b
):
    from patients.models import PaymentMatchReversal

    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    patient, payment, receipt = pair(admin_client, org_a)
    original = match(admin_client, patient, payment, receipt).data["id"]
    with rls_org(org_a):
        stored = PaymentMatch.objects.get(pk=original)
        for values in ({"active": False}, {"reason": "rewrite"}, {"snapshot": {}}):
            with pytest.raises(IntegrityError), transaction.atomic():
                PaymentMatch.objects.filter(pk=original).update(**values)
        with pytest.raises(IntegrityError), transaction.atomic():
            PaymentMatch.objects.create(
                org=org_a,
                receipt=receipt,
                invoice_payment=payment,
                reason="Inactive forgery",
                active=False,
            )
        with pytest.raises(IntegrityError), transaction.atomic():
            PaymentMatch.objects.create(
                org=org_a,
                receipt=receipt,
                invoice_payment=payment,
                reason="Duplicate active",
            )
        for reason, actor in [(" ", stored.created_by), ("No actor", None)]:
            with pytest.raises(IntegrityError), transaction.atomic():
                PaymentMatchReversal.objects.create(
                    org=org_a, match=stored, reason=reason, created_by=actor
                )
        with pytest.raises(RuntimeError), transaction.atomic():
            PaymentMatchReversal.objects.create(
                org=org_a,
                match=stored,
                reason="Rollback demo",
                created_by=stored.created_by,
            )
            raise RuntimeError("Rollback")
        assert PaymentMatch.objects.get(pk=original).active
        assert not PaymentMatchReversal.objects.exists()
    with rls_org(org_b):
        with pytest.raises(IntegrityError), transaction.atomic():
            PaymentMatchReversal.objects.create(
                org=org_b,
                match_id=original,
                reason="Foreign link",
                created_by=stored.created_by,
            )
    assert reverse(admin_client, patient, original).status_code == 201
    with rls_org(org_b):
        assert not PaymentMatchReversal.objects.exists()
    with rls_org(org_a):
        audit = PaymentMatchReversal.objects.get()
        with pytest.raises(IntegrityError), transaction.atomic():
            PaymentMatchReversal.objects.filter(pk=audit.id).update(reason="Rewrite")
        with pytest.raises(IntegrityError), transaction.atomic():
            audit.delete()
        with pytest.raises(IntegrityError), transaction.atomic():
            PaymentMatch.objects.filter(pk=original).update(active=True)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='mp_payment_match_reversal'"
            )
            assert cursor.fetchone() == (True, True)


def test_reversal_after_drift_and_reassignment(admin_client, org_a):
    patient, payment, receipt = pair(admin_client, org_a)
    original = match(admin_client, patient, payment, receipt).data["id"]
    with rls_org(org_a):
        Payment.objects.filter(pk=payment.id).update(amount=Decimal("1"))
        replacement = Payment.objects.create(
            org=org_a,
            invoice=payment.invoice,
            amount=receipt.amount,
            payment_date="2026-09-02",
            payment_method="CASH",
            reference_number="Corrected fictional reference",
        )
    assert reverse(admin_client, patient, original).status_code == 201
    assert match(admin_client, patient, payment, receipt).status_code == 400
    assert match(admin_client, patient, replacement, receipt).status_code == 201
    with rls_org(org_a):
        assert PaymentMatch.objects.get(pk=original).snapshot["amount"] == "75.25"
        assert (
            PaymentMatch.objects.get(active=True).invoice_payment_id == replacement.id
        )
