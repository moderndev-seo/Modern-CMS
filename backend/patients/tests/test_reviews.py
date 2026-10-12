from uuid import uuid4

import pytest
from django.db import IntegrityError, ProgrammingError, connection, transaction

from common.testing import rls_org
from patients.models import PracticeReview, ReviewChange
from patients.tests.test_journey import BASE, DATE, create, report

URL = BASE + "reviews/"
PERIOD = "?start=2026-09-01&end=2026-09-30"


def record(client, patient=None, **overrides):
    patient = patient or create(client)
    return client.post(
        URL,
        {
            "patient": patient["id"],
            "source": "google",
            "rating": 5,
            "body": "Fictional feedback",
            "reviewed_at": DATE,
            "request_id": str(uuid4()),
            **overrides,
        },
        format="json",
    )


def change(client, identifier, revision=0, action="draft", **overrides):
    fields = (
        {"draft": "Fictional local reply"}
        if action == "draft"
        else {"status": "handled", "reason": "Fictional local follow-up complete"}
    )
    return client.patch(
        f"{URL}{identifier}/",
        {
            "action": action,
            "revision": revision,
            "request_id": str(uuid4()),
            **fields,
            **overrides,
        },
        format="json",
    )


def test_rating_summary_unknown_unrated_and_utc_window(admin_client):
    assert admin_client.get(URL + PERIOD).data["summary"]["average"] is None
    patient = create(admin_client)
    before = report(admin_client)
    for fields in [
        dict(rating=5, reviewed_at="2026-09-01T00:00:00Z"),
        dict(rating=1, reviewed_at="2026-09-30T23:59:59Z"),
        dict(rating=None, source="unknown"),
        dict(rating=3, reviewed_at="2026-10-01T00:00:00Z"),
    ]:
        result = record(admin_client, patient, **fields)
        assert result.status_code == 201, result.data
    data = admin_client.get(URL + PERIOD).data["summary"]
    assert (
        data["count"] == 3 and data["rated_count"] == 2 and data["unrated_count"] == 1
    )
    assert data["average"] == 3 and data["needs_attention"] == 3
    assert sum(r["count"] for r in data["histogram"]) == 2
    sources = {r["source"]: r for r in data["sources"]}
    assert sources["google"]["average"] == 3 and sources["google"]["count"] == 2
    assert sources["unknown"]["average"] is None and sources["unknown"]["count"] == 1
    assert sources["yelp"]["count"] == 0 and sources["yelp"]["average"] is None
    filtered = admin_client.get(URL + PERIOD + "&source=unknown&search=feedback").data
    assert len(filtered["reviews"]) == 1 and filtered["summary"] == data
    assert report(admin_client) == before


def test_draft_status_archive_restore_audit_and_retry(admin_client):
    patient = create(admin_client)
    before = report(admin_client)
    key = str(uuid4())
    first = record(admin_client, patient, request_id=key)
    assert first.status_code == 201, first.data
    identifier = first.data["id"]
    assert record(admin_client, patient, request_id=key).status_code == 200
    assert record(admin_client, patient, request_id=key, rating=4).status_code == 409
    draft_key = str(uuid4())
    for expected in (201, 200):
        result = change(admin_client, identifier, request_id=draft_key)
        assert result.status_code == expected, result.data
    assert change(admin_client, identifier).status_code == 409
    assert change(admin_client, identifier, 1, action="status").status_code == 201
    assert admin_client.get(URL + PERIOD).data["summary"]["needs_attention"] == 0
    assert (
        change(
            admin_client,
            identifier,
            2,
            action="status",
            status="archived",
            reason="Duplicate fictional record",
        ).status_code
        == 201
    )
    summary = admin_client.get(URL + PERIOD).data["summary"]
    assert summary["count"] == 0 and summary["average"] is None
    assert change(admin_client, identifier, 3).status_code == 409
    assert len(admin_client.get(URL + PERIOD + "&status=archived").data["reviews"]) == 1
    assert (
        change(
            admin_client,
            identifier,
            3,
            action="status",
            status="open",
            reason="Restore fictional record",
        ).status_code
        == 201
    )
    assert change(admin_client, identifier, 4, draft="").status_code == 201
    detail = admin_client.get(f"{URL}{identifier}/").data
    assert detail["review"]["draft"] == "" and detail["review"]["revision"] == 5
    assert [h["revision"] for h in detail["history"]] == [5, 4, 3, 2, 1]
    assert detail["history"][2]["before"]["status"] == "handled"
    assert detail["history"][2]["after"]["status"] == "archived"
    assert admin_client.get(URL + PERIOD).data["summary"]["average"] == 5
    assert report(admin_client) == before


def test_patient_permissions_tenant_api_and_strict_input(
    admin_client, user_client, org_b_client, unauthenticated_client
):
    patient = create(admin_client)
    identifier = record(admin_client, patient).data["id"]
    for client in (user_client, org_b_client):
        assert client.get(f"{URL}{identifier}/").status_code == 404
        assert change(client, identifier).status_code == 404
        assert client.get(URL + PERIOD).data["summary"]["count"] == 0
        assert client.get(URL + PERIOD + f"&patient={patient['id']}").status_code == 404
    assert record(user_client, patient).status_code == 403
    assert record(org_b_client, patient).status_code == 404
    assert unauthenticated_client.get(URL).status_code in (401, 403)
    assert admin_client.delete(f"{URL}{identifier}/").status_code == 405
    for fields in (
        {"rating": 0},
        {"rating": 6},
        {"rating": None, "body": " "},
        {"source": "invented"},
        {"reviewed_at": "2099-01-01T00:00:00Z"},
        {"org": str(uuid4())},
        {"status": "handled"},
    ):
        assert record(admin_client, patient, **fields).status_code == 400
    assert change(admin_client, identifier, status="handled").status_code == 400
    assert (
        change(admin_client, identifier, action="status", reason=" ").status_code == 400
    )
    assert (
        admin_client.post(f"{URL}{identifier}/publish/", {}, format="json").status_code
        == 404
    )
    own = record(user_client)
    assert own.status_code == 201
    assert change(user_client, own.data["id"]).status_code == 201


def test_date_validation_patient_search_and_pagination(admin_client):
    patient = create(admin_client)
    for _ in range(21):
        assert record(admin_client, patient).status_code == 201
    one = admin_client.get(URL + PERIOD).data
    two = admin_client.get(URL + PERIOD + "&reviews_page=2").data
    assert len(one["reviews"]) == 20 and len(two["reviews"]) == 1
    assert one["summary"] == two["summary"] and one["summary"]["count"] == 21
    assert not {r["id"] for r in one["reviews"]} & {r["id"] for r in two["reviews"]}
    assert (
        len(
            admin_client.get(URL + PERIOD + "&search=Fictional+Patient").data[
                "patient_choices"
            ]
        )
        == 1
    )
    for params in (
        "start=bad",
        "start=2026-10-01&end=2026-09-01",
        "end=9999-12-31",
        "status=sent",
        "source=bad",
        "reviews_page=0",
        "patient=bad",
    ):
        assert admin_client.get(URL + "?" + params).status_code == 400


def test_forced_rls_foreign_links_and_immutable_database_history(
    admin_client, org_b_client, org_a, org_b, admin_user, user_b
):
    patient = create(admin_client)
    identifier = record(admin_client, patient).data["id"]
    foreign_patient = create(org_b_client)
    foreign = record(org_b_client, foreign_patient).data["id"]
    assert change(admin_client, identifier).status_code == 201
    with rls_org(org_a):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname IN ('mp_practice_review','mp_review_change')"
            )
            rows = cursor.fetchall()
            assert len(rows) == 2 and all(r[1] and r[2] for r in rows)
        attempts = [
            lambda: PracticeReview.objects.create(
                org=org_a,
                patient_id=foreign_patient["id"],
                rating=1,
                reviewed_at=DATE,
                request_id=uuid4(),
                created_by=admin_user,
            ),
            lambda: PracticeReview.objects.create(
                org=org_a,
                patient_id=patient["id"],
                rating=1,
                reviewed_at=DATE,
                request_id=uuid4(),
                created_by=user_b,
            ),
            lambda: PracticeReview.objects.create(
                org=org_b,
                patient_id=foreign_patient["id"],
                rating=1,
                reviewed_at=DATE,
                request_id=uuid4(),
                created_by=user_b,
            ),
            lambda: ReviewChange.objects.create(
                org=org_a,
                review_id=foreign,
                action="draft",
                payload={"draft": "Foreign"},
                revision=1,
                request_id=uuid4(),
                created_by=admin_user,
            ),
            lambda: PracticeReview.objects.filter(pk=identifier).update(rating=1),
            lambda: PracticeReview.objects.filter(pk=identifier).update(
                status="archived", revision=2
            ),
            lambda: ReviewChange.objects.filter(review_id=identifier).update(
                payload={}
            ),
            lambda: ReviewChange.objects.filter(review_id=identifier).delete(),
        ]
        for attempt in attempts:
            with (
                pytest.raises((IntegrityError, ProgrammingError)),
                transaction.atomic(),
            ):
                attempt()
    with rls_org(org_b):
        assert not PracticeReview.objects.filter(pk=identifier).exists()
        assert not ReviewChange.objects.filter(review_id=identifier).exists()


def test_seed_rerun_preserves_edits_and_patient_records(admin_user):
    from django.core.management import call_command

    from common.models import Org
    from patients.management.commands.seed_modern_practice import demo_id
    from patients.models import Patient, Receipt

    call_command("seed_modern_practice", member_email=admin_user.email)
    call_command("seed_modern_practice_reviews")
    for key in ("harbor", "cedar"):
        with rls_org(Org.objects.get(pk=demo_id(key))):
            row = PracticeReview.objects.get(pk=demo_id(key + ":reviews:alex"))
            ReviewChange.objects.create(
                org=row.org,
                review=row,
                action="draft",
                payload={"draft": "Staff edited draft"},
                revision=2,
                request_id=uuid4(),
                created_by=admin_user,
            )
    call_command("seed_modern_practice_reviews")
    for key in ("harbor", "cedar"):
        with rls_org(Org.objects.get(pk=demo_id(key))):
            row = PracticeReview.objects.get(pk=demo_id(key + ":reviews:alex"))
            assert row.draft == "Staff edited draft" and row.revision == 2
            assert (
                PracticeReview.objects.count() == 3
                and ReviewChange.objects.count() == 2
            )
            assert Patient.objects.count() == 3 and Receipt.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_competing_review_changes_do_not_overwrite(admin_client, org_a, admin_user):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import DatabaseError, connections

    identifier = record(admin_client).data["id"]
    barrier = Barrier(2)

    def attempt(text):
        try:
            with transaction.atomic():
                with connections["default"].cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.current_org',%s,true)", [str(org_a.id)]
                    )
                    cursor.execute("SET LOCAL lock_timeout='5s'")
                barrier.wait(timeout=10)
                ReviewChange.objects.create(
                    org_id=org_a.id,
                    review_id=identifier,
                    action="draft",
                    payload={"draft": text},
                    revision=1,
                    request_id=uuid4(),
                    created_by_id=admin_user.id,
                )
            return "accepted"
        except DatabaseError as error:
            return error.__cause__.sqlstate
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(attempt, text) for text in ("First draft", "Second draft")
        ]
        results = [f.result(timeout=20) for f in futures]
    assert results.count("accepted") == 1 and "23514" in results
    with rls_org(org_a):
        assert ReviewChange.objects.filter(review_id=identifier).count() == 1
