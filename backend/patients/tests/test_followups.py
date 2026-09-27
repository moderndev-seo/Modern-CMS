from unittest.mock import patch

from common.testing import rls_org
from patients.tests.test_journey import BASE, create, report
from tasks.models import Task


def followup(client, patient, **overrides):
    return client.post(
        f"{BASE}{patient['id']}/tasks/",
        {
            "title": "Fictional follow-up",
            "due_date": "2026-10-05",
            **overrides,
        },
        format="json",
    )


def test_followup_reuses_tasks_and_status_does_not_change_growth(
    user_client, user_profile
):
    patient = create(user_client)
    before = report(user_client)
    with patch("tasks.views.task_views.send_email_to_assigned_user.delay") as notify:
        response = followup(user_client, patient)
        assert response.status_code == 201, response.data
        notify.assert_not_called()
    task = Task.objects.get(id=response.data["id"])
    assert task.status == "New"
    assert list(task.contacts.values_list("id", flat=True)) == [patient["contact"]]
    assert list(task.assigned_to.values_list("id", flat=True)) == [user_profile.id]
    assert task.created_by_id == user_profile.user_id
    for status in ("In Progress", "Completed", "New"):
        response = user_client.patch(
            f"{BASE}{patient['id']}/tasks/{task.id}/", {"status": status}, format="json"
        )
        assert response.status_code == 200, response.data
        task.refresh_from_db()
        assert task.status == status
        assert task.updated_by_id == user_profile.user_id
    detail = user_client.get(f"{BASE}{patient['id']}/").data
    assert detail["followup_count"] == 1
    assert detail["followups"][0]["id"] == str(task.id)
    assert report(user_client) == before


def test_followup_preserves_record_permissions(admin_client, user_client, org_a):
    patient = create(admin_client)
    created = followup(admin_client, patient)
    assert created.status_code == 201
    task_id = created.data["id"]
    detail = user_client.get(f"{BASE}{patient['id']}/").data
    assert detail["followups"] == []
    assert not detail["can_create_followup"]
    assert followup(user_client, patient).status_code == 403
    assert (
        user_client.patch(
            f"{BASE}{patient['id']}/tasks/{task_id}/",
            {"status": "Completed"},
            format="json",
        ).status_code
        == 404
    )
    other = create(admin_client)
    assert (
        admin_client.patch(
            f"{BASE}{other['id']}/tasks/{task_id}/",
            {"status": "Completed"},
            format="json",
        ).status_code
        == 404
    )


def test_followup_tenant_isolation_and_strict_fields(
    admin_client, org_b_client, org_b, unauthenticated_client
):
    patient = create(admin_client)
    other = create(org_b_client)
    result = followup(admin_client, patient)
    assert result.status_code == 201
    task_id = result.data["id"]
    assert followup(org_b_client, patient).status_code == 404
    assert (
        org_b_client.patch(
            f"{BASE}{other['id']}/tasks/{task_id}/",
            {"status": "Completed"},
            format="json",
        ).status_code
        == 404
    )
    for fields in (
        {"org": str(org_b.id)},
        {"contacts": [other["contact"]]},
        {"assigned_to": []},
        {"status": "Completed"},
        {"due_date": None},
        {"due_date": "invalid"},
    ):
        assert followup(admin_client, patient, **fields).status_code == 400
    assert (
        admin_client.patch(
            f"{BASE}{patient['id']}/tasks/{task_id}/",
            {"status": "Completed", "org": str(org_b.id)},
            format="json",
        ).status_code
        == 400
    )
    assert unauthenticated_client.post(
        f"{BASE}{patient['id']}/tasks/", {}, format="json"
    ).status_code in (401, 403)
    with rls_org(org_b):
        assert not Task.objects.filter(id=task_id).exists()
