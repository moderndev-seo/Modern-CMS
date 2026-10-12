from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction

from common.testing import rls_org
from patients.models import (
    ConversationChange,
    LocalConversation,
    LocalMessage,
)
from patients.tests.test_journey import BASE, DATE, create, report

URL = BASE + "messages/"


def start(client, patient=None, **overrides):
    patient = patient or create(client)
    return client.post(
        URL,
        {
            "patient": patient["id"],
            "subject": "TEST - Treatment question",
            "request_id": str(uuid4()),
            **overrides,
        },
        format="json",
    )


def change(client, identifier, revision=0, **overrides):
    return client.patch(
        f"{URL}{identifier}/",
        {
            "action": "draft",
            "draft": "Fictional saved reply",
            "revision": revision,
            "request_id": str(uuid4()),
            **overrides,
        },
        format="json",
    )


def entry(client, identifier, **overrides):
    return client.post(
        f"{URL}{identifier}/entries/",
        {
            "kind": "received",
            "body": "Fictional question",
            "occurred_at": DATE,
            "request_id": str(uuid4()),
            **overrides,
        },
        format="json",
    )


def test_local_workflow_retry_history_and_growth(admin_client, admin_profile):
    patient = create(admin_client)
    before = report(admin_client)
    request_id = str(uuid4())
    thread = start(admin_client, patient, request_id=request_id)
    assert thread.status_code == 201, thread.data
    identifier = thread.data["id"]
    assert start(admin_client, patient, request_id=request_id).status_code == 200
    assert (
        start(admin_client, patient, request_id=request_id, subject="Other").status_code
        == 409
    )
    token = str(uuid4())
    for expected in [201, 200]:
        result = entry(admin_client, identifier, request_id=token)
        assert result.status_code == expected, result.data
    assert (
        entry(admin_client, identifier, request_id=token, body="Changed").status_code
        == 409
    )
    draft_key = str(uuid4())
    for expected in [201, 200]:
        response = change(admin_client, identifier, request_id=draft_key)
        assert response.status_code == expected, response.data
    assert change(admin_client, identifier).status_code == 409
    response = admin_client.patch(
        f"{URL}{identifier}/",
        {
            "action": "state",
            "owner": str(admin_profile.id),
            "status": "waiting",
            "revision": 1,
            "request_id": str(uuid4()),
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert change(admin_client, identifier, revision=2, draft="").status_code == 201
    detail = admin_client.get(f"{URL}{identifier}/").data
    assert detail["conversation"]["draft"] == ""
    assert detail["conversation"]["owner"] == str(admin_profile.id)
    assert detail["conversation"]["revision"] == 3
    assert len(detail["entries"]) == 1
    assert [h["revision"] for h in detail["history"]] == [3, 2, 1]
    assert detail["history"][-1]["before"]["draft"] == ""
    for revision, status in [(3, "resolved"), (4, "open")]:
        response = admin_client.patch(
            f"{URL}{identifier}/",
            {
                "action": "state",
                "owner": None,
                "status": status,
                "revision": revision,
                "request_id": str(uuid4()),
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        if status == "resolved":
            assert entry(admin_client, identifier).status_code == 409
            assert change(admin_client, identifier, revision=4).status_code == 409
    assert entry(admin_client, identifier, kind="note").status_code == 201
    assert report(admin_client) == before


def test_contact_permissions_and_tenant_api(
    admin_client,
    user_client,
    org_b_client,
    user_profile,
    profile_b,
    unauthenticated_client,
):
    patient = create(admin_client)
    identifier = start(admin_client, patient).data["id"]
    for client in [user_client, org_b_client]:
        assert client.get(f"{URL}{identifier}/").status_code == 404
        assert change(client, identifier).status_code == 404
        assert entry(client, identifier).status_code == 404
        assert client.get(URL).data["conversations"] == []
        assert client.get(URL + f"?patient={patient['id']}").status_code == 404
    assert start(user_client, patient).status_code == 403
    assert start(org_b_client, patient).status_code == 404
    for profile in [user_profile, profile_b]:
        response = admin_client.patch(
            f"{URL}{identifier}/",
            {
                "action": "state",
                "owner": str(profile.id),
                "status": "open",
                "revision": 0,
                "request_id": str(uuid4()),
            },
            format="json",
        )
        assert response.status_code == 400, response.data
    assert unauthenticated_client.get(URL).status_code in (401, 403)
    assert admin_client.delete(f"{URL}{identifier}/").status_code == 405
    assert (
        admin_client.post(f"{URL}{identifier}/send/", {}, format="json").status_code
        == 404
    )


def test_template_admin_permissions_and_tenant_scope(
    admin_client, user_client, org_b_client
):
    data = {
        "title": "TEST - Reply",
        "body": "Fictional reply",
        "request_id": str(uuid4()),
    }
    assert user_client.post(URL + "templates/", data, format="json").status_code == 403
    result = admin_client.post(URL + "templates/", data, format="json")
    assert result.status_code == 201, result.data
    identifier = result.data["id"]
    assert admin_client.post(URL + "templates/", data, format="json").status_code == 200
    assert org_b_client.get(URL + "templates/").data["templates"] == []
    for client, expected in [
        (user_client, 403),
        (org_b_client, 404),
        (admin_client, 200),
    ]:
        result = client.patch(
            f"{URL}templates/{identifier}/",
            {"active": False, "revision": 0},
            format="json",
        )
        assert result.status_code == expected, result.data
    assert (
        admin_client.patch(
            f"{URL}templates/{identifier}/",
            {"active": True, "revision": 0},
            format="json",
        ).status_code
        == 409
    )
    identifier2 = start(admin_client).data["id"]
    assert admin_client.get(f"{URL}{identifier2}/").data["templates"] == []


def test_input_and_pagination(admin_client):
    patient = create(admin_client)
    identifier = None
    for index in range(22):
        result = start(admin_client, patient, subject=f"TEST question {index}")
        assert result.status_code == 201, result.data
        identifier = result.data["id"]
    first = admin_client.get(URL).data
    second = admin_client.get(URL + "?conversations_page=2").data
    assert len(first["conversations"]) == 20 and len(second["conversations"]) == 2
    assert not {r["id"] for r in first["conversations"]} & {
        r["id"] for r in second["conversations"]
    }
    for query in [
        "conversations_page=0",
        "status=sent",
        "owner=someone",
        "tasks=bad",
        "patient=bad",
    ]:
        assert admin_client.get(URL + "?" + query).status_code == 400
    assert admin_client.get(URL + "?search=Fictional+Patient").data["patient_choices"]
    for fields in [
        {"org": str(uuid4())},
        {"kind": "sent"},
        {"body": " "},
        {"occurred_at": "2099-01-01T00:00:00Z"},
    ]:
        assert entry(admin_client, identifier, **fields).status_code == 400
    assert change(admin_client, identifier, owner=None).status_code == 400


def test_database_rls_links_and_history_immutability(
    admin_client, org_b_client, org_a, org_b, admin_user
):
    identifier = start(admin_client).data["id"]
    foreign = start(org_b_client).data["id"]
    assert entry(admin_client, identifier).status_code == 201
    assert change(admin_client, identifier).status_code == 201
    with rls_org(org_a):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('mp_local_conversation','mp_local_message','mp_conversation_change','mp_local_message_template')"
            )
            assert len(rows := cursor.fetchall()) == 4 and all(
                r[1] and r[2] for r in rows
            )
        operations = [
            lambda: LocalMessage.objects.create(
                org=org_a,
                conversation_id=foreign,
                body="Foreign",
                kind="note",
                occurred_at=DATE,
                request_id=uuid4(),
                created_by=admin_user,
            ),
            lambda: LocalConversation.objects.filter(pk=identifier).update(
                draft="Silent overwrite", revision=2
            ),
            lambda: LocalMessage.objects.filter(conversation_id=identifier).update(
                body="Changed"
            ),
            lambda: ConversationChange.objects.filter(
                conversation_id=identifier
            ).update(payload={}),
            lambda: LocalMessage.objects.filter(conversation_id=identifier).delete(),
        ]
        for operation in operations:
            with pytest.raises(IntegrityError), transaction.atomic():
                operation()
    with rls_org(org_b):
        assert not LocalConversation.objects.filter(pk=identifier).exists()
        assert not LocalMessage.objects.filter(conversation_id=identifier).exists()
        assert not ConversationChange.objects.filter(
            conversation_id=identifier
        ).exists()


def test_followup_queue_reuses_task_visibility(user_client, admin_client):
    from patients.tests.test_followups import followup

    mine = create(user_client)
    hidden = create(admin_client)
    assert followup(user_client, mine).status_code == 201
    assert followup(admin_client, hidden).status_code == 201
    result = user_client.get(URL + "?tasks=all")
    assert result.status_code == 200, result.data
    assert len(result.data["followups"]) == 1
    assert result.data["followup_due_count"] == 1


def test_seed_preserves_changes_and_is_repeatable(admin_user):
    from django.core.management import call_command

    from common.models import Org
    from patients.management.commands.seed_modern_practice import demo_id

    call_command("seed_modern_practice", member_email=admin_user.email)
    call_command("seed_modern_practice_messages")
    for key in ("harbor", "cedar"):
        with rls_org(Org.objects.get(pk=demo_id(key))):
            row = LocalConversation.objects.get(
                pk=demo_id(key + ":messages:conversation")
            )
            ConversationChange.objects.create(
                org=row.org,
                conversation=row,
                action="draft",
                payload={"draft": "Staff edited draft"},
                revision=2,
                request_id=uuid4(),
                created_by=admin_user,
            )
    call_command("seed_modern_practice_messages")
    for key in ("harbor", "cedar"):
        with rls_org(Org.objects.get(pk=demo_id(key))):
            row = LocalConversation.objects.get(
                pk=demo_id(key + ":messages:conversation")
            )
            assert row.draft == "Staff edited draft" and row.revision == 2
            assert LocalConversation.objects.count() == 1
            assert LocalMessage.objects.count() == 1
            assert ConversationChange.objects.count() == 2
            from patients.models import LocalMessageTemplate

            assert LocalMessageTemplate.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_competing_drafts_do_not_overwrite(admin_client, org_a, admin_user):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import DatabaseError, connections

    identifier = start(admin_client).data["id"]
    barrier = Barrier(2)

    def attempt(text):
        try:
            with transaction.atomic():
                with connections["default"].cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.current_org', %s, true)",
                        [str(org_a.id)],
                    )
                    cursor.execute("SET LOCAL lock_timeout='5s'")
                barrier.wait(timeout=10)
                ConversationChange.objects.create(
                    org_id=org_a.id,
                    conversation_id=identifier,
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
    assert results.count("accepted") == 1, results
    assert "23514" in results
    with rls_org(org_a):
        assert (
            ConversationChange.objects.filter(conversation_id=identifier).count() == 1
        )
        assert LocalConversation.objects.get(pk=identifier).revision == 1


def test_direct_foreign_patient_owner_and_change_links(
    admin_client, org_b_client, org_a, org_b, admin_user, profile_b
):
    from django.db import ProgrammingError

    from patients.models import LocalMessageTemplate

    foreign_patient = create(org_b_client)
    foreign_thread = start(org_b_client, foreign_patient).data["id"]
    patient = create(admin_client)
    identifier = start(admin_client, patient).data["id"]
    with rls_org(org_a):
        attempts = [
            lambda: LocalConversation.objects.create(
                org=org_a,
                patient_id=foreign_patient["id"],
                subject="Foreign",
                request_id=uuid4(),
            ),
            lambda: LocalConversation.objects.create(
                org=org_a,
                patient_id=patient["id"],
                owner=profile_b,
                subject="Foreign owner",
                request_id=uuid4(),
            ),
            lambda: ConversationChange.objects.create(
                org=org_a,
                conversation_id=foreign_thread,
                action="draft",
                payload={"draft": "Foreign"},
                revision=1,
                request_id=uuid4(),
                created_by=admin_user,
            ),
            lambda: ConversationChange.objects.create(
                org=org_a,
                conversation_id=identifier,
                action="state",
                payload={"owner": str(profile_b.id), "status": "open"},
                revision=1,
                request_id=uuid4(),
                created_by=admin_user,
            ),
            lambda: LocalMessageTemplate.objects.create(
                org=org_b, title="Foreign", body="Foreign", request_id=uuid4()
            ),
        ]
        for attempt in attempts:
            with (
                pytest.raises((IntegrityError, ProgrammingError)),
                transaction.atomic(),
            ):
                attempt()
