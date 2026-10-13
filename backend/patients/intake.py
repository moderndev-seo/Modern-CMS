"""Sandbox event ingestion. No public endpoint, vendor verification or outbound calls."""

import hashlib
import json

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from common.permissions import is_org_admin
from patients.models import (
    AttributionConnection,
    AttributionEvent,
    AttributionIdentity,
    Receipt,
)
from patients.serializers import EventSerializer, PatientSerializer, ReceiptSerializer
from patients.views import PracticeView

KINDS = (
    "lead",
    "touch",
    "booked",
    "attended",
    "consultation",
    "treated",
    "payment",
    "refund",
)


class Conflict(APIException):
    status_code = 409
    default_detail = (
        "This external ID already has different facts. Nothing was changed."
    )


class StrictInput(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise ValidationError({"non_field_errors": ["Use a JSON object."]})
        if set(data) - set(self.fields):
            raise ValidationError(
                {
                    "non_field_errors": [
                        "Unsupported fields. Do not supply practice or internal record IDs."
                    ]
                }
            )
        return super().to_internal_value(data)


class ConnectionInput(StrictInput):
    name = serializers.CharField(max_length=100)
    request_id = serializers.UUIDField()


class Envelope(StrictInput):
    event_id = serializers.RegexField(r"^[A-Za-z0-9_.:-]{1,100}$")
    subject_id = serializers.RegexField(r"^[A-Za-z0-9_.:-]{1,100}$")
    kind = serializers.ChoiceField(choices=KINDS)
    data = serializers.DictField()

    def validate(self, attrs):
        if len(json.dumps(attrs, sort_keys=True).encode()) > 16000:
            raise ValidationError("Event exceeds the 16 KB limit.")
        return attrs


def require_sandbox(request):
    if not is_org_admin(request.profile):
        raise PermissionDenied(
            "Only practice administrators can use attribution intake."
        )
    if not request.profile.org.name.startswith("TEST -"):
        raise PermissionDenied(
            "Sandbox intake is restricted to clearly labeled TEST practices."
        )


def result(item, replay=False):
    return {
        "id": str(item.id),
        "event_id": item.external_id,
        "kind": item.kind,
        "patient_id": str(item.identity.patient_id),
        "journey_event_id": str(item.event_id) if item.event_id else None,
        "receipt_id": str(item.receipt_id) if item.receipt_id else None,
        "replayed": replay,
        "evidence": "sandbox",
        "received_at": item.created_at,
    }


def ingest(request, connection_id, body):
    """Serialize a stream and atomically save one event plus its existing CRM record."""
    require_sandbox(request)
    envelope = Envelope(data=body)
    envelope.is_valid(raise_exception=True)
    data = envelope.validated_data
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    try:
        with transaction.atomic():
            stream = get_object_or_404(
                AttributionConnection.objects.select_for_update(),
                pk=connection_id,
                org=request.profile.org,
            )
            previous = (
                AttributionEvent.objects.filter(
                    connection=stream, external_id=data["event_id"]
                )
                .select_related("identity")
                .first()
            )
            if previous:
                if previous.payload_hash != digest:
                    raise Conflict()
                return result(previous, True)
            identity = (
                AttributionIdentity.objects.filter(
                    connection=stream, external_id=data["subject_id"]
                )
                .select_related("patient")
                .first()
            )
            facts = dict(data["data"])
            common = {"org": request.profile.org, "created_by": request.user}
            event = receipt = None
            kind = data["kind"]
            if kind == "lead":
                if identity:
                    raise Conflict(
                        "This subject already has a lead. Submit a touch; original attribution is preserved."
                    )
                if "contact" in facts:
                    raise ValidationError(
                        "Sandbox leads cannot link existing contacts. Use fictional identities."
                    )
                if "lead_at" not in facts:
                    raise ValidationError("lead_at is required for imported leads.")
                serializer = PatientSerializer(data=facts, context={"request": request})
                serializer.is_valid(raise_exception=True)
                patient = serializer.save(**common)
                identity = AttributionIdentity.objects.create(
                    connection=stream,
                    external_id=data["subject_id"],
                    patient=patient,
                    **common,
                )
            else:
                if not identity:
                    raise Conflict(
                        "Unmatched subject. Import its lead first, then retry this event. No patient was guessed."
                    )
                patient = identity.patient
                if "occurred_at" not in facts:
                    raise ValidationError(
                        "occurred_at is required for imported events."
                    )
                if kind in ("payment", "refund"):
                    # No invoice amount, authorization or pending payment can masquerade as collected cash.
                    currency = facts.pop("currency", None)
                    if currency != "USD":
                        raise ValidationError(
                            "Only explicitly denominated USD cash is supported."
                        )
                    if "kind" in facts or "reference" in facts or "payment" in facts:
                        raise ValidationError(
                            "Cash kind, reference and payment links are resolved by the server."
                        )
                    payment_event_id = facts.pop("payment_event_id", None)
                    if (kind == "refund") != bool(payment_event_id):
                        raise ValidationError("Only refunds require payment_event_id.")
                    if payment_event_id is not None and not isinstance(
                        payment_event_id, str
                    ):
                        raise ValidationError("payment_event_id must be a string.")
                    payment = None
                    if kind == "refund":
                        parent = AttributionEvent.objects.filter(
                            connection=stream,
                            identity=identity,
                            external_id=payment_event_id,
                            kind="payment",
                        ).first()
                        if not parent:
                            raise Conflict(
                                "Unmatched original payment. Import it first, then retry the refund."
                            )
                        payment = get_object_or_404(
                            Receipt.objects.select_for_update(),
                            pk=parent.receipt_id,
                            org=request.profile.org,
                            patient=patient,
                            excluded=False,
                        )
                        facts["payment"] = str(payment.id)
                    facts.update(
                        kind=kind,
                        reference=f"INT-{stream.id}-{hashlib.sha256(data['event_id'].encode()).hexdigest()[:40]}",
                    )
                    serializer = ReceiptSerializer(
                        data=facts, context={"patient": patient}
                    )
                    serializer.is_valid(raise_exception=True)
                    cleaned = dict(serializer.validated_data)
                    cleaned.pop("payment", None)
                    if payment:
                        if cleaned["occurred_at"] < payment.occurred_at:
                            raise ValidationError(
                                "A refund cannot precede its payment."
                            )
                        refunded = (
                            Receipt.objects.filter(
                                org=request.profile.org, payment=payment, kind="refund"
                            ).aggregate(total=Sum("amount"))["total"]
                            or 0
                        )
                        if cleaned["amount"] > payment.amount - refunded:
                            raise ValidationError(
                                "Refund exceeds the unrefunded payment balance."
                            )
                    receipt = Receipt.objects.create(
                        patient=patient, payment=payment, **common, **cleaned
                    )
                else:
                    if "kind" in facts:
                        raise ValidationError("Event kind comes from the envelope.")
                    serializer = EventSerializer(
                        data={**facts, "kind": kind}, context={"patient": patient}
                    )
                    serializer.is_valid(raise_exception=True)
                    event = serializer.save(patient=patient, **common)
            item = AttributionEvent.objects.create(
                connection=stream,
                identity=identity,
                external_id=data["event_id"],
                kind=kind,
                payload_hash=digest,
                event=event,
                receipt=receipt,
                **common,
            )
            return result(item)
    except IntegrityError:
        raise ValidationError(
            "Record conflict or invalid cash relationship/budget. Nothing was imported. Review existing records before retrying."
        ) from None


class AttributionConnections(PracticeView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        if not is_org_admin(request.profile):
            raise PermissionDenied(
                "Only practice administrators can inspect attribution intake."
            )
        return Response(
            {
                "sandbox": True,
                "can_write": request.profile.org.name.startswith("TEST -"),
                "connections": list(
                    AttributionConnection.objects.filter(org=request.profile.org)
                    .order_by("created_at")
                    .values("id", "name")
                ),
                "kinds": KINDS,
            }
        )

    def post(self, request):
        require_sandbox(request)
        serializer = ConnectionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        item, created = AttributionConnection.objects.get_or_create(
            org=request.profile.org,
            request_id=serializer.validated_data["request_id"],
            defaults={
                "name": serializer.validated_data["name"],
                "created_by": request.user,
            },
        )
        if item.name != serializer.validated_data["name"]:
            raise Conflict()
        return Response(
            {"id": str(item.id), "name": item.name}, status=201 if created else 200
        )


class AttributionEvents(PracticeView):
    authentication_classes = [JWTAuthentication]

    def get(self, request, connection_pk):
        if not is_org_admin(request.profile):
            raise PermissionDenied(
                "Only practice administrators can inspect attribution intake."
            )
        stream = get_object_or_404(
            AttributionConnection, pk=connection_pk, org=request.profile.org
        )
        field = serializers.IntegerField(min_value=1, max_value=1000000)
        page = field.run_validation(request.query_params.get("page", 1))
        records = (
            AttributionEvent.objects.filter(connection=stream, org=request.profile.org)
            .select_related("identity")
            .order_by("-created_at", "id")
        )
        return Response(
            {
                "connection": {"id": str(stream.id), "name": stream.name},
                "page": page,
                "count": records.count(),
                "page_size": 50,
                "results": [
                    result(item) for item in records[(page - 1) * 50 : page * 50]
                ],
            }
        )

    def post(self, request, connection_pk):
        outcome = ingest(request, connection_pk, request.data)
        return Response(outcome, status=200 if outcome["replayed"] else 201)
