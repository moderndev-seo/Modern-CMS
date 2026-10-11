"""Patient journeys extend Contact; receipts never stand in for invoices."""

from django.db import models
from django.utils import timezone

from common.base import BaseOrgModel

SOURCES = [
    ("google_ads", "Google Ads"),
    ("organic_search", "Organic search"),
    ("meta_ads", "Meta Ads"),
    ("referral", "Referral"),
    ("email", "Email"),
    ("direct", "Direct"),
    ("unknown", "Unknown"),
]


class Patient(BaseOrgModel):
    contact = models.OneToOneField("contacts.Contact", on_delete=models.PROTECT)
    lead_at = models.DateTimeField(default=timezone.now)
    original_source = models.CharField(
        max_length=30, choices=SOURCES, default="unknown"
    )
    original_campaign = models.CharField(max_length=255, blank=True)
    original_keyword = models.CharField(max_length=255, blank=True)
    original_landing_page = models.URLField(max_length=1000, blank=True)
    original_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mp_patient"
        indexes = [models.Index(fields=["org", "-created_at"])]


class JourneyEvent(BaseOrgModel):
    KINDS = [
        ("touch", "Marketing touch"),
        ("booked", "Appointment booked"),
        ("attended", "Appointment attended"),
        ("consultation", "Consultation"),
        ("treated", "Treatment completed"),
    ]
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="events"
    )
    kind = models.CharField(max_length=20, choices=KINDS)
    occurred_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=30, choices=SOURCES, default="unknown")
    campaign = models.CharField(max_length=255, blank=True)
    landing_page = models.URLField(max_length=1000, blank=True)
    notes = models.TextField(blank=True, max_length=2000)

    class Meta:
        db_table = "mp_journey_event"
        indexes = [models.Index(fields=["org", "patient", "occurred_at"])]


class Receipt(BaseOrgModel):
    excluded = models.BooleanField(default=False, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="receipts"
    )
    kind = models.CharField(
        max_length=10, choices=[("payment", "Payment"), ("refund", "Refund")]
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    occurred_at = models.DateTimeField(default=timezone.now)
    payment = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="refunds"
    )
    reference = models.CharField(max_length=100)
    notes = models.TextField(blank=True, max_length=2000)

    class Meta:
        db_table = "mp_receipt"
        indexes = [models.Index(fields=["org", "occurred_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="mp_receipt_positive"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(kind="payment", payment__isnull=True)
                    | models.Q(kind="refund", payment__isnull=False)
                ),
                name="mp_refund_has_payment",
            ),
            models.UniqueConstraint(
                fields=["org", "reference"], name="mp_receipt_reference"
            ),
        ]


class MarketingSpend(BaseOrgModel):
    source = models.CharField(max_length=30, choices=SOURCES)
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "mp_marketing_spend"
        indexes = [models.Index(fields=["org", "date"])]
        constraints = [
            models.UniqueConstraint(
                fields=["org", "source", "date"], name="mp_daily_spend"
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gte=0), name="mp_spend_nonnegative"
            ),
        ]


class Appointment(BaseOrgModel):
    STATUSES = [
        (value, value.replace("_", " ").title())
        for value in ("scheduled", "attended", "cancelled", "no_show")
    ]
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="appointments"
    )
    request_id = models.UUIDField()
    title = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUSES, default="scheduled")
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "mp_appointment"
        indexes = [models.Index(fields=["org", "patient", "starts_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["org", "request_id"], name="mp_appointment_request"
            ),
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="mp_appointment_order",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["scheduled", "attended", "cancelled", "no_show"]
                ),
                name="mp_appointment_status",
            ),
        ]


class AppointmentChange(BaseOrgModel):
    appointment = models.ForeignKey(
        Appointment, on_delete=models.PROTECT, related_name="changes"
    )
    action = models.CharField(max_length=20)
    reason = models.CharField(max_length=1000)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    journey_event = models.OneToOneField(
        JourneyEvent, null=True, blank=True, on_delete=models.PROTECT
    )

    class Meta:
        db_table = "mp_appointment_change"
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["org", "appointment", "created_at"])]


class PaymentMatch(BaseOrgModel):
    """Immutable evidence that two existing records represented the same payment."""

    receipt = models.ForeignKey(
        Receipt, on_delete=models.PROTECT, related_name="invoice_matches"
    )
    invoice_payment = models.ForeignKey(
        "invoices.Payment", on_delete=models.PROTECT, related_name="patient_matches"
    )
    reason = models.CharField(max_length=1000)
    snapshot = models.JSONField(default=dict)
    active = models.BooleanField(default=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["receipt"],
                condition=models.Q(active=True),
                name="mp_active_receipt_match",
            ),
            models.UniqueConstraint(
                fields=["invoice_payment"],
                condition=models.Q(active=True),
                name="mp_active_invoice_match",
            ),
        ]
        db_table = "mp_payment_match"
        ordering = ["created_at", "id"]


class PaymentMatchReversal(BaseOrgModel):
    """Permanent correction evidence; original match facts are never rewritten."""

    match = models.OneToOneField(
        PaymentMatch, on_delete=models.PROTECT, related_name="reversal"
    )
    reason = models.CharField(max_length=1000)

    class Meta:
        db_table = "mp_payment_match_reversal"
        ordering = ["created_at", "id"]


class InvoiceCreditAdjustment(BaseOrgModel):
    """Charge-reduction evidence, separate from cash and the original invoice."""

    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="invoice_credits"
    )
    invoice = models.ForeignKey(
        "invoices.Invoice", on_delete=models.PROTECT, related_name="practice_credits"
    )
    request_id = models.UUIDField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=1000)
    snapshot = models.JSONField(default=dict)
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal"
    )

    class Meta:
        db_table = "mp_invoice_credit"
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="mp_invoice_credit_positive"
            ),
            models.UniqueConstraint(
                fields=["org", "request_id"], name="mp_invoice_credit_request"
            ),
        ]


class ReceiptAllocation(BaseOrgModel):
    """Each immutable version replaces the complete allocation for one receipt."""

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT)
    receipt = models.ForeignKey(Receipt, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    request_id = models.UUIDField()
    reason = models.CharField(max_length=1000)
    lines = models.JSONField(default=list)
    refund_lines = models.JSONField(default=list)
    snapshot = models.JSONField(default=dict)

    class Meta:
        db_table = "mp_receipt_allocation"
        constraints = [
            models.UniqueConstraint(
                fields=["org", "request_id"], name="mp_allocation_request"
            ),
            models.UniqueConstraint(
                fields=["receipt", "revision"], name="mp_allocation_revision"
            ),
            models.CheckConstraint(
                condition=models.Q(revision__gt=0),
                name="mp_allocation_revision_positive",
            ),
        ]


class ReceiptCorrection(BaseOrgModel):
    """Permanent amount-correction evidence; never represents a money transfer."""

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT)
    receipt = models.ForeignKey(Receipt, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    request_id = models.UUIDField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=1000)
    snapshot = models.JSONField(default=dict)

    class Meta:
        db_table = "mp_receipt_correction"
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["org", "request_id"], name="mp_cash_correction_request"
            ),
            models.UniqueConstraint(
                fields=["receipt", "revision"], name="mp_cash_correction_revision"
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="mp_cash_correction_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(revision__gt=0),
                name="mp_cash_correction_revision_positive",
            ),
        ]


class ReceiptExclusion(BaseOrgModel):
    """Append-only decisions to exclude or restore a duplicate payment."""

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT)
    receipt = models.ForeignKey(
        Receipt, on_delete=models.PROTECT, related_name="exclusions"
    )
    retained = models.ForeignKey(
        Receipt,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="duplicate_decisions",
    )
    excluded = models.BooleanField()
    revision = models.PositiveIntegerField()
    request_id = models.UUIDField()
    reason = models.CharField(max_length=1000)
    snapshot = models.JSONField(default=dict)

    class Meta:
        db_table = "mp_receipt_exclusion"
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["org", "request_id"], name="mp_exclusion_request"
            ),
            models.UniqueConstraint(
                fields=["receipt", "revision"], name="mp_exclusion_revision"
            ),
            models.CheckConstraint(
                condition=models.Q(revision__gt=0),
                name="mp_exclusion_revision_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(excluded=True, retained__isnull=False)
                    | models.Q(excluded=False, retained__isnull=True)
                ),
                name="mp_exclusion_retained",
            ),
        ]
