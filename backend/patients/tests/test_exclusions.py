from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction

from common.testing import rls_org
from patients.models import Receipt, ReceiptExclusion
from patients.tests.test_allocations import allocate, line
from patients.tests.test_corrections import cash, correct
from patients.tests.test_journey import BASE, DATE, create, record, report
from patients.tests.test_matching import match, pair

pytestmark = [
    pytest.mark.postgres_only,
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="Requires audit triggers"
    ),
]


def duplicate(org, receipt):
    with rls_org(org):
        return Receipt.objects.create(
            org=org,
            patient_id=receipt.patient_id,
            kind="payment",
            amount=receipt.amount,
            occurred_at=receipt.occurred_at,
            reference=str(uuid4()),
        )


def decide(client, patient, receipt, retained=None, **overrides):
    return client.post(
        f"{BASE}{patient['id']}/exclusions/",
        {
            "receipt": str(receipt.id),
            "retained": str(retained.id) if retained else None,
            "excluded": retained is not None,
            "revision": 0,
            "request_id": str(uuid4()),
            "reason": "Fictional duplicate entry verified",
            **overrides,
        },
        format="json",
    )


def test_exclusion_restoration_all_reports_and_original_facts(admin_client, org_a):
    patient, kept = cash(admin_client, org_a, original_source="unknown")
    repeated = duplicate(org_a, kept)
    original = Receipt.objects.values().get(id=repeated.id)
    assert report(admin_client)["totals"]["net_revenue"] == 200
    result = decide(admin_client, patient, repeated, kept)
    assert result.status_code == 201, result.data
    data = report(admin_client)
    assert data["totals"]["net_revenue"] == 100 and data["totals"]["roas"] is None
    assert (
        next(r for r in data["sources"] if r["source"] == "unknown")["net_revenue"]
        == 100
    )
    assert (
        report(admin_client, "2026-09-03", "2026-09-30")["totals"]["net_revenue"] == 0
    )
    detail = admin_client.get(f"{BASE}{patient['id']}/").data
    assert detail["net_revenue"] == 100 and len(detail["receipts"]) == 2
    assert len(detail["exclusions"]) == 1 and detail["original_source"] == "unknown"
    billing = admin_client.get(f"{BASE}{patient['id']}/billing/").data
    assert billing["net_collected"] == 100
    assert billing["receipt_coverage"]["unmatched"]["net_collected"] == 100
    allocations = admin_client.get(f"{BASE}{patient['id']}/allocations/").data
    assert allocations["totals"]["net_collected"] == 100
    current = Receipt.objects.values().get(id=repeated.id)
    for key in original.keys() - {"excluded", "updated_at", "updated_by_id"}:
        assert original[key] == current[key]
    assert decide(admin_client, patient, repeated, revision=1).status_code == 201
    assert report(admin_client)["totals"]["net_revenue"] == 200
    assert ReceiptExclusion.objects.count() == 2 and Receipt.objects.count() == 2


def test_retry_stale_and_invalid_decisions(admin_client, org_a):
    patient, kept = cash(admin_client, org_a)
    repeated = duplicate(org_a, kept)
    request_id = str(uuid4())
    assert (
        decide(admin_client, patient, repeated, kept, request_id=request_id).status_code
        == 201
    )
    assert (
        decide(admin_client, patient, repeated, kept, request_id=request_id).status_code
        == 200
    )
    assert (
        decide(
            admin_client,
            patient,
            repeated,
            kept,
            request_id=request_id,
            reason="Changed",
        ).status_code
        == 409
    )
    assert decide(admin_client, patient, repeated).status_code == 409
    assert decide(admin_client, patient, repeated, revision=1).status_code == 201
    # Late retry cannot exclude it again after restoration.
    assert (
        decide(admin_client, patient, repeated, kept, request_id=request_id).status_code
        == 200
    )
    repeated.refresh_from_db()
    assert not repeated.excluded
    for changes in (
        {"reason": " "},
        {"revision": -1},
        {"snapshot": {}},
        {"org": str(org_a.id)},
        {"excluded": False},
    ):
        assert (
            decide(
                admin_client, patient, repeated, kept, **{"revision": 2, **changes}
            ).status_code
            == 400
        )
    assert decide(admin_client, patient, kept, kept).status_code == 409
    assert correct(admin_client, patient, repeated, amount="90.00").status_code == 201
    assert decide(admin_client, patient, repeated, kept, revision=2).status_code == 409


def test_refunds_reconciliation_and_excluded_writes_blocked(admin_client, org_a):
    patient, payment, kept = pair(admin_client, org_a, amount="100.00")
    repeated = duplicate(org_a, kept)
    assert match(admin_client, patient, payment, repeated).status_code == 201
    assert decide(admin_client, patient, repeated, kept).status_code == 409
    # Separate unmatched receipt with an allocation also cannot be excluded.
    extra = duplicate(org_a, kept)
    assert (
        allocate(
            admin_client, patient, extra, [line(payment.invoice, "50.00")]
        ).status_code
        == 201
    )
    assert decide(admin_client, patient, extra, kept).status_code == 409
    assert allocate(admin_client, patient, extra, [], revision=1).status_code == 201
    assert decide(admin_client, patient, extra, kept).status_code == 201
    assert match(admin_client, patient, payment, extra).status_code in (400, 409)
    assert allocate(admin_client, patient, extra, [], revision=2).status_code == 409
    assert correct(admin_client, patient, extra).status_code == 409
    response = record(
        admin_client,
        patient,
        "receipts",
        kind="refund",
        payment=str(extra.id),
        amount="1.00",
        reference=str(uuid4()),
        occurred_at=DATE,
    )
    assert response.status_code == 404
    # Restore before accepting refunds, then prevent exclusion of a refunded payment.
    assert decide(admin_client, patient, extra, revision=1).status_code == 201
    with rls_org(org_a):
        Receipt.objects.create(
            org=org_a,
            patient_id=patient["id"],
            kind="refund",
            payment=extra,
            amount=Decimal("1"),
            reference=str(uuid4()),
        )
    assert decide(admin_client, patient, extra, kept, revision=2).status_code == 409


def test_permissions_foreign_and_wrong_patient_links(
    admin_client, user_client, org_b_client, org_a, org_b, unauthenticated_client
):
    patient, kept = cash(admin_client, org_a)
    repeated = duplicate(org_a, kept)
    other, foreign = cash(org_b_client, org_b)
    own_member = create(user_client)
    url = f"{BASE}{patient['id']}/exclusions/"
    assert org_b_client.get(url).status_code == 404
    assert org_b_client.post(url, {}, format="json").status_code == 404
    assert unauthenticated_client.get(url).status_code in (401, 403)
    assert user_client.get(f"{BASE}{own_member['id']}/exclusions/").status_code == 403
    assert decide(user_client, own_member, repeated, kept).status_code == 403
    assert decide(admin_client, patient, repeated, foreign).status_code == 404
    assert decide(admin_client, patient, foreign, kept).status_code == 404
    wrong, wrong_cash = cash(admin_client, org_a, email="other-test@example.invalid")
    assert decide(admin_client, patient, repeated, wrong_cash).status_code == 404
    result = admin_client.get(url, {"org": str(org_b.id), "patient": other["id"]})
    assert result.status_code == 200 and result.data["receipt_count"] == 2
    assert admin_client.patch(url, {}, format="json").status_code == 405
    assert admin_client.delete(url).status_code == 405


def test_database_guards_snapshots_and_retained_dependency(admin_client, org_a, org_b):
    patient, kept = cash(admin_client, org_a)
    repeated = duplicate(org_a, kept)
    actor = kept.created_by
    values = dict(
        org=org_a,
        patient_id=patient["id"],
        receipt=repeated,
        retained=kept,
        excluded=True,
        revision=1,
        request_id=uuid4(),
        reason="Fictional duplicate",
        created_by=actor,
        snapshot={"forged": True},
    )
    with rls_org(org_a):
        with pytest.raises(IntegrityError), transaction.atomic():
            Receipt.objects.filter(id=repeated.id).update(excluded=True)
        entry = ReceiptExclusion.objects.create(**values)
        entry.refresh_from_db()
        assert "forged" not in entry.snapshot
        assert str(entry.snapshot["receipt"]["id"]) == str(repeated.id)
        for action in (
            lambda: ReceiptExclusion.objects.filter(id=entry.id).update(
                reason="rewrite"
            ),
            lambda: ReceiptExclusion.objects.filter(id=entry.id).delete(),
            lambda: Receipt.objects.filter(id=repeated.id).update(excluded=False),
            lambda: Receipt.objects.create(
                org=org_a,
                patient_id=patient["id"],
                payment=repeated,
                kind="refund",
                amount=1,
                reference=str(uuid4()),
            ),
        ):
            with pytest.raises(IntegrityError), transaction.atomic():
                action()
        third = duplicate(org_a, kept)
        assert decide(admin_client, patient, kept, third).status_code == 409
        assert decide(admin_client, patient, third, repeated).status_code == 409
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='mp_receipt_exclusion'"
            )
            assert cursor.fetchone() == (True, True)
    with rls_org(org_b):
        assert not ReceiptExclusion.objects.filter(id=entry.id).exists()
        with pytest.raises(IntegrityError), transaction.atomic():
            ReceiptExclusion.objects.create(
                **{**values, "org": org_b, "request_id": uuid4()}
            )


def test_direct_database_cannot_reuse_excluded_cash(admin_client, org_a):
    from patients.models import PaymentMatch, ReceiptAllocation, ReceiptCorrection

    patient, payment, kept = pair(admin_client, org_a, amount="100.00")
    repeated = duplicate(org_a, kept)
    assert decide(admin_client, patient, repeated, kept).status_code == 201
    with rls_org(org_a):
        common = dict(
            org=org_a,
            receipt=repeated,
            created_by=kept.created_by,
            reason="Fictional bypass attempt",
        )
        for model, values in (
            (PaymentMatch, dict(invoice_payment=payment)),
            (
                ReceiptAllocation,
                dict(
                    patient_id=patient["id"],
                    revision=1,
                    request_id=uuid4(),
                    lines=[],
                    refund_lines=[],
                ),
            ),
            (
                ReceiptCorrection,
                dict(
                    patient_id=patient["id"],
                    revision=1,
                    request_id=uuid4(),
                    amount=Decimal("90"),
                ),
            ),
        ):
            with (
                pytest.raises(IntegrityError, match="Restore excluded cash"),
                transaction.atomic(),
            ):
                model.objects.create(**common, **values)
        assert not PaymentMatch.objects.exists()
        assert not ReceiptAllocation.objects.exists()
        assert not ReceiptCorrection.objects.exists()
        repeated.refresh_from_db()
        assert repeated.amount == 100 and repeated.excluded


def test_latest_100_display_limit_never_limits_excluded_totals(admin_client, org_a):
    patient, kept = cash(admin_client, org_a)
    repeated = duplicate(org_a, kept)
    assert decide(admin_client, patient, repeated, kept).status_code == 201
    with rls_org(org_a):
        for _ in range(101):
            Receipt.objects.create(
                org=org_a,
                patient_id=patient["id"],
                kind="payment",
                amount=1,
                occurred_at="2026-09-03T12:00:00Z",
                reference=str(uuid4()),
            )
    data = admin_client.get(f"{BASE}{patient['id']}/exclusions/").data
    assert data["receipt_count"] == 103 and len(data["receipts"]) == 100
    assert report(admin_client)["totals"]["net_revenue"] == 201
    assert (
        admin_client.get(f"{BASE}{patient['id']}/billing/").data["net_collected"] == 201
    )
    assert (
        admin_client.get(f"{BASE}{patient['id']}/allocations/").data["totals"][
            "net_collected"
        ]
        == 201
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("isolation", ["READ COMMITTED", "REPEATABLE READ"])
def test_competing_exclusions_cannot_remove_both_copies(
    admin_client, org_a, admin_user, isolation
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import DatabaseError, connections

    patient, kept = cash(admin_client, org_a)
    repeated = duplicate(org_a, kept)
    start = Barrier(2)

    def attempt(receipt_id, retained_id):
        try:
            with transaction.atomic():
                with connections["default"].cursor() as cursor:
                    cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
                    cursor.execute(
                        "SELECT set_config('app.current_org', %s, true)",
                        [str(org_a.id)],
                    )
                    cursor.execute("SET LOCAL lock_timeout = '5s'")
                    # Establish both snapshots before either writer proceeds.
                    cursor.execute("SELECT count(*) FROM mp_receipt")
                start.wait(timeout=10)
                ReceiptExclusion.objects.create(
                    org_id=org_a.id,
                    patient_id=patient["id"],
                    receipt_id=receipt_id,
                    retained_id=retained_id,
                    excluded=True,
                    revision=1,
                    request_id=uuid4(),
                    reason="Fictional competing duplicate decisions",
                    created_by_id=admin_user.id,
                )
            return "accepted"
        except DatabaseError as exc:
            return exc.__cause__.sqlstate
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(attempt, a.id, b.id)
            for a, b in ((kept, repeated), (repeated, kept))
        ]
        results = [future.result(timeout=20) for future in futures]
    assert results.count("accepted") == 1
    assert next(value for value in results if value != "accepted") in ("23514", "40001")
    with rls_org(org_a):
        assert Receipt.objects.filter(excluded=True).count() == 1
        assert ReceiptExclusion.objects.count() == 1
