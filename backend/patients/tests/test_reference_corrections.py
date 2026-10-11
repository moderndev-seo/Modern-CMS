from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction

from common.testing import rls_org
from patients.models import Receipt, ReceiptCorrection, ReceiptReference
from patients.tests.test_allocations import allocate, line
from patients.tests.test_corrections import cash, correct
from patients.tests.test_exclusions import decide, duplicate
from patients.tests.test_journey import BASE, DATE, create, record, report
from patients.tests.test_matching import match, pair

pytestmark = [
    pytest.mark.postgres_only,
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="Requires audit triggers"
    ),
]


def rename(client, patient, receipt, reference="TEST-corrected-reference", **overrides):
    return client.post(
        f"{BASE}{patient['id']}/corrections/",
        {
            "receipt": str(receipt.id),
            "reference": reference,
            "revision": 0,
            "request_id": str(uuid4()),
            "reason": "Fictional reference typo",
            **overrides,
        },
        format="json",
    )


def test_reference_restore_preserves_cash_and_reserves_all_prior_keys(
    admin_client, org_a
):
    patient, receipt = cash(admin_client, org_a)
    original = Receipt.objects.values().get(id=receipt.id)
    before = report(admin_client)
    result = rename(admin_client, patient, receipt)
    assert result.status_code == 201, result.data
    receipt.refresh_from_db()
    assert receipt.reference == "TEST-corrected-reference"
    after = Receipt.objects.values().get(id=receipt.id)
    for key in original.keys() - {"reference", "updated_at", "updated_by_id"}:
        assert after[key] == original[key]
    assert report(admin_client) == before
    history = admin_client.get(f"{BASE}{patient['id']}/").data["corrections"]
    assert history[0]["field"] == "reference"
    assert history[0]["before_reference"] == original["reference"]
    assert history[0]["after_reference"] == receipt.reference
    assert (
        rename(
            admin_client, patient, receipt, original["reference"], revision=1
        ).status_code
        == 201
    )
    assert report(admin_client) == before
    for key in (original["reference"], "TEST-corrected-reference"):
        response = record(
            admin_client,
            patient,
            "receipts",
            kind="payment",
            amount="100.00",
            reference=key,
            occurred_at=DATE,
        )
        assert response.status_code == 400
    assert Receipt.objects.count() == 1 and ReceiptCorrection.objects.count() == 2
    assert ReceiptReference.objects.filter(receipt=receipt).count() == 2


def test_retry_revision_and_one_field_validation(admin_client, org_a):
    patient, receipt = cash(admin_client, org_a)
    request_id = str(uuid4())
    assert (
        rename(admin_client, patient, receipt, request_id=request_id).status_code == 201
    )
    assert (
        rename(admin_client, patient, receipt, request_id=request_id).status_code == 200
    )
    assert (
        rename(
            admin_client, patient, receipt, "TEST-changed", request_id=request_id
        ).status_code
        == 409
    )
    assert rename(admin_client, patient, receipt, "TEST-changed").status_code == 409
    assert rename(admin_client, patient, receipt, revision=1).status_code == 409
    assert (
        correct(admin_client, patient, receipt, amount="80.00", revision=1).status_code
        == 201
    )
    # Retry of a reference change must not overwrite the later amount correction.
    assert (
        rename(admin_client, patient, receipt, request_id=request_id).status_code == 200
    )
    receipt.refresh_from_db()
    assert receipt.amount == 80 and receipt.reference == "TEST-corrected-reference"
    for change in (
        {"reference": " "},
        {"reference": "X" * 101},
        {"reference": None},
        {"amount": "90.00"},
        {"reason": " "},
        {"snapshot": {}},
        {"occurred_at": DATE},
    ):
        assert rename(admin_client, patient, receipt, **change).status_code == 400
    empty = admin_client.post(
        f"{BASE}{patient['id']}/corrections/",
        {
            "receipt": str(receipt.id),
            "revision": 2,
            "request_id": str(uuid4()),
            "reason": "Missing change",
        },
        format="json",
    )
    assert empty.status_code == 400


def test_reference_collisions_and_direct_database_guards(admin_client, org_a, org_b):
    patient, receipt = cash(admin_client, org_a)
    other = duplicate(org_a, receipt)
    assert rename(admin_client, patient, receipt, other.reference).status_code == 409
    assert ReceiptCorrection.objects.count() == 0
    with rls_org(org_a):
        for operation in (
            lambda: Receipt.objects.filter(id=receipt.id).update(reference="bypass"),
            lambda: ReceiptReference.objects.filter(receipt=receipt).update(
                reference="bypass"
            ),
            lambda: ReceiptReference.objects.filter(receipt=receipt).delete(),
            lambda: ReceiptReference.objects.create(
                org=org_a, receipt=receipt, reference="forged"
            ),
            lambda: ReceiptCorrection.objects.create(
                org=org_a,
                receipt=receipt,
                patient_id=patient["id"],
                revision=1,
                request_id=uuid4(),
                reference="combo",
                amount=90,
                reason="Combined edit",
                created_by=receipt.created_by,
            ),
        ):
            with pytest.raises(IntegrityError), transaction.atomic():
                operation()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='mp_cash_reference_reservation'"
            )
            assert cursor.fetchone() == (True, True)
    assert rename(admin_client, patient, receipt).status_code == 201
    old_reference = receipt.reference
    with rls_org(org_a):
        with pytest.raises(IntegrityError), transaction.atomic():
            Receipt.objects.create(
                org=org_a,
                patient_id=patient["id"],
                kind="payment",
                amount=1,
                reference=old_reference,
            )
    with rls_org(org_b):
        assert not ReceiptReference.objects.filter(receipt=receipt).exists()


def test_refund_reference_and_reconciliation_prerequisites(admin_client, org_a):
    patient, invoice_payment, payment = pair(admin_client, org_a, "100.00")
    with rls_org(org_a):
        refund = Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="refund",
            payment=payment,
            amount=10,
            reference="TEST-refund",
        )
    assert rename(admin_client, patient, refund, "TEST-refund-fixed").status_code == 201
    assert match(admin_client, patient, invoice_payment, payment).status_code == 201
    assert rename(admin_client, patient, payment).status_code == 409
    assert (
        rename(
            admin_client, patient, refund, "TEST-refund-fixed-again", revision=1
        ).status_code
        == 409
    )
    second = duplicate(org_a, payment)
    assert (
        allocate(
            admin_client, patient, second, [line(invoice_payment.invoice, "20.00")]
        ).status_code
        == 201
    )
    assert rename(admin_client, patient, second).status_code == 409
    assert allocate(admin_client, patient, second, [], revision=1).status_code == 201
    assert decide(admin_client, patient, second, payment).status_code == 201
    assert rename(admin_client, patient, second).status_code == 409
    assert decide(admin_client, patient, second, revision=1).status_code == 201
    assert rename(admin_client, patient, second).status_code == 201


def test_reference_admin_tenant_permissions_and_org_scoped_keys(
    admin_client, user_client, org_b_client, org_a, org_b, unauthenticated_client
):
    patient, receipt = cash(admin_client, org_a)
    foreign, other = cash(org_b_client, org_b)
    member_patient = create(user_client)
    assert rename(user_client, member_patient, receipt).status_code == 403
    assert rename(unauthenticated_client, patient, receipt).status_code in (401, 403)
    assert rename(org_b_client, patient, receipt).status_code == 404
    assert rename(admin_client, patient, other).status_code == 404
    wrong = create(admin_client, email="reference-other@example.invalid")
    assert rename(admin_client, wrong, receipt).status_code == 404
    assert rename(admin_client, patient, receipt).status_code == 201
    # Independent practices may use the same visible reference.
    assert rename(org_b_client, foreign, other).status_code == 201
    with rls_org(org_b):
        with pytest.raises(IntegrityError), transaction.atomic():
            ReceiptCorrection.objects.create(
                org=org_b,
                patient_id=foreign["id"],
                receipt=receipt,
                reference="foreign-link",
                amount=100,
                revision=2,
                request_id=uuid4(),
                reason="Foreign reference",
                created_by=other.created_by,
            )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("isolation", ["READ COMMITTED", "REPEATABLE READ"])
def test_competing_reference_claims_cannot_duplicate_keys(
    admin_client, org_a, admin_user, isolation
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import DatabaseError, connections

    patient, receipt = cash(admin_client, org_a)
    other = duplicate(org_a, receipt)
    start = Barrier(2)

    def attempt(cash_id):
        try:
            with transaction.atomic():
                with connections["default"].cursor() as cursor:
                    cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
                    cursor.execute(
                        "SELECT set_config('app.current_org', %s, true)",
                        [str(org_a.id)],
                    )
                    cursor.execute("SET LOCAL lock_timeout='5s'")
                    cursor.execute("SELECT count(*) FROM mp_receipt")
                start.wait(timeout=10)
                ReceiptCorrection.objects.create(
                    org_id=org_a.id,
                    patient_id=patient["id"],
                    receipt_id=cash_id,
                    reference="TEST-shared-reference",
                    amount=100,
                    revision=1,
                    request_id=uuid4(),
                    reason="Fictional simultaneous reference claim",
                    created_by_id=admin_user.id,
                )
            return "accepted"
        except DatabaseError as exc:
            return exc.__cause__.sqlstate
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result(timeout=20)
            for f in [pool.submit(attempt, receipt.id), pool.submit(attempt, other.id)]
        ]
    assert results.count("accepted") == 1
    assert next(r for r in results if r != "accepted") in ("23514", "40001", "23505")
    with rls_org(org_a):
        assert Receipt.objects.filter(reference="TEST-shared-reference").count() == 1
        assert ReceiptCorrection.objects.count() == 1
