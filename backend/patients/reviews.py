"""Manual review tracking only; no review provider, public reply or invitation."""

from datetime import datetime, time, timedelta
from datetime import timezone as utc

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from contacts.access import assert_contact_access, visible_contacts_qs
from patients.appointments import Conflict
from patients.credits import StrictInput
from patients.messages import patient_name
from patients.models import Patient, PracticeReview, ReviewChange
from patients.pagination import window
from patients.views import PracticeView


def visible_reviews(profile):
    return PracticeReview.objects.filter(
        org=profile.org,
        patient__org=profile.org,
        patient__contact__in=visible_contacts_qs(profile),
    ).select_related("patient__contact")


def review_data(row):
    return {
        "id": str(row.id),
        "patient": str(row.patient_id),
        "patient_name": patient_name(row.patient),
        "source": row.source,
        "rating": row.rating,
        "body": row.body,
        "reviewed_at": row.reviewed_at,
        "recorded_at": row.created_at,
        "status": row.status,
        "draft": row.draft,
        "revision": row.revision,
    }


class ReviewInput(StrictInput):
    patient = serializers.UUIDField()
    source = serializers.ChoiceField(choices=PracticeReview.SOURCES, default="unknown")
    rating = serializers.IntegerField(
        min_value=1, max_value=5, allow_null=True, required=False, default=None
    )
    body = serializers.CharField(
        max_length=5000, allow_blank=True, required=False, default=""
    )
    reviewed_at = serializers.DateTimeField()
    request_id = serializers.UUIDField()

    def validate(self, values):
        if values["reviewed_at"] > timezone.now():
            raise ValidationError("Use the actual review date, not a future date.")
        if values["rating"] is None and not values["body"]:
            raise ValidationError(
                "Record a rating or review text; do not invent missing details."
            )
        return values


class ReviewUpdate(StrictInput):
    action = serializers.ChoiceField(choices=["draft", "status"])
    revision = serializers.IntegerField(min_value=0)
    request_id = serializers.UUIDField()
    draft = serializers.CharField(
        max_length=5000, allow_blank=True, trim_whitespace=False, required=False
    )
    status = serializers.ChoiceField(choices=PracticeReview.STATUSES, required=False)
    reason = serializers.CharField(max_length=1000, required=False)

    def validate(self, values):
        expected = {"action", "revision", "request_id"} | (
            {"draft"} if values["action"] == "draft" else {"status", "reason"}
        )
        if set(values) != expected:
            raise ValidationError(
                "Save either a draft or a status with its reason, using exactly those fields."
            )
        return values


def summary(rows):
    result = rows.aggregate(
        count=Count("id"), rated_count=Count("rating"), average=Avg("rating")
    )
    result["unrated_count"] = result["count"] - result["rated_count"]
    result["needs_attention"] = rows.filter(status__in=["open", "in_progress"]).count()
    result["histogram"] = [
        {"rating": r, "count": rows.filter(rating=r).count()} for r in range(5, 0, -1)
    ]
    sources = {
        r["source"]: r
        for r in rows.values("source").annotate(
            count=Count("id"), rated_count=Count("rating"), average=Avg("rating")
        )
    }
    result["sources"] = [
        {
            "source": key,
            "label": label,
            **sources.get(key, {"count": 0, "rated_count": 0, "average": None}),
        }
        for key, label in PracticeReview.SOURCES
    ]
    return result


class ReviewList(PracticeView):
    def get(self, request):
        today = timezone.now().date()
        date = serializers.DateField()
        start = date.run_validation(
            request.query_params.get("start", str(today - timedelta(days=29)))
        )
        end = date.run_validation(request.query_params.get("end", str(today)))
        if start > end or end.year >= 9999 or end - start > timedelta(days=3660):
            raise ValidationError("Choose an ordered date range of at most ten years.")
        lower = datetime.combine(start, time.min, utc.utc)
        upper = datetime.combine(end + timedelta(days=1), time.min, utc.utc)
        rows = visible_reviews(request.profile).filter(
            reviewed_at__gte=lower, reviewed_at__lt=upper
        )
        choices = Patient.objects.filter(
            org=request.profile.org, contact__in=visible_contacts_qs(request.profile)
        ).select_related("contact")
        patient_filter = request.query_params.get("patient")
        if patient_filter:
            patient_id = serializers.UUIDField().run_validation(patient_filter)
            patient = get_object_or_404(choices, pk=patient_id)
            rows = rows.filter(patient=patient)
            choices = choices.filter(pk=patient_id)
        report = summary(rows.exclude(status="archived"))
        status = request.query_params.get("status", "active")
        source = request.query_params.get("source", "all")
        if status not in ["active", "all", *[s for s, _ in PracticeReview.STATUSES]]:
            raise ValidationError("Choose a valid review status.")
        if source not in ["all", *[s for s, _ in PracticeReview.SOURCES]]:
            raise ValidationError("Choose a valid review source.")
        if status == "active":
            rows = rows.exclude(status="archived")
        elif status != "all":
            rows = rows.filter(status=status)
        if source != "all":
            rows = rows.filter(source=source)
        query = request.query_params.get("search", "").strip()
        if len(query) > 100:
            raise ValidationError("Search must be at most 100 characters.")
        if query:
            people = Q()
            for word in query.split():
                people &= Q(patient__contact__first_name__icontains=word) | Q(
                    patient__contact__last_name__icontains=word
                )
                if not patient_filter:
                    choices = choices.filter(
                        Q(contact__first_name__icontains=word)
                        | Q(contact__last_name__icontains=word)
                    )
            rows = rows.filter(people | Q(body__icontains=query))
        patient_choices = (
            list(choices.order_by("contact__first_name", "id")[:21])
            if patient_filter or len(query) >= 2
            else []
        )
        pages = []
        records = [
            review_data(row)
            for row in window(
                request,
                "reviews",
                rows.order_by("-reviewed_at", "-created_at", "id"),
                pages,
                "Reviews",
                20,
            )
        ]
        return Response(
            {
                "start": start,
                "end": end,
                "summary": report,
                "reviews": records,
                "pages": pages,
                "patient_choices": [
                    {"id": str(p.id), "name": patient_name(p)}
                    for p in patient_choices[:20]
                ],
                "more_patients": len(patient_choices) > 20,
                "sources": PracticeReview.SOURCES,
                "statuses": PracticeReview.STATUSES,
            }
        )

    def post(self, request):
        serializer = ReviewInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        patient = self.patient(request, values["patient"])
        assert_contact_access(request.profile, patient.contact)
        try:
            with transaction.atomic():
                Patient.objects.select_for_update().get(
                    pk=patient.id, org=request.profile.org
                )
                old = PracticeReview.objects.filter(
                    org=request.profile.org, request_id=values["request_id"]
                ).first()
                if old:
                    if old.patient_id != patient.id or any(
                        getattr(old, k) != values[k]
                        for k in ("source", "rating", "body", "reviewed_at")
                    ):
                        raise Conflict("Request already used for a different review.")
                    return Response({"id": str(old.id), "already_recorded": True})
                row = PracticeReview.objects.create(
                    org=request.profile.org,
                    patient=patient,
                    created_by=request.user,
                    **{k: v for k, v in values.items() if k != "patient"},
                )
        except IntegrityError as error:
            raise Conflict(
                "Review conflicts with an existing record. Reload and review."
            ) from error
        return Response({"id": str(row.id), "already_recorded": False}, status=201)


class ReviewDetail(PracticeView):
    def get(self, request, review_pk):
        row = get_object_or_404(visible_reviews(request.profile), pk=review_pk)
        pages = []
        history = (
            ReviewChange.objects.filter(org=request.profile.org, review=row)
            .select_related("created_by")
            .order_by("-revision")
        )
        entries = [
            {
                "id": str(c.id),
                "action": c.action,
                "reason": c.reason,
                "before": c.before,
                "after": c.after,
                "revision": c.revision,
                "at": c.created_at,
                "actor": c.created_by.email if c.created_by else "Not recorded",
            }
            for c in window(request, "history", history, pages, "Review history", 30)
        ]
        return Response(
            {
                "review": review_data(row),
                "history": entries,
                "pages": pages,
                "sources": PracticeReview.SOURCES,
                "statuses": PracticeReview.STATUSES,
            }
        )

    def patch(self, request, review_pk):
        serializer = ReviewUpdate(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        action = values["action"]
        payload = {action: values[action]}
        reason = values.get("reason", "")
        try:
            with transaction.atomic():
                row = get_object_or_404(
                    visible_reviews(request.profile).select_for_update(of=("self",)),
                    pk=review_pk,
                )
                old = ReviewChange.objects.filter(
                    org=request.profile.org, request_id=values["request_id"]
                ).first()
                if old:
                    if (
                        old.review_id != row.id
                        or old.revision != values["revision"] + 1
                        or old.action != action
                        or old.payload != payload
                        or old.reason != reason
                    ):
                        raise Conflict("Request already used for a different change.")
                    return Response({"id": str(old.id), "already_recorded": True})
                if row.revision != values["revision"]:
                    raise Conflict("Review changed. Reload before saving.")
                if action == "draft" and row.status == "archived":
                    raise Conflict("Restore this review before changing its draft.")
                change = ReviewChange.objects.create(
                    org=request.profile.org,
                    review=row,
                    action=action,
                    payload=payload,
                    reason=reason,
                    revision=values["revision"] + 1,
                    request_id=values["request_id"],
                    created_by=request.user,
                )
        except IntegrityError as error:
            raise Conflict(
                "Change rejected. Reload and choose a different valid value."
            ) from error
        return Response({"id": str(change.id), "already_recorded": False}, status=201)
