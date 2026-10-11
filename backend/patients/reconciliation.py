"""Derived receipt coverage; never allocate cash or infer an amount owed."""

from decimal import Decimal

from django.db.models import Sum

from patients.matching import matches_current_records
from patients.models import Receipt

ZERO = Decimal("0.00")


def receipt_coverage(patient, matches):
    """Refunds follow their original receipt only through a valid active match.

    Covers all recorded dates and all matches, independent of UI pagination.
    A reversed or changed match supplies no evidence for current invoice coverage.
    """
    refunds = {
        row["payment_id"]: row["total"]
        for row in Receipt.objects.filter(
            org_id=patient.org_id, patient=patient, kind="refund"
        )
        .values("payment_id")
        .annotate(total=Sum("amount"))
    }
    valid = {}
    changed = set()
    for match in matches.filter(active=True):
        if matches_current_records(match):
            valid[match.receipt_id] = match.invoice_payment.invoice_id
        else:
            changed.add(match.receipt_id)
    groups = {
        name: {
            "payments": ZERO,
            "refunds": ZERO,
            "net_collected": ZERO,
            "payment_count": 0,
        }
        for name in ("linked", "unmatched", "needs_review")
    }
    by_invoice = {}
    for receipt in Receipt.objects.filter(
        org_id=patient.org_id, patient=patient, kind="payment", excluded=False
    ):
        invoice_id = valid.get(receipt.id)
        group = (
            "linked"
            if invoice_id
            else "needs_review"
            if receipt.id in changed
            else "unmatched"
        )
        refunded = refunds.get(receipt.id, ZERO)
        for target in [groups[group]] + (
            [
                by_invoice.setdefault(
                    str(invoice_id),
                    {
                        "payments": ZERO,
                        "refunds": ZERO,
                        "net_collected": ZERO,
                        "payment_count": 0,
                    },
                )
            ]
            if invoice_id
            else []
        ):
            target["payments"] += receipt.amount
            target["refunds"] += refunded
            target["net_collected"] += receipt.amount - refunded
            target["payment_count"] += 1
    return {
        "currency": "USD",
        "scope": "All recorded dates; all receipt and match records.",
        **groups,
        "by_invoice": by_invoice,
    }
