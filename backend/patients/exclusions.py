"""Reversible, audited duplicate-payment exclusion. Never deletes or moves money."""

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response

from patients.appointments import Conflict
from patients.corrections import blockers
from patients.credits import CreditView, StrictInput
from patients.models import Receipt, ReceiptExclusion


def exclusion_history(org, patient):
    return [
        {
            "id": str(row.id),
            "receipt": str(row.receipt_id),
            "reference": row.snapshot["receipt"]["reference"],
            "amount": row.snapshot["receipt"]["amount"],
            "excluded": row.excluded,
            "revision": row.revision,
            "retained_reference": row.snapshot.get("retained", {}).get("reference"),
            "reason": row.reason,
            "occurred_at": row.created_at,
            "actor": row.created_by.email if row.created_by else "Not recorded",
        }
        for row in ReceiptExclusion.objects.filter(org=org, patient=patient)
        .select_related("created_by")
        .order_by("created_at", "id")
    ]


class ExclusionInput(StrictInput):
    receipt = serializers.UUIDField()
    retained = serializers.UUIDField(allow_null=True)
    excluded = serializers.BooleanField()
    revision = serializers.IntegerField(min_value=0)
    request_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=1000)

    def validate(self, values):
        if values["excluded"] != (values["retained"] is not None):
            raise serializers.ValidationError(
                "Select a retained payment only when excluding a duplicate."
            )
        return values


class PatientExclusions(CreditView):
    def get(self, request, pk):
        patient = self.credit_patient(request, pk)
        org = request.profile.org
        history = exclusion_history(org, patient)
        versions = {}
        for entry in history:
            versions[entry["receipt"]] = max(
                versions.get(entry["receipt"], 0), entry["revision"]
            )
        receipts = Receipt.objects.filter(
            org=org, patient=patient, kind="payment"
        ).order_by("-occurred_at", "id")
        rows = []
        for cash in receipts[:100]:
            reasons = blockers(org, cash.id) if not cash.excluded else []
            if (
                not cash.excluded
                and Receipt.objects.filter(org=org, payment=cash).exists()
            ):
                reasons.append(
                    "Payments with refunds cannot be excluded in this version."
                )
            rows.append(
                {
                    "id": str(cash.id),
                    "reference": cash.reference,
                    "amount": cash.amount,
                    "occurred_at": cash.occurred_at,
                    "excluded": cash.excluded,
                    "revision": versions.get(str(cash.id), 0),
                    "blockers": reasons,
                }
            )
        return Response(
            {
                "patient_name": f"{patient.contact.first_name} {patient.contact.last_name}".strip(),
                "receipts": rows,
                "receipt_count": receipts.count(),
                "history": list(reversed(history))[:100],
                "history_count": len(history),
            }
        )

    def post(self, request, pk):
        patient = self.credit_patient(request, pk)
        org = request.profile.org
        serializer = ExclusionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            with transaction.atomic():
                ids = [values["receipt"]] + (
                    [values["retained"]] if values["retained"] else []
                )
                cash = {
                    row.id: row
                    for row in Receipt.objects.select_for_update()
                    .filter(org=org, patient=patient, kind="payment", id__in=ids)
                    .order_by("id")
                }
                for item in ids:
                    if item not in cash:
                        get_object_or_404(
                            Receipt, org=org, patient=patient, kind="payment", id=item
                        )
                old = ReceiptExclusion.objects.filter(
                    org=org, request_id=values["request_id"]
                ).first()
                if old:
                    if (
                        old.patient_id != patient.id
                        or old.receipt_id != values["receipt"]
                        or old.retained_id != values["retained"]
                        or old.excluded != values["excluded"]
                        or old.revision != values["revision"] + 1
                        or old.reason != values["reason"]
                    ):
                        raise Conflict(
                            "Request already used for different details. Reload before continuing."
                        )
                    return Response({"id": str(old.id), "already_recorded": True})
                entry = ReceiptExclusion.objects.create(
                    org=org,
                    patient=patient,
                    receipt_id=values["receipt"],
                    retained_id=values["retained"],
                    excluded=values["excluded"],
                    revision=values["revision"] + 1,
                    request_id=values["request_id"],
                    reason=values["reason"],
                    created_by=request.user,
                )
        except IntegrityError as error:
            raise Conflict(
                "Decision rejected. Reload and check the version, retained equal-amount payment, refunds, matches and allocations. A payment retained by another active exclusion cannot be excluded."
            ) from error
        return Response({"id": str(entry.id), "already_recorded": False}, status=201)
