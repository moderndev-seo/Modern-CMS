"""Local-only patient conversation workspace. No mailbox, transport or send action."""

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from common.models import Profile
from common.permissions import is_org_admin
from contacts.access import (
    assert_contact_access,
    has_contact_access,
    visible_contacts_qs,
)
from patients.appointments import Conflict
from patients.credits import StrictInput
from patients.models import (
    ConversationChange,
    LocalConversation,
    LocalMessage,
    LocalMessageTemplate,
    Patient,
)
from patients.pagination import window
from patients.views import PracticeView
from tasks.access import visible_tasks_qs


def patient_name(patient):
    return f"{patient.contact.first_name} {patient.contact.last_name}".strip()


def conversation_data(row):
    return {
        "id": str(row.id),
        "patient": str(row.patient_id),
        "patient_name": patient_name(row.patient),
        "subject": row.subject,
        "status": row.status,
        "owner": str(row.owner_id) if row.owner_id else None,
        "owner_name": row.owner.user.email if row.owner else "Unassigned",
        "revision": row.revision,
        "draft": row.draft,
        "updated_at": row.updated_at,
        "created_at": row.created_at,
    }


def visible_conversations(profile):
    return LocalConversation.objects.filter(
        org=profile.org,
        patient__org=profile.org,
        patient__contact__in=visible_contacts_qs(profile),
    ).select_related("patient__contact", "owner__user")


def get_conversation(request, pk, lock=False):
    queryset = visible_conversations(request.profile)
    # Lock only the base table: nullable owner joins cannot be locked on PostgreSQL.
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    return get_object_or_404(queryset, pk=pk)


def eligible_owners(profile, patient):
    return [
        p
        for p in Profile.objects.filter(
            org=profile.org, is_active=True, user__is_active=True
        ).select_related("user")
        if has_contact_access(p, patient.contact)
    ]


class ConversationInput(StrictInput):
    patient = serializers.UUIDField()
    subject = serializers.CharField(max_length=200)
    request_id = serializers.UUIDField()


class EntryInput(StrictInput):
    kind = serializers.ChoiceField(choices=["note", "received", "outbound_log"])
    body = serializers.CharField(max_length=5000)
    occurred_at = serializers.DateTimeField()
    request_id = serializers.UUIDField()

    def validate_occurred_at(self, value):
        if value > timezone.now():
            raise ValidationError("Use the actual time, not a future date.")
        return value


class ChangeInput(StrictInput):
    action = serializers.ChoiceField(choices=["draft", "state"])
    revision = serializers.IntegerField(min_value=0)
    request_id = serializers.UUIDField()
    draft = serializers.CharField(
        max_length=5000, allow_blank=True, required=False, trim_whitespace=False
    )
    owner = serializers.UUIDField(allow_null=True, required=False)
    status = serializers.ChoiceField(
        choices=["open", "waiting", "resolved"], required=False
    )

    def validate(self, values):
        expected = {"action", "revision", "request_id"} | (
            {"draft"} if values["action"] == "draft" else {"owner", "status"}
        )
        if set(values) != expected:
            raise ValidationError(
                "Save either a local draft or ownership/status, with exactly its fields."
            )
        return values


class MessagesInbox(PracticeView):
    def get(self, request):
        profile = request.profile
        query = request.query_params.get("search", "").strip()
        if len(query) > 100:
            raise ValidationError("Search must be at most 100 characters.")
        selection = request.query_params.get("status", "active")
        if selection not in ("active", "open", "waiting", "resolved", "all"):
            raise ValidationError("Choose a valid conversation status.")
        owner = request.query_params.get("owner", "all")
        if owner not in ("all", "mine", "unassigned"):
            raise ValidationError("Choose all, mine or unassigned.")
        selected_patient = request.query_params.get("patient")
        patient_filter = None
        if selected_patient:
            patient_id = serializers.UUIDField().run_validation(selected_patient)
            patient_filter = get_object_or_404(
                Patient.objects.filter(
                    org=profile.org, contact__in=visible_contacts_qs(profile)
                ),
                pk=patient_id,
            )
        all_rows = visible_conversations(profile)
        if patient_filter:
            all_rows = all_rows.filter(patient=patient_filter)
        counts = {
            s: all_rows.filter(status=s).count()
            for s in ("open", "waiting", "resolved")
        }
        rows = all_rows
        if selection == "active":
            rows = rows.exclude(status="resolved")
        elif selection != "all":
            rows = rows.filter(status=selection)
        if owner == "mine":
            rows = rows.filter(owner=profile)
        elif owner == "unassigned":
            rows = rows.filter(owner__isnull=True)
        if query:
            people = Q()
            for word in query.split():
                people &= Q(patient__contact__first_name__icontains=word) | Q(
                    patient__contact__last_name__icontains=word
                )
            rows = rows.filter(Q(subject__icontains=query) | people)
        pages = []
        records = [
            conversation_data(row)
            for row in window(
                request,
                "conversations",
                rows.order_by("-updated_at", "id"),
                pages,
                "Conversations",
                20,
            )
        ]
        tasks = (
            visible_tasks_qs(profile)
            .filter(
                contacts__in=visible_contacts_qs(profile),
                contacts__patient__org=profile.org,
            )
            .exclude(status="Completed")
            .distinct()
            .order_by("due_date", "id")
        )
        due = tasks.filter(due_date__lte=timezone.now().date())
        task_filter = request.query_params.get("tasks", "due")
        if task_filter not in ("due", "all"):
            raise ValidationError("Choose due or all follow-ups.")
        task_rows = window(
            request,
            "followups",
            due if task_filter == "due" else tasks,
            pages,
            "Follow-ups",
            20,
        )
        choices = Patient.objects.filter(
            org=profile.org, contact__in=visible_contacts_qs(profile)
        ).select_related("contact")
        if patient_filter:
            choices = choices.filter(pk=patient_filter.pk)
        elif query:
            for word in query.split():
                choices = choices.filter(
                    Q(contact__first_name__icontains=word)
                    | Q(contact__last_name__icontains=word)
                )
        choices = (
            list(choices.order_by("contact__first_name", "id")[:21])
            if patient_filter or len(query) >= 2
            else []
        )
        return Response(
            {
                "mode": "local_only",
                "counts": counts,
                "conversations": records,
                "pages": pages,
                "followup_due_count": due.count(),
                "followups": [
                    {
                        "id": str(t.id),
                        "title": t.title,
                        "due_date": t.due_date,
                        "status": t.status,
                    }
                    for t in task_rows
                ],
                "patient_choices": [
                    {"id": str(p.id), "name": patient_name(p)} for p in choices[:20]
                ],
                "more_patients": len(choices) > 20,
                "can_manage_templates": is_org_admin(profile),
            }
        )

    def post(self, request):
        serializer = ConversationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        patient = self.patient(request, values["patient"])
        assert_contact_access(request.profile, patient.contact)
        try:
            with transaction.atomic():
                # Serializes retries for the same patient, including initial creation.
                Patient.objects.select_for_update().get(
                    pk=patient.id, org=request.profile.org
                )
                old = LocalConversation.objects.filter(
                    org=request.profile.org, request_id=values["request_id"]
                ).first()
                if old:
                    if old.patient_id != patient.id or old.subject != values["subject"]:
                        raise Conflict(
                            "This request already created a different conversation."
                        )
                    return Response({"id": str(old.id), "already_recorded": True})
                row = LocalConversation.objects.create(
                    org=request.profile.org,
                    patient=patient,
                    subject=values["subject"],
                    request_id=values["request_id"],
                    created_by=request.user,
                )
        except IntegrityError as error:
            raise Conflict(
                "Conversation request conflicts with an existing record. Reload and review."
            ) from error
        return Response({"id": str(row.id), "already_recorded": False}, status=201)


class ConversationDetail(PracticeView):
    def get(self, request, conversation_pk):
        row = get_conversation(request, conversation_pk)
        org = request.profile.org
        pages = []
        entries = (
            LocalMessage.objects.filter(org=org, conversation=row)
            .select_related("created_by")
            .order_by("-occurred_at", "-created_at", "id")
        )
        changes = (
            ConversationChange.objects.filter(org=org, conversation=row)
            .select_related("created_by")
            .order_by("-revision")
        )
        owner_names = {
            str(p.id): p.user.email
            for p in Profile.objects.filter(org=org).select_related("user")
        }

        def owner_label(value):
            return (
                owner_names.get(value, "Former practice member")
                if value
                else "Unassigned"
            )

        return Response(
            {
                "conversation": conversation_data(row),
                "pages": pages,
                "owners": [
                    {"id": str(p.id), "name": p.user.email}
                    for p in eligible_owners(request.profile, row.patient)
                ],
                "templates": list(
                    LocalMessageTemplate.objects.filter(org=org, active=True)
                    .order_by("title", "id")
                    .values("id", "title", "body")
                ),
                "entries": [
                    {
                        "id": str(m.id),
                        "kind": m.kind,
                        "body": m.body,
                        "occurred_at": m.occurred_at,
                        "recorded_at": m.created_at,
                        "actor": m.created_by.email if m.created_by else "Not recorded",
                    }
                    for m in window(
                        request, "entries", entries, pages, "Conversation entries", 30
                    )
                ],
                "history": [
                    {
                        "id": str(c.id),
                        "revision": c.revision,
                        "action": c.action,
                        "before": c.before,
                        "after": c.after,
                        "before_owner": owner_label(c.before.get("owner")),
                        "after_owner": owner_label(c.after.get("owner")),
                        "at": c.created_at,
                        "actor": c.created_by.email if c.created_by else "Not recorded",
                    }
                    for c in window(
                        request, "history", changes, pages, "Change history", 30
                    )
                ],
            }
        )

    def patch(self, request, conversation_pk):
        serializer = ChangeInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        org = request.profile.org
        payload = (
            {"draft": values["draft"]}
            if values["action"] == "draft"
            else {
                "owner": str(values["owner"]) if values["owner"] else None,
                "status": values["status"],
            }
        )
        try:
            with transaction.atomic():
                row = get_conversation(request, conversation_pk, lock=True)
                old = ConversationChange.objects.filter(
                    org=org, request_id=values["request_id"]
                ).first()
                if old:
                    if (
                        old.conversation_id != row.id
                        or old.revision != values["revision"] + 1
                        or old.action != values["action"]
                        or old.payload != payload
                    ):
                        raise Conflict("Request already used for another change.")
                    return Response({"id": str(old.id), "already_recorded": True})
                if row.revision != values["revision"]:
                    raise Conflict("Conversation changed. Reload before saving.")
                if values["action"] == "state" and values["owner"]:
                    if values["owner"] not in {
                        p.id for p in eligible_owners(request.profile, row.patient)
                    }:
                        raise ValidationError(
                            "Choose an active practice member who already has access to this patient."
                        )
                if values["action"] == "draft" and row.status == "resolved":
                    raise Conflict("Reopen this conversation before editing its draft.")
                change = ConversationChange.objects.create(
                    org=org,
                    conversation=row,
                    action=values["action"],
                    payload=payload,
                    revision=values["revision"] + 1,
                    request_id=values["request_id"],
                    created_by=request.user,
                )
        except IntegrityError as error:
            raise Conflict(
                "Change rejected. Reload and choose a different valid value."
            ) from error
        return Response({"id": str(change.id), "already_recorded": False}, status=201)


class ConversationEntries(PracticeView):
    def post(self, request, conversation_pk):
        serializer = EntryInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        org = request.profile.org
        try:
            with transaction.atomic():
                row = get_conversation(request, conversation_pk, lock=True)
                old = LocalMessage.objects.filter(
                    org=org, request_id=values["request_id"]
                ).first()
                if old:
                    if old.conversation_id != row.id or any(
                        getattr(old, k) != values[k]
                        for k in ("kind", "body", "occurred_at")
                    ):
                        raise Conflict("Request already used for a different entry.")
                    return Response({"id": str(old.id), "already_recorded": True})
                if row.status == "resolved":
                    raise Conflict("Reopen this conversation before adding entries.")
                entry = LocalMessage.objects.create(
                    org=org, conversation=row, created_by=request.user, **values
                )
                LocalConversation.objects.filter(org=org, pk=row.pk).update(
                    updated_at=entry.created_at, updated_by=request.user
                )
        except IntegrityError as error:
            raise Conflict(
                "Entry rejected. Reload and review this conversation."
            ) from error
        return Response({"id": str(entry.id), "already_recorded": False}, status=201)


class TemplateInput(StrictInput):
    title = serializers.CharField(max_length=100)
    body = serializers.CharField(max_length=5000)
    request_id = serializers.UUIDField()


class MessageTemplates(PracticeView):
    def get(self, request):
        pages = []
        rows = LocalMessageTemplate.objects.filter(org=request.profile.org).order_by(
            "-active", "title", "id"
        )
        return Response(
            {
                "can_manage": is_org_admin(request.profile),
                "pages": pages,
                "templates": [
                    {
                        "id": str(t.id),
                        "title": t.title,
                        "body": t.body,
                        "active": t.active,
                        "revision": t.revision,
                    }
                    for t in window(request, "templates", rows, pages, "Templates", 30)
                ],
            }
        )

    def post(self, request):
        if not is_org_admin(request.profile):
            raise PermissionDenied("Only practice administrators may manage templates.")
        serializer = TemplateInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        row, created = LocalMessageTemplate.objects.get_or_create(
            org=request.profile.org,
            request_id=values["request_id"],
            defaults={**values, "created_by": request.user},
        )
        if row.title != values["title"] or row.body != values["body"]:
            raise Conflict("Request already used for another template.")
        return Response(
            {"id": str(row.id), "already_recorded": not created},
            status=201 if created else 200,
        )


class TemplateDetail(PracticeView):
    def patch(self, request, template_pk):
        if not is_org_admin(request.profile):
            raise PermissionDenied("Only practice administrators may manage templates.")
        if set(request.data) != {"active", "revision"}:
            raise ValidationError("Only active and revision may be supplied.")
        active = serializers.BooleanField().run_validation(request.data["active"])
        revision = serializers.IntegerField(min_value=0).run_validation(
            request.data["revision"]
        )
        with transaction.atomic():
            row = get_object_or_404(
                LocalMessageTemplate.objects.select_for_update(),
                pk=template_pk,
                org=request.profile.org,
            )
            if row.revision != revision:
                raise Conflict("Template changed. Reload before saving.")
            if row.active == active:
                raise Conflict("Template already has that state.")
            row.active = active
            row.revision += 1
            row.updated_by = request.user
            row.save()
        return Response(
            {"id": str(row.id), "active": row.active, "revision": row.revision}
        )
