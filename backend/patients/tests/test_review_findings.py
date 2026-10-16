"""PR #1 alternate-route regressions under migrated restricted PostgreSQL."""

import pytest
from django.contrib.contenttypes.models import ContentType

from cases.models import Case
from common.models import Comment, Profile
from contacts.models import Contact
from opportunity.models import Opportunity
from patients.tests.test_authorization import grant, member  # noqa: F401
from patients.tests.test_journey import create


@pytest.fixture
def linked(admin_client, member, org_a):  # noqa: F811
    patient = create(admin_client)
    profile, client = member
    contact = Contact.objects.get(pk=patient["contact"])
    contact.assigned_to.add(profile)
    grant(profile, has_patient_access=True, has_patient_finance_access=True)
    deal = Opportunity.objects.create(
        org=org_a, name="TEST protected deal", created_by=profile.user
    )
    deal.contacts.add(contact)
    case = Case.objects.create(
        org=org_a,
        name="TEST protected case",
        status="New",
        priority="Low",
        created_by=profile.user,
    )
    case.contacts.add(contact)
    case.watchers.add(profile, through_defaults={"org": org_a})
    return profile, client, contact, deal, case


def test_revoked_opportunity_kanban(linked):
    profile, client, contact, deal, case = linked
    grant(profile, has_patient_access=False)
    response = client.get("/api/opportunities/kanban/")
    assert response.status_code == 200
    assert str(deal.pk) not in str(response.data)


def test_revoked_opportunity_line_items(linked):
    profile, client, contact, deal, case = linked
    grant(profile, has_patient_finance_access=False)
    assert client.get(f"/api/opportunities/{deal.pk}/line-items/").status_code == 403


def test_revoked_watching_list(linked):
    profile, client, contact, deal, case = linked
    grant(profile, has_patient_access=False)
    response = client.get("/api/cases/watching/")
    assert response.status_code == 200
    assert str(case.pk) not in str(response.data)


def test_revoked_merge(linked, org_a):
    profile, client, contact, deal, case = linked
    target = Case.objects.create(org=org_a, name="TEST target", created_by=profile.user)
    target.contacts.add(contact)
    grant(profile, has_patient_access=False)
    assert client.post(f"/api/cases/{case.pk}/merge/{target.pk}/").status_code == 403


def test_creation_persists_capabilities(admin_client, org_a):
    values = dict(
        has_patient_access=True,
        can_record_patient_outcomes=True,
        has_patient_finance_access=True,
    )
    response = admin_client.post(
        "/api/users/",
        {"email": "test-granted@example.invalid", "role": "USER", **values},
        format="json",
    )
    assert response.status_code == 201, response.data
    profile = Profile.objects.get(org=org_a, user__email="test-granted@example.invalid")
    assert all(getattr(profile, name) for name in values)


def test_authorized_portal_author_context(linked, org_a):
    profile, client, contact, deal, case = linked
    Comment.objects.create(
        org=org_a,
        content_type=ContentType.objects.get_for_model(Case),
        object_id=case.pk,
        commented_by_contact=contact,
        comment="TEST portal response",
    )
    response = client.get(f"/api/cases/{case.pk}/")
    assert response.status_code == 200, response.data
    assert response.data["comments"][0]["commented_by_contact"]["id"] == str(contact.pk)


def test_revoked_bulk_delete(linked):
    profile, client, contact, deal, case = linked
    grant(profile, has_patient_access=False)
    response = client.post(
        "/api/cases/bulk/delete/", {"ids": [str(case.pk)]}, format="json"
    )
    assert response.status_code == 200
    case.refresh_from_db()
    assert case.is_active


@pytest.mark.parametrize(
    "capability", ["has_patient_access", "has_patient_finance_access"]
)
@pytest.mark.parametrize("verb", ["get", "get_detail", "post", "put", "delete"])
def test_line_items_recheck_revoked_capabilities(linked, capability, verb):
    from opportunity.models import OpportunityLineItem

    profile, client, contact, deal, case = linked
    item = OpportunityLineItem.objects.create(
        org=deal.org, opportunity=deal, name="TEST item", quantity=1, unit_price=12
    )
    url = f"/api/opportunities/{deal.pk}/line-items/"
    if verb in ("get_detail", "put", "delete"):
        url += f"{item.pk}/"
    if verb == "get_detail":
        verb = "get"
    assert client.get(url).status_code == 200
    grant(profile, **{capability: False})
    response = (
        getattr(client, verb)(
            url,
            {"name": "TEST denied", "quantity": 1, "unit_price": "99"},
            format="json",
        )
        if verb != "get"
        else client.get(url)
    )
    assert response.status_code == 403
    item.refresh_from_db()
    assert item.unit_price == 12


@pytest.mark.parametrize(
    "resource,scope", [("opportunities", "opportunities"), ("cases", "cases")]
)
@pytest.mark.parametrize("credential", ["pat", "org_key"])
def test_alternate_routes_credential_ceiling(linked, resource, scope, credential):
    from rest_framework.test import APIClient

    from common.models import PersonalAccessToken

    profile, client, contact, deal, case = linked
    actor = APIClient()
    if credential == "pat":
        raw, token = PersonalAccessToken.generate(
            profile, "TEST scoped", scopes=[f"{scope}:read", f"{scope}:write"]
        )
        actor.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
    else:
        actor.credentials(HTTP_TOKEN=profile.org.api_key)
    url = (
        f"/api/opportunities/{deal.pk}/line-items/"
        if resource == "opportunities"
        else f"/api/cases/{case.pk}/"
    )
    assert actor.get(url).status_code in (403, 404)
    listing = actor.get(
        "/api/opportunities/kanban/"
        if resource == "opportunities"
        else "/api/cases/watching/"
    )
    assert listing.status_code in (200, 403)
    if listing.status_code == 200:
        assert str(deal.pk if resource == "opportunities" else case.pk) not in str(
            listing.data
        )
    if credential == "pat":
        token.scopes += ["patients:read"]
        token.save()
        assert actor.get(url).status_code == 200
        if resource == "opportunities":
            assert (
                actor.post(
                    url,
                    {"name": "TEST denied", "quantity": 1, "unit_price": "2"},
                    format="json",
                ).status_code
                == 403
            )
            token.scopes += ["patients:write"]
            token.save()
            assert (
                actor.post(
                    url,
                    {"name": "TEST permitted", "quantity": 1, "unit_price": "2"},
                    format="json",
                ).status_code
                == 201
            )


@pytest.mark.parametrize(
    "path",
    [
        "watching/",
        "kanban/",
        "analytics/drilldown/?metric=frt",
        "analytics/export/?metric=frt",
    ],
)
def test_case_alternate_lists_exclude_revoked(linked, path):
    from django.utils import timezone

    profile, client, contact, deal, case = linked
    case.first_response_at = timezone.now()
    case.save()
    grant(profile, has_patient_access=False)
    response = client.get("/api/cases/" + path)
    assert response.status_code == 200
    body = (
        b"".join(response.streaming_content).decode()
        if response.streaming
        else str(response.data)
    )
    assert str(case.pk) not in body
    assert case.name not in body


@pytest.mark.parametrize("side", ["source", "target"])
def test_unmerge_rechecks_both_patients(linked, org_a, admin_client, side):
    profile, client, contact, deal, source = linked
    target = Case.objects.create(org=org_a, name="TEST target", created_by=profile.user)
    target.contacts.add(contact)
    assert client.post(f"/api/cases/{source.pk}/merge/{target.pk}/").status_code == 200
    # Revoke Contact visibility on only one linked record, not merely case ownership.
    patient2 = create(
        admin_client, first_name="Other", email="other-test@example.invalid"
    )
    other = Contact.objects.get(pk=patient2["contact"])
    (source if side == "source" else target).contacts.add(other)
    assert client.post(f"/api/cases/{source.pk}/unmerge/").status_code == 403
    if side == "source":
        response = client.get(f"/api/cases/{target.pk}/")
        assert response.status_code == 200
        entry = next(
            row
            for row in response.data["merged_from_cases"]
            if str(row["id"]) == str(source.pk)
        )
        assert entry["restricted"] and not entry["can_unmerge"]
    source.refresh_from_db()
    assert source.merged_into_id == target.pk
    assert admin_client.post(f"/api/cases/{source.pk}/unmerge/").status_code == 200


def test_plain_crm_and_foreign_routes(linked, org_a, org_b_client, admin_client):
    profile, client, contact, deal, case = linked
    plain_deal = Opportunity.objects.create(
        org=org_a, name="TEST plain deal", created_by=profile.user
    )
    plain_case = Case.objects.create(
        org=org_a, name="TEST plain case", created_by=profile.user
    )
    grant(profile, has_patient_access=False, has_patient_finance_access=False)
    assert (
        client.get(f"/api/opportunities/{plain_deal.pk}/line-items/").status_code == 200
    )
    assert client.get(f"/api/cases/{plain_case.pk}/").status_code == 200
    for route in [
        f"/api/opportunities/{deal.pk}/line-items/",
        f"/api/cases/{case.pk}/",
        f"/api/cases/{case.pk}/merge/{plain_case.pk}/",
    ]:
        response = (
            org_b_client.post(route) if "/merge/" in route else org_b_client.get(route)
        )
        assert response.status_code in (403, 404)
    assert (
        admin_client.get(f"/api/opportunities/{deal.pk}/line-items/").status_code == 200
    )


@pytest.mark.parametrize("actor_kind", ["member", "pat", "org_key"])
def test_unauthorized_member_creation_grants(
    admin_client, linked, actor_kind, admin_profile
):
    from rest_framework.test import APIClient

    from common.models import PersonalAccessToken

    profile, client, contact, deal, case = linked
    actor = client
    if actor_kind != "member":
        actor = APIClient()
        if actor_kind == "pat":
            raw, _ = PersonalAccessToken.generate(
                admin_profile, "TEST admin token", scopes=["*"]
            )
            actor.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        else:
            actor.credentials(HTTP_TOKEN=profile.org.api_key)
    response = actor.post(
        "/api/users/",
        {
            "email": "denied-test@example.invalid",
            "role": "ADMIN",
            "has_patient_access": True,
        },
        format="json",
    )
    assert response.status_code == 403
    assert not Profile.objects.filter(
        user__email="denied-test@example.invalid"
    ).exists()


def test_creation_defaults_remain_false(admin_client, org_a):
    response = admin_client.post(
        "/api/users/",
        {"email": "default-test@example.invalid", "role": "USER"},
        format="json",
    )
    assert response.status_code == 201, response.data
    p = Profile.objects.get(org=org_a, user__email="default-test@example.invalid")
    assert not any(
        [
            p.has_patient_access,
            p.can_record_patient_outcomes,
            p.has_patient_finance_access,
        ]
    )


@pytest.mark.parametrize(
    "kind", ["contact", "task", "opportunity", "invoice", "account"]
)
def test_portal_author_context_across_details(linked, org_a, kind, admin_client):
    from accounts.models import Account
    from common.serializer import CommentSerializer
    from invoices.models import Invoice
    from tasks.models import Task

    profile, client, contact, deal, case = linked
    if kind == "contact":
        obj = contact
        route = "contacts"
    elif kind == "opportunity":
        obj = deal
        route = "opportunities"
    elif kind == "task":
        obj = Task.objects.create(
            org=org_a,
            title="TEST task",
            status="New",
            priority="Low",
            created_by=profile.user,
        )
        obj.contacts.add(contact)
        route = "tasks"
    elif kind == "invoice":
        obj = Invoice.objects.create(
            org=org_a, contact=contact, created_by=profile.user
        )
        route = "invoices"
    else:
        obj = Account.objects.create(
            org=org_a, name="TEST account", created_by=profile.user
        )
        route = "accounts"
    comment = Comment.objects.create(
        org=org_a,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        commented_by_contact=contact,
        comment="TEST portal",
    )
    assert CommentSerializer(comment).data["commented_by_contact"] == {
        "restricted": True
    }
    response = admin_client.get(f"/api/{route}/{obj.pk}/")
    assert response.status_code == 200, response.data
    assert str(contact.pk) in str(response.data["comments"][0]["commented_by_contact"])
    grant(profile, has_patient_access=False)
    assert CommentSerializer(comment, context={"profile": profile}).data[
        "commented_by_contact"
    ] == {"restricted": True}
    response = client.get(f"/api/{route}/{obj.pk}/")
    if kind == "account":
        assert response.status_code == 200
        assert response.data["comments"][0]["commented_by_contact"] == {
            "restricted": True
        }
    else:
        assert response.status_code in (403, 404)


@pytest.mark.parametrize("surface", ["detail", "list", "leaderboard", "history"])
@pytest.mark.parametrize(
    "restriction", ["finance", "patient", "contact", "pat", "org_key"]
)
def test_goal_progress_does_not_disclose_revoked_patient_deal(
    linked, org_a, admin_client, surface, restriction
):
    from datetime import timedelta

    from django.utils import timezone
    from rest_framework.test import APIClient

    from common.models import PersonalAccessToken
    from opportunity.models import SalesGoal

    profile, client, contact, deal, case = linked
    day = timezone.localdate() - timedelta(days=1 if surface == "history" else 0)
    deal.stage = "CLOSED_WON"
    deal.amount = 250
    deal.closed_on = day
    deal.save()
    deal.assigned_to.add(profile)
    plain = Opportunity.objects.create(
        org=org_a,
        name="TEST unprotected won deal",
        stage="CLOSED_WON",
        amount=10,
        closed_on=day,
        created_by=profile.user,
    )
    plain.assigned_to.add(profile)
    goal = SalesGoal.objects.create(
        org=org_a,
        name="TEST goal",
        goal_type="REVENUE",
        target_value=1000,
        period_type="MONTHLY",
        period_start=day,
        period_end=day,
        assigned_to=profile,
    )
    url = (
        "/api/opportunities/goals/"
        + {
            "detail": f"{goal.pk}/",
            "list": "",
            "leaderboard": "leaderboard/",
            "history": "history/",
        }[surface]
    )

    def progress(actor):
        response = actor.get(url)
        assert response.status_code == 200, response.data
        data = response.data
        if surface == "detail":
            return data["progress_value"]
        if surface == "list":
            return data["goals"][0]["progress_value"]
        return data["leaderboard" if surface == "leaderboard" else "history"][0][
            "achieved"
        ]

    assert progress(client) == 260
    if restriction == "finance":
        grant(profile, has_patient_finance_access=False)
    elif restriction == "patient":
        grant(profile, has_patient_access=False)
    elif restriction == "contact":
        contact.assigned_to.clear()
    else:
        client = APIClient()
        if restriction == "pat":
            raw, token = PersonalAccessToken.generate(
                profile, "TEST goals", scopes=["opportunities:read"]
            )
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        else:
            client.credentials(HTTP_TOKEN=org_a.api_key)
    assert progress(client) == 10
    assert progress(admin_client) == 260
    if restriction == "pat":
        token.scopes.append("patients:read")
        token.save()
        assert progress(client) == 260


@pytest.mark.parametrize("metric", ["frt", "mttr", "sla", "backlog", "agents"])
def test_case_metric_counts_exclude_revoked_records(linked, metric):
    from django.utils import timezone

    profile, client, contact, deal, case = linked
    case.first_response_at = timezone.now()
    case.resolved_at = timezone.now() if metric == "mttr" else None
    case.save()
    case.assigned_to.add(profile)
    url = f"/api/cases/analytics/{metric}/"
    before = client.get(url)
    assert before.status_code == 200
    grant(profile, has_patient_access=False)
    response = client.get(url)
    assert response.status_code == 200
    if metric in ("frt", "mttr"):
        assert before.data["count"] == 1
        assert response.data["count"] == 0
    elif metric == "sla":
        assert before.data["total"] == 1
        assert response.data["total"] == 0
    elif metric == "agents":
        assert before.data["results"]
        assert response.data["results"] == []
    else:
        assert any(row["open_count"] for row in before.data["series"])
        assert all(row["open_count"] == 0 for row in response.data["series"])


def test_service_analytics_admin_pat_cannot_inherit_patient_access(
    linked, admin_profile
):
    from rest_framework.test import APIClient

    from common.models import PersonalAccessToken

    profile, client, contact, deal, case = linked
    raw, token = PersonalAccessToken.generate(
        admin_profile, "TEST case analytics", scopes=["cases:read"]
    )
    actor = APIClient()
    actor.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
    response = actor.get("/api/cases/analytics/service/")
    assert response.status_code == 200, response.data
    assert response.data["totals"]["opened"] == 0
    token.scopes.append("patients:read")
    token.save()
    response = actor.get("/api/cases/analytics/service/")
    assert response.status_code == 200
    assert response.data["totals"]["opened"] == 1


@pytest.mark.parametrize("notification", ["assignment", "stale", "goal"])
def test_opportunity_notifications_recheck_patient_access(
    linked, org_a, mailoutbox, notification
):
    from django.utils import timezone

    from opportunity.models import SalesGoal
    from opportunity.tasks import (
        _send_goal_milestone_email,
        send_email_to_assigned_user,
        send_stale_deals_alert,
    )

    profile, client, contact, deal, case = linked
    deal.assigned_to.add(profile)
    deal.stage = "CLOSED_WON"
    deal.amount = 250
    deal.closed_on = timezone.localdate()
    deal.save()
    goal = SalesGoal.objects.create(
        org=org_a,
        name="TEST goal",
        goal_type="REVENUE",
        target_value=500,
        period_type="MONTHLY",
        period_start=timezone.localdate(),
        period_end=timezone.localdate(),
        assigned_to=profile,
    )

    def notify():
        if notification == "assignment":
            send_email_to_assigned_user([str(profile.pk)], str(deal.pk), str(org_a.pk))
        elif notification == "stale":
            send_stale_deals_alert(org_a, [(deal, "TEST stage", 10, 3)])
        else:
            _send_goal_milestone_email(profile, goal, "50%", 50, 250)

    notify()
    assert len(mailoutbox) == 1
    mailoutbox.clear()
    grant(profile, has_patient_access=False)
    notify()
    assert len(mailoutbox) == 0
