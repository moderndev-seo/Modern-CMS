"""Read-only local setup checks; no patient rows or environment values are output."""

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor

from common.rls import INSERT_POLICY, ISOLATION_POLICY, ORG_SCOPED_TABLES

LOCAL_EMAIL_BACKENDS = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
}


def inspect_setup():
    checks = []

    def record(name, passed, detail):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    record(
        "local_email",
        settings.EMAIL_BACKEND in LOCAL_EMAIL_BACKENDS,
        "Email backend must be console, in-memory or dummy for this local workflow.",
    )
    record("postgresql", connection.vendor == "postgresql", "PostgreSQL is required.")
    if connection.vendor != "postgresql":
        return checks

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        role = cursor.fetchone()
        record(
            "application_role",
            role is not None and not any(role),
            "Application role must be neither superuser nor BYPASSRLS.",
        )
        cursor.execute(
            """SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                      array_agg(p.polname) FILTER (WHERE p.polname IS NOT NULL)
               FROM pg_class c
               LEFT JOIN pg_policy p ON p.polrelid = c.oid
               WHERE c.relnamespace = 'public'::regnamespace
                 AND c.relname = ANY(%s)
               GROUP BY c.oid, c.relname, c.relrowsecurity, c.relforcerowsecurity""",
            [ORG_SCOPED_TABLES],
        )
        tables = {row[0]: row[1:] for row in cursor.fetchall()}
    for name in sorted(ORG_SCOPED_TABLES):
        state = tables.get(name)
        passed = (
            state is not None
            and state[0]
            and state[1]
            and {ISOLATION_POLICY, INSERT_POLICY}.issubset(state[2] or [])
        )
        record(
            f"rls:{name}",
            passed,
            "Table must exist with enabled/forced RLS and both named tenant policies.",
        )
    executor = MigrationExecutor(connection)
    pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    record("migrations", not pending, f"{len(pending)} pending migration steps.")
    return checks


class Command(BaseCommand):
    help = "Check local Modern Practice setup without changing settings or records."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--json", action="store_true", help="Print machine-readable checks."
        )

    def handle(self, *args, **options):
        try:
            checks = inspect_setup()
        except DatabaseError:
            raise CommandError(
                "Database inspection failed. Check local service readiness and private configuration."
            ) from None
        passed = all(item["passed"] for item in checks)
        scope = (
            "Local setup only. Policy names/flags are checked, not policy expressions or "
            "isolation behavior. This does not verify web/worker readiness, external integrations, "
            "backups, access permissions or production readiness. Run the documented tests too."
        )
        if options["json"]:
            self.stdout.write(
                json.dumps({"passed": passed, "checks": checks, "scope": scope})
            )
        else:
            for item in checks:
                self.stdout.write(
                    f"{'PASS' if item['passed'] else 'FAIL'} {item['check']}: {item['detail']}"
                )
            self.stdout.write(scope)
        if not passed:
            raise CommandError(
                "Local setup checks failed; no configuration was changed."
            )
