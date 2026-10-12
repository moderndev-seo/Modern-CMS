"""Add only fictional local review records; never contact a review provider."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.models import Org, Profile
from patients.management.commands.seed_modern_practice import demo_id, stamp
from patients.management.commands.seed_modern_practice_billing import demo_context
from patients.models import Patient, PracticeReview, ReviewChange


class Command(BaseCommand):
    help = "Add local reviews only to the two exact fictional TEST practices. Requires existing patients and administrators; safe to rerun without overwriting edits."

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
                    actor = (
                        Profile.objects.filter(
                            org=org, role="ADMIN", is_active=True, user__is_active=True
                        )
                        .select_related("user")
                        .order_by("id")
                        .first()
                    )
                    if not actor:
                        raise CommandError(
                            "An existing active TEST practice administrator is required; no access granted."
                        )
                    for suffix, source, rating, body in [
                        (
                            "alex",
                            "google",
                            5 if key == "harbor" else 4,
                            "TEST - Fictional feedback: the team explained the next steps clearly.",
                        ),
                        (
                            "jordan",
                            "healthgrades",
                            2 if key == "harbor" else 1,
                            "TEST - Fictional feedback: check-in took longer than expected.",
                        ),
                        (
                            "casey",
                            "unknown",
                            None,
                            "TEST - Fictional feedback: please make parking directions easier to find. No rating or source was recorded.",
                        ),
                    ]:
                        patient = Patient.objects.filter(
                            pk=demo_id(key + ":" + suffix), org=org
                        ).first()
                        if not patient:
                            raise CommandError(
                                "Existing fictional patient missing; no rows changed."
                            )
                        row, created = PracticeReview.objects.get_or_create(
                            pk=demo_id(key + ":reviews:" + suffix),
                            defaults={
                                "org": org,
                                "patient": patient,
                                "source": source,
                                "rating": rating,
                                "body": body,
                                "reviewed_at": stamp(18),
                                "request_id": demo_id(
                                    key + ":reviews:request:" + suffix
                                ),
                                "created_by": actor.user,
                            },
                        )
                        if created and suffix == "alex":
                            ReviewChange.objects.create(
                                org=org,
                                review=row,
                                action="draft",
                                payload={
                                    "draft": "TEST - Fictional local draft: Thank you for sharing your feedback."
                                },
                                revision=1,
                                request_id=demo_id(key + ":reviews:initial-draft"),
                                created_by=actor.user,
                            )
                    self.stdout.write(
                        f"{org.name}: local fictional reviews created or preserved; nothing requested or posted."
                    )
