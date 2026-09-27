from common.testing import rls_org
from contacts.models import Contact

BASE = "/api/patients/"


def test_lookup_matches_full_name_email_and_existing_journey(admin_client, org_a):
    contact = Contact.objects.create(
        org=org_a,
        first_name="Alex",
        last_name="Rivera",
        email="alex@example.invalid",
        description="Private notes not returned",
    )
    other = Contact.objects.create(org=org_a, first_name="Alex", last_name="Smith")
    journey = admin_client.post(BASE, {"contact": str(contact.id)}, format="json")
    assert journey.status_code == 201
    response = admin_client.get(BASE + "contacts/", {"search": "  ALEX Rivera  "})
    assert response.status_code == 200
    assert response.data == {
        "results": [
            {
                "id": str(contact.id),
                "name": "Alex Rivera",
                "email": contact.email,
                "is_active": True,
                "patient_id": journey.data["id"],
            }
        ],
        "has_more": False,
    }
    assert (
        admin_client.get(BASE + "contacts/", {"search": "alex@example"}).data
        == response.data
    )
    result = admin_client.get(BASE + "contacts/", {"search": "Smith"}).data["results"][
        0
    ]
    assert result["id"] == str(other.id) and result["patient_id"] is None
    assert Contact.objects.filter(org=org_a).count() == 2


def test_lookup_is_tenant_scoped_and_membership_required(
    admin_client,
    user_client,
    org_b_client,
    org_a,
    org_b,
    user_profile,
    unauthenticated_client,
):
    with rls_org(org_a):
        own = Contact.objects.create(
            org=org_a,
            first_name="Shared",
            last_name="Name",
            created_by=user_profile.user,
        )
    with rls_org(org_b):
        foreign = Contact.objects.create(
            org=org_b, first_name="Shared", last_name="Name"
        )
    for client, expected in (
        (admin_client, own),
        (user_client, own),
        (org_b_client, foreign),
    ):
        response = client.get(
            BASE + "contacts/", {"search": "Shared", "org": str(org_b.id)}
        )
        assert response.status_code == 200
        assert [row["id"] for row in response.data["results"]] == [str(expected.id)]
    assert (
        admin_client.post(BASE, {"contact": str(foreign.id)}, format="json").status_code
        == 400
    )
    assert unauthenticated_client.get(
        BASE + "contacts/", {"search": "Shared"}
    ).status_code in (401, 403)
    user_profile.is_active = False
    user_profile.save()
    assert user_client.get(BASE + "contacts/", {"search": "Shared"}).status_code == 403


def test_lookup_bounded_and_inactive_identity_visible(admin_client, org_a):
    Contact.objects.bulk_create(
        [
            Contact(
                org=org_a,
                first_name="Fictional",
                last_name=f"Person {index:02}",
                is_active=index != 0,
            )
            for index in range(26)
        ]
    )
    response = admin_client.get(BASE + "contacts/", {"search": "Fictional"})
    assert response.status_code == 200
    assert len(response.data["results"]) == 25 and response.data["has_more"]
    assert response.data["results"][0]["is_active"] is False
    for query in ("", "a", " " * 5, "a" * 101):
        assert (
            admin_client.get(BASE + "contacts/", {"search": query}).status_code == 400
        )
    response = admin_client.get(BASE + "contacts/", {"search": "No match"})
    assert response.data == {"results": [], "has_more": False}


def test_lookup_does_not_expand_contact_permissions(admin_client, user_client, org_a):
    restricted = Contact.objects.create(
        org=org_a, first_name="Restricted", last_name="Identity"
    )
    assert (
        len(
            admin_client.get(BASE + "contacts/", {"search": "Restricted"}).data[
                "results"
            ]
        )
        == 1
    )
    assert (
        user_client.get(BASE + "contacts/", {"search": "Restricted"}).data["results"]
        == []
    )

    assert (
        user_client.post(
            BASE, {"contact": str(restricted.id)}, format="json"
        ).status_code
        == 400
    )
