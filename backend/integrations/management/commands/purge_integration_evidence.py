"""Purge expired fictional replay bodies without forgetting delivery identity."""

from django.core.management.base import BaseCommand, CommandError

from integrations.retention import purge_expired


class Command(BaseCommand):
    help = "Erase expired synthetic integration evidence for one allowlisted TEST practice."

    def add_arguments(self, parser):
        parser.add_argument("--org", required=True)
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        try:
            count = purge_expired(options["org"], options["limit"])
        except ValueError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(
            f"Purged {count} expired replay bodies; receipt identities retained."
        )
