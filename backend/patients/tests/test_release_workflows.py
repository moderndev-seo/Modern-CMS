"""Release acceptance: real member administration and shared CRM patient links."""

import pytest

from common.models import PersonalAccessToken, Profile, User
from common.testing import _make_authenticated_client
from contacts.models import Contact
from patients.tests.test_journey import BASE, DATE, create, record


@pytest.fixture
def staff(org_a):
    user = User.objects.create_user(
        email="clinical-review@example.invalid", password="test-only"
    )
    profile = Profile.objects.create(user=user, org=org_a)
    return profile, _make_authenticated_client(user, org_a, profile)


def set_permissions(admin, profile, **values):
    response = admin.patch(f"/api/user/{profile.user_id}/", values, format="json")
    assert response.status_code == 200, response.data
    profile.refresh_from_db()
    for name, value in values.items():
        assert getattr(profile, name) == value


@pytest.mark.parametrize(
    "read,outcomes,finance,marketing",
    [
        (False, False, False, False),
        (False, False, False, True),
        (True, False, False, False),
        (True, True, False, False),
        (True, False, True, False),
        (True, True, True, True),
    ],
)
def test_real_staff_permission_matrix(
    admin_client, staff, read, outcomes, finance, marketing
):
    patient = create(admin_client)
    profile, client = staff
    Contact.objects.get(pk=patient["contact"]).assigned_to.add(profile)
    set_permissions(
        admin_client,
        profile,
        has_patient_access=read,
        can_record_patient_outcomes=outcomes,
        has_patient_finance_access=finance,
        has_marketing_access=marketing,
    )
    assert client.get(BASE).status_code == (200 if read else 403)
    detail = client.get(f"{BASE}{patient['id']}/")
    assert detail.status_code == (200 if read else 403)
    assert client.get(f"{BASE}{patient['id']}/receipts/").status_code == (
        200 if read and finance else 403
    )
    assert record(
        client, patient, "events", kind="treated", occurred_at=DATE
    ).status_code == (201 if read and outcomes else 403)
    assert (
        record(
            client,
            patient,
            "receipts",
            kind="payment",
            amount="100",
            reference="TEST-review",
            occurred_at=DATE,
        ).status_code
        == 403
    )
    assert client.get(BASE + "growth/").status_code == (200 if marketing else 403)
    if read:
        assert ("net_revenue" in detail.data) == finance


def test_admin_api_revokes_existing_jwt_and_pat_access(admin_client, staff):
    from rest_framework.test import APIClient

    patient = create(admin_client)
    profile, client = staff
    Contact.objects.get(pk=patient["contact"]).assigned_to.add(profile)
    set_permissions(
        admin_client, profile, has_patient_access=True, can_record_patient_outcomes=True
    )
    raw, token = PersonalAccessToken.generate(
        profile=profile,
        name="TEST reviewed integration",
        scopes=["patients:read", "patients:write"],
    )
    integration = APIClient()
    integration.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
    for actor in (client, integration):
        assert actor.get(f"{BASE}{patient['id']}/").status_code == 200
    set_permissions(admin_client, profile, has_patient_access=False)
    for actor in (client, integration):
        assert actor.get(f"{BASE}{patient['id']}/").status_code == 403
        assert (
            record(
                actor, patient, "events", kind="treated", occurred_at=DATE
            ).status_code
            == 403
        )
    assert (
        client.patch(
            f"/api/user/{profile.user_id}/", {"has_patient_access": True}, format="json"
        ).status_code
        == 400
    )
    profile.refresh_from_db()
    assert not profile.has_patient_access
    set_permissions(admin_client, profile, has_patient_access=True)
    assert integration.get(BASE).status_code == 200
    response = admin_client.delete(f"/api/org/tokens/{token.id}/")
    assert response.status_code in (200, 204), response.data
    assert integration.get(BASE).status_code in (401, 403)


@pytest.mark.parametrize("kind", ["case", "opportunity", "lead"])
def test_authorized_shared_crm_patient_contacts_remain_visible(
    admin_client, staff, org_a, kind
):
    from cases.models import Case
    from leads.models import Lead
    from opportunity.models import Opportunity

    patient = create(admin_client)
    profile, client = staff
    contact = Contact.objects.get(pk=patient["contact"])
    contact.assigned_to.add(profile)
    set_permissions(
        admin_client,
        profile,
        has_patient_access=True,
        has_patient_finance_access=kind != "case",
    )
    if kind == "case":
        obj = Case.objects.create(
            org=org_a,
            name="TEST case",
            status="New",
            priority="Low",
            created_by=profile.user,
        )
        url, key = "cases", "cases_obj"
    elif kind == "opportunity":
        obj = Opportunity.objects.create(
            org=org_a, name="TEST opportunity", created_by=profile.user
        )
        url, key = "opportunities", "opportunity_obj"
    else:
        obj = Lead.objects.create(
            org=org_a, first_name="TEST", last_name="Inquiry", created_by=profile.user
        )
        url, key = "leads", "lead_obj"
    obj.contacts.add(contact)
    for actor in (admin_client, client):
        response = actor.get(f"/api/{url}/{obj.id}/")
        assert response.status_code == 200, response.data
        assert response.data[key]["contacts"][0]["id"] == str(contact.id)
    set_permissions(admin_client, profile, has_patient_access=False)
    response = client.get(f"/api/{url}/{obj.id}/")
    assert response.status_code == 403, response.data
    assert client.delete(f"/api/{url}/{obj.id}/").status_code == 403
    assert type(obj).objects.filter(pk=obj.pk).exists()


def test_profile_history_does_not_bypass_revoked_patient_access(
    admin_client, staff, org_a
):
    from django.contrib.contenttypes.models import ContentType

    from common.models import Comment

    patient = create(admin_client)
    profile, client = staff
    contact = Contact.objects.get(pk=patient["contact"])
    contact.assigned_to.add(profile)
    set_permissions(admin_client, profile, has_patient_access=True)
    comment = Comment.objects.create(
        org=org_a,
        content_type=ContentType.objects.get_for_model(Contact),
        object_id=contact.pk,
        commented_by=profile,
        comment="TEST private patient history",
    )
    url = f"/api/user/{profile.user_id}/"
    assert str(comment.pk) in str(client.get(url).data)
    set_permissions(admin_client, profile, has_patient_access=False)
    denied_history = client.get(url)
    assert denied_history.status_code == 200
    assert "TEST private patient history" not in str(denied_history.data)
    assert str(comment.pk) not in str(denied_history.data)


def test_patient_task_creator_cannot_delete_after_revocation(
    admin_client, staff, org_a
):
    from tasks.models import Task

    patient = create(admin_client)
    profile, client = staff
    contact = Contact.objects.get(pk=patient["contact"])
    contact.assigned_to.add(profile)
    task = Task.objects.create(
        org=org_a,
        title="TEST follow-up",
        status="New",
        priority="Low",
        created_by=profile.user,
    )
    task.contacts.add(contact)
    set_permissions(admin_client, profile, has_patient_access=True)
    assert client.get(f"/api/tasks/{task.pk}/").status_code == 200
    set_permissions(admin_client, profile, has_patient_access=False)
    assert client.delete(f"/api/tasks/{task.pk}/").status_code == 403
    assert Task.objects.filter(pk=task.pk).exists()


@pytest.mark.parametrize(
    "resource", ["contacts", "cases", "tasks", "leads", "opportunities", "accounts"]
)
@pytest.mark.parametrize("interaction_kind", ["comment", "attachment"])
def test_generic_interactions_cannot_bypass_patient_revocation(
    admin_client, staff, org_a, resource, interaction_kind
):
    from django.contrib.contenttypes.models import ContentType

    from common.models import Attachments, Comment

    patient = create(admin_client)
    profile, client = staff
    contact = Contact.objects.get(pk=patient["contact"])
    contact.assigned_to.add(profile)
    values = dict(
        org=org_a,
        content_type=ContentType.objects.get_for_model(Contact),
        object_id=contact.pk,
    )
    if interaction_kind == "comment":
        obj = Comment.objects.create(
            **values, commented_by=profile, comment="TEST original"
        )
    else:
        obj = Attachments.objects.create(
            **values,
            created_by=profile.user,
            file_name="TEST.txt",
            attachment="TEST.txt",
        )
    url = f"/api/{resource}/{interaction_kind}/{obj.pk}/"
    set_permissions(admin_client, profile, has_patient_access=True)
    if interaction_kind == "comment":
        assert (
            client.patch(url, {"comment": "TEST authorized"}, format="json").status_code
            == 200
        )
    set_permissions(admin_client, profile, has_patient_access=False)
    if interaction_kind == "comment":
        assert (
            client.patch(url, {"comment": "TEST denied"}, format="json").status_code
            == 403
        )
        obj.refresh_from_db()
        assert obj.comment == "TEST authorized"
    assert client.delete(url).status_code == 403
    assert type(obj).objects.filter(pk=obj.pk).exists()


@pytest.mark.parametrize("kind", ["comments", "attachments"])
def test_invoice_generic_route_respects_patient_parent(
    admin_client, staff, org_a, kind
):
    from django.contrib.contenttypes.models import ContentType

    from common.models import Attachments, Comment

    patient = create(admin_client)
    profile, client = staff
    contact = Contact.objects.get(pk=patient["contact"])
    values = dict(
        org=org_a,
        content_type=ContentType.objects.get_for_model(Contact),
        object_id=contact.pk,
    )
    obj = (
        Comment.objects.create(**values, commented_by=profile, comment="TEST")
        if kind == "comments"
        else Attachments.objects.create(
            **values,
            created_by=profile.user,
            attachment="TEST.txt",
            file_name="TEST.txt",
        )
    )
    assert client.delete(f"/api/invoices/{kind}/{obj.pk}/").status_code == 403
    assert type(obj).objects.filter(pk=obj.pk).exists()
