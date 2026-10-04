from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction

from common.testing import rls_org
from invoices.models import Invoice
from patients.models import Receipt, ReceiptAllocation
from patients.tests.test_allocations import allocate, line, state
from patients.tests.test_billing import invoice
from patients.tests.test_credits import credit, reverse_credit
from patients.tests.test_journey import BASE, create, report
from patients.tests.test_matching import match, pair


def refund(org, patient, payment, amount="20.00"):
    with rls_org(org):
        return Receipt.objects.create(
            org=org,
            patient_id=patient["id"],
            kind="refund",
            payment=payment,
            amount=Decimal(amount),
            reference=f"TEST-refund-{uuid4()}",
        )


def refund_line(receipt, bill=None, amount="20.00"):
    return {
        "refund": str(receipt.id),
        "invoice": str(bill.id) if bill else None,
        "amount": amount,
    }


def balances(client, patient):
    response = client.get(f"{BASE}{patient['id']}/balances/")
    assert response.status_code == 200, response.data
    return response.data


def test_refund_splits_credits_and_balances_do_not_double_subtract_cash(
    admin_client, org_a
):
    patient, payment, receipt = pair(admin_client, org_a, "100.00")
    returned = refund(org_a, patient, receipt)
    assert match(admin_client, patient, payment, receipt).status_code == 201
    with rls_org(org_a):
        second = invoice(org_a, patient, status="Sent")
        original = list(Invoice.objects.order_by("id").values())
        original_cash = list(Receipt.objects.order_by("id").values())
    growth = report(admin_client)
    result = allocate(
        admin_client,
        patient,
        receipt,
        [line(payment.invoice, "50.00"), line(second, "30.00")],
        refund_lines=[
            refund_line(returned, payment.invoice, "12.00"),
            refund_line(returned, second, "8.00"),
        ],
    )
    assert result.status_code == 201, result.data
    data = balances(admin_client, patient)
    assert data["available"] and data["totals"]["net_allocated"] == 80
    assert data["totals"]["explained_refunds"] == 20
    assert data["totals"]["recorded_balance"] == data["totals"]["outstanding"] == 320
    adjustment = credit(admin_client, patient, payment.invoice, amount="50.00")
    assert adjustment.status_code == 201
    data = balances(admin_client, patient)
    assert data["available"] and data["totals"]["recorded_balance"] == 270
    assert data["totals"]["active_credits"] == 50
    assert (
        reverse_credit(admin_client, patient, adjustment.data["id"]).status_code == 201
    )
    assert balances(admin_client, patient)["totals"]["recorded_balance"] == 320
    assert report(admin_client) == growth
    with rls_org(org_a):
        assert list(Invoice.objects.order_by("id").values()) == original
        assert list(Receipt.objects.order_by("id").values()) == original_cash


def test_missing_partial_and_unallocated_refund_explanations(admin_client, org_a):
    patient, payment, receipt = pair(admin_client, org_a, "100.00")
    returned = refund(org_a, patient, receipt)
    assert match(admin_client, patient, payment, receipt).status_code == 201
    assert (
        allocate(
            admin_client, patient, receipt, [line(payment.invoice, "80.00")]
        ).status_code
        == 201
    )
    data = balances(admin_client, patient)
    assert not data["available"] and data["totals"] is None
    assert data["invoices"][0]["recorded_balance"] is None
    assert data["refunds"]["unreconciled"] == 20
    assert (
        allocate(
            admin_client,
            patient,
            receipt,
            [line(payment.invoice, "80.00")],
            revision=1,
            refund_lines=[refund_line(returned, None, "10.00")],
        ).status_code
        == 201
    )
    assert balances(admin_client, patient)["refunds"]["unreconciled"] == 10
    assert (
        allocate(
            admin_client,
            patient,
            receipt,
            [line(payment.invoice, "80.00")],
            revision=2,
            refund_lines=[refund_line(returned)],
        ).status_code
        == 201
    )
    data = balances(admin_client, patient)
    assert data["available"] and data["refunds"]["from_unallocated_cash"] == 20
    assert data["totals"]["explained_refunds"] == 0
    assert data["totals"]["recorded_balance"] == 120


def test_balances_gate_matches_cash_drift_currency_and_credit_drift(
    admin_client, org_a
):
    patient, payment, receipt = pair(admin_client, org_a, "100.00")
    data = balances(admin_client, patient)
    assert not data["available"] and len(data["blockers"]) == 2
    assert (
        allocate(
            admin_client, patient, receipt, [line(payment.invoice, "100.00")]
        ).status_code
        == 201
    )
    assert not balances(admin_client, patient)["available"]
    matching = match(admin_client, patient, payment, receipt)
    assert matching.status_code == 201
    assert balances(admin_client, patient)["available"]
    adjustment = credit(admin_client, patient, payment.invoice, amount="50.00")
    assert adjustment.status_code == 201
    with rls_org(org_a):
        Invoice.objects.filter(pk=payment.invoice_id).update(
            total_amount=Decimal("180")
        )
    data = balances(admin_client, patient)
    assert not data["available"] and any(
        "credits" in reason for reason in data["blockers"]
    )
    assert (
        allocate(
            admin_client,
            patient,
            receipt,
            [line(payment.invoice, "100.00")],
            revision=1,
        ).status_code
        == 201
    )
    assert not balances(admin_client, patient)["available"]  # stale credit still blocks
    assert (
        reverse_credit(admin_client, patient, adjustment.data["id"]).status_code == 201
    )
    assert balances(admin_client, patient)["available"]
    with rls_org(org_a):
        foreign_currency = invoice(org_a, patient, status="Sent", currency="EUR")
    assert not balances(admin_client, patient)["available"]
    with rls_org(org_a):
        Invoice.objects.filter(pk=foreign_currency.id).update(status="Draft")
    assert balances(admin_client, patient)["available"]
    response = admin_client.post(
        f"{BASE}{patient['id']}/billing/reversals/",
        {"match": matching.data["id"], "reason": "Fictional balance test"},
        format="json",
    )
    assert response.status_code == 201
    assert not balances(admin_client, patient)["available"]


def test_overpayments_not_silently_netted_and_all_invoices_count(admin_client, org_a):
    patient, payment, receipt = pair(admin_client, org_a, "300.00")
    assert match(admin_client, patient, payment, receipt).status_code == 201
    assert (
        allocate(
            admin_client, patient, receipt, [line(payment.invoice, "300.00")]
        ).status_code
        == 201
    )
    data = balances(admin_client, patient)
    assert data["available"] and data["totals"]["recorded_balance"] == -100
    assert data["totals"]["outstanding"] == 0 and data["totals"]["overpaid"] == 100
    with rls_org(org_a):
        for _ in range(100):
            invoice(org_a, patient, status="Sent")
    data = balances(admin_client, patient)
    assert len(data["invoices"]) == 101 and data["available"]
    assert data["totals"]["outstanding"] == 20000 and data["totals"]["overpaid"] == 100
    assert data["totals"]["recorded_balance"] == 19900


def test_refund_permissions_links_and_retry(
    admin_client, user_client, org_b_client, org_a, org_b
):
    patient, payment, receipt = pair(admin_client, org_a, "100.00")
    other, other_payment, other_receipt = pair(org_b_client, org_b, "100.00")
    returned = refund(org_a, patient, receipt)
    foreign = refund(org_b, other, other_receipt)
    assert user_client.get(f"{BASE}{patient['id']}/balances/").status_code == 403
    assert org_b_client.get(f"{BASE}{patient['id']}/balances/").status_code == 404
    assert (
        admin_client.post(
            f"{BASE}{patient['id']}/balances/", {}, format="json"
        ).status_code
        == 405
    )
    assert (
        allocate(
            user_client, patient, receipt, [], refund_lines=[refund_line(returned)]
        ).status_code
        == 403
    )
    assert (
        allocate(
            admin_client, patient, receipt, [], refund_lines=[refund_line(foreign)]
        ).status_code
        == 404
    )
    assert (
        allocate(
            admin_client,
            patient,
            receipt,
            [],
            refund_lines=[refund_line(returned, other_payment.invoice)],
        ).status_code
        == 404
    )
    same_patient_other_cash = None
    with rls_org(org_a):
        same_patient_other_cash = Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="payment",
            amount=Decimal("100"),
            reference="TEST-other-cash",
        )
    unrelated = refund(org_a, patient, same_patient_other_cash)
    assert (
        allocate(
            admin_client, patient, receipt, [], refund_lines=[refund_line(unrelated)]
        ).status_code
        == 404
    )
    for lines in [
        [refund_line(returned, amount="20.01")],
        [refund_line(returned), refund_line(returned)],
        [refund_line(returned, amount="0")],
        [{**refund_line(returned), "scope": str(org_b.id)}],
    ]:
        assert (
            allocate(admin_client, patient, receipt, [], refund_lines=lines).status_code
            == 400
        )
    request_id = str(uuid4())
    fields = {"refund_lines": [refund_line(returned)], "request_id": request_id}
    first = allocate(admin_client, patient, receipt, [], **fields)
    assert first.status_code == 201, first.data
    assert allocate(admin_client, patient, receipt, [], **fields).status_code == 200
    assert (
        allocate(
            admin_client,
            patient,
            receipt,
            [],
            refund_lines=[refund_line(returned, payment.invoice)],
            request_id=request_id,
        ).status_code
        == 409
    )
    assert allocate(admin_client, patient, receipt, [], revision=1).status_code == 201
    assert allocate(admin_client, patient, receipt, [], **fields).status_code == 200
    assert state(admin_client, patient)["refund_totals"]["unreconciled"] == 40


@pytest.mark.skipif(connection.vendor != "postgresql", reason="PostgreSQL guards")
def test_refund_direct_database_budget_links_and_immutable_history(
    admin_client, org_b_client, org_a, org_b, admin_user
):
    patient, payment, receipt = pair(admin_client, org_a, "100.00")
    other, other_payment, other_receipt = pair(org_b_client, org_b, "100.00")
    returned = refund(org_a, patient, receipt)
    foreign = refund(org_b, other, other_receipt)
    with rls_org(org_a):

        def insert(refund_lines, **extra):
            fields = dict(
                org=org_a,
                patient_id=patient["id"],
                receipt=receipt,
                revision=1,
                request_id=uuid4(),
                reason="Fictional direct refund reconciliation",
                created_by=admin_user,
                lines=[],
                refund_lines=refund_lines,
                snapshot={"forged": True},
            )
            fields.update(extra)
            return ReceiptAllocation.objects.create(**fields)

        for lines in [
            [refund_line(foreign)],
            [refund_line(returned, other_payment.invoice)],
            [refund_line(returned, amount="20.01")],
            [
                refund_line(returned, None, "12.00"),
                refund_line(returned, payment.invoice, "12.00"),
            ],
            [refund_line(returned)] * 2,
            [{}],
            [{"refund": None, "invoice": None, "amount": "1.00"}],
        ]:
            with pytest.raises(IntegrityError), transaction.atomic():
                insert(lines)
        row = insert(
            [
                refund_line(returned, payment.invoice, "5.00"),
                refund_line(returned, None, "15.00"),
            ]
        )
        row.refresh_from_db()
        assert row.snapshot["receipt"]["refunds"] == [
            {"id": str(returned.id), "amount": "20.00"}
        ]
        assert str(payment.invoice_id) in row.snapshot["invoices"]
        assert "forged" not in row.snapshot
        with pytest.raises(IntegrityError), transaction.atomic():
            ReceiptAllocation.objects.filter(pk=row.id).update(refund_lines=[])
        with pytest.raises(IntegrityError), transaction.atomic():
            ReceiptAllocation.objects.filter(pk=row.id).delete()
    with rls_org(org_b):
        assert not ReceiptAllocation.objects.filter(pk=row.id).exists()


def test_refund_only_plan_drift_and_reassigned_credit_block_balances(
    admin_client, org_a
):
    patient, payment, receipt = pair(admin_client, org_a, "100.00")
    returned = refund(org_a, patient, receipt, "100.00")
    assert match(admin_client, patient, payment, receipt).status_code == 201
    assert (
        allocate(
            admin_client,
            patient,
            receipt,
            [],
            refund_lines=[refund_line(returned, payment.invoice, "100.00")],
        ).status_code
        == 201
    )
    assert balances(admin_client, patient)["available"]
    with rls_org(org_a):
        Invoice.objects.filter(pk=payment.invoice_id).update(
            invoice_number="TEST-CHANGED"
        )
    data = balances(admin_client, patient)
    assert not data["available"] and data["refunds"]["unreconciled"] == 100
    assert (
        allocate(
            admin_client,
            patient,
            receipt,
            [],
            revision=1,
            refund_lines=[refund_line(returned, None, "100.00")],
        ).status_code
        == 201
    )
    adjustment = credit(admin_client, patient, payment.invoice, amount="20.00")
    assert adjustment.status_code == 201
    other = create(admin_client)
    with rls_org(org_a):
        Invoice.objects.filter(pk=payment.invoice_id).update(
            contact_id=other["contact"]
        )
    data = balances(admin_client, patient)
    assert not data["available"] and any(
        "reassigned" in reason for reason in data["blockers"]
    )
