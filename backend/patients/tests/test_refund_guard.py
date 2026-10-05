"""Database refund limits, including concurrent writers bypassing the API."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from django.db import (
    DatabaseError,
    IntegrityError,
    connection,
    connections,
    transaction,
)
from django.db.models import Sum

from common.testing import rls_org
from patients.models import Receipt
from patients.tests.test_journey import create

pytestmark = [
    pytest.mark.postgres_only,
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="Requires PostgreSQL triggers"
    ),
]


def cash(org, patient, **overrides):
    return Receipt.objects.create(
        org=org,
        patient_id=patient["id"],
        **{
            "kind": "payment",
            "amount": "100.00",
            "reference": str(uuid4()),
            **overrides,
        },
    )


def test_direct_refund_budget_insert_update_and_parent_reduction(admin_client, org_a):
    patient = create(admin_client)
    payment = cash(org_a, patient)
    original = Receipt.objects.values().get(id=payment.id)
    first = cash(org_a, patient, kind="refund", payment=payment, amount="60.00")
    with pytest.raises(IntegrityError, match="exceed"), transaction.atomic():
        cash(org_a, patient, kind="refund", payment=payment, amount="40.01")
    second = cash(org_a, patient, kind="refund", payment=payment, amount="40.00")
    with pytest.raises(IntegrityError, match="exceed"), transaction.atomic():
        Receipt.objects.filter(id=first.id).update(amount="60.01")
    with pytest.raises(IntegrityError, match="less"), transaction.atomic():
        Receipt.objects.filter(id=payment.id).update(amount="99.99")
    # Re-saving existing facts must not double-count the refund itself.
    second.save()
    payment.refresh_from_db()
    assert payment.amount == Decimal("100.00")
    assert Receipt.objects.values().get(id=payment.id) == original
    assert (
        Receipt.objects.filter(payment=payment).aggregate(total=Sum("amount"))["total"]
        == 100
    )


def test_refund_relink_and_parent_identity_cannot_bypass_budget(admin_client, org_a):
    patient = create(admin_client)
    other = create(admin_client)
    large = cash(org_a, patient)
    small = cash(org_a, patient, amount="10.00")
    refund = cash(org_a, patient, kind="refund", payment=large, amount="60.00")
    with pytest.raises(IntegrityError, match="exceed"), transaction.atomic():
        Receipt.objects.filter(id=refund.id).update(payment=small)
    with pytest.raises(IntegrityError, match="cannot change"), transaction.atomic():
        Receipt.objects.filter(id=large.id).update(patient_id=other["id"])
    refund.refresh_from_db()
    assert refund.payment_id == large.id


def test_guard_preserves_tenant_link_rejection(
    admin_client, org_b_client, org_a, org_b
):
    a = create(admin_client)
    b = create(org_b_client)
    with rls_org(org_a):
        payment = cash(org_a, a)
    with rls_org(org_b):
        with (
            pytest.raises(IntegrityError, match="same patient and practice"),
            transaction.atomic(),
        ):
            cash(org_b, b, kind="refund", payment=payment, amount="1.00")
        assert not Receipt.objects.filter(id=payment.id).exists()
    with rls_org(org_a):
        payment.refresh_from_db()
        assert payment.amount == 100
        assert not Receipt.objects.filter(payment=payment).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("isolation", ["READ COMMITTED", "REPEATABLE READ"])
def test_competing_refunds_cannot_overspend(admin_client, org_a, isolation):
    patient = create(admin_client)
    payment = cash(org_a, patient)
    start = Barrier(2)

    def attempt():
        try:
            with transaction.atomic():
                with connections["default"].cursor() as cursor:
                    cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
                    cursor.execute(
                        "SELECT set_config('app.current_org', %s, true)",
                        [str(org_a.id)],
                    )
                    cursor.execute("SET LOCAL lock_timeout = '5s'")
                # Establish both snapshots before either refund is written.
                assert Receipt.objects.get(id=payment.id).amount == 100
                start.wait(timeout=10)
                cash(org_a, patient, kind="refund", payment=payment, amount="60.00")
            return "accepted"
        except DatabaseError as exc:
            return exc.__cause__.sqlstate
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        results = [f.result(timeout=20) for f in futures]
    assert results.count("accepted") == 1, results
    assert next(result for result in results if result != "accepted") in {
        "23514",
        "40001",
    }
    with rls_org(org_a):
        assert (
            Receipt.objects.filter(payment=payment).aggregate(total=Sum("amount"))[
                "total"
            ]
            == 60
        )
        payment.refresh_from_db()
        assert payment.amount == 100
