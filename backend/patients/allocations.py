"""Explicit distribution of net receipt cash; never write either financial ledger."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from invoices.models import Invoice
from patients.appointments import Conflict
from patients.credits import CreditView, StrictInput, credit_snapshot
from patients.models import Receipt, ReceiptAllocation

ZERO = Decimal("0.00")


def receipt_facts(receipt):
    refunds = list(
        Receipt.objects.filter(org_id=receipt.org_id, payment=receipt, kind="refund")
        .order_by("id")
        .values("id", "amount")
    )
    total = sum((row["amount"] for row in refunds), ZERO)
    return {
        "amount": str(receipt.amount),
        "reference": receipt.reference,
        "patient": str(receipt.patient_id),
        "contact": str(receipt.patient.contact_id),
        "kind": receipt.kind,
        "net": str(receipt.amount - total),
        "refunds": [
            {"id": str(row["id"]), "amount": str(row["amount"])} for row in refunds
        ],
    }


def allocation_snapshot(receipt, invoices):
    return {
        "receipt": receipt_facts(receipt),
        "invoices": {str(i.id): credit_snapshot(i) for i in invoices},
    }


def current_plan(receipt, plan, invoices):
    if plan is None or not (plan.lines or plan.refund_lines):
        return True
    invoice_ids = {
        row["invoice"] for row in plan.lines + plan.refund_lines if row["invoice"]
    }
    selected = [invoices.get(key) for key in sorted(invoice_ids)]
    return all(
        i is not None
        and i.currency == "USD"
        and i.status not in ("Draft", "Pending", "Cancelled")
        and i.contact_id == receipt.patient.contact_id
        for i in selected
    ) and plan.snapshot == allocation_snapshot(receipt, selected)


class AllocationLine(StrictInput):
    invoice = serializers.UUIDField()
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )


class RefundAllocationLine(AllocationLine):
    refund = serializers.UUIDField()
    invoice = serializers.UUIDField(allow_null=True)


class AllocationInput(StrictInput):
    receipt = serializers.UUIDField()
    revision = serializers.IntegerField(min_value=0)
    request_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=1000)
    lines = AllocationLine(many=True, max_length=20)
    refund_lines = RefundAllocationLine(
        many=True, max_length=100, required=False, default=list
    )

    def validate_refund_lines(self, lines):
        if len({(row["refund"], row["invoice"]) for row in lines}) != len(lines):
            raise ValidationError("Use each refund/invoice pair once.")
        return sorted(
            [
                {
                    "refund": str(row["refund"]),
                    "invoice": str(row["invoice"]) if row["invoice"] else None,
                    "amount": str(row["amount"]),
                }
                for row in lines
            ],
            key=lambda row: (row["refund"], row["invoice"] or ""),
        )

    def validate_lines(self, lines):
        if len({row["invoice"] for row in lines}) != len(lines):
            raise ValidationError("Use each invoice once per receipt.")
        return sorted(
            [
                {"invoice": str(row["invoice"]), "amount": str(row["amount"])}
                for row in lines
            ],
            key=lambda row: row["invoice"],
        )


class PatientAllocations(CreditView):
    def get(self, request, pk):
        patient = self.credit_patient(request, pk)
        org = request.profile.org
        receipts = list(
            Receipt.objects.filter(org=org, patient=patient, kind="payment")
            .select_related("patient")
            .order_by("-occurred_at", "id")
        )
        invoices = {
            str(i.id): i
            for i in Invoice.objects.filter(org=org, contact=patient.contact).order_by(
                "-created_at", "id"
            )
        }
        plans = list(
            ReceiptAllocation.objects.filter(org=org, patient=patient)
            .select_related("created_by")
            .order_by("-created_at", "-revision")
        )
        latest = {}
        for plan in plans:
            if (
                plan.receipt_id not in latest
                or latest[plan.receipt_id].revision < plan.revision
            ):
                latest[plan.receipt_id] = plan
        by_invoice = {}
        refunds_by_invoice = {}
        refund_totals = {
            "recorded": ZERO,
            "reconciled": ZERO,
            "unreconciled": ZERO,
            "from_unallocated_cash": ZERO,
        }
        review_count = 0
        rows = []
        totals = {
            "net_collected": ZERO,
            "allocated": ZERO,
            "unallocated": ZERO,
            "needs_review": ZERO,
        }
        for receipt in receipts:
            plan = latest.get(receipt.id)
            net = Decimal(receipt_facts(receipt)["net"])
            refund_records = list(
                Receipt.objects.filter(
                    org=org, payment=receipt, kind="refund"
                ).order_by("id")
            )
            valid = current_plan(receipt, plan, invoices)
            review_count += int(not valid)
            reconciled = {}
            if valid and plan:
                for line in plan.refund_lines:
                    amount = Decimal(line["amount"])
                    reconciled[line["refund"]] = (
                        reconciled.get(line["refund"], ZERO) + amount
                    )
                    if line["invoice"]:
                        refunds_by_invoice[line["invoice"]] = (
                            refunds_by_invoice.get(line["invoice"], ZERO) + amount
                        )
                    else:
                        refund_totals["from_unallocated_cash"] += amount
            for refund in refund_records:
                refund_totals["recorded"] += refund.amount
                refund_totals["reconciled"] += reconciled.get(str(refund.id), ZERO)
                refund_totals["unreconciled"] += refund.amount - reconciled.get(
                    str(refund.id), ZERO
                )
            allocated = (
                sum((Decimal(line["amount"]) for line in plan.lines), ZERO)
                if plan and valid
                else ZERO
            )
            totals["net_collected"] += net
            totals["allocated"] += allocated
            totals["unallocated" if valid else "needs_review"] += net - allocated
            if valid and plan:
                for line in plan.lines:
                    by_invoice[line["invoice"]] = by_invoice.get(
                        line["invoice"], ZERO
                    ) + Decimal(line["amount"])
            rows.append(
                {
                    "id": str(receipt.id),
                    "reference": receipt.reference,
                    "gross": receipt.amount,
                    "net": net,
                    "revision": plan.revision if plan else 0,
                    "lines": plan.lines if plan else [],
                    "needs_review": not valid,
                    "refund_lines": plan.refund_lines if plan else [],
                    "refunds": [
                        {
                            "id": str(r.id),
                            "reference": r.reference,
                            "amount": r.amount,
                            "unreconciled": r.amount - reconciled.get(str(r.id), ZERO),
                        }
                        for r in refund_records
                    ],
                    "allocated": allocated if valid else None,
                }
            )
        return Response(
            {
                "patient_name": f"{patient.contact.first_name} {patient.contact.last_name}".strip(),
                "totals": totals,
                "by_invoice": by_invoice,
                "refunds_by_invoice": refunds_by_invoice,
                "refund_totals": refund_totals,
                "review_count": review_count,
                "receipt_count": len(rows),
                "receipts": rows[:100],
                "invoice_count": len(invoices),
                "invoices": [
                    {
                        "id": str(i.id),
                        "number": i.invoice_number,
                        "eligible": i.currency == "USD"
                        and i.status not in ("Draft", "Pending", "Cancelled"),
                    }
                    for i in list(invoices.values())[:100]
                ],
                "history_count": len(plans),
                "history": [
                    {
                        "id": str(p.id),
                        "receipt": p.snapshot["receipt"]["reference"],
                        "revision": p.revision,
                        "reason": p.reason,
                        "at": p.created_at,
                        "actor": p.created_by.email if p.created_by else "Not recorded",
                        "lines": p.lines,
                        "refund_lines": p.refund_lines,
                        "invoices": p.snapshot["invoices"],
                    }
                    for p in plans[:100]
                ],
            }
        )

    def post(self, request, pk):
        patient = self.credit_patient(request, pk)
        serializer = AllocationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values, org = serializer.validated_data, request.profile.org
        try:
            with transaction.atomic():
                receipt = get_object_or_404(
                    Receipt.objects.select_for_update(),
                    pk=values["receipt"],
                    org=org,
                    patient=patient,
                    kind="payment",
                )
                existing = ReceiptAllocation.objects.filter(
                    org=org, request_id=values["request_id"]
                ).first()
                if existing:
                    if (
                        existing.receipt_id != receipt.id
                        or existing.revision != values["revision"] + 1
                        or existing.lines != values["lines"]
                        or existing.refund_lines != values["refund_lines"]
                        or existing.reason != values["reason"]
                    ):
                        raise Conflict(
                            "This request was already used for different allocation details."
                        )
                    return Response({"id": str(existing.id), "already_recorded": True})
                last = (
                    ReceiptAllocation.objects.filter(org=org, receipt=receipt)
                    .order_by("-revision")
                    .first()
                )
                if values["revision"] != (last.revision if last else 0):
                    raise Conflict(
                        "The allocation changed. Reload and review before saving."
                    )
                invoices = []
                invoice_ids = sorted(
                    {
                        line["invoice"]
                        for line in values["lines"] + values["refund_lines"]
                        if line["invoice"]
                    }
                )
                for invoice_id in invoice_ids:
                    bill = get_object_or_404(
                        Invoice.objects.select_for_update(),
                        pk=invoice_id,
                        org=org,
                        contact=patient.contact,
                    )
                    if bill.currency != "USD" or bill.status in (
                        "Draft",
                        "Pending",
                        "Cancelled",
                    ):
                        raise ValidationError(
                            {
                                "detail": "Choose issued, non-cancelled USD invoices for this patient."
                            }
                        )
                    invoices.append(bill)
                if sum(
                    (Decimal(row["amount"]) for row in values["lines"]), ZERO
                ) > Decimal(receipt_facts(receipt)["net"]):
                    raise ValidationError(
                        {
                            "detail": "Allocated cash cannot exceed the receipt less its recorded refunds."
                        }
                    )
                refund_used = {}
                for line in values["refund_lines"]:
                    refund = get_object_or_404(
                        Receipt.objects,
                        pk=line["refund"],
                        org=org,
                        patient=patient,
                        payment=receipt,
                        kind="refund",
                    )
                    refund_used[refund.id] = refund_used.get(refund.id, ZERO) + Decimal(
                        line["amount"]
                    )
                    if refund_used[refund.id] > refund.amount:
                        raise ValidationError(
                            {
                                "detail": "Refund allocations cannot exceed the recorded refund."
                            }
                        )
                plan = ReceiptAllocation.objects.create(
                    org=org,
                    patient=patient,
                    receipt=receipt,
                    revision=values["revision"] + 1,
                    request_id=values["request_id"],
                    reason=values["reason"],
                    lines=values["lines"],
                    refund_lines=values["refund_lines"],
                    snapshot=allocation_snapshot(receipt, invoices),
                    created_by=request.user,
                )
        except IntegrityError as error:
            raise Conflict(
                "Allocation could not be saved. Reload and review the latest records."
            ) from error
        return Response({"id": str(plan.id), "already_recorded": False}, status=201)
