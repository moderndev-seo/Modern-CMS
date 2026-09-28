"""Explicit one-to-one matching of existing USD payment records, without cash writes."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from common.permissions import is_org_admin
from contacts.access import assert_contact_access
from invoices.models import Invoice, Payment
from patients.appointments import Conflict
from patients.models import PaymentMatch, PaymentMatchReversal, Receipt
from patients.views import PracticeView


class MatchInput(serializers.Serializer):
    receipt = serializers.UUIDField()
    invoice_payment = serializers.UUIDField()
    reason = serializers.CharField(max_length=1000)

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise ValidationError(
                {"detail": "Only receipt, invoice_payment and reason may be supplied."}
            )
        return super().to_internal_value(data)


def match_snapshot(receipt, payment):
    return {
        "invoice": str(payment.invoice_id),
        "contact": str(payment.invoice.contact_id),
        "currency": payment.invoice.currency,
        "amount": str(receipt.amount),
        "receipt_reference": receipt.reference,
        "payment_reference": payment.reference_number,
        "payment_date": str(payment.payment_date),
    }


def matches_current_records(match):
    r, p = match.receipt, match.invoice_payment
    return (
        r.kind == "payment"
        and r.amount == p.amount == Decimal(match.snapshot["amount"])
        and r.org_id == p.org_id == p.invoice.org_id == match.org_id
        and r.patient.contact_id == p.invoice.contact_id
        and p.invoice.status not in ("Draft", "Pending", "Cancelled")
        and match_snapshot(r, p) == match.snapshot
    )


class MatchPayments(PracticeView):
    def post(self, request, pk):
        patient = self.patient(request, pk)
        if not is_org_admin(request.profile):
            raise PermissionDenied("Only practice administrators may match payments.")
        assert_contact_access(request.profile, patient.contact)
        serializer = MatchInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        org = request.profile.org
        try:
            with transaction.atomic():
                receipt = get_object_or_404(
                    Receipt.objects.select_for_update(),
                    pk=values["receipt"],
                    patient=patient,
                    org=org,
                )
                payment = get_object_or_404(
                    Payment.objects.select_for_update(),
                    pk=values["invoice_payment"],
                    org=org,
                    invoice__org=org,
                    invoice__contact=patient.contact,
                )
                # Invoice contact/currency must not change between validation and insertion.
                payment.invoice = Invoice.objects.select_for_update().get(
                    pk=payment.invoice_id, org=org
                )
                if payment.invoice.contact_id != patient.contact_id:
                    raise ValidationError(
                        {"detail": "The invoice contact changed. Reload and review."}
                    )
                if (
                    receipt.kind != "payment"
                    or receipt.amount != payment.amount
                    or payment.invoice.currency != "USD"
                ):
                    raise ValidationError(
                        {
                            "detail": "Match an equal USD payment amount. Refunds, splits and currency conversion are not supported."
                        }
                    )
                if payment.invoice.status in ("Draft", "Pending", "Cancelled"):
                    raise ValidationError(
                        {
                            "detail": "Choose a payment on an issued, non-cancelled invoice."
                        }
                    )
                existing = PaymentMatch.objects.filter(
                    org=org, receipt=receipt, invoice_payment=payment, active=True
                ).first()
                if existing:
                    return Response({"id": str(existing.id), "already_matched": True})
                if (
                    PaymentMatch.objects.filter(
                        org=org, receipt=receipt, active=True
                    ).exists()
                    or PaymentMatch.objects.filter(
                        org=org, invoice_payment=payment, active=True
                    ).exists()
                ):
                    raise Conflict(
                        "One of these records is already matched. No records were changed."
                    )
                match = PaymentMatch.objects.create(
                    org=org,
                    receipt=receipt,
                    invoice_payment=payment,
                    reason=values["reason"],
                    snapshot=match_snapshot(receipt, payment),
                    created_by=request.user,
                )
        except IntegrityError as error:
            raise Conflict(
                "These records could not be matched. Reload and check for an existing match."
            ) from error
        return Response({"id": str(match.id), "already_matched": False}, status=201)


class ReversalInput(serializers.Serializer):
    match = serializers.UUIDField()
    reason = serializers.CharField(max_length=1000)

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise ValidationError({"detail": "Only match and reason may be supplied."})
        return super().to_internal_value(data)


class ReversePaymentMatch(PracticeView):
    def post(self, request, pk):
        patient = self.patient(request, pk)
        if not is_org_admin(request.profile):
            raise PermissionDenied("Only practice administrators may reverse matches.")
        assert_contact_access(request.profile, patient.contact)
        serializer = ReversalInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        org = request.profile.org
        with transaction.atomic():
            original = get_object_or_404(
                PaymentMatch.objects.select_for_update(of=("self",)),
                pk=values["match"],
                org=org,
                receipt__patient=patient,
                receipt__org=org,
            )
            existing = PaymentMatchReversal.objects.filter(
                org=org, match=original
            ).first()
            if existing:
                return Response({"id": str(existing.id), "already_reversed": True})
            reversal = PaymentMatchReversal.objects.create(
                org=org,
                match=original,
                reason=values["reason"],
                created_by=request.user,
            )
            # PostgreSQL's audit trigger releases both unique active references atomically.
            # The test-only SQLite backend has no trigger support for this invariant.
            from django.db import connection

            if connection.vendor != "postgresql":
                PaymentMatch.objects.filter(pk=original.id, org=org).update(
                    active=False
                )
        return Response({"id": str(reversal.id), "already_reversed": False}, status=201)
