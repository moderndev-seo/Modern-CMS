"""Pinned fictional declarations. No receiver or vendor network client exists."""

import hashlib
import json

OBSERVATIONS = {
    "acquisition": (
        "marketing.touch_observed",
        "inquiry.created",
        "inquiry.qualified",
        "inquiry.disqualified",
    ),
    "booking": (
        "appointment.requested",
        "appointment.booked",
        "appointment.rescheduled",
        "appointment.cancelled",
        "appointment.no_show",
    ),
    "clinical": (
        "appointment.attended",
        "consultation.completed",
        "treatment.completed",
    ),
    "financial": (
        "payment.recorded",
        "payment.authorized",
        "payment.captured",
        "payment.settled",
        "refund.recorded",
        "refund.settled",
        "payment.disputed",
        "chargeback.posted",
        "chargeback.reversed",
    ),
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def manifest(key):
    adapter, source = key.split(":")
    if adapter not in ("fixture_a", "fixture_b") or source not in OBSERVATIONS:
        raise ValueError("Unknown fictional manifest")
    return {
        "id": key,
        "version": "1.0",
        "contract": "1.0",
        "fictional": True,
        "source_class": source,
        "observations": list(OBSERVATIONS[source]),
        "object_kinds": {
            "acquisition": ["inquiry", "touch"],
            "booking": ["appointment"],
            "clinical": ["encounter", "outcome"],
            "financial": ["transaction"],
        }[source],
        "transport": "fixture-json-a" if adapter == "fixture_a" else "fixture-json-b",
        "history": "synthetic-only",
        "coverage": "no-live-coverage",
    }


MANIFESTS = {
    f"{a}:{s}": manifest(f"{a}:{s}")
    for a in ("fixture_a", "fixture_b")
    for s in OBSERVATIONS
}


def permits_observation(manifest_id, event_type):
    """Future authority declaration only; never grants an HTTP receive scope."""
    return event_type in MANIFESTS.get(manifest_id, {}).get("observations", ())


# Receive-capable fixtures are new snapshots, never upgrades of existing grants.
RECEIVE_MANIFESTS = {}
for _adapter in ("fixture_a", "fixture_b"):
    _key = f"{_adapter}:acquisition:ingress-v1"
    RECEIVE_MANIFESTS[_key] = {
        **manifest(f"{_adapter}:acquisition"),
        "id": _key,
        "version": "1.1",
        "ingress": "fixture.ingress/1",
    }
ALL_MANIFESTS = {**MANIFESTS, **RECEIVE_MANIFESTS}
