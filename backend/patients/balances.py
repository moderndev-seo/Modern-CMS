"""Conservative recorded balances: never infer money from invoice payment entries."""

from decimal import Decimal

from rest_framework.response import Response

from invoices.models import Invoice, Payment
from patients.allocations import PatientAllocations
from patients.credits import credit_summary
from patients.matching import matches_current_records
from patients.models import InvoiceCreditAdjustment, PaymentMatch

ZERO = Decimal("0.00")
EXCLUDED = ("Draft", "Pending", "Cancelled")


class PatientBalances(PatientAllocations):
    def get(self, request, pk):
        allocation = super().get(request, pk).data
        patient = self.credit_patient(request, pk)
        org = request.profile.org
        invoices = list(
            Invoice.objects.filter(org=org, contact=patient.contact).order_by(
                "invoice_number", "id"
            )
        )
        issued = [i for i in invoices if i.status not in EXCLUDED]
        credits = list(
            InvoiceCreditAdjustment.objects.filter(
                org=org, patient=patient
            ).select_related("reversal")
        )
        matches = list(
            PaymentMatch.objects.filter(
                org=org, receipt__patient=patient, active=True
            ).select_related("receipt__patient", "invoice_payment__invoice")
        )
        payments = Payment.objects.filter(org=org, invoice__in=invoices)
        valid_payment_ids = {
            m.invoice_payment_id for m in matches if matches_current_records(m)
        }
        blockers = []
        if allocation["review_count"]:
            blockers.append(
                "Review changed receipt allocations, then save replacement plans."
            )
        if allocation["totals"]["unallocated"] != ZERO:
            blockers.append(
                "Allocate all remaining receipt cash before using invoice balances."
            )
        if allocation["refund_totals"]["unreconciled"] != ZERO:
            blockers.append(
                "Explain each recorded refund by invoice or unallocated cash."
            )
        if any(i.currency != "USD" for i in issued):
            blockers.append(
                "Issued invoices include another currency; no conversion or mixed-currency balance is available."
            )
        if payments.exclude(pk__in=valid_payment_ids).exists() or any(
            not matches_current_records(m) for m in matches
        ):
            blockers.append(
                "Reconcile existing invoice-payment entries with valid receipt matches; missing or changed matches remain."
            )
        invoice_ids = {i.id for i in issued}
        if any(
            c.invoice_id not in invoice_ids
            and not c.reversal_of_id
            and not hasattr(c, "reversal")
            for c in credits
        ):
            blockers.append(
                "Active charge credits refer to an excluded or reassigned invoice; review those credits."
            )
        states = {
            i.id: credit_summary(i, credits) for i in issued if i.currency == "USD"
        }
        if any(
            s["needs_review"] or s["adjusted_billed"] is None for s in states.values()
        ):
            blockers.append("Review changed charge credits before using balances.")
        available = not blockers
        rows = []
        for bill in issued:
            credit = states.get(bill.id)
            adjusted = credit["adjusted_billed"] if credit else None
            allocated = (
                allocation["by_invoice"].get(str(bill.id), ZERO)
                if bill.currency == "USD"
                else None
            )
            explained_refunds = (
                allocation["refunds_by_invoice"].get(str(bill.id), ZERO)
                if bill.currency == "USD"
                else None
            )
            balance = adjusted - allocated if available else None
            rows.append(
                {
                    "id": str(bill.id),
                    "number": bill.invoice_number,
                    "currency": bill.currency,
                    "original_billed": bill.total_amount,
                    "active_credits": credit["active_credits"] if credit else None,
                    "adjusted_billed": adjusted,
                    "net_allocated": allocated,
                    "explained_refunds": explained_refunds,
                    "recorded_balance": balance,
                    "outstanding": max(balance, ZERO) if available else None,
                    "overpaid": max(-balance, ZERO) if available else None,
                }
            )
        totals = None
        if available:
            totals = {
                key: sum((row[key] for row in rows), ZERO)
                for key in (
                    "original_billed",
                    "active_credits",
                    "adjusted_billed",
                    "net_allocated",
                    "explained_refunds",
                    "recorded_balance",
                    "outstanding",
                    "overpaid",
                )
            }
        return Response(
            {
                "patient_name": allocation["patient_name"],
                "available": available,
                "blockers": blockers,
                "totals": totals,
                "invoices": rows,
                "excluded_invoice_count": len(invoices) - len(issued),
                "cash": allocation["totals"],
                "refunds": allocation["refund_totals"],
            }
        )

    # This endpoint is read-only; inherited allocation writes must not be exposed.
    http_method_names = ["get", "head", "options"]
