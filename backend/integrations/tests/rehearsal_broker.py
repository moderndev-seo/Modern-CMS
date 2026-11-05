"""Explicit broker-outage test with host-controlled disposable mp-broker-* Redis.

Start with that broker stopped. On <MP_BROKER_GATE>.ready, start only that
container, wait for Redis readiness, then create <gate>.resume in the backend.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse
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
from integrations.tests import rehearsal_redis
from integrations.tests import test_processing as scheduling

fictional = scheduling.fictional
replay_keys = scheduling.replay_keys
receiver = scheduling.receiver
receive_enabled = scheduling.receive_enabled
processing_enabled = scheduling.processing_enabled
accepted = scheduling.accepted


@pytest.mark.django_db(transaction=True)
def test_broker_outage_recovers_accepted_receipt(accepted, org_a, tmp_path):
    broker = os.environ["MP_BROKER_URL"]
    assert (urlparse(broker).hostname or "").startswith("mp-broker-")
    assert connection.settings_dict["NAME"].startswith("test_")
    gate = Path(os.environ["MP_BROKER_GATE"])
    ready, resume = Path(str(gate) + ".ready"), Path(str(gate) + ".resume")
    assert not ready.exists() and not resume.exists()
    queue = "mp-outage-" + uuid4().hex
    done = tmp_path / "done"

    def route(org_id):
        with app.connection_for_write(url=broker, connect_timeout=1) as transport:
            return process_practice.apply_async(
                args=[org_id], queue=queue, connection=transport, retry=False
            )

    def dispatch():
        with (
            override_settings(INTEGRATION_TEST_ORGS=[accepted]),
            patch("integrations.tasks.process_practice.delay", side_effect=route),
        ):
            return dispatch_practices.run()

    # Real transport failure: no mocked publish exception.
    assert dispatch() == {"queued": 0, "failed": 1}
    with rls_org(org_a):
        assert not Work.objects.exists() and not Observation.objects.exists()
    ready.write_text("failed publication observed")
    deadline = time.monotonic() + 90
    while not resume.exists():
        assert time.monotonic() < deadline, "Host did not restore isolated broker"
        time.sleep(0.2)

    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "crm.test_settings_postgres",
        "DBNAME": connection.settings_dict["NAME"],
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
        "MP_REHEARSAL_DONE": str(done),
        "MP_REHEARSAL_FAULT": "",
    }
    worker = subprocess.Popen(
        [sys.executable, "-c", rehearsal_redis.BOOTSTRAP],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert dispatch() == {"queued": 1, "failed": 0}
        rehearsal_redis.wait_until(lambda: done.exists(), worker)
        assert dispatch() == {"queued": 1, "failed": 0}
        rehearsal_redis.wait_until(
            lambda: len(done.read_text().splitlines()) >= 2, worker
        )
        with rls_org(org_a):
            assert Observation.objects.count() == Attempt.objects.count() == 1
            assert Work.objects.get().state == "applied"
    finally:
        if worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=10)
