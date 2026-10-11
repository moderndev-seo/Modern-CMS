"""UTC activity-period reporting. Never treat invoice value as cash."""

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from django.db.models import Count, Sum

from patients.models import SOURCES, JourneyEvent, MarketingSpend, Patient, Receipt

ZERO = Decimal("0.00")


def growth_report(org, start, end):
    lower = datetime.combine(start, time.min, timezone.utc)
    upper = datetime.combine(end + timedelta(days=1), time.min, timezone.utc)
    rows = {
        source: {
            "source": source,
            "label": label,
            "leads": 0,
            "booked": 0,
            "treated": 0,
            "payments": ZERO,
            "refunds": ZERO,
            "net_revenue": ZERO,
            "spend": None,
            "roas": None,
        }
        for source, label in SOURCES
    }
    for row in (
        Patient.objects.filter(org=org, lead_at__gte=lower, lead_at__lt=upper)
        .values("original_source")
        .annotate(count=Count("id"))
    ):
        rows[row["original_source"]]["leads"] = row["count"]
    for kind, key in (("booked", "booked"), ("treated", "treated")):
        for row in (
            JourneyEvent.objects.filter(
                org=org,
                patient__org=org,
                kind=kind,
                occurred_at__gte=lower,
                occurred_at__lt=upper,
            )
            .values("patient__original_source")
            .annotate(count=Count("patient_id", distinct=True))
        ):
            rows[row["patient__original_source"]][key] = row["count"]
    for row in (
        Receipt.objects.filter(
            excluded=False,
            org=org,
            patient__org=org,
            occurred_at__gte=lower,
            occurred_at__lt=upper,
        )
        .values("patient__original_source", "kind")
        .annotate(total=Sum("amount"))
    ):
        key = "payments" if row["kind"] == "payment" else "refunds"
        rows[row["patient__original_source"]][key] = row["total"]
    for row in (
        MarketingSpend.objects.filter(org=org, date__gte=start, date__lte=end)
        .values("source")
        .annotate(total=Sum("amount"))
    ):
        rows[row["source"]]["spend"] = row["total"]
    for row in rows.values():
        row["net_revenue"] = row["payments"] - row["refunds"]
        if row["spend"] is not None and row["spend"] > 0:
            row["roas"] = round(row["net_revenue"] / row["spend"], 2)
    active = [
        r
        for r in rows.values()
        if r["spend"] is not None
        or any(r[k] for k in ("leads", "booked", "treated", "payments", "refunds"))
    ]
    totals = {
        key: sum(
            (r[key] for r in rows.values()),
            ZERO if key in ("payments", "refunds", "net_revenue") else 0,
        )
        for key in ("leads", "booked", "treated", "payments", "refunds", "net_revenue")
    }
    entered = [r["spend"] for r in rows.values() if r["spend"] is not None]
    totals["spend"] = sum(entered, ZERO) if entered else None
    totals["missing_spend_sources"] = [r["label"] for r in active if r["spend"] is None]
    totals["roas"] = (
        round(totals["net_revenue"] / totals["spend"], 2)
        if totals["spend"] and not totals["missing_spend_sources"]
        else None
    )
    return {
        "start": start,
        "end": end,
        "timezone": "UTC",
        "currency": "USD",
        "totals": totals,
        "sources": list(rows.values()),
        "spend_entries": list(
            MarketingSpend.objects.filter(org=org, date__gte=start, date__lte=end)
            .order_by("-date", "source")
            .values("source", "date", "amount")
        ),
    }
