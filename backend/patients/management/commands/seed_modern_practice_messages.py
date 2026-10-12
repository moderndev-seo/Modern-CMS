"""Add clearly fictional local conversations; never connect a sending service."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.models import Org, Profile
from patients.management.commands.seed_modern_practice import demo_id, stamp
from patients.management.commands.seed_modern_practice_billing import demo_context
from patients.models import (
    ConversationChange,
    LocalConversation,
    LocalMessage,
    LocalMessageTemplate,
    Patient,
)


class Command(BaseCommand):
    help = "Add local-only fictional messages to the two existing TEST practices. Requires an existing active practice administrator; never grants access. Safe to rerun."

    def handle(self, *args, **options):
        with transaction.atomic():
            for key, name in [
                ("harbor", "TEST - Harbor Spine & Ortho (fictional)"),
                ("cedar", "TEST - Cedar Family Dental (fictional)"),
            ]:
                org = Org.objects.filter(pk=demo_id(key), name=name).first()
                if not org:
                    raise CommandError(
                        "Run the base demo seed first; exact fictional practice missing."
                    )
                with demo_context(org):
                    patient = Patient.objects.filter(
                        pk=demo_id(key + ":alex"), org=org
                    ).first()
                    actor = (
                        Profile.objects.filter(
                            org=org, role="ADMIN", is_active=True, user__is_active=True
                        )
                        .select_related("user")
                        .order_by("id")
                        .first()
                    )
                    if not patient or not actor:
                        raise CommandError(
                            "Demo patient or existing active practice administrator missing; no rows changed."
                        )
                    thread, created = LocalConversation.objects.get_or_create(
                        id=demo_id(key + ":messages:conversation"),
                        defaults={
                            "org": org,
                            "patient": patient,
                            "subject": "TEST - Fictional treatment follow-up",
                            "request_id": demo_id(key + ":messages:start"),
                            "created_by": actor.user,
                        },
                    )
                    if created:
                        LocalMessage.objects.create(
                            id=demo_id(key + ":messages:entry"),
                            org=org,
                            conversation=thread,
                            kind="received",
                            body="TEST - Fictional patient asks what to prepare for a follow-up visit. Manually logged for this demo; no real message was received.",
                            occurred_at=stamp(18),
                            request_id=demo_id(key + ":messages:entry-request"),
                            created_by=actor.user,
                        )
                        ConversationChange.objects.create(
                            id=demo_id(key + ":messages:draft"),
                            org=org,
                            conversation=thread,
                            action="draft",
                            payload={
                                "draft": "TEST - Fictional draft: Our team will help confirm the details for your follow-up visit."
                            },
                            revision=1,
                            request_id=demo_id(key + ":messages:draft-request"),
                            created_by=actor.user,
                        )
                    LocalMessageTemplate.objects.get_or_create(
                        id=demo_id(key + ":messages:template"),
                        defaults={
                            "org": org,
                            "title": "TEST - Follow-up planning",
                            "body": "Please confirm a convenient time for our team to follow up. Review this wording before using it outside this local workspace.",
                            "request_id": demo_id(key + ":messages:template-request"),
                            "created_by": actor.user,
                        },
                    )
                    self.stdout.write(
                        f"{org.name}: {'created' if created else 'preserved'} local conversation; nothing sent."
                    )
