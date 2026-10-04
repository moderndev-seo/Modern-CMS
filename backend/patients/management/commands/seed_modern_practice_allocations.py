"""Add an optional second fictional invoice; never add cash or allocate it automatically."""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.models import Org
from invoices.models import Invoice, InvoiceLineItem
from patients.management.commands.seed_modern_practice import demo_id
from patients.management.commands.seed_modern_practice_billing import demo_context
from patients.models import Patient


class Command(BaseCommand):
    help = "Add a second USD 400 TEST invoice in each demo practice for split-allocation rehearsal. Run the base and billing seeds first."

    def handle(self, *args, **options):
        with transaction.atomic():
            for key in ("harbor", "cedar"):
                org = Org.objects.filter(
                    pk=demo_id(key), name__startswith="TEST -"
                ).first()
                if not org:
                    raise CommandError(
                        "Base TEST practice is missing; run the base and billing seeds first."
                    )
                with demo_context(org):
                    patient = Patient.objects.filter(
                        pk=demo_id(key + ":alex"), org=org
                    ).first()
                    original = Invoice.objects.filter(
                        pk=demo_id(key + ":billing:invoice"), org=org
                    ).first()
                    if not patient or not original:
                        raise CommandError(
                            "Base patient or billing invoice missing; no changes committed."
                        )
                    if Invoice.objects.filter(
                        pk=demo_id(key + ":allocation:invoice"), org=org
                    ).exists():
                        self.stdout.write(
                            f"{org.name}: allocation demo invoice exists; left unchanged."
                        )
                        continue
                    bill = Invoice.objects.create(
                        id=demo_id(key + ":allocation:invoice"),
                        org=org,
                        account=original.account,
                        contact=patient.contact,
                        invoice_title="TEST - Fictional second invoice for allocation rehearsal",
                        invoice_number=f"TEST-{key.upper()}-SPLIT",
                        status="Draft",
                        currency="USD",
                        client_name="Alex Rivera (fictional)",
                        client_email="alex@example.invalid",
                    )
                    InvoiceLineItem.objects.create(
                        id=demo_id(key + ":allocation:line"),
                        org=org,
                        invoice=bill,
                        name="Fictional additional treatment",
                        quantity=1,
                        unit_price=Decimal("400.00"),
                    )
                    bill.save()
                    bill.status = "Sent"
                    bill.save(update_fields=["status"])
                    self.stdout.write(
                        f"{org.name}: USD 400 fictional invoice added; receipts and allocations unchanged."
                    )
