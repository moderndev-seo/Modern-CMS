"""Add only deterministic fictional records; never replace existing practice data."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from common.models import Org, Profile, User
from contacts.models import Contact
from patients.models import JourneyEvent, MarketingSpend, Patient, Receipt


def demo_id(key):
    return uuid5(NAMESPACE_URL, f"modern-practice-milestone-1:{key}")


def stamp(day, hour=12):
    return datetime(2026, 9, day, hour, tzinfo=timezone.utc)


class Command(BaseCommand):
    help = "Seed two fictional test practices idempotently. Optional --member-email grants an existing active user access to ONLY these demo practices."

    def add_arguments(self, parser):
        parser.add_argument("--member-email")

    def handle(self, *args, **options):
        member = None
        if options["member_email"]:
            member = User.objects.filter(
                email__iexact=options["member_email"], is_active=True
            ).first()
            if not member:
                raise CommandError(
                    "The member email must identify an existing active user."
                )
        previous = ""
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.current_org', true)")
                previous = cursor.fetchone()[0] or ""
        try:
            with transaction.atomic():
                for key, name in (
                    ("harbor", "TEST - Harbor Spine & Ortho (fictional)"),
                    ("cedar", "TEST - Cedar Family Dental (fictional)"),
                ):
                    org, created = Org.objects.get_or_create(
                        id=demo_id(key),
                        defaults={
                            "name": name,
                            "default_currency": "USD",
                            "timezone": "UTC",
                        },
                    )
                    if not created and org.name != name:
                        raise CommandError(
                            "Demo identifier is already occupied by a different practice. No data changed."
                        )
                    if connection.vendor == "postgresql":
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "SELECT set_config('app.current_org', %s, true)",
                                [str(org.id)],
                            )
                    if member:
                        Profile.objects.get_or_create(
                            user=member, org=org, defaults={"role": "ADMIN"}
                        )
                    Contact.objects.get_or_create(
                        id=demo_id(f"{key}:intake:contact"),
                        defaults={
                            "org": org,
                            "first_name": "Taylor",
                            "last_name": "Intake Demo",
                            "email": f"intake.{key}@example.invalid",
                            "description": "Fictional contact for demonstrating existing-contact selection. No journey created by the seed.",
                        },
                    )
                    for suffix, first, last, source, campaign in (
                        ("alex", "Alex", "Rivera", "google_ads", "September care"),
                        ("jordan", "Jordan", "Ellis", "referral", ""),
                        ("casey", "Casey", "Morgan", "unknown", ""),
                    ):
                        identity = f"{key}:{suffix}"
                        contact, _ = Contact.objects.get_or_create(
                            id=demo_id(identity + ":contact"),
                            defaults={
                                "org": org,
                                "first_name": first,
                                "last_name": last,
                                "email": f"{suffix}.{key}@example.invalid",
                            },
                        )
                        patient, _ = Patient.objects.get_or_create(
                            id=demo_id(identity),
                            defaults={
                                "org": org,
                                "contact": contact,
                                "lead_at": stamp(2),
                                "original_source": source,
                                "original_campaign": campaign,
                                "original_keyword": "specialist near me"
                                if source == "google_ads"
                                else "",
                                "original_landing_page": "https://example.invalid/care"
                                if source == "google_ads"
                                else "",
                                "original_at": stamp(1)
                                if source != "unknown"
                                else None,
                            },
                        )
                        events = (
                            [
                                ("booked", 3),
                                ("attended", 5),
                                ("consultation", 5),
                                ("treated", 8),
                                ("touch", 9),
                            ]
                            if suffix == "alex"
                            else ([("booked", 4)] if suffix == "jordan" else [])
                        )
                        for kind, day in events:
                            JourneyEvent.objects.get_or_create(
                                id=demo_id(identity + ":" + kind),
                                defaults={
                                    "org": org,
                                    "patient": patient,
                                    "kind": kind,
                                    "occurred_at": stamp(day),
                                    "source": "email" if kind == "touch" else "unknown",
                                    "campaign": "Return visit"
                                    if kind == "touch"
                                    else "",
                                    "notes": "Fictional milestone-one demonstration.",
                                },
                            )
                        if suffix == "alex":
                            amount = (
                                Decimal("1200.00")
                                if key == "harbor"
                                else Decimal("800.00")
                            )
                            payment, _ = Receipt.objects.get_or_create(
                                id=demo_id(identity + ":payment"),
                                defaults={
                                    "org": org,
                                    "patient": patient,
                                    "kind": "payment",
                                    "amount": amount,
                                    "occurred_at": stamp(10),
                                    "reference": f"DEMO-{key}-001",
                                },
                            )
                            Receipt.objects.get_or_create(
                                id=demo_id(identity + ":refund"),
                                defaults={
                                    "org": org,
                                    "patient": patient,
                                    "kind": "refund",
                                    "amount": Decimal("100.00"),
                                    "occurred_at": stamp(12),
                                    "payment": payment,
                                    "reference": f"DEMO-{key}-REFUND-001",
                                },
                            )
                    MarketingSpend.objects.get_or_create(
                        org=org,
                        source="google_ads",
                        date=stamp(1).date(),
                        defaults={"amount": Decimal("200.00")},
                    )
                    MarketingSpend.objects.get_or_create(
                        org=org,
                        source="referral",
                        date=stamp(1).date(),
                        defaults={"amount": Decimal("0.00")},
                    )
                    self.stdout.write(f"{name}: {org.id}")
        finally:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.current_org', %s, false)", [previous]
                    )
        self.stdout.write(
            self.style.SUCCESS(
                "Demo seed complete; existing records retained. Reporting period: 2026-09-01 to 2026-09-30 (UTC)."
            )
        )
