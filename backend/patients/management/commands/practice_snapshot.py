"""Read-only per-table fingerprints for local persistence checks; never output row data."""

import hashlib
import json

from django.core.management.base import BaseCommand
from django.db import connection

from common.models import Org
from common.rls import ORG_SCOPED_TABLES


class Command(BaseCommand):
    help = "Print per-practice data fingerprints without exposing patient values (PostgreSQL only)."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise RuntimeError("Requires PostgreSQL")
        quote = connection.ops.quote_name
        tables = set(connection.introspection.table_names())
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org', true)")
            previous = cursor.fetchone()[0] or ""
            try:
                for org in Org.objects.order_by("id"):
                    cursor.execute(
                        "SELECT set_config('app.current_org', %s, false)", [str(org.id)]
                    )
                    snapshot = {}
                    for table in sorted(set(ORG_SCOPED_TABLES) & tables):
                        cursor.execute(
                            f"SELECT row_to_json(t)::text FROM {quote(table)} t WHERE org_id=%s ORDER BY id",
                            [org.id],
                        )
                        rows = [row[0] for row in cursor.fetchall()]
                        snapshot[table] = {
                            "count": len(rows),
                            "sha256": hashlib.sha256(
                                json.dumps(rows).encode()
                            ).hexdigest(),
                        }
                    self.stdout.write(
                        json.dumps(
                            {"org": str(org.id), "name": org.name, "tables": snapshot},
                            sort_keys=True,
                        )
                    )
            finally:
                cursor.execute(
                    "SELECT set_config('app.current_org', %s, false)", [previous]
                )
