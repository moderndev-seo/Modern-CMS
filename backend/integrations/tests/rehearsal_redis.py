"""Explicit local rehearsal: pytest integrations/tests/rehearsal_redis.py.

Not collected by the default test_*.py pattern. Requires the local Compose Redis
service. Uses Redis database 15, a unique queue and only the pytest database.
Kills only worker subprocesses it creates. No Redis flush or demo database access.
"""

import json
import os
import subprocess
import sys
import time
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.conf import settings
from django.db import connection
from django.test import override_settings

from common.testing import rls_org
from crm.celery import app
from integrations.models import IntegrationObservation as Observation
from integrations.models import IntegrationProcessingAttempt as Attempt
from integrations.models import IntegrationProcessingWork as Work
from integrations.tasks import dispatch_practices, process_practice
from integrations.tests import test_processing as scheduling

fictional = scheduling.fictional
replay_keys = scheduling.replay_keys
receiver = scheduling.receiver
receive_enabled = scheduling.receive_enabled
processing_enabled = scheduling.processing_enabled
accepted = scheduling.accepted

BOOTSTRAP = """
import os, time
from datetime import timedelta
from pathlib import Path
import django
django.setup()
from crm.celery import app
from integrations import processing, tasks
processing.LEASE = timedelta(seconds=2)
mode = os.environ.get("MP_REHEARSAL_FAULT", "")
def pause():
    Path(os.environ["MP_REHEARSAL_SIGNAL"]).write_text("reached")
    time.sleep(300)
original_apply = tasks.apply_work
def apply_fault(*args, **kwargs):
    if mode == "after":
        original_apply(*args, **kwargs)
    pause()
original_prepare = tasks.prepare_work
def prepare_fault(*args, **kwargs):
    if mode == "prepared":
        original_prepare(*args, **kwargs)
    pause()
original_release = processing._release
def release_fault(row, state, reason, **kwargs):
    if state == "applied":
        pause()  # Observation INSERT exists only inside the uncommitted transaction.
    return original_release(row, state, reason, **kwargs)
if mode in ("before", "after"):
    tasks.apply_work = apply_fault
elif mode in ("accepted", "prepared"):
    tasks.prepare_work = prepare_fault
elif mode == "uncommitted":
    processing._release = release_fault
original_run = tasks.process_practice.run
def tracked(*args, **kwargs):
    result = original_run(*args, **kwargs)
    with open(os.environ["MP_REHEARSAL_DONE"], "a") as output:
        output.write("done\\n")
    return result
tasks.process_practice.run = tracked
app.worker_main(["worker", "--pool=solo", "--concurrency=1", "--queues="+os.environ["MP_REHEARSAL_QUEUE"],
                 "--loglevel=ERROR", "--without-gossip", "--without-mingle", "--without-heartbeat"])
"""


def wait_until(predicate, worker, timeout=25):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        assert worker.poll() is None, "Rehearsal worker exited unexpectedly"
        if predicate():
            return
        time.sleep(0.1)
    pytest.fail("Rehearsal condition timed out")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "stage", ["accepted", "prepared", "before", "uncommitted", "after"]
)
def test_worker_kill_and_redis_redispatch(accepted, org_a, tmp_path, stage):
    database = connection.settings_dict["NAME"]
    assert database.startswith("test_"), "Rehearsal requires a test database"
    queue = "mp-rehearsal-" + uuid4().hex
    signal = tmp_path / "fault-reached"
    done = tmp_path / "tasks-finished"
    broker = "redis://redis:6379/15"
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "crm.test_settings_postgres",
        "DBNAME": database,
        "CELERY_BROKER_URL": broker,
        "CELERY_RESULT_BACKEND": "cache+memory://",
        "INTEGRATION_FOUNDATION_ENABLED": "true",
        "INTEGRATION_PROCESSING_ENABLED": "true",
        "INTEGRATION_TEST_ORGS": accepted,
        "INTEGRATION_REPLAY_KEY_VERSION": settings.INTEGRATION_REPLAY_KEY_VERSION,
        "INTEGRATION_REPLAY_KEYS_JSON": json.dumps(
            {
                k: v.decode() if isinstance(v, bytes) else v
                for k, v in settings.INTEGRATION_REPLAY_KEYS.items()
            }
        ),
        "MP_REHEARSAL_QUEUE": queue,
        "MP_REHEARSAL_SIGNAL": str(signal),
        "MP_REHEARSAL_DONE": str(done),
        "MP_REHEARSAL_FAULT": stage,
    }

    def start():
        return subprocess.Popen(
            [sys.executable, "-c", BOOTSTRAP],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def publish():
        def route(org_id):
            with app.connection_for_write(url=broker) as transport:
                return process_practice.apply_async(
                    args=[org_id], queue=queue, connection=transport
                )

        # Exercise the real periodic dispatcher; only routing is test-specific.
        with (
            override_settings(INTEGRATION_TEST_ORGS=[accepted]),
            patch("integrations.tasks.process_practice.delay", side_effect=route),
        ):
            assert dispatch_practices.run() == {"queued": 1, "failed": 0}

    def applied():
        with rls_org(org_a):
            return (
                Observation.objects.count() == 1
                and Work.objects.get().state == "applied"
            )

    if stage == "accepted":
        # Accepted receipts survive failed notification before any worker starts.
        with (
            override_settings(INTEGRATION_TEST_ORGS=[accepted]),
            patch(
                "integrations.tasks.process_practice.delay",
                side_effect=RuntimeError("synthetic publish failure"),
            ),
        ):
            assert dispatch_practices.run() == {"queued": 0, "failed": 1}
        with rls_org(org_a):
            assert not Work.objects.exists()
            assert not Observation.objects.exists()

    worker = start()
    try:
        publish()
        wait_until(signal.exists, worker)
        worker.kill()
        worker.wait(timeout=10)
        with rls_org(org_a):
            assert Observation.objects.count() == int(stage == "after")
            assert Attempt.objects.count() == int(stage not in ("accepted", "prepared"))
            assert Work.objects.count() == int(stage != "accepted")
        # A fresh process and PostgreSQL connection must recover durable state.
        connection.close()
        time.sleep(2.1)
        env["MP_REHEARSAL_FAULT"] = ""
        worker = start()
        publish()
        wait_until(
            lambda: (
                done.exists() and len(done.read_text().splitlines()) >= 1 and applied()
            ),
            worker,
        )
        publish()
        wait_until(lambda: len(done.read_text().splitlines()) >= 2, worker)
        with rls_org(org_a):
            assert Observation.objects.count() == 1
            assert Attempt.objects.count() == (
                2 if stage in ("before", "uncommitted") else 1
            )
    finally:
        if worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=10)
