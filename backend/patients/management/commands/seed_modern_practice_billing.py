"""Add fictional invoice payment counterparts for the existing two demo practices."""

from contextlib import contextmanager

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from accounts.models import Account
from common.models import Org
from invoices.models import Invoice, InvoiceLineItem, Payment
from patients.management.commands.seed_modern_practice import demo_id
from patients.models import Receipt


@contextmanager
def demo_context(org):
    if connection.vendor != "postgresql":
        yield
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org', true)")
        previous = cursor.fetchone()[0] or ""
        cursor.execute("SELECT set_config('app.current_org', %s, true)", [str(org.id)])
    try:
        yield
    finally:
        if not connection.needs_rollback:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_org', %s, true)", [previous]
                )


class Command(BaseCommand):
    help = "Add fictional billing counterparts only; never add receipts or automatically match them. Run the base demo seed first."

    def handle(self, *args, **options):
        with transaction.atomic():
            for key in ("harbor", "cedar"):
                org = Org.objects.filter(
                    pk=demo_id(key), name__startswith="TEST -"
                ).first()
                if not org:
                    raise CommandError(
                        "Run seed_modern_practice first; fictional practice missing."
                    )
                with demo_context(org):
                    receipt = (
                        Receipt.objects.select_related("patient__contact")
                        .filter(
                            pk=demo_id(key + ":alex:payment"), org=org, kind="payment"
                        )
                        .first()
                    )
                    if not receipt:
                        raise CommandError(
                            "Base demo payment is missing; no billing rows changed."
                        )
                    if Invoice.objects.filter(
                        pk=demo_id(key + ":billing:invoice"), org=org
                    ).exists():
                        self.stdout.write(
                            f"{org.name}: billing demo already exists; left unchanged."
                        )
                        continue
                    account, _ = Account.objects.get_or_create(
                        pk=demo_id(key + ":billing:account"),
                        defaults={
                            "org": org,
                            "name": "TEST - Fictional patient billing",
                        },
                    )
                    invoice = Invoice.objects.create(
                        id=demo_id(key + ":billing:invoice"),
                        org=org,
                        account=account,
                        contact=receipt.patient.contact,
                        invoice_title="TEST - Fictional treatment invoice",
                        invoice_number=f"TEST-{key.upper()}-MATCH",
                        status="Draft",
                        currency="USD",
                        client_name="Alex Rivera (fictional)",
                        client_email="alex@example.invalid",
                    )
                    InvoiceLineItem.objects.create(
                        id=demo_id(key + ":billing:line"),
                        org=org,
                        invoice=invoice,
                        name="Fictional treatment",
                        quantity=1,
                        unit_price=receipt.amount,
                    )
                    invoice.save()  # Existing invoice calculation derives total from its line.
                    invoice.status = "Sent"
                    invoice.save(update_fields=["status"])
                    Payment.objects.create(
                        id=demo_id(key + ":billing:payment"),
                        org=org,
                        invoice=invoice,
                        amount=receipt.amount,
                        payment_date=receipt.occurred_at.date(),
                        payment_method="CASH",
                        reference_number="TEST - " + receipt.reference,
                        notes="Fictional counterpart only. No live charge. Match manually after review.",
                    )
                    self.stdout.write(
                        f"{org.name}: fictional invoice/payment added; receipts unchanged."
                    )
