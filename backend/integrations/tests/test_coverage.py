"""Known local processing gaps never become claimed source completeness."""

import pytest

from integrations import coverage, processing
from integrations.tests import test_acceptance as acceptance
from integrations.tests import test_ingress_storage as storage
from integrations.tests import test_processing as scheduling

fictional = scheduling.fictional
replay_keys = scheduling.replay_keys
receiver = scheduling.receiver
receive_enabled = scheduling.receive_enabled
processing_enabled = scheduling.processing_enabled
accepted = scheduling.accepted


def test_empty_stream_has_no_coverage(receiver, org_a):
    result = coverage.stream_progress(org_a.id, receiver[0])
    assert result["processing_status"] == "no_data"
    assert result["ingestion_checkpoint"] is result["applied_checkpoint"] is None
    assert result["source_coverage"] == "unknown"


def test_applied_prefix_stops_at_missing_companion(accepted, receiver):
    result = coverage.stream_progress(accepted, receiver[0])
    assert result["accepted_count"] == result["unresolved_count"] == 1
    assert result["ingestion_checkpoint"] is not None
    assert result["applied_checkpoint"] is None
    claim = scheduling.get_claim(accepted)
    processing.apply_work(accepted, *claim)
    result = coverage.stream_progress(accepted, receiver[0])
    assert result["processing_status"] == "caught_up"
    assert result["ingestion_checkpoint"] == result["applied_checkpoint"]
    assert result["source_coverage"] == "unknown" and result["provider_cursor"] is None


def test_later_applied_event_cannot_hide_gap(accepted, receiver):
    first = scheduling.get_claim(accepted)
    assert acceptance.send(receiver[1], storage.raw()).status_code == 202
    processing.prepare_work(accepted)
    second = processing.claim_work(accepted)[0]
    processing.apply_work(accepted, *second)
    result = coverage.stream_progress(accepted, receiver[0])
    assert result["accepted_count"] == 2 and result["applied_count"] == 1
    assert result["processing_status"] == "partial"
    assert result["applied_checkpoint"] is None
    processing.apply_work(accepted, *first)
    result = coverage.stream_progress(accepted, receiver[0])
    assert result["processing_status"] == "caught_up"
    assert result["applied_checkpoint"] == result["ingestion_checkpoint"]


def test_quarantine_remains_gap(accepted, receiver, settings):
    claim = scheduling.get_claim(accepted)
    settings.INTEGRATION_REPLAY_KEYS = {}
    processing.apply_work(accepted, *claim)
    result = coverage.stream_progress(accepted, receiver[0])
    assert result["unresolved_count"] == 1 and result["applied_checkpoint"] is None


def test_foreign_stream_unavailable(accepted, receiver, org_b):
    with pytest.raises(ValueError, match="unavailable"):
        coverage.stream_progress(org_b.id, receiver[0])
