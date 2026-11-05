"""Explicit coordinated restart test; requires a disposable mp-restart-* DB host.

The test writes <MP_RESTART_GATE>.ready after committing its fictional state.
The host operator restarts ONLY that disposable PostgreSQL container, waits for
readiness, then writes <MP_RESTART_GATE>.resume inside the backend container.
No database dump or credentials are written to the gate files.
"""

import os
import time
from pathlib import Path

import pytest
from django.db import connection

from common.testing import rls_org
from integrations import pages, processing, tasks
from integrations.models import IntegrationAppliedPrefix as Prefix
from integrations.models import IntegrationEventInbox as Inbox
from integrations.models import IntegrationObservation as Observation
from integrations.models import IntegrationPendingWork as Pending
from integrations.models import IntegrationProcessingAttempt as Attempt
from integrations.models import IntegrationProcessingWork as Work
from integrations.models import IntegrationStreamPage as Page
from integrations.tests import test_acceptance as acceptance
from integrations.tests import test_ingress_storage as storage
from integrations.tests import test_pages as page_tests
from integrations.tests import test_processing as scheduling

fictional = scheduling.fictional
replay_keys = scheduling.replay_keys
receiver = scheduling.receiver
receive_enabled = scheduling.receive_enabled
processing_enabled = scheduling.processing_enabled
accepted = scheduling.accepted


def snapshot(org):
    with rls_org(org):
        return {
            model._meta.db_table: list(model.objects.order_by("id").values())
            for model in (Inbox, Pending, Work, Attempt, Observation, Page, Prefix)
        }


@pytest.mark.django_db(transaction=True)
def test_database_restart_preserves_and_resumes(accepted, receiver, org_a):
    assert connection.settings_dict["HOST"].startswith("mp-restart-")
    assert connection.settings_dict["NAME"].startswith("test_")
    gate = Path(os.environ["MP_RESTART_GATE"])
    ready, resume = Path(str(gate) + ".ready"), Path(str(gate) + ".resume")
    assert not ready.exists() and not resume.exists(), "Use a fresh rehearsal gate"

    processing.apply_work(accepted, *scheduling.get_claim(accepted))
    with rls_org(org_a):
        first = str(Inbox.objects.get().id)
    _, first_cursor = page_tests.accept(accepted, receiver, [first])
    pages.page_progress(accepted, receiver[0])

    assert acceptance.send(receiver[1], storage.raw()).status_code == 202
    claim = scheduling.get_claim(accepted)
    with rls_org(org_a):
        second = str(Work.objects.get(pk=claim[0]).pending.inbox_id)
    _, last_cursor = page_tests.accept(
        accepted, receiver, [second], previous=first_cursor
    )
    assert acceptance.send(receiver[1], storage.raw()).status_code == 202
    before = snapshot(org_a)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_postmaster_start_time()")
        started = cursor.fetchone()[0]
    connection.close()
    ready.write_text("ready")
    deadline = time.monotonic() + 90
    while not resume.exists():
        assert time.monotonic() < deadline, "Host did not complete isolated restart"
        time.sleep(0.2)

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_postmaster_start_time()")
        assert cursor.fetchone()[0] > started, "Database server was not restarted"
    assert snapshot(org_a) == before
    result = pages.page_progress(accepted, receiver[0])
    assert result["applied_cursor"] == str(first_cursor)
    assert result["ingestion_cursor"] == str(last_cursor)
    assert processing.apply_work(accepted, *claim)
    assert tasks.process_practice.run(accepted)["applied"] == 1
    assert tasks.process_practice.run(accepted)["applied"] == 0
    with rls_org(org_a):
        assert Inbox.objects.count() == Observation.objects.count() == 3
        assert Attempt.objects.count() == 3
    assert pages.page_progress(accepted, receiver[0])["applied_cursor"] == str(
        last_cursor
    )
