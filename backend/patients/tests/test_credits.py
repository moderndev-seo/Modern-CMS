from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction

from common.testing import rls_org
from invoices.models import Invoice
from patients.models import InvoiceCreditAdjustment, Receipt
from patients.tests.test_billing import invoice
from patients.tests.test_journey import BASE, create, report


def credit(client, patient, bill, amount="50.00", **extra):
    return client.post(
        f"{BASE}{patient['id']}/billing/credits/",
        {
            "invoice": str(bill.id),
            "amount": amount,
            "reason": "Fictional approved charge correction",
            "request_id": str(uuid4()),
            **extra,
        },
        format="json",
    )


def reverse_credit(client, patient, credit_id, **extra):
    return client.post(
        f"{BASE}{patient['id']}/billing/credit-reversals/",
        {
            "credit": credit_id,
            "reason": "Fictional correction reversed",
            "request_id": str(uuid4()),
            **extra,
        },
        format="json",
    )


def billing(client, patient):
    response = client.get(f"{BASE}{patient['id']}/billing/")
    assert response.status_code == 200, response.data
    return response.data


def setup(client, org):
    patient = create(client)
    with rls_org(org):
        bill = invoice(org, patient, status="Sent")
    return patient, bill


def test_credit_retry_reversal_and_original_ledgers_unchanged(admin_client, org_a):
    patient, bill = setup(admin_client, org_a)
    before = report(admin_client)
    with rls_org(org_a):
        original = Invoice.objects.filter(pk=bill.id).values().get()
    request_id = str(uuid4())
    result = credit(admin_client, patient, bill, request_id=request_id)
    assert result.status_code == 201, result.data
    assert credit(admin_client, patient, bill, request_id=request_id).status_code == 200
    assert (
        credit(
            admin_client, patient, bill, amount="51", request_id=request_id
        ).status_code
        == 409
    )
    state = billing(admin_client, patient)["results"][0]["credit_adjustment"]
    assert (
        state["active_credits"] == 50
        and state["adjusted_billed"] == 150
        and state["can_credit"]
    )
    reversal = reverse_credit(admin_client, patient, result.data["id"])
    assert reversal.status_code == 201, reversal.data
    assert reverse_credit(admin_client, patient, result.data["id"]).status_code == 200
    assert reverse_credit(admin_client, patient, reversal.data["id"]).status_code == 404
    data = billing(admin_client, patient)
    assert data["credit_history"]["count"] == 2
    assert data["results"][0]["credit_adjustment"]["adjusted_billed"] == 200
    # Old request retries do not recreate a reversed credit.
    assert credit(admin_client, patient, bill, request_id=request_id).status_code == 200
    assert (
        billing(admin_client, patient)["results"][0]["credit_adjustment"][
            "active_credits"
        ]
        == 0
    )
    with rls_org(org_a):
        assert Invoice.objects.filter(pk=bill.id).values().get() == original
        assert not Receipt.objects.exists()
        assert InvoiceCreditAdjustment.objects.count() == 2
    assert report(admin_client) == before


def test_credit_limits_input_and_invoice_drift(admin_client, org_a):
    patient, bill = setup(admin_client, org_a)
    for amount in ("0", "-1", "0.001", "201", "NaN"):
        assert credit(admin_client, patient, bill, amount=amount).status_code == 400
    assert credit(admin_client, patient, bill, reason=" ").status_code == 400
    assert credit(admin_client, patient, bill, snapshot={}).status_code == 400
    first = credit(admin_client, patient, bill, amount="125")
    assert first.status_code == 201
    assert credit(admin_client, patient, bill, amount="75.01").status_code == 400
    assert credit(admin_client, patient, bill, amount="75").status_code == 201
    assert not billing(admin_client, patient)["results"][0]["credit_adjustment"][
        "can_credit"
    ]
    with rls_org(org_a):
        Invoice.objects.filter(pk=bill.id).update(total_amount=Decimal("100"))
    state = billing(admin_client, patient)["results"][0]["credit_adjustment"]
    assert state["needs_review"] and state["adjusted_billed"] is None
    assert credit(admin_client, patient, bill, amount="1").status_code == 400
    assert reverse_credit(admin_client, patient, first.data["id"]).status_code == 201
    assert billing(admin_client, patient)["results"][0]["credit_adjustment"][
        "needs_review"
    ]
    with rls_org(org_a):
        remaining = InvoiceCreditAdjustment.objects.get(
            reversal_of__isnull=True, reversal__isnull=True
        )
    assert reverse_credit(admin_client, patient, str(remaining.id)).status_code == 201
    assert (
        billing(admin_client, patient)["results"][0]["credit_adjustment"][
            "adjusted_billed"
        ]
        == 100
    )
    assert credit(admin_client, patient, bill, amount="10").status_code == 201


def test_credit_permissions_foreign_links_and_status(
    admin_client, user_client, org_b_client, org_a, org_b
):
    patient, bill = setup(admin_client, org_a)
    foreign, foreign_bill = setup(org_b_client, org_b)
    other = create(admin_client)
    assert credit(user_client, patient, bill).status_code == 403
    assert credit(org_b_client, patient, bill).status_code == 404
    assert credit(admin_client, patient, foreign_bill).status_code == 404
    assert credit(admin_client, other, bill).status_code == 404
    original = credit(admin_client, patient, bill).data["id"]
    assert reverse_credit(user_client, patient, original).status_code == 403
    assert reverse_credit(org_b_client, foreign, original).status_code == 404
    assert reverse_credit(admin_client, other, original).status_code == 404
    assert (
        reverse_credit(admin_client, patient, original, org=str(org_b.id)).status_code
        == 400
    )
    assert (
        reverse_credit(admin_client, patient, original, reason=" ").status_code == 400
    )
    with rls_org(org_a):
        Invoice.objects.filter(pk=bill.id).update(currency="EUR")
    assert credit(admin_client, patient, bill).status_code == 400
    assert reverse_credit(admin_client, patient, original).status_code == 201
    for status in ("Draft", "Pending", "Cancelled"):
        with rls_org(org_a):
            Invoice.objects.filter(pk=bill.id).update(currency="USD", status=status)
        assert credit(admin_client, patient, bill).status_code == 400


@pytest.mark.postgres_only
def test_credit_database_enforces_cap_links_snapshot_and_audit(
    admin_client, org_b_client, org_a, org_b
):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    patient, bill = setup(admin_client, org_a)
    foreign, foreign_bill = setup(org_b_client, org_b)
    result = credit(admin_client, patient, bill, amount="150")
    with rls_org(org_a):
        original = InvoiceCreditAdjustment.objects.get(pk=result.data["id"])
        values = dict(
            org=org_a,
            patient_id=patient["id"],
            invoice=bill,
            amount=Decimal("10"),
            reason="Fictional DB check",
            created_by=original.created_by,
        )
        for override in (
            {"invoice": foreign_bill},
            {"patient_id": foreign["id"]},
            {"amount": Decimal("51")},
            {"amount": Decimal("-1")},
            {"reason": " "},
            {"created_by": None},
        ):
            with pytest.raises(IntegrityError), transaction.atomic():
                InvoiceCreditAdjustment.objects.create(
                    **{**values, **override}, request_id=uuid4()
                )
        with pytest.raises(RuntimeError), transaction.atomic():
            InvoiceCreditAdjustment.objects.create(**values, request_id=uuid4())
            raise RuntimeError("rollback")
        assert InvoiceCreditAdjustment.objects.count() == 1
        valid = InvoiceCreditAdjustment.objects.create(
            **values, snapshot={"forged": True}, request_id=uuid4()
        )
        valid.refresh_from_db()
        assert valid.snapshot["total"] == "200.00" and "forged" not in valid.snapshot
        with pytest.raises(IntegrityError), transaction.atomic():
            InvoiceCreditAdjustment.objects.filter(pk=valid.id).update(reason="rewrite")
        with pytest.raises(IntegrityError), transaction.atomic():
            valid.delete()
        with pytest.raises(IntegrityError), transaction.atomic():
            InvoiceCreditAdjustment.objects.create(
                **{**values, "amount": Decimal("1"), "reversal_of": original},
                request_id=uuid4(),
            )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='mp_invoice_credit'"
            )
            assert cursor.fetchone() == (True, True)
    with rls_org(org_b):
        assert not InvoiceCreditAdjustment.objects.exists()
        with pytest.raises(IntegrityError), transaction.atomic():
            InvoiceCreditAdjustment.objects.create(
                org=org_b,
                patient_id=foreign["id"],
                invoice=foreign_bill,
                reversal_of=original,
                amount=150,
                reason="Forged reversal",
                created_by=original.created_by,
                request_id=uuid4(),
            )


def test_credit_totals_include_history_beyond_visible_limit(admin_client, org_a):
    patient, bill = setup(admin_client, org_a)
    first = credit(admin_client, patient, bill, amount="1")
    with rls_org(org_a):
        original = InvoiceCreditAdjustment.objects.get(pk=first.data["id"])
        for _ in range(100):
            InvoiceCreditAdjustment.objects.create(
                org=org_a,
                patient_id=patient["id"],
                invoice=bill,
                amount=1,
                reason="Fictional pagination check",
                created_by=original.created_by,
                request_id=uuid4(),
            )
    data = billing(admin_client, patient)
    assert (
        data["credit_history"]["count"] == 101
        and len(data["credit_history"]["entries"]) == 100
    )
    assert data["results"][0]["credit_adjustment"]["active_credits"] == 101
    assert data["results"][0]["credit_adjustment"]["adjusted_billed"] == 99
