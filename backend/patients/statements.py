"""Internal financial review, never a new invoice or a claim of settled funds."""

import csv
import io
from decimal import Decimal

from django.db import connection, transaction
from django.utils import timezone
from rest_framework.response import Response

from patients.balances import PatientBalances
from patients.corrections import correction_history
from patients.exclusions import exclusion_history
from patients.models import InvoiceCreditAdjustment, Receipt

NOTICE = (
    "Internal recorded financial review · USD · All recorded dates. "
    "Not an invoice, credit note, bank settlement or insurance determination. "
    "Internal credits do not change legacy invoice documents or paid/due fields. "
    "Unavailable balances are blank, never zero. Refunds already reduce net cash; do not subtract twice."
)


def csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    text = str(value)
    # Quote formula-like text even when malicious text starts with whitespace.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(
        ("\t", "\r", "\n")
    ):
        text = "'" + text
    return text


def statement_csv(data):
    output = io.StringIO(newline="")
    writer = csv.writer(output)

    def row(*values):
        writer.writerow([csv_cell(value) for value in values])

    row("Modern Practice internal financial review")
    row("Practice", data["practice"])
    row("Patient", data["patient_name"])
    row("Generated UTC", data["generated_at"])
    row("Scope", NOTICE)
    row(
        "Balance status",
        "Available from recorded data" if data["available"] else "Unavailable",
    )
    for reason in data["blockers"]:
        row("Review required", reason)
    row("Net collected USD", data["cash"]["net_collected"])
    row("Allocated USD", data["cash"]["allocated"])
    row("Unallocated USD", data["cash"]["unallocated"])
    row("Cash needing review USD", data["cash"]["needs_review"])
    row()
    row(
        "Issued invoices",
        "Currency",
        "Original billed",
        "Active internal credits",
        "Adjusted billed",
        "Net allocated",
        "Explained refunds (already deducted)",
        "Recorded balance",
        "Outstanding",
        "Overpaid",
    )
    for bill in data["invoices"]:
        row(
            *(
                bill[key]
                for key in (
                    "number",
                    "currency",
                    "original_billed",
                    "active_credits",
                    "adjusted_billed",
                    "net_allocated",
                    "explained_refunds",
                    "recorded_balance",
                    "outstanding",
                    "overpaid",
                )
            )
        )
    row("Excluded draft/pending/cancelled invoices", data["excluded_invoice_count"])
    row()
    row(
        "Credit audit ID",
        "Invoice at entry",
        "Amount USD",
        "Reverses audit ID",
        "Reversed",
        "Reason",
        "Actor",
        "Recorded UTC",
    )
    for credit in data["credits"]:
        row(
            *(
                credit[key]
                for key in (
                    "id",
                    "invoice",
                    "amount",
                    "reversal_of",
                    "reversed",
                    "reason",
                    "actor",
                    "at",
                )
            )
        )
    row()
    row(
        "Cash ID",
        "Reference",
        "Kind",
        "Amount USD",
        "Recorded cash UTC",
        "Parent payment ID",
        "Excluded duplicate",
    )
    for cash in data["receipts"]:
        row(
            *(
                cash[key]
                for key in (
                    "id",
                    "reference",
                    "kind",
                    "amount",
                    "occurred_at",
                    "payment_id",
                    "excluded",
                )
            )
        )
    row()
    row(
        "Cash correction ID",
        "Receipt ID",
        "Field",
        "Before",
        "After",
        "Reason",
        "Actor",
        "Recorded UTC",
    )
    for change in data["corrections"]:
        field = change["field"]
        before, after = (
            (change["before_date"], change["after_date"])
            if field == "occurred_at"
            else (change["before_reference"], change["after_reference"])
            if field == "reference"
            else (change["before"], change["after"])
        )
        row(
            change["id"],
            change["receipt"],
            field,
            before,
            after,
            change["reason"],
            change["actor"],
            change["occurred_at"],
        )
    row()
    row(
        "Exclusion decision ID",
        "Receipt ID",
        "Excluded",
        "Retained reference",
        "Reason",
        "Actor",
        "Recorded UTC",
    )
    for change in data["exclusions"]:
        row(
            *(
                change[key]
                for key in (
                    "id",
                    "receipt",
                    "excluded",
                    "retained_reference",
                    "reason",
                    "actor",
                    "occurred_at",
                )
            )
        )
    return output.getvalue()


class PatientStatement(PatientBalances):
    def get(self, request, pk):
        # Read-only review with inherited admin/contact checks and forced RLS.
        owns_transaction = not connection.in_atomic_block
        with transaction.atomic():
            if owns_transaction and connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                    )
            data = super().get(request, pk).data
            patient = self.credit_patient(request, pk)
            org = request.profile.org
            data.update(
                {
                    "practice": org.name,
                    "patient_id": str(patient.id),
                    "generated_at": timezone.now(),
                    "notice": NOTICE,
                    "credits": [
                        {
                            "id": str(c.id),
                            "invoice": c.snapshot["number"],
                            "amount": c.amount,
                            "reversal_of": str(c.reversal_of_id)
                            if c.reversal_of_id
                            else None,
                            "reversed": hasattr(c, "reversal"),
                            "reason": c.reason,
                            "actor": c.created_by.email
                            if c.created_by
                            else "Not recorded",
                            "at": c.created_at,
                        }
                        for c in InvoiceCreditAdjustment.objects.filter(
                            org=org, patient=patient
                        )
                        .select_related("created_by", "reversal")
                        .order_by("created_at", "id")
                    ],
                    "receipts": list(
                        Receipt.objects.filter(org=org, patient=patient)
                        .order_by("occurred_at", "id")
                        .values(
                            "id",
                            "reference",
                            "kind",
                            "amount",
                            "occurred_at",
                            "payment_id",
                            "excluded",
                        )
                    ),
                    "corrections": correction_history(org, patient),
                    "exclusions": exclusion_history(org, patient),
                }
            )
            response = Response(
                {"csv": statement_csv(data)}
                if request.query_params.get("download") == "csv"
                else data
            )
            response["Cache-Control"] = "private, no-store"
            return response
