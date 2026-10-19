"""Bounded process-local failure counters; never accept request data as labels."""

import logging
from threading import Lock
from uuid import uuid4

_REASONS = {
    401: "invalid_authentication",
    403: "authorization_denied",
    404: "unavailable_route",
    503: "service_unavailable",
}
_COUNTS = dict.fromkeys((*_REASONS.values(), "request_rejected"), 0)
_LOCK = Lock()
_MAX_COUNT = 2**63 - 1
_LOG = logging.getLogger(__name__)


def record_failure(status):
    reason = _REASONS.get(status, "request_rejected")
    correlation_id = str(uuid4())
    with _LOCK:
        _COUNTS[reason] = min(_COUNTS[reason] + 1, _MAX_COUNT)
    _LOG.warning(
        "Integration failure reason=%s correlation_id=%s", reason, correlation_id
    )
    return correlation_id


def failure_counts():
    """Return an internal snapshot; no public telemetry or tenant lookup."""
    with _LOCK:
        return dict(_COUNTS)
