"""Real request regressions: membership, grants, sharing and credentials intersect."""

import pytest
from rest_framework.test import APIClient

from common.models import PersonalAccessToken, Profile, User
from common.serializer import CreateProfileSerializer
from common.testing import _make_authenticated_client
from contacts.access import has_contact_access
from contacts.models import Contact
from contacts.serializer import ContactLinkSerializer
from patients.tests.test_journey import BASE, DATE, create, record


@pytest.fixture
def member(org_a):
    user = User.objects.create_user(
        email="marketing@example.invalid", password="test-only"
    )
    profile = Profile.objects.create(user=user, org=org_a, has_marketing_access=True)
    return profile, _make_authenticated_client(user, org_a, profile)


def grant(profile, **flags):
    for key, value in flags.items():
        setattr(profile, key, value)
    profile.save()


@pytest.mark.parametrize(
    "path", ["", "contacts/?search=Alex", "messages/", "reviews/", "attribution/"]
)
def test_marketing_membership_is_not_patient_access(admin_client, member, path):
    create(admin_client)
    profile, client = member
    assert not profile.has_patient_access
    assert not profile.can_record_patient_outcomes
    assert not profile.has_patient_finance_access
    assert client.get(BASE + path).status_code == 403
    assert client.post(BASE, {"first_name": "Denied"}, format="json").status_code == 403
    growth = client.get(BASE + "growth/?start=2026-09-01&end=2026-09-30")
    assert growth.status_code == 200
    assert "contact" not in str(growth.data)


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "events/",
        "receipts/",
        "appointments/",
        "billing/",
        "statement/",
        "statement/?format=csv",
        "balances/",
        "corrections/",
        "exclusions/",
        "allocations/",
    ],
)
def test_contact_denial_holds_across_patient_routes(admin_client, member, suffix):
    patient = create(admin_client)
    profile, client = member
    grant(
        profile,
        has_patient_access=True,
        can_record_patient_outcomes=True,
        has_patient_finance_access=True,
    )
    contact = Contact.objects.get(pk=patient["contact"])
    assert not has_contact_access(profile, contact)
    assert client.get(BASE).data["results"] == []
    assert client.get(f"{BASE}{patient['id']}/{suffix}").status_code in (403, 404)
    assert (
        record(client, patient, "events", kind="treated", occurred_at=DATE).status_code
        == 403
    )
    assert client.get(f"/api/contacts/{contact.id}/").status_code == 403
    assert ContactLinkSerializer(contact, context={"profile": profile}).data == {
        "restricted": True
    }


def test_patient_read_outcomes_and_finance_are_independent(admin_client, member):
    patient = create(admin_client)
    profile, client = member
    contact = Contact.objects.get(pk=patient["contact"])
    contact.assigned_to.add(profile)
    # Even contact assignment alone cannot grant patient information.
    assert client.get(f"/api/contacts/{contact.id}/").status_code == 403
    grant(profile, has_patient_access=True)
    detail = client.get(f"{BASE}{patient['id']}/")
    assert detail.status_code == 200
    assert client.get(f"/api/contacts/{contact.id}/").data["contact_obj"]["id"] == str(
        contact.id
    )
    for key in ("receipts", "net_revenue", "corrections", "exclusions"):
        assert key not in detail.data
    assert client.get(f"{BASE}{patient['id']}/events/").status_code == 200
    assert client.get(f"{BASE}{patient['id']}/receipts/").status_code == 403
    assert (
        record(client, patient, "events", kind="treated", occurred_at=DATE).status_code
        == 403
    )
    grant(profile, can_record_patient_outcomes=True)
    assert (
        record(client, patient, "events", kind="treated", occurred_at=DATE).status_code
        == 201
    )
    assert (
        record(
            client,
            patient,
            "receipts",
            kind="payment",
            amount="5",
            reference="denied",
            occurred_at=DATE,
        ).status_code
        == 403
    )
    grant(profile, has_patient_finance_access=True, can_record_patient_outcomes=False)
    assert client.get(f"{BASE}{patient['id']}/receipts/").status_code == 200
    assert "net_revenue" in client.get(f"{BASE}{patient['id']}/").data
    assert (
        record(client, patient, "events", kind="treated", occurred_at=DATE).status_code
        == 403
    )
    # Administrator-only reconciliation/export policy stays narrower than receipt read.
    assert client.get(f"{BASE}{patient['id']}/statement/").status_code == 403


@pytest.mark.parametrize("scopes", [[], ["*:read", "*:write"], ["contacts:read"]])
def test_broad_admin_pat_does_not_implicitly_gain_patients(
    admin_client, admin_profile, scopes
):
    patient = create(admin_client)
    raw, _ = PersonalAccessToken.generate(
        profile=admin_profile, name="test", scopes=scopes
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
    assert client.get(BASE).status_code == 403
    assert client.get(f"{BASE}{patient['id']}/receipts/").status_code == 403
    assert (
        record(client, patient, "events", kind="treated", occurred_at=DATE).status_code
        == 403
    )
    assert client.get(f"/api/contacts/{patient['contact']}/").status_code == 403


def test_explicit_pat_still_obeys_member_and_contact_permissions(
    admin_client, member, org_b_client
):
    patient = create(admin_client)
    other = create(org_b_client)
    profile, _ = member
    raw, _ = PersonalAccessToken.generate(
        profile=profile, name="test", scopes=["patients:read", "patients:write"]
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
    assert client.get(BASE).status_code == 403
    grant(profile, has_patient_access=True, can_record_patient_outcomes=True)
    assert client.get(BASE).data["results"] == []
    assert client.get(f"{BASE}{patient['id']}/").status_code == 403
    Contact.objects.get(pk=patient["contact"]).assigned_to.add(profile)
    assert client.get(f"{BASE}{patient['id']}/").status_code == 200
    assert (
        record(client, patient, "events", kind="treated", occurred_at=DATE).status_code
        == 201
    )
    assert client.get(f"{BASE}{other['id']}/").status_code == 404
    assert (
        client.post(BASE, {"contact": other["contact"]}, format="json").status_code
        == 400
    )
    assert client.get(BASE + "attribution/").status_code in (401, 403)


def test_org_key_is_not_a_patient_administrator(admin_client, org_a):
    patient = create(admin_client)
    client = APIClient()
    client.credentials(HTTP_TOKEN=str(org_a.api_key))
    assert client.get(BASE).status_code == 403
    assert client.get(f"/api/contacts/{patient['contact']}/").status_code == 403


def test_patient_capabilities_cannot_be_self_granted(member):
    profile, client = member
    values = {
        "has_patient_access": True,
        "can_record_patient_outcomes": True,
        "has_patient_finance_access": True,
    }
    serializer = CreateProfileSerializer(profile, data=values, partial=True)
    assert not serializer.is_valid()
    assert set(serializer.errors) == set(values)
    response = client.patch("/api/profile/", values, format="json")
    assert response.status_code in (200, 400)
    profile.refresh_from_db()
    assert (
        not profile.has_patient_access
        and not profile.can_record_patient_outcomes
        and not profile.has_patient_finance_access
    )
    authorized = CreateProfileSerializer(
        profile, data=values, partial=True, can_grant_privileges=True
    )
    assert authorized.is_valid(), authorized.errors
    authorized.save()
    assert profile.has_patient_access


def test_alternate_task_invoice_and_search_routes(admin_client, member, org_a):
    from patients.tests.test_billing import invoice
    from tasks.models import Task

    patient = create(admin_client)
    profile, client = member
    contact = Contact.objects.get(pk=patient["contact"])
    contact.assigned_to.add(profile)
    task = Task.objects.create(
        org=org_a,
        title="Protected outcome",
        created_by=profile.user,
        status="New",
        priority="Medium",
    )
    task.contacts.add(contact)
    task.assigned_to.add(profile)
    bill = invoice(org_a, patient, created_by=profile.user)
    assert client.get(f"/api/tasks/{task.id}/").status_code == 403
    assert client.get(f"/api/invoices/{bill.id}/").status_code == 403
    assert client.get("/api/invoices/").data["count"] == 0
    results = client.get("/api/search/?q=Alex").data["results"]
    assert not any(row["id"] == str(contact.id) for row in results)
    # Patient identity/outcome access must still not unlock financial documents.
    grant(profile, has_patient_access=True)
    assert client.get(f"/api/invoices/{bill.id}/").status_code == 403
    grant(profile, has_patient_finance_access=True)
    assert client.get(f"/api/invoices/{bill.id}/").status_code == 200
    assert client.put(f"/api/invoices/{bill.id}/", {}, format="json").status_code == 403


@pytest.mark.parametrize("scopes", [[], ["*:write"], ["users:write", "user:write"]])
def test_pat_cannot_grant_practice_capabilities(admin_profile, member, scopes):
    profile, _ = member
    raw, _ = PersonalAccessToken.generate(
        profile=admin_profile, name="test", scopes=scopes
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
    assert (
        client.patch(
            f"/api/user/{profile.pk}/", {"has_patient_access": True}, format="json"
        ).status_code
        == 403
    )
    profile.refresh_from_db()
    assert not profile.has_patient_access


def test_patient_read_scope_cannot_be_used_for_shared_contact_writes(
    admin_client, admin_profile
):
    patient = create(admin_client)
    raw, token = PersonalAccessToken.generate(
        profile=admin_profile,
        name="read patient, write CRM",
        scopes=["patients:read", "*:read", "*:write"],
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
    url = f"/api/contacts/{patient['contact']}/"
    assert client.get(url).status_code == 200
    assert (
        client.patch(url, {"first_name": "Changed"}, format="json").status_code == 403
    )
    contact = Contact.objects.get(pk=patient["contact"])
    assert contact.first_name != "Changed"
    token.scopes.append("patients:write")
    token.save(update_fields=["scopes"])
    assert (
        client.patch(url, {"first_name": "Changed"}, format="json").status_code == 200
    )
    contact.refresh_from_db()
    assert contact.first_name == "Changed"
