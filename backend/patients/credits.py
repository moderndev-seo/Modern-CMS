"""Audited charge reductions; no receipt, payment or original invoice writes."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from common.permissions import is_org_admin
from contacts.access import assert_contact_access
from invoices.models import Invoice
from patients.appointments import Conflict
from patients.models import InvoiceCreditAdjustment
from patients.views import PracticeView

ZERO = Decimal("0.00")


def credit_snapshot(invoice):
    return {
        "total": str(invoice.total_amount),
        "currency": invoice.currency,
        "contact": str(invoice.contact_id),
        "number": invoice.invoice_number,
    }


def credit_summary(invoice, entries):
    active = [
        entry
        for entry in entries
        if entry.invoice_id == invoice.id
        and not entry.reversal_of_id
        and not hasattr(entry, "reversal")
    ]
    total = sum((entry.amount for entry in active), ZERO)
    eligible = invoice.currency == "USD" and invoice.status not in (
        "Draft",
        "Pending",
        "Cancelled",
    )
    consistent = (
        eligible
        and all(entry.snapshot == credit_snapshot(invoice) for entry in active)
        and total <= invoice.total_amount
    )
    return {
        "active_credits": total,
        "needs_review": bool(active) and not consistent,
        "adjusted_billed": invoice.total_amount - total if consistent else None,
        "can_credit": consistent and total < invoice.total_amount,
    }


class StrictInput(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise ValidationError({"detail": "Unexpected fields supplied."})
        return super().to_internal_value(data)


class CreditInput(StrictInput):
    invoice = serializers.UUIDField()
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    reason = serializers.CharField(max_length=1000)
    request_id = serializers.UUIDField()


class ReverseCreditInput(StrictInput):
    credit = serializers.UUIDField()
    reason = serializers.CharField(max_length=1000)
    request_id = serializers.UUIDField()


class CreditView(PracticeView):
    def credit_patient(self, request, pk):
        patient = self.patient(request, pk)
        if not is_org_admin(request.profile):
            raise PermissionDenied(
                "Only practice administrators may review or change patient billing."
            )
        assert_contact_access(request.profile, patient.contact)
        return patient

    def existing_request(self, org, patient, values, reverse=False):
        existing = InvoiceCreditAdjustment.objects.filter(
            org=org, request_id=values["request_id"]
        ).first()
        if not existing:
            return None
        same = existing.patient_id == patient.id and existing.reason == values["reason"]
        if reverse:
            same = same and existing.reversal_of_id == values["credit"]
        else:
            same = (
                same
                and not existing.reversal_of_id
                and existing.invoice_id == values["invoice"]
                and existing.amount == values["amount"]
            )
        if not same:
            raise Conflict(
                "This request was already used for different credit details. Reload before continuing."
            )
        return Response({"id": str(existing.id), "already_recorded": True})


class CreateInvoiceCredit(CreditView):
    def post(self, request, pk):
        patient = self.credit_patient(request, pk)
        serializer = CreditInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values, org = serializer.validated_data, request.profile.org
        try:
            with transaction.atomic():
                invoice = get_object_or_404(
                    Invoice.objects.select_for_update(),
                    pk=values["invoice"],
                    org=org,
                    contact=patient.contact,
                )
                retry = self.existing_request(org, patient, values)
                if retry is not None:
                    return retry
                existing = InvoiceCreditAdjustment.objects.filter(
                    org=org, invoice=invoice
                ).select_related("reversal")
                state = credit_summary(invoice, existing)
                if (
                    not state["can_credit"]
                    or values["amount"] > state["adjusted_billed"]
                ):
                    raise ValidationError(
                        {
                            "detail": "Use an issued USD invoice and an amount within its remaining billed value. Reverse changed credits before adding another."
                        }
                    )
                credit = InvoiceCreditAdjustment.objects.create(
                    org=org,
                    patient=patient,
                    invoice=invoice,
                    amount=values["amount"],
                    reason=values["reason"],
                    request_id=values["request_id"],
                    snapshot=credit_snapshot(invoice),
                    created_by=request.user,
                )
        except IntegrityError as error:
            raise Conflict(
                "Credit could not be recorded. Reload and review the current invoice and history."
            ) from error
        return Response({"id": str(credit.id), "already_recorded": False}, status=201)


class ReverseInvoiceCredit(CreditView):
    def post(self, request, pk):
        patient = self.credit_patient(request, pk)
        serializer = ReverseCreditInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values, org = serializer.validated_data, request.profile.org
        try:
            with transaction.atomic():
                credit = get_object_or_404(
                    InvoiceCreditAdjustment.objects,
                    pk=values["credit"],
                    org=org,
                    patient=patient,
                    reversal_of__isnull=True,
                )
                # Same lock order as credit creation. Reversal remains possible after invoice drift.
                get_object_or_404(
                    Invoice.objects.select_for_update(), pk=credit.invoice_id, org=org
                )
                retry = self.existing_request(org, patient, values, reverse=True)
                if retry is not None:
                    return retry
                existing = InvoiceCreditAdjustment.objects.filter(
                    org=org, reversal_of=credit
                ).first()
                if existing:
                    return Response({"id": str(existing.id), "already_recorded": True})
                reversal = InvoiceCreditAdjustment.objects.create(
                    org=org,
                    patient=patient,
                    invoice_id=credit.invoice_id,
                    amount=credit.amount,
                    reversal_of=credit,
                    reason=values["reason"],
                    request_id=values["request_id"],
                    snapshot=credit.snapshot,
                    created_by=request.user,
                )
        except IntegrityError as error:
            raise Conflict(
                "Credit reversal could not be recorded. Reload and review the history."
            ) from error
        return Response({"id": str(reversal.id), "already_recorded": False}, status=201)
