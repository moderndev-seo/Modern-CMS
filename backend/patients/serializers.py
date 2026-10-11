from django.utils import timezone
from rest_framework import serializers

from contacts.access import visible_contacts_qs
from contacts.models import Contact
from patients.models import JourneyEvent, MarketingSpend, Patient, Receipt
from tasks.models import Task


class StrictSerializer(serializers.ModelSerializer):
    """Reject forged server fields and unsupported fields instead of silently ignoring them."""

    def to_internal_value(self, data):
        allowed = {name for name, field in self.fields.items() if not field.read_only}
        invalid = set(data) - allowed
        if invalid:
            raise serializers.ValidationError(
                {name: "This field cannot be set." for name in invalid}
            )
        return super().to_internal_value(data)

    def validate(self, attrs):
        for key in ("occurred_at", "lead_at", "original_at"):
            if attrs.get(key) and attrs[key] > timezone.now():
                raise serializers.ValidationError(
                    {key: "Use an actual timestamp, not a future date."}
                )
        return attrs


class PatientSerializer(StrictSerializer):
    first_name = serializers.CharField(max_length=255, required=False, write_only=True)
    last_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, write_only=True
    )
    email = serializers.EmailField(required=False, allow_blank=True, write_only=True)
    contact = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.none(), required=False
    )
    name = serializers.SerializerMethodField()
    contact_email = serializers.EmailField(
        source="contact.email", read_only=True, allow_null=True
    )

    class Meta:
        model = Patient
        fields = [
            "id",
            "contact",
            "name",
            "contact_email",
            "first_name",
            "last_name",
            "email",
            "lead_at",
            "original_source",
            "original_campaign",
            "original_keyword",
            "original_landing_page",
            "original_at",
        ]
        read_only_fields = ["id"]
        validators = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact"].queryset = visible_contacts_qs(
            self.context["request"].profile
        )

    def get_name(self, obj):
        return f"{obj.contact.first_name} {obj.contact.last_name}".strip()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        org = self.context["request"].profile.org
        contact = attrs.get("contact")
        if contact:
            if any(key in attrs for key in ("first_name", "last_name", "email")):
                raise serializers.ValidationError(
                    "Link an existing contact OR enter a new identity."
                )
            if Patient.objects.filter(org=org, contact=contact).exists():
                raise serializers.ValidationError(
                    {"contact": "This contact already has a patient journey."}
                )
        elif not attrs.get("first_name"):
            raise serializers.ValidationError(
                {"first_name": "Enter a first name or link an existing contact."}
            )
        elif (
            attrs.get("email")
            and Contact.objects.filter(org=org, email__iexact=attrs["email"]).exists()
        ):
            raise serializers.ValidationError(
                {
                    "email": "A contact already uses this email. Link that contact instead."
                }
            )
        lead_at = attrs.get("lead_at", timezone.now())
        if attrs.get("original_at") and attrs["original_at"] > lead_at:
            raise serializers.ValidationError(
                {
                    "original_at": "First touch must be on or before the known lead timestamp."
                }
            )
        return attrs

    def create(self, validated_data):
        identity = {
            key: validated_data.pop(key)
            for key in ("first_name", "last_name", "email")
            if key in validated_data
        }
        if "contact" not in validated_data:
            validated_data["contact"] = Contact.objects.create(
                org=validated_data["org"],
                created_by=validated_data["created_by"],
                **identity,
            )
        return super().create(validated_data)


class EventSerializer(StrictSerializer):
    class Meta:
        model = JourneyEvent
        fields = [
            "id",
            "kind",
            "occurred_at",
            "source",
            "campaign",
            "landing_page",
            "notes",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("occurred_at", timezone.now()) < self.context["patient"].lead_at:
            raise serializers.ValidationError(
                {
                    "occurred_at": "Journey events cannot precede the known lead timestamp."
                }
            )
        if attrs.get("kind") != "touch" and any(
            attrs.get(k) for k in ("campaign", "landing_page")
        ):
            raise serializers.ValidationError(
                "Campaign and landing page belong on marketing touches."
            )
        return attrs


class ReceiptSerializer(StrictSerializer):
    payment = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Receipt
        fields = [
            "id",
            "excluded",
            "kind",
            "amount",
            "occurred_at",
            "payment",
            "reference",
            "notes",
        ]
        read_only_fields = ["id", "excluded"]
        validators = []

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["amount"] <= 0:
            raise serializers.ValidationError(
                {"amount": "Enter a positive USD amount."}
            )
        if attrs.get("occurred_at", timezone.now()) < self.context["patient"].lead_at:
            raise serializers.ValidationError(
                {"occurred_at": "Receipts cannot precede the known lead timestamp."}
            )
        if (attrs["kind"] == "refund") != bool(attrs.get("payment")):
            raise serializers.ValidationError(
                {
                    "payment": "Refunds require the original payment; payments must not link another payment."
                }
            )
        return attrs


class SpendSerializer(StrictSerializer):
    class Meta:
        model = MarketingSpend
        fields = ["source", "date", "amount"]
        validators = []

    def validate(self, attrs):
        if attrs["amount"] < 0:
            raise serializers.ValidationError({"amount": "Spend cannot be negative."})
        if attrs["date"] > timezone.now().date():
            raise serializers.ValidationError(
                {"date": "Only record actual spend through today (UTC)."}
            )
        return attrs


class FollowupSerializer(StrictSerializer):
    due_date = serializers.DateField(required=True, allow_null=False)
    priority = serializers.ChoiceField(choices=Task.PRIORITY_CHOICES, default="Medium")
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=2000
    )

    class Meta:
        model = Task
        fields = ["id", "title", "status", "priority", "due_date", "description"]
        read_only_fields = ["id", "status"]
