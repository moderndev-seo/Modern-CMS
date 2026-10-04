from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction

from common.testing import rls_org
from invoices.models import Invoice, Payment
from patients.models import Receipt, ReceiptAllocation
from patients.tests.test_billing import invoice
from patients.tests.test_journey import BASE, create, report
from patients.tests.test_matching import match, pair


def allocate(client, patient, receipt, lines, revision=0, **overrides):
    return client.post(
        f"{BASE}{patient['id']}/allocations/",
        {
            "receipt": str(receipt.id),
            "lines": lines,
            "revision": revision,
            "reason": "Fictional allocation review",
            "request_id": str(uuid4()),
            **overrides,
        },
        format="json",
    )


def line(bill, amount):
    return {"invoice": str(bill.id), "amount": amount}


def state(client, patient):
    response = client.get(f"{BASE}{patient['id']}/allocations/")
    assert response.status_code == 200, response.data
    return response.data


def test_split_replace_clear_retry_and_unchanged_ledgers(admin_client, org_a):
    patient, payment, receipt = pair(admin_client, org_a, "100")
    with rls_org(org_a):
        second = invoice(org_a, patient, status="Sent")
        original_invoices = list(Invoice.objects.order_by("id").values())
        original_payments = list(Payment.objects.values())
        original_receipts = list(Receipt.objects.values())
    assert match(admin_client, patient, payment, receipt).status_code == 201
    before = report(admin_client)
    request_id = str(uuid4())
    lines = [line(payment.invoice, "60.00"), line(second, "30.00")]
    first = allocate(admin_client, patient, receipt, lines, request_id=request_id)
    assert first.status_code == 201, first.data
    assert (
        allocate(
            admin_client, patient, receipt, list(reversed(lines)), request_id=request_id
        ).status_code
        == 200
    )
    assert (
        allocate(
            admin_client,
            patient,
            receipt,
            lines,
            request_id=request_id,
            reason="different",
        ).status_code
        == 409
    )
    totals = state(admin_client, patient)["totals"]
    assert totals == {
        "net_collected": Decimal("100"),
        "allocated": Decimal("90"),
        "unallocated": Decimal("10"),
        "needs_review": 0,
    }
    assert allocate(admin_client, patient, receipt, []).status_code == 409
    assert (
        allocate(
            admin_client, patient, receipt, [line(second, "100.00")], revision=1
        ).status_code
        == 201
    )
    assert state(admin_client, patient)["by_invoice"] == {
        str(second.id): Decimal("100")
    }
    assert allocate(admin_client, patient, receipt, [], revision=2).status_code == 201
    # Retrying the old request does not restore the replaced plan.
    assert (
        allocate(
            admin_client, patient, receipt, lines, request_id=request_id
        ).status_code
        == 200
    )
    data = state(admin_client, patient)
    assert data["totals"]["allocated"] == 0 and data["totals"]["unallocated"] == 100
    assert data["history_count"] == 3
    with rls_org(org_a):
        assert list(Invoice.objects.order_by("id").values()) == original_invoices
        assert list(Payment.objects.values()) == original_payments
        assert list(Receipt.objects.values()) == original_receipts
    assert report(admin_client) == before
    assert admin_client.get(f"{BASE}{patient['id']}/billing/").data["matching"][
        "matches"
    ][0]["consistent"]


def test_refunds_and_invoice_drift_require_explicit_replacement(admin_client, org_a):
    patient, payment, receipt = pair(admin_client, org_a, "100")
    assert (
        allocate(
            admin_client, patient, receipt, [line(payment.invoice, "100.00")]
        ).status_code
        == 201
    )
    with rls_org(org_a):
        Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="refund",
            amount=Decimal("20"),
            payment=receipt,
            reference="new-refund",
        )
    data = state(admin_client, patient)
    assert (
        data["receipts"][0]["needs_review"] and data["receipts"][0]["allocated"] is None
    )
    assert data["totals"] == {
        "net_collected": 80,
        "allocated": 0,
        "unallocated": 0,
        "needs_review": 80,
    }
    assert (
        allocate(
            admin_client, patient, receipt, [line(payment.invoice, "80.01")], revision=1
        ).status_code
        == 400
    )
    assert (
        allocate(
            admin_client, patient, receipt, [line(payment.invoice, "80.00")], revision=1
        ).status_code
        == 201
    )
    assert state(admin_client, patient)["totals"]["allocated"] == 80
    with rls_org(org_a):
        Invoice.objects.filter(pk=payment.invoice_id).update(total_amount=Decimal("90"))
    assert state(admin_client, patient)["totals"]["needs_review"] == 80
    assert (
        allocate(
            admin_client, patient, receipt, [line(payment.invoice, "80.00")], revision=2
        ).status_code
        == 201
    )
    with rls_org(org_a):
        Invoice.objects.filter(pk=payment.invoice_id).update(status="Cancelled")
    assert state(admin_client, patient)["receipts"][0]["needs_review"]
    assert allocate(admin_client, patient, receipt, [], revision=3).status_code == 201
    assert state(admin_client, patient)["totals"]["unallocated"] == 80


def test_allocation_permissions_and_validation(
    admin_client, user_client, org_b_client, org_a, org_b
):
    patient, payment, receipt = pair(admin_client, org_a)
    foreign, other_payment, other_receipt = pair(org_b_client, org_b)
    lines = [line(payment.invoice, "10.00")]
    assert org_b_client.get(f"{BASE}{patient['id']}/allocations/").status_code == 404
    assert user_client.get(f"{BASE}{patient['id']}/allocations/").status_code == 403
    assert allocate(user_client, patient, receipt, lines).status_code == 403
    assert allocate(org_b_client, patient, receipt, lines).status_code == 404
    assert allocate(admin_client, patient, other_receipt, lines).status_code == 404
    assert (
        allocate(
            admin_client, patient, receipt, [line(other_payment.invoice, "10.00")]
        ).status_code
        == 404
    )
    other_patient = create(admin_client)
    assert allocate(admin_client, other_patient, receipt, []).status_code == 404
    for amount in ["0", "-1", "0.001", "NaN", "76"]:
        assert (
            allocate(
                admin_client, patient, receipt, [line(payment.invoice, amount)]
            ).status_code
            == 400
        )
    for fields in [
        {"reason": " "},
        {"org": str(org_b.id)},
        {"revision": -1},
        {"request_id": "bad"},
    ]:
        assert (
            allocate(admin_client, patient, receipt, lines, **fields).status_code == 400
        )
    assert allocate(admin_client, patient, receipt, lines * 2).status_code == 400
    assert allocate(admin_client, patient, receipt, lines * 21).status_code == 400
    assert (
        allocate(
            admin_client, patient, receipt, [{**lines[0], "org": str(org_b.id)}]
        ).status_code
        == 400
    )
    for overrides in [
        {"currency": "EUR"},
        {"currency": "USD", "status": "Draft"},
        {"status": "Pending"},
        {"status": "Cancelled"},
    ]:
        with rls_org(org_a):
            Invoice.objects.filter(pk=payment.invoice_id).update(**overrides)
        assert allocate(admin_client, patient, receipt, lines).status_code == 400
    assert state(org_b_client, foreign)["history_count"] == 0


@pytest.mark.skipif(connection.vendor != "postgresql", reason="PostgreSQL guards")
def test_allocation_database_guards_and_forced_rls(
    admin_client, org_b_client, org_a, org_b, admin_user
):
    patient, payment, receipt = pair(admin_client, org_a)
    foreign, foreign_payment, foreign_receipt = pair(org_b_client, org_b)
    with rls_org(org_a):

        def insert(**overrides):
            fields = dict(
                org=org_a,
                patient_id=patient["id"],
                receipt=receipt,
                revision=1,
                request_id=uuid4(),
                reason="Fictional direct audit",
                lines=[line(payment.invoice, "10.00")],
                snapshot={"forged": True},
                created_by=admin_user,
            )
            fields.update(overrides)
            return ReceiptAllocation.objects.create(**fields)

        for overrides in [
            {"patient_id": foreign["id"]},
            {"receipt": foreign_receipt},
            {"lines": [line(foreign_payment.invoice, "10.00")]},
            {"lines": [line(payment.invoice, "76.00")]},
            {"lines": [line(payment.invoice, "0.00")]},
            {"lines": [line(payment.invoice, "10.001")]},
            {"lines": [line(payment.invoice, "10.00")] * 2},
            {"lines": {}},
            {"lines": [{}]},
            {"revision": 2},
            {"created_by": None},
            {"reason": " \t"},
        ]:
            with pytest.raises(IntegrityError), transaction.atomic():
                insert(**overrides)
        first = insert()
        first.refresh_from_db()
        assert (
            first.snapshot["receipt"]["net"] == "75.25"
            and "forged" not in first.snapshot
        )
        assert (
            first.snapshot["invoices"][str(payment.invoice_id)]["number"]
            == payment.invoice.invoice_number
        )
        for action in [
            lambda: ReceiptAllocation.objects.filter(pk=first.id).update(
                reason="changed"
            ),
            lambda: ReceiptAllocation.objects.filter(pk=first.id).delete(),
            lambda: insert(),
            lambda: insert(revision=2, request_id=first.request_id),
        ]:
            with pytest.raises(IntegrityError), transaction.atomic():
                action()
        assert ReceiptAllocation.objects.count() == 1
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='mp_receipt_allocation'"
            )
            assert cursor.fetchone() == (True, True)
    with rls_org(org_b):
        assert not ReceiptAllocation.objects.filter(pk=first.id).exists()
        with pytest.raises(IntegrityError), transaction.atomic():
            ReceiptAllocation.objects.create(
                org=org_b,
                patient_id=foreign["id"],
                receipt=receipt,
                revision=1,
                request_id=uuid4(),
                reason="foreign",
                lines=[],
                created_by=admin_user,
            )


def test_allocation_totals_include_records_beyond_display_limit(admin_client, org_a):
    patient, payment, receipt = pair(admin_client, org_a, "1")
    for index in range(101):
        assert (
            allocate(
                admin_client,
                patient,
                receipt,
                [line(payment.invoice, "1.00")],
                revision=index,
            ).status_code
            == 201
        )
    data = state(admin_client, patient)
    assert data["history_count"] == 101 and len(data["history"]) == 100
    assert data["totals"]["allocated"] == 1
    assert data["receipts"][0]["revision"] == 101

    with rls_org(org_a):
        for index in range(100):
            Receipt.objects.create(
                org=org_a,
                patient_id=patient["id"],
                kind="payment",
                amount=Decimal("1"),
                reference=f"pagination-{index}",
            )
    data = state(admin_client, patient)
    assert data["receipt_count"] == 101 and len(data["receipts"]) == 100
    assert str(receipt.id) not in {row["id"] for row in data["receipts"]}
    assert data["totals"] == {
        "net_collected": 101,
        "allocated": 1,
        "unallocated": 100,
        "needs_review": 0,
    }


def test_optional_allocation_seed_is_rerunnable(admin_user):
    from io import StringIO

    from django.core.management import call_command

    from common.models import Org
    from patients.management.commands.seed_modern_practice import demo_id

    sink = StringIO()
    call_command("seed_modern_practice", member_email=admin_user.email, stdout=sink)
    call_command("seed_modern_practice_billing", stdout=sink)
    call_command("seed_modern_practice_allocations", stdout=sink)
    snapshots = {}
    for key in ("harbor", "cedar"):
        org = Org.objects.get(pk=demo_id(key))
        with rls_org(org):
            snapshots[key] = (
                list(Invoice.objects.order_by("id").values()),
                list(Payment.objects.order_by("id").values()),
                list(Receipt.objects.order_by("id").values()),
            )
            assert (
                Invoice.objects.get(
                    pk=demo_id(key + ":allocation:invoice")
                ).total_amount
                == 400
            )
            assert ReceiptAllocation.objects.count() == 0
    call_command("seed_modern_practice_allocations", stdout=sink)
    for key in ("harbor", "cedar"):
        with rls_org(Org.objects.get(pk=demo_id(key))):
            assert (
                list(Invoice.objects.order_by("id").values()),
                list(Payment.objects.order_by("id").values()),
                list(Receipt.objects.order_by("id").values()),
            ) == snapshots[key]
