"""Read-only billing review; invoice entries never become Growth receipts implicitly."""

from decimal import Decimal

from django.db.models import Sum
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from common.permissions import is_org_admin
from contacts.access import assert_contact_access
from invoices.models import UNPAID_STATUSES, Invoice, Payment
from patients.matching import matches_current_records
from patients.models import PaymentMatch, Receipt
from patients.reconciliation import receipt_coverage
from patients.views import PracticeView

BILLED_STATUSES = (*UNPAID_STATUSES, "Paid")
ZERO = Decimal("0.00")


class PatientBilling(PracticeView):
    def get(self, request, pk):
        patient = self.patient(request, pk)
        if not is_org_admin(request.profile):
            raise PermissionDenied("Only practice administrators may review billing.")
        assert_contact_access(request.profile, patient.contact)
        try:
            page = int(request.query_params.get("page", 1))
            if page < 1:
                raise ValueError
        except ValueError:
            raise ValidationError({"page": "Use a positive integer."}) from None
        org = request.profile.org
        invoices = Invoice.objects.filter(
            org=org, contact=patient.contact, contact__org=org
        )
        payments = Payment.objects.filter(
            org=org, invoice__in=invoices, invoice__org=org
        )
        currencies = {}
        for row in invoices.values("currency").distinct():
            currencies[row["currency"]] = {
                "currency": row["currency"] or "Unspecified",
                "billed": ZERO,
                "invoice_payments": ZERO,
            }
        for row in (
            invoices.filter(status__in=BILLED_STATUSES)
            .values("currency")
            .annotate(total=Sum("total_amount"))
        ):
            currencies[row["currency"]]["billed"] = row["total"] or ZERO
        for row in payments.values("invoice__currency").annotate(total=Sum("amount")):
            currencies[row["invoice__currency"]]["invoice_payments"] = (
                row["total"] or ZERO
            )
        receipts = {
            row["kind"]: row["total"]
            for row in Receipt.objects.filter(org=org, patient=patient)
            .values("kind")
            .annotate(total=Sum("amount"))
        }
        selected = list(
            invoices.order_by("-created_at", "id")[(page - 1) * 20 : page * 20]
        )
        ledger = {
            row["invoice_id"]: row["total"]
            for row in payments.filter(invoice_id__in=[item.id for item in selected])
            .values("invoice_id")
            .annotate(total=Sum("amount"))
        }
        matches = (
            PaymentMatch.objects.filter(
                org=org, receipt__patient=patient, receipt__org=org
            )
            .select_related(
                "receipt__patient",
                "invoice_payment__invoice",
                "created_by",
                "reversal__created_by",
            )
            .order_by("-created_at", "id")
        )
        coverage = receipt_coverage(patient, matches)
        receipt_choices = (
            Receipt.objects.filter(org=org, patient=patient, kind="payment")
            .exclude(pk__in=matches.filter(active=True).values("receipt_id"))
            .order_by("-occurred_at", "id")
        )
        payment_choices = (
            payments.filter(invoice__currency="USD")
            .exclude(
                pk__in=PaymentMatch.objects.filter(org=org, active=True).values(
                    "invoice_payment_id"
                )
            )
            .exclude(invoice__status__in=["Draft", "Pending", "Cancelled"])
            .select_related("invoice")
            .order_by("-payment_date", "id")
        )
        return Response(
            {
                "patient_id": str(patient.id),
                "patient_name": f"{patient.contact.first_name} {patient.contact.last_name}".strip(),
                "scope": "All recorded dates; invoices linked to this patient's CRM contact. Explicit equal-amount payment matches do not allocate refunds or change either ledger.",
                "receipt_currency": "USD",
                "receipt_coverage": coverage,
                "matching": {
                    "receipt_count": receipt_choices.count(),
                    "payment_count": payment_choices.count(),
                    "match_count": matches.count(),
                    "receipts": [
                        {
                            "id": str(r.id),
                            "reference": r.reference,
                            "amount": r.amount,
                            "at": r.occurred_at,
                        }
                        for r in receipt_choices[:100]
                    ],
                    "invoice_payments": [
                        {
                            "id": str(p.id),
                            "invoice": p.invoice.invoice_number,
                            "reference": p.reference_number,
                            "amount": p.amount,
                            "date": p.payment_date,
                        }
                        for p in payment_choices[:100]
                    ],
                    "matches": [
                        {
                            "id": str(m.id),
                            "receipt": m.snapshot["receipt_reference"],
                            "invoice": m.snapshot["invoice"],
                            "amount": m.snapshot["amount"],
                            "reason": m.reason,
                            "at": m.created_at,
                            "actor": m.created_by.email
                            if m.created_by
                            else "Not recorded",
                            "active": m.active,
                            "consistent": matches_current_records(m)
                            if m.active
                            else None,
                            "reversal": {
                                "reason": m.reversal.reason,
                                "at": m.reversal.created_at,
                                "actor": m.reversal.created_by.email
                                if m.reversal.created_by
                                else "Not recorded",
                            }
                            if hasattr(m, "reversal")
                            else None,
                        }
                        for m in matches[:100]
                    ],
                },
                "payments": receipts.get("payment", ZERO),
                "refunds": receipts.get("refund", ZERO),
                "net_collected": receipts.get("payment", ZERO)
                - receipts.get("refund", ZERO),
                "currencies": sorted(
                    currencies.values(), key=lambda row: row["currency"]
                ),
                "count": invoices.count(),
                "excluded_from_billed_count": invoices.exclude(
                    status__in=BILLED_STATUSES
                ).count(),
                "page": page,
                "page_size": 20,
                "results": [
                    {
                        "id": str(item.id),
                        "number": item.invoice_number,
                        "title": item.invoice_title,
                        "status": item.status,
                        "currency": item.currency or "Unspecified",
                        "total": item.total_amount,
                        "invoice_payments": ledger.get(item.id, ZERO),
                        "stored_paid": item.amount_paid,
                        "stored_due": item.amount_due,
                        "ledger_matches_stored_paid": ledger.get(item.id, ZERO)
                        == item.amount_paid,
                        "included_in_billed": item.status in BILLED_STATUSES,
                    }
                    for item in selected
                ],
            }
        )
