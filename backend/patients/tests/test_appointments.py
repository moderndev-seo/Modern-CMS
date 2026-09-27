from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from common.testing import rls_org
from patients.models import Appointment, AppointmentChange, JourneyEvent
from patients.tests.test_journey import BASE, create


def payload(**overrides):
    start = timezone.now() + timedelta(days=1)
    return {
        "request_id": str(uuid4()),
        "title": "Fictional consultation",
        "location": "Demo room",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(minutes=30)).isoformat(),
        **overrides,
    }


def book(client, patient, values=None):
    response = client.post(
        f"{BASE}{patient['id']}/appointments/", values or payload(), format="json"
    )
    assert response.status_code == 201, response.data
    return response.data


def detail_url(patient, appointment):
    return f"{BASE}{patient['id']}/appointments/{appointment['id']}/"


def change(client, patient_record, appointment, action, **overrides):
    return client.patch(
        detail_url(patient_record, appointment),
        {
            "action": action,
            "revision": appointment["revision"],
            "reason": "Fictional workflow check",
            **overrides,
        },
        format="json",
    )


def test_booking_retry_reschedule_conflict_and_cancel_history(admin_client):
    patient = create(admin_client)
    values = payload()
    appointment = book(admin_client, patient, values)
    retry = admin_client.post(
        f"{BASE}{patient['id']}/appointments/", values, format="json"
    )
    assert retry.status_code == 200 and retry.data["id"] == appointment["id"]
    assert Appointment.objects.count() == AppointmentChange.objects.count() == 1
    assert JourneyEvent.objects.filter(kind="booked").count() == 1
    assert (
        admin_client.post(
            f"{BASE}{patient['id']}/appointments/",
            {**values, "title": "Different"},
            format="json",
        ).status_code
        == 409
    )
    start = timezone.now() + timedelta(days=2)
    moved = change(
        admin_client,
        patient,
        appointment,
        "rescheduled",
        starts_at=start.isoformat(),
        ends_at=(start + timedelta(minutes=45)).isoformat(),
    )
    assert moved.status_code == 200 and moved.data["revision"] == 2
    assert change(admin_client, patient, appointment, "cancelled").status_code == 409
    cancelled = change(admin_client, patient, moved.data, "cancelled")
    assert cancelled.status_code == 200 and cancelled.data["status"] == "cancelled"
    assert change(admin_client, patient, cancelled.data, "attended").status_code == 409
    history = admin_client.get(detail_url(patient, appointment)).data["history"]
    assert [row["action"] for row in history] == ["booked", "rescheduled", "cancelled"]
    assert history[1]["before"]["starts_at"] != history[1]["after"]["starts_at"]
    assert all(row["actor"] and row["reason"] for row in history)
    assert JourneyEvent.objects.count() == 1
    assert admin_client.delete(detail_url(patient, appointment)).status_code == 405


def test_attendance_and_no_show_use_actual_time_and_preserve_revenue(admin_client):
    patient = create(admin_client)
    appointment = book(admin_client, patient)
    assert change(admin_client, patient, appointment, "attended").status_code == 400
    stored = Appointment.objects.get(pk=appointment["id"])
    with patch(
        "patients.appointments.timezone.now",
        return_value=stored.starts_at + timedelta(minutes=1),
    ):
        attended = change(admin_client, patient, appointment, "attended")
    assert attended.status_code == 200
    event = JourneyEvent.objects.get(kind="attended")
    assert event.occurred_at == stored.starts_at + timedelta(minutes=1)
    assert change(admin_client, patient, attended.data, "attended").status_code == 409
    other = book(
        admin_client,
        patient,
        payload(
            starts_at=(stored.starts_at + timedelta(days=1)).isoformat(),
            ends_at=(stored.ends_at + timedelta(days=1)).isoformat(),
        ),
    )
    assert change(admin_client, patient, other, "no_show").status_code == 400
    with patch(
        "patients.appointments.timezone.now",
        return_value=stored.ends_at + timedelta(days=1, minutes=1),
    ):
        assert change(admin_client, patient, other, "no_show").status_code == 200
    report = admin_client.get(
        BASE + "growth/",
        {
            "start": timezone.now().date().isoformat(),
            "end": (timezone.now() + timedelta(days=3)).date().isoformat(),
        },
    ).data
    assert report["totals"]["booked"] == 1
    assert report["totals"]["treated"] == 0 and report["totals"]["net_revenue"] == 0
    assert JourneyEvent.objects.filter(kind="attended").count() == 1


def test_slots_validation_and_same_patient_overlap(admin_client):
    patient = create(admin_client)
    values = payload()
    appointment = book(admin_client, patient, values)
    assert (
        admin_client.post(
            f"{BASE}{patient['id']}/appointments/",
            {**values, "request_id": str(uuid4())},
            format="json",
        ).status_code
        == 409
    )
    other = create(admin_client)
    book(admin_client, other, {**values, "request_id": str(uuid4())})
    first = Appointment.objects.get(id=appointment["id"])
    adjacent = payload(
        starts_at=first.ends_at.isoformat(),
        ends_at=(first.ends_at + timedelta(minutes=30)).isoformat(),
    )
    book(admin_client, patient, adjacent)
    assert (
        change(
            admin_client,
            patient,
            appointment,
            "rescheduled",
            starts_at=adjacent["starts_at"],
            ends_at=adjacent["ends_at"],
        ).status_code
        == 409
    )

    for changes in (
        {"ends_at": values["starts_at"]},
        {"starts_at": "2020-01-01T00:00:00Z"},
        {"org": str(uuid4())},
        {"patient": other["id"]},
        {"status": "attended"},
        {"revision": 9},
    ):
        response = admin_client.post(
            f"{BASE}{patient['id']}/appointments/",
            {**values, "request_id": str(uuid4()), **changes},
            format="json",
        )
        assert response.status_code == 400, response.data
    assert (
        change(admin_client, patient, appointment, "cancelled", reason="").status_code
        == 400
    )
    assert (
        change(
            admin_client, patient, appointment, "cancelled", patient=other["id"]
        ).status_code
        == 400
    )
    assert change(admin_client, patient, appointment, "rescheduled").status_code == 400


def test_appointment_permissions_and_cross_practice_links(
    admin_client, user_client, org_b_client, unauthenticated_client
):
    patient = create(admin_client)
    appointment = book(admin_client, patient)
    other = create(org_b_client)
    for client in (user_client, org_b_client):
        assert client.get(detail_url(patient, appointment)).status_code in (403, 404)
        assert change(client, patient, appointment, "cancelled").status_code in (
            403,
            404,
        )
        assert client.post(
            f"{BASE}{patient['id']}/appointments/", payload(), format="json"
        ).status_code in (403, 404)
    assert org_b_client.get(detail_url(other, appointment)).status_code == 404
    assert org_b_client.get(f"{BASE}{other['id']}/appointments/").data["results"] == []
    assert unauthenticated_client.get(detail_url(patient, appointment)).status_code in (
        401,
        403,
    )
    own = create(user_client)
    book(user_client, own)


@pytest.mark.postgres_only
def test_appointment_database_rls_links_and_immutable_history(
    admin_client, org_b_client, org_a, org_b
):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    patient = create(admin_client)
    appointment = book(admin_client, patient)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )
        assert cursor.fetchone() == (False, False)
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('mp_appointment','mp_appointment_change')"
        )
        assert cursor.fetchall() == [(True, True), (True, True)]
    with rls_org(org_b):
        assert not Appointment.objects.filter(id=appointment["id"]).exists()
        assert not AppointmentChange.objects.exists()
        with pytest.raises(IntegrityError), transaction.atomic():
            AppointmentChange.objects.create(
                org=org_b,
                appointment_id=appointment["id"],
                action="booked",
                reason="Forged",
            )
        with pytest.raises(IntegrityError), transaction.atomic():
            Appointment.objects.create(org=org_b, patient_id=patient["id"], **payload())
        with (
            pytest.raises(IntegrityError, match="same practice"),
            transaction.atomic(),
        ):
            Appointment.objects.create(org=org_a, patient_id=patient["id"], **payload())
    with rls_org(org_a):
        audit = AppointmentChange.objects.get(appointment_id=appointment["id"])
        with pytest.raises(IntegrityError, match="append-only"), transaction.atomic():
            AppointmentChange.objects.filter(id=audit.id).update(reason="Overwrite")
        with pytest.raises(IntegrityError, match="append-only"), transaction.atomic():
            audit.delete()
        with pytest.raises(IntegrityError, match="immutable"), transaction.atomic():
            Appointment.objects.filter(id=appointment["id"]).update(request_id=uuid4())


def test_admin_reopens_cancellation_without_rewriting_history_or_growth(admin_client):
    patient = create(admin_client)
    appointment = book(admin_client, patient)
    cancelled = change(admin_client, patient, appointment, "cancelled").data
    url = detail_url(patient, appointment)
    original_history = admin_client.get(url).data["history"]
    assert admin_client.get(url).data["can_reopen"] is True
    report_params = {
        "start": timezone.now().date().isoformat(),
        "end": (timezone.now() + timedelta(days=3)).date().isoformat(),
    }
    before = admin_client.get(BASE + "growth/", report_params).data
    slot = payload()
    times = {key: slot[key] for key in ("starts_at", "ends_at")}
    reopened = change(admin_client, patient, cancelled, "reopened", **times)
    assert reopened.status_code == 200, reopened.data
    assert reopened.data["status"] == "scheduled" and reopened.data["revision"] == 3
    detail = admin_client.get(url).data
    assert detail["can_reopen"] is False
    assert detail["history"][:2] == original_history
    correction = detail["history"][-1]
    assert correction["action"] == "reopened"
    assert correction["before"]["status"] == "cancelled"
    assert correction["after"]["status"] == "scheduled"
    assert correction["reason"] and correction["actor"]
    assert JourneyEvent.objects.filter(kind="booked").count() == 1
    assert admin_client.get(BASE + "growth/", report_params).data == before
    assert (
        change(admin_client, patient, cancelled, "reopened", **times).status_code == 409
    )
    assert AppointmentChange.objects.count() == 3


def test_reopening_requires_admin_valid_future_slot_and_closed_outcome(
    admin_client, user_client, org_b_client
):
    patient = create(user_client)
    appointment = book(user_client, patient)
    cancelled = change(user_client, patient, appointment, "cancelled").data
    slot = payload()
    times = {key: slot[key] for key in ("starts_at", "ends_at")}
    assert user_client.get(detail_url(patient, appointment)).data["can_reopen"] is False
    assert (
        change(user_client, patient, cancelled, "reopened", **times).status_code == 403
    )
    assert (
        change(org_b_client, patient, cancelled, "reopened", **times).status_code == 404
    )
    foreign_patient = create(org_b_client)
    assert (
        change(
            org_b_client, foreign_patient, cancelled, "reopened", **times
        ).status_code
        == 404
    )
    assert change(admin_client, patient, cancelled, "reopened").status_code == 400
    assert (
        change(
            admin_client, patient, cancelled, "reopened", **times, reason=" "
        ).status_code
        == 400
    )
    assert (
        change(
            admin_client,
            patient,
            cancelled,
            "reopened",
            starts_at="2020-01-01T10:00:00Z",
            ends_at="2020-01-01T11:00:00Z",
        ).status_code
        == 400
    )
    assert (
        change(
            admin_client, patient, cancelled, "reopened", **times, patient=str(uuid4())
        ).status_code
        == 400
    )
    book(admin_client, patient, slot)
    assert (
        change(admin_client, patient, cancelled, "reopened", **times).status_code == 409
    )
    assert Appointment.objects.get(id=appointment["id"]).status == "cancelled"
    assert (
        AppointmentChange.objects.filter(appointment_id=appointment["id"]).count() == 2
    )


def test_reopen_no_show_then_attend_but_never_reverse_attendance(admin_client):
    patient = create(admin_client)
    appointment = book(admin_client, patient)
    stored = Appointment.objects.get(pk=appointment["id"])
    after_end = stored.ends_at + timedelta(minutes=1)
    with patch("patients.appointments.timezone.now", return_value=after_end):
        no_show = change(admin_client, patient, appointment, "no_show").data
        new_start = after_end + timedelta(days=1)
        times = {
            "starts_at": new_start.isoformat(),
            "ends_at": (new_start + timedelta(minutes=30)).isoformat(),
        }
        reopened = change(admin_client, patient, no_show, "reopened", **times)
        assert reopened.status_code == 200
        assert (
            change(
                admin_client, patient, reopened.data, "reopened", **times
            ).status_code
            == 409
        )
    with patch("patients.appointments.timezone.now", return_value=new_start):
        attended = change(admin_client, patient, reopened.data, "attended")
        assert attended.status_code == 200
        assert (
            change(
                admin_client, patient, attended.data, "reopened", **times
            ).status_code
            == 409
        )
    assert JourneyEvent.objects.filter(kind="booked").count() == 1
    assert JourneyEvent.objects.filter(kind="attended").count() == 1
    assert [
        row["action"]
        for row in admin_client.get(detail_url(patient, appointment)).data["history"]
    ] == ["booked", "no_show", "reopened", "attended"]
