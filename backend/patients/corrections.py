"""Audited corrections to recorded cash amounts and references, never actual money movements."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response

from patients.appointments import Conflict
from patients.credits import CreditView, StrictInput
from patients.models import PaymentMatch, Receipt, ReceiptAllocation, ReceiptCorrection


def correction_history(org, patient):
    return [
        {
            "id": str(row.id),
            "receipt": str(row.receipt_id),
            "reference": row.snapshot["reference"],
            "kind": row.snapshot["kind"],
            "field": "reference" if row.reference is not None else "amount",
            "before_reference": row.snapshot["reference"],
            "after_reference": row.reference
            if row.reference is not None
            else row.snapshot["reference"],
            "before": row.snapshot["amount"],
            "after": row.amount,
            "revision": row.revision,
            "reason": row.reason,
            "occurred_at": row.created_at,
            "actor": row.created_by.email if row.created_by else "Not recorded",
        }
        for row in ReceiptCorrection.objects.filter(org=org, patient=patient)
        .select_related("created_by")
        .order_by("created_at", "id")
    ]


def blockers(org, payment_id):
    reasons = []
    if PaymentMatch.objects.filter(
        org=org, receipt_id=payment_id, active=True
    ).exists():
        reasons.append("Reverse the active payment match in Billing review first.")
    latest = (
        ReceiptAllocation.objects.filter(org=org, receipt_id=payment_id)
        .order_by("-revision")
        .first()
    )
    if latest and (latest.lines or latest.refund_lines):
        reasons.append(
            "Clear the payment's allocation plan and refund explanations first."
        )
    return reasons


class CorrectionInput(StrictInput):
    receipt = serializers.UUIDField()
    revision = serializers.IntegerField(min_value=0)
    request_id = serializers.UUIDField()
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False
    )
    reference = serializers.CharField(max_length=100, required=False)
    reason = serializers.CharField(max_length=1000)

    def validate(self, values):
        if ("amount" in values) == ("reference" in values):
            raise serializers.ValidationError(
                "Correct exactly one field: amount or reference."
            )
        return values


class PatientCorrections(CreditView):
    def get(self, request, pk):
        patient = self.credit_patient(request, pk)
        org = request.profile.org
        history = correction_history(org, patient)
        revisions = {}
        for entry in history:
            revisions[entry["receipt"]] = max(
                revisions.get(entry["receipt"], 0), entry["revision"]
            )
        receipts = Receipt.objects.filter(org=org, patient=patient).order_by(
            "-occurred_at", "id"
        )
        count = receipts.count()
        return Response(
            {
                "patient_name": f"{patient.contact.first_name} {patient.contact.last_name}".strip(),
                "receipt_count": count,
                "history_count": len(history),
                "receipts": [
                    {
                        "id": str(row.id),
                        "reference": row.reference,
                        "kind": row.kind,
                        "amount": row.amount,
                        "occurred_at": row.occurred_at,
                        "revision": revisions.get(str(row.id), 0),
                        "blockers": [
                            "Restore this excluded payment before correcting it."
                        ]
                        if row.excluded
                        else blockers(org, row.payment_id or row.id),
                    }
                    for row in receipts[:100]
                ],
                "history": list(reversed(history))[:100],
            }
        )

    def post(self, request, pk):
        patient = self.credit_patient(request, pk)
        serializer = CorrectionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values, org = serializer.validated_data, request.profile.org
        try:
            with transaction.atomic():
                receipt = get_object_or_404(
                    Receipt, org=org, patient=patient, pk=values["receipt"]
                )
                # Refunds, allocations and matches serialize on the original payment.
                get_object_or_404(
                    Receipt.objects.select_for_update(),
                    org=org,
                    patient=patient,
                    pk=receipt.payment_id or receipt.id,
                )
                receipt = get_object_or_404(
                    Receipt.objects.select_for_update(),
                    org=org,
                    patient=patient,
                    pk=receipt.id,
                )
                old = ReceiptCorrection.objects.filter(
                    org=org, request_id=values["request_id"]
                ).first()
                if old:
                    if (
                        old.patient_id != patient.id
                        or old.receipt_id != receipt.id
                        or old.revision != values["revision"] + 1
                        or old.reference != values.get("reference")
                        or ("amount" in values and old.amount != values["amount"])
                        or old.reason != values["reason"]
                    ):
                        raise Conflict(
                            "Request already used for different details. Reload before continuing."
                        )
                    return Response({"id": str(old.id), "already_recorded": True})
                reasons = blockers(org, receipt.payment_id or receipt.id)
                if reasons:
                    raise Conflict(" ".join(reasons))
                previous = (
                    ReceiptCorrection.objects.filter(org=org, receipt=receipt)
                    .order_by("-revision")
                    .first()
                )
                if values["revision"] != (previous.revision if previous else 0):
                    raise Conflict(
                        "This receipt changed. Reload and review the latest record."
                    )
                field = "reference" if "reference" in values else "amount"
                if getattr(receipt, field) == values[field]:
                    raise Conflict(
                        "The corrected value must differ from the current value."
                    )
                entry = ReceiptCorrection.objects.create(
                    org=org,
                    patient=patient,
                    receipt=receipt,
                    revision=values["revision"] + 1,
                    request_id=values["request_id"],
                    amount=values.get("amount", receipt.amount),
                    reference=values.get("reference"),
                    reason=values["reason"],
                    created_by=request.user,
                )
        except IntegrityError as error:
            raise Conflict(
                "Correction rejected. Reload and check reserved references, refund limits, matches and allocations."
            ) from error
        return Response({"id": str(entry.id), "already_recorded": False}, status=201)
