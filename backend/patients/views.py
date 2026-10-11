from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasOrgContext, is_org_admin
from contacts.access import (
    assert_contact_access,
    has_contact_access,
    visible_contacts_qs,
)
from patients.models import JourneyEvent, MarketingSpend, Patient, Receipt
from patients.reporting import growth_report
from patients.serializers import (
    EventSerializer,
    FollowupSerializer,
    PatientSerializer,
    ReceiptSerializer,
    SpendSerializer,
)
from tasks.access import visible_tasks_qs
from tasks.models import Task


class PracticeView(APIView):
    permission_classes = [IsAuthenticated, HasOrgContext]

    def patient(self, request, pk):
        return get_object_or_404(
            Patient.objects.select_related("contact"),
            pk=pk,
            org=request.profile.org,
            contact__org=request.profile.org,
        )

    def require_admin(self, request):
        if not is_org_admin(request.profile):
            raise PermissionDenied(
                "Only practice administrators may record payments, refunds, or spend."
            )


class ContactSearch(PracticeView):
    """Bounded intake lookup; never expose another practice's identities."""

    def get(self, request):
        query = request.query_params.get("search", "").strip()
        if not 2 <= len(query) <= 100:
            raise ValidationError({"search": "Enter between 2 and 100 characters."})
        contacts = visible_contacts_qs(request.profile)
        for word in query.split():
            contacts = contacts.filter(
                Q(first_name__icontains=word)
                | Q(last_name__icontains=word)
                | Q(email__icontains=word)
            )
        matches = list(contacts.order_by("first_name", "last_name", "id")[:26])
        journeys = {
            patient.contact_id: str(patient.id)
            for patient in Patient.objects.filter(
                org=request.profile.org,
                contact__org=request.profile.org,
                contact_id__in=[contact.id for contact in matches[:25]],
            )
        }
        return Response(
            {
                "results": [
                    {
                        "id": str(contact.id),
                        "name": f"{contact.first_name} {contact.last_name}".strip(),
                        "email": contact.email or "",
                        "is_active": contact.is_active,
                        "patient_id": journeys.get(contact.id),
                    }
                    for contact in matches[:25]
                ],
                "has_more": len(matches) > 25,
            }
        )


class PatientList(PracticeView):
    def get(self, request):
        queryset = (
            Patient.objects.filter(
                org=request.profile.org, contact__org=request.profile.org
            )
            .select_related("contact")
            .order_by("-lead_at")
        )
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(contact__first_name__icontains=search)
                | Q(contact__last_name__icontains=search)
                | Q(contact__email__icontains=search)
            )
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except ValueError:
            raise ValidationError({"page": "Use a positive integer."}) from None
        return Response(
            {
                "count": queryset.count(),
                "page": page,
                "page_size": 50,
                "results": PatientSerializer(
                    queryset[(page - 1) * 50 : page * 50],
                    many=True,
                    context={"request": request},
                ).data,
            }
        )

    def post(self, request):
        serializer = PatientSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save(org=request.profile.org, created_by=request.user)
        except IntegrityError:
            raise ValidationError(
                "That contact or email already has a record in this practice."
            ) from None
        return Response(serializer.data, status=201)


class PatientDetail(PracticeView):
    def get(self, request, pk):
        patient = self.patient(request, pk)
        events = JourneyEvent.objects.filter(
            org=request.profile.org, patient=patient
        ).order_by("occurred_at", "created_at")
        receipts = Receipt.objects.filter(
            org=request.profile.org, patient=patient
        ).order_by("occurred_at", "created_at")
        data = dict(PatientSerializer(patient, context={"request": request}).data)
        followups = (
            visible_tasks_qs(request.profile)
            .filter(contacts=patient.contact)
            .order_by("-created_at", "id")
        )
        data["followups"] = FollowupSerializer(followups[:50], many=True).data
        data["followup_count"] = followups.count()
        data["can_review_billing"] = is_org_admin(request.profile)
        data["can_create_followup"] = has_contact_access(
            request.profile, patient.contact
        )
        data["events"] = EventSerializer(events, many=True).data
        data["receipts"] = ReceiptSerializer(receipts, many=True).data
        from patients.corrections import correction_history

        data["corrections"] = correction_history(request.profile.org, patient)
        from patients.exclusions import exclusion_history

        data["exclusions"] = exclusion_history(request.profile.org, patient)
        data["net_revenue"] = sum(
            (
                r.amount if r.kind == "payment" else -r.amount
                for r in receipts
                if not r.excluded
            ),
            0,
        )
        return Response(data)


class EventList(PracticeView):
    def get(self, request, pk):
        patient = self.patient(request, pk)
        return Response(
            EventSerializer(
                JourneyEvent.objects.filter(
                    org=request.profile.org, patient=patient
                ).order_by("occurred_at"),
                many=True,
            ).data
        )

    def post(self, request, pk):
        patient = self.patient(request, pk)
        serializer = EventSerializer(data=request.data, context={"patient": patient})
        serializer.is_valid(raise_exception=True)
        serializer.save(
            org=request.profile.org, patient=patient, created_by=request.user
        )
        return Response(serializer.data, status=201)


class ReceiptList(PracticeView):
    def get(self, request, pk):
        patient = self.patient(request, pk)
        return Response(
            ReceiptSerializer(
                Receipt.objects.filter(
                    org=request.profile.org, patient=patient
                ).order_by("occurred_at"),
                many=True,
            ).data
        )

    def post(self, request, pk):
        patient = self.patient(request, pk)
        self.require_admin(request)
        serializer = ReceiptSerializer(data=request.data, context={"patient": patient})
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        payment_id = data.pop("payment", None)
        try:
            with transaction.atomic():
                if payment_id:
                    payment = get_object_or_404(
                        Receipt.objects.select_for_update(),
                        pk=payment_id,
                        org=request.profile.org,
                        patient=patient,
                        kind="payment",
                        excluded=False,
                    )
                    if data.get("occurred_at", timezone.now()) < payment.occurred_at:
                        raise ValidationError(
                            {"occurred_at": "A refund cannot precede its payment."}
                        )
                    refunded = (
                        Receipt.objects.filter(
                            org=request.profile.org, payment=payment
                        ).aggregate(total=Sum("amount"))["total"]
                        or 0
                    )
                    if data["amount"] > payment.amount - refunded:
                        raise ValidationError(
                            {"amount": "Refund exceeds the unrefunded payment balance."}
                        )
                    data["payment"] = payment
                receipt = Receipt.objects.create(
                    org=request.profile.org,
                    patient=patient,
                    created_by=request.user,
                    **data,
                )
        except IntegrityError:
            raise ValidationError(
                {
                    "reference": "This reference already exists in this practice. Nothing was recorded twice."
                }
            ) from None
        return Response(ReceiptSerializer(receipt).data, status=201)


class Growth(PracticeView):
    def get(self, request):
        today = timezone.now().date()
        field = serializers.DateField()
        start = field.run_validation(
            request.query_params.get("start", str(today.replace(day=1)))
        )
        end = field.run_validation(request.query_params.get("end", str(today)))
        if start > end or end.year >= 9999 or end - start > timedelta(days=3660):
            raise ValidationError("Choose an ordered date range of at most ten years.")
        return Response(growth_report(request.profile.org, start, end))


class Spend(PracticeView):
    def put(self, request):
        self.require_admin(request)
        serializer = SpendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        record, _ = MarketingSpend.objects.update_or_create(
            org=request.profile.org,
            source=data["source"],
            date=data["date"],
            defaults={"amount": data["amount"], "updated_by": request.user},
            create_defaults={"amount": data["amount"], "created_by": request.user},
        )
        return Response(SpendSerializer(record).data)


class FollowupList(PracticeView):
    def post(self, request, pk):
        patient = self.patient(request, pk)
        assert_contact_access(request.profile, patient.contact)
        serializer = FollowupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            task = serializer.save(
                org=request.profile.org, created_by=request.user, status="New"
            )
            task.contacts.add(patient.contact)
            task.assigned_to.add(request.profile)
        return Response(FollowupSerializer(task).data, status=201)


class FollowupStatus(PracticeView):
    def patch(self, request, pk, task_pk):
        patient = self.patient(request, pk)
        task = get_object_or_404(
            visible_tasks_qs(request.profile), pk=task_pk, contacts=patient.contact
        )
        if set(request.data) != {"status"}:
            raise ValidationError(
                "Only status can be changed here. Use Tasks for other edits."
            )
        field = serializers.ChoiceField(choices=Task.STATUS_CHOICES)
        task.status = field.run_validation(request.data["status"])
        task.updated_by = request.user
        task.save(update_fields=["status", "updated_by", "updated_at"])
        return Response(FollowupSerializer(task).data)
