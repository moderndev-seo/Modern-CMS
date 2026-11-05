"""Bounded fictional jobs. Queue arguments and results contain no event payloads."""

from celery import shared_task
from django.conf import settings

from integrations.authentication import enabled
from integrations.processing import (
    apply_work,
    claim_work,
    prepare_work,
    recover_work,
    retry_work,
)


@shared_task(ignore_result=True)
def process_practice(org_id):
    if not getattr(settings, "INTEGRATION_PROCESSING_ENABLED", False) or not enabled(
        org_id
    ):
        return {"status": "disabled"}
    counts = {"prepared": 0, "recovered": 0, "claimed": 0, "applied": 0, "failed": 0}
    try:
        counts["prepared"] = prepare_work(org_id)
        counts["recovered"] = recover_work(org_id)
        claims = claim_work(org_id)
    except Exception:
        # Safe aggregate only; no exception/SQL/payload enters task telemetry.
        counts["failed"] += 1
        return counts
    counts["claimed"] = len(claims)
    for work_id, token in claims:
        try:
            counts["applied"] += int(apply_work(org_id, work_id, token))
        except Exception:
            counts["failed"] += 1
            try:
                retry_work(org_id, work_id, token)
            except Exception:
                # The durable lease remains recoverable on a later sweep.
                pass
    return counts


@shared_task(ignore_result=True)
def dispatch_practices():
    if not getattr(settings, "INTEGRATION_PROCESSING_ENABLED", False):
        return {"queued": 0, "failed": 0}
    from uuid import UUID

    # A fixed bounded fictional allowlist, never a cross-tenant row scan.
    try:
        practices = sorted(
            {str(UUID(str(value))) for value in settings.INTEGRATION_TEST_ORGS}
        )
    except (TypeError, ValueError, AttributeError):
        return {"queued": 0, "failed": 1}
    if len(practices) > 100:
        return {"queued": 0, "failed": 1}
    result = {"queued": 0, "failed": 0}
    for org_id in practices:
        if not enabled(org_id):
            continue
        try:
            process_practice.delay(org_id)
            result["queued"] += 1
        except Exception:
            result["failed"] += 1
    return result
