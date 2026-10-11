from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from patients.models import AppointmentChange, JourneyEvent
from patients.tests.test_appointments import book, change, detail_url
from patients.tests.test_journey import BASE, create, report


def test_corrected_attendance_retains_events_and_current_progress(admin_client):
    patient = create(admin_client)
    appointment = book(admin_client, patient)
    before_report = report(admin_client)
    with patch(
        "patients.appointments.timezone.now",
        return_value=timezone.now() + timedelta(days=3),
    ):
        attended = change(admin_client, patient, appointment, "attended").data
        original = list(JourneyEvent.objects.order_by("id").values())
        corrected = change(
            admin_client, patient, attended, "outcome_corrected", outcome="no_show"
        )
        assert corrected.status_code == 200, corrected.data
        events = admin_client.get(f"{BASE}{patient['id']}/").data["events"]
        assert [e["superseded"] for e in events if e["kind"] == "attended"] == [True]
        assert list(JourneyEvent.objects.order_by("id").values()) == original
        assert (
            change(
                admin_client, patient, attended, "outcome_corrected", outcome="no_show"
            ).status_code
            == 409
        )
        restored = change(
            admin_client,
            patient,
            corrected.data,
            "outcome_corrected",
            outcome="attended",
        )
        assert restored.status_code == 200
        events = admin_client.get(f"{BASE}{patient['id']}/events/").data
        assert sorted(e["superseded"] for e in events if e["kind"] == "attended") == [
            False,
            True,
        ]
        cancelled = change(
            admin_client,
            patient,
            restored.data,
            "outcome_corrected",
            outcome="cancelled",
        )
        assert cancelled.status_code == 200
        events = admin_client.get(f"{BASE}{patient['id']}/").data["events"]
        assert all(e["superseded"] for e in events if e["kind"] == "attended")
    assert report(admin_client) == before_report
    changes = admin_client.get(detail_url(patient, appointment)).data["history"]
    assert [c["action"] for c in changes] == [
        "booked",
        "attended",
        "outcome_corrected",
        "outcome_corrected",
        "outcome_corrected",
    ]
    assert all(c["reason"] and c["actor"] for c in changes)


def test_outcome_correction_requires_admin_closed_state_valid_time_and_tenant(
    admin_client, user_client, org_b_client, unauthenticated_client
):
    patient = create(user_client)
    appointment = book(user_client, patient)
    assert (
        change(
            admin_client, patient, appointment, "outcome_corrected", outcome="no_show"
        ).status_code
        == 409
    )
    cancelled = change(user_client, patient, appointment, "cancelled").data
    assert (
        change(
            user_client, patient, cancelled, "outcome_corrected", outcome="attended"
        ).status_code
        == 403
    )
    assert (
        change(
            org_b_client, patient, cancelled, "outcome_corrected", outcome="attended"
        ).status_code
        == 404
    )
    assert change(
        unauthenticated_client,
        patient,
        cancelled,
        "outcome_corrected",
        outcome="attended",
    ).status_code in (401, 403)
    foreign = create(org_b_client)
    assert (
        change(
            org_b_client, foreign, cancelled, "outcome_corrected", outcome="attended"
        ).status_code
        == 404
    )
    for args, status in [
        ({"outcome": "attended"}, 400),
        ({"outcome": "no_show"}, 400),
        ({"outcome": "cancelled"}, 409),
        ({}, 400),
        ({"outcome": "scheduled"}, 400),
        ({"outcome": "attended", "reason": " "}, 400),
    ]:
        assert (
            change(
                admin_client, patient, cancelled, "outcome_corrected", **args
            ).status_code
            == status
        )
    assert AppointmentChange.objects.count() == 2
    assert (
        admin_client.get(detail_url(patient, appointment)).data["can_reopen"]
        is not False
    )
    assert (
        user_client.get(detail_url(patient, appointment)).data["can_correct_outcome"]
        is False
    )
