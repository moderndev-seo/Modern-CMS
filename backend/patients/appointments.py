"""Operational scheduling, with immutable history and explicit journey events."""

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response

from common.permissions import is_org_admin
from contacts.access import assert_contact_access
from patients.models import Appointment, AppointmentChange, JourneyEvent, Patient
from patients.serializers import StrictSerializer
from patients.views import PracticeView


class Conflict(APIException):
    status_code = 409
    default_detail = "This appointment changed. Reload and try again."


class AppointmentSerializer(StrictSerializer):
    class Meta:
        model = Appointment
        fields = [
            "id",
            "request_id",
            "title",
            "location",
            "starts_at",
            "ends_at",
            "status",
            "revision",
        ]
        read_only_fields = ["id", "status", "revision"]
        validators = []

    def validate(self, attrs):
        if attrs["ends_at"] <= attrs["starts_at"]:
            raise ValidationError({"ends_at": "End must be after start."})
        return attrs


class ChangeSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=["rescheduled", "cancelled", "attended", "no_show", "reopened"]
    )
    revision = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=1000)
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)

    def to_internal_value(self, data):
        if set(data) - set(self.fields):
            raise ValidationError(
                {
                    "non_field_errors": "Unsupported fields. Patient, practice, and audit fields cannot be changed."
                }
            )
        return super().to_internal_value(data)

    def validate(self, attrs):
        if attrs["action"] in ("rescheduled", "reopened"):
            if "starts_at" not in attrs or "ends_at" not in attrs:
                raise ValidationError(
                    "Rescheduling or reopening requires both start and end."
                )
            if attrs["ends_at"] <= attrs["starts_at"]:
                raise ValidationError("End must be after start.")
        elif "starts_at" in attrs or "ends_at" in attrs:
            raise ValidationError(
                "Times can only be changed by rescheduling or reopening."
            )
        return attrs


def snapshot(appointment):
    return {
        "starts_at": appointment.starts_at.isoformat(),
        "ends_at": appointment.ends_at.isoformat(),
        "status": appointment.status,
        "revision": appointment.revision,
    }


def audit(request, appointment, action, reason, before):
    event = None
    if action in ("booked", "attended"):
        event = JourneyEvent.objects.create(
            org=request.profile.org,
            patient=appointment.patient,
            created_by=request.user,
            kind=action,
            occurred_at=timezone.now(),
            notes=f"Appointment {appointment.id}: {appointment.title}",
        )
    AppointmentChange.objects.create(
        org=request.profile.org,
        appointment=appointment,
        created_by=request.user,
        action=action,
        reason=reason,
        before=before,
        after=snapshot(appointment),
        journey_event=event,
    )


def require_slot(patient, start, end, exclude=None):
    if start <= timezone.now():
        raise ValidationError({"starts_at": "Choose a future appointment time (UTC)."})
    existing = Appointment.objects.filter(
        org=patient.org,
        patient=patient,
        status="scheduled",
        starts_at__lt=end,
        ends_at__gt=start,
    )
    if exclude:
        existing = existing.exclude(pk=exclude)
    if existing.exists():
        raise Conflict(
            "This patient already has a scheduled appointment during that time."
        )


def existing_response(existing, patient, values):
    if existing.patient_id != patient.id or any(
        getattr(existing, field) != values.get(field, "")
        for field in ("title", "location", "starts_at", "ends_at")
    ):
        raise Conflict(
            "This booking request was already used. Reload before creating a different appointment."
        )
    return Response(AppointmentSerializer(existing).data)


class AppointmentList(PracticeView):
    def get(self, request, pk):
        patient = self.patient(request, pk)
        assert_contact_access(request.profile, patient.contact)
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except ValueError:
            raise ValidationError({"page": "Use a positive integer."}) from None
        appointments = Appointment.objects.filter(
            org=request.profile.org, patient=patient
        ).order_by("-starts_at", "id")
        return Response(
            {
                "count": appointments.count(),
                "page": page,
                "page_size": 20,
                "results": AppointmentSerializer(
                    appointments[(page - 1) * 20 : page * 20], many=True
                ).data,
            }
        )

    def post(self, request, pk):
        patient = self.patient(request, pk)
        assert_contact_access(request.profile, patient.contact)
        serializer = AppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            with transaction.atomic():
                # One lock order for booking and rescheduling prevents competing slots for this patient.
                Patient.objects.select_for_update().get(
                    pk=patient.pk, org=request.profile.org
                )
                existing = Appointment.objects.filter(
                    org=request.profile.org, request_id=values["request_id"]
                ).first()
                if existing:
                    return existing_response(existing, patient, values)
                require_slot(patient, values["starts_at"], values["ends_at"])
                appointment = serializer.save(
                    org=request.profile.org, patient=patient, created_by=request.user
                )
                audit(request, appointment, "booked", "Appointment scheduled", {})
        except IntegrityError:
            existing = Appointment.objects.filter(
                org=request.profile.org, request_id=values["request_id"]
            ).first()
            if existing:
                return existing_response(existing, patient, values)
            raise
        return Response(AppointmentSerializer(appointment).data, status=201)


class AppointmentDetail(PracticeView):
    def get(self, request, pk, appointment_pk):
        patient = self.patient(request, pk)
        assert_contact_access(request.profile, patient.contact)
        appointment = get_object_or_404(
            Appointment, pk=appointment_pk, patient=patient, org=request.profile.org
        )
        changes = (
            AppointmentChange.objects.filter(
                org=request.profile.org, appointment=appointment
            )
            .select_related("created_by")
            .order_by("after__revision", "created_at", "id")
        )
        data = dict(AppointmentSerializer(appointment).data)
        data["can_reopen"] = is_org_admin(request.profile) and appointment.status in (
            "cancelled",
            "no_show",
        )
        data["history"] = [
            {
                "id": str(change.id),
                "action": change.action,
                "reason": change.reason,
                "at": change.created_at,
                "actor": change.created_by.email
                if change.created_by
                else "Not recorded",
                "before": change.before,
                "after": change.after,
            }
            for change in changes
        ]
        return Response(data)

    def patch(self, request, pk, appointment_pk):
        patient = self.patient(request, pk)
        assert_contact_access(request.profile, patient.contact)
        serializer = ChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        with transaction.atomic():
            Patient.objects.select_for_update().get(
                pk=patient.pk, org=request.profile.org
            )
            appointment = get_object_or_404(
                Appointment.objects.select_for_update(),
                pk=appointment_pk,
                org=request.profile.org,
                patient=patient,
            )
            if appointment.revision != values["revision"]:
                raise Conflict()
            action = values["action"]
            if action == "reopened":
                if not is_org_admin(request.profile):
                    raise PermissionDenied(
                        "Only practice administrators may reopen appointments."
                    )
                if appointment.status not in ("cancelled", "no_show"):
                    raise Conflict(
                        "Only cancelled or no-show appointments can be reopened. Recorded attendance cannot be corrected here."
                    )
            elif appointment.status != "scheduled":
                raise Conflict(
                    "This appointment is closed. An administrator can reopen cancellations or no-shows."
                )
            before = snapshot(appointment)
            if action in ("rescheduled", "reopened"):
                require_slot(
                    patient,
                    values["starts_at"],
                    values["ends_at"],
                    exclude=appointment.pk,
                )
                if (
                    action == "rescheduled"
                    and appointment.starts_at == values["starts_at"]
                    and appointment.ends_at == values["ends_at"]
                ):
                    raise ValidationError(
                        {"detail": "Choose a different time to reschedule."}
                    )
                appointment.status = "scheduled"
                appointment.starts_at, appointment.ends_at = (
                    values["starts_at"],
                    values["ends_at"],
                )
            else:
                now = timezone.now()
                if action == "attended" and appointment.starts_at > now:
                    raise ValidationError(
                        {
                            "detail": "Attendance cannot be recorded before the scheduled start."
                        }
                    )
                if action == "no_show" and appointment.ends_at > now:
                    raise ValidationError(
                        {
                            "detail": "No-show cannot be recorded before the scheduled end."
                        }
                    )
                appointment.status = action
            appointment.revision += 1
            appointment.updated_by = request.user
            appointment.save()
            audit(request, appointment, action, values["reason"], before)
        return Response(AppointmentSerializer(appointment).data)
