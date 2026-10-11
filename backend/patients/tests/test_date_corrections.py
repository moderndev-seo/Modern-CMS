from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction

from common.testing import rls_org
from patients.models import Receipt, ReceiptCorrection
from patients.tests.test_corrections import cash, correct
from patients.tests.test_journey import BASE, DATE, create, record, report
from patients.tests.test_matching import match, pair

pytestmark = [
    pytest.mark.postgres_only,
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="Audit triggers required"
    ),
]


def redate(client, patient, receipt, date="2026-08-31T23:59:59Z", **overrides):
    return client.post(
        f"{BASE}{patient['id']}/corrections/",
        {
            "receipt": str(receipt.id),
            "occurred_at": date,
            "revision": 0,
            "request_id": str(uuid4()),
            "reason": "Fictional receipt date typo",
            **overrides,
        },
        format="json",
    )


def test_date_restates_period_preserves_attribution_and_retry(admin_client, org_a):
    patient, receipt = cash(admin_client, org_a)
    original = Receipt.objects.values().get(id=receipt.id)
    before = report(admin_client)
    request_id = str(uuid4())
    response = redate(admin_client, patient, receipt, request_id=request_id)
    assert response.status_code == 201, response.data
    assert report(admin_client)["totals"]["net_revenue"] == 0
    august = report(admin_client, "2026-08-01", "2026-08-31")
    assert august["totals"]["net_revenue"] == 100
    after = Receipt.objects.values().get(id=receipt.id)
    for key in original.keys() - {"occurred_at", "updated_at", "updated_by_id"}:
        assert original[key] == after[key]
    assert redate(admin_client, patient, receipt, DATE, revision=1).status_code == 201
    assert report(admin_client) == before
    assert (
        redate(admin_client, patient, receipt, request_id=request_id).status_code == 200
    )
    receipt.refresh_from_db()
    assert receipt.occurred_at == original["occurred_at"]
    history = admin_client.get(f"{BASE}{patient['id']}/corrections/").data["history"]
    assert len(history) == 2 and all(e["field"] == "occurred_at" for e in history)
    assert history[0]["before_date"] != history[0]["after_date"]
    assert redate(admin_client, patient, receipt).status_code == 409
    assert redate(admin_client, patient, receipt, DATE, revision=2).status_code == 409
    for values in (
        {"amount": "99"},
        {"reference": "combined"},
        {"reason": " "},
        {"date": "2999-01-01T00:00:00Z"},
    ):
        assert (
            redate(admin_client, patient, receipt, revision=2, **values).status_code
            == 400
        )


def test_refund_ordering_and_direct_date_bypass(admin_client, org_a):
    patient, receipt = cash(admin_client, org_a)
    refund_result = record(
        admin_client,
        patient,
        "receipts",
        kind="refund",
        payment=str(receipt.id),
        amount="10",
        reference="TEST-date-refund",
        occurred_at="2026-09-03T12:00:00Z",
    )
    assert refund_result.status_code == 201, refund_result.data
    refund = Receipt.objects.get(id=refund_result.data["id"])
    assert (
        redate(admin_client, patient, receipt, "2026-09-04T12:00:00Z").status_code
        == 409
    )
    assert (
        redate(admin_client, patient, refund, "2026-08-31T12:00:00Z").status_code == 409
    )
    assert ReceiptCorrection.objects.count() == 0
    assert (
        redate(admin_client, patient, refund, "2026-10-01T00:00:00Z").status_code == 201
    )
    assert report(admin_client)["totals"]["net_revenue"] == 100
    assert (
        report(admin_client, "2026-10-01", "2026-10-31")["totals"]["net_revenue"] == -10
    )
    with rls_org(org_a):
        for operation in (
            lambda: Receipt.objects.filter(id=receipt.id).update(
                occurred_at="2026-08-30T00:00:00Z"
            ),
            lambda: Receipt.objects.create(
                org=org_a,
                patient_id=patient["id"],
                kind="refund",
                payment=receipt,
                amount=1,
                reference="TEST-too-early",
                occurred_at="2026-08-01T00:00:00Z",
            ),
            lambda: ReceiptCorrection.objects.create(
                org=org_a,
                patient_id=patient["id"],
                receipt=receipt,
                amount=100,
                occurred_at="2999-01-01T00:00:00Z",
                revision=1,
                request_id=uuid4(),
                reason="Future",
                created_by=receipt.created_by,
            ),
        ):
            with pytest.raises(IntegrityError), transaction.atomic():
                operation()


def test_date_permissions_foreign_links_and_match_block(
    admin_client, user_client, org_b_client, org_a, org_b, unauthenticated_client
):
    patient, receipt = cash(admin_client, org_a)
    foreign, other = cash(org_b_client, org_b)
    assert redate(user_client, patient, receipt).status_code in (403, 404)
    assert redate(unauthenticated_client, patient, receipt).status_code in (401, 403)
    assert redate(org_b_client, patient, receipt).status_code == 404
    assert redate(admin_client, patient, other).status_code == 404
    assert redate(admin_client, create(admin_client), receipt).status_code == 404
    with rls_org(org_b):
        with pytest.raises(IntegrityError), transaction.atomic():
            ReceiptCorrection.objects.create(
                org=org_b,
                patient_id=foreign["id"],
                receipt=receipt,
                amount=100,
                occurred_at=DATE,
                revision=1,
                request_id=uuid4(),
                reason="Foreign",
                created_by=other.created_by,
            )
    matched_patient, payment, matched = pair(admin_client, org_a, "100.00")
    assert match(admin_client, matched_patient, payment, matched).status_code == 201
    assert redate(admin_client, matched_patient, matched).status_code == 409
    assert correct(admin_client, patient, receipt).status_code == 201
    assert redate(admin_client, patient, receipt, revision=1).status_code == 201


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("isolation", ["READ COMMITTED", "REPEATABLE READ"])
def test_competing_date_correction_and_refund_keep_chronology(
    admin_client, org_a, admin_user, isolation
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import DatabaseError, connections

    patient, receipt = cash(admin_client, org_a)
    barrier = Barrier(2)

    def attempt(correction):
        try:
            with transaction.atomic():
                with connections["default"].cursor() as cursor:
                    cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
                    cursor.execute(
                        "SELECT set_config('app.current_org', %s, true)",
                        [str(org_a.id)],
                    )
                    cursor.execute("SET LOCAL lock_timeout='5s'")
                Receipt.objects.get(id=receipt.id)
                barrier.wait(timeout=10)
                if correction:
                    ReceiptCorrection.objects.create(
                        org_id=org_a.id,
                        patient_id=patient["id"],
                        receipt_id=receipt.id,
                        amount=100,
                        occurred_at="2026-09-04T00:00:00Z",
                        revision=1,
                        request_id=uuid4(),
                        reason="Fictional concurrent date correction",
                        created_by_id=admin_user.id,
                    )
                else:
                    Receipt.objects.create(
                        org_id=org_a.id,
                        patient_id=patient["id"],
                        payment_id=receipt.id,
                        kind="refund",
                        amount=10,
                        reference="TEST-concurrent-dated-refund",
                        occurred_at="2026-09-03T00:00:00Z",
                    )
            return "accepted"
        except DatabaseError as exc:
            return exc.__cause__.sqlstate
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, value) for value in (True, False)]
        results = [f.result(timeout=20) for f in futures]
    assert results.count("accepted") == 1, results
    assert next(r for r in results if r != "accepted") in ("23514", "40001")
    with rls_org(org_a):
        receipt.refresh_from_db()
        assert not Receipt.objects.filter(
            payment=receipt, occurred_at__lt=receipt.occurred_at
        ).exists()
