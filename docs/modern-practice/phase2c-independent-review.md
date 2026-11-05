# Phase 2C independent agent review — November 5, 2026

Scope: the local, uncommitted Phase 2C implementation on
`codex/phase-2c-processing`, including processing, tasks, page checkpoints,
coverage, migrations 0010–0018, tests and handoff claims. The owner requested
independent review. A separate reviewer agent inspected the source read-only;
the implementing agent reproduced and fixed its finding. This is not external
human release approval, hosted CI evidence or authorization to publish/merge.

## Finding and resolution

**P2 — Released lease tokens could be reactivated through direct storage writes.**
Migration 0011 allowed unchanged attempt counts when returning to `processing`;
0012 accepted a historical attempt with the same token/expiry. After normal
`retry_work` release, a direct ORM/SQL update could restore that token before its
original expiry, allowing `apply_work` to accept it again. Normal `claim_work`
already rotated tokens correctly. This was a database enforcement gap, not a
demonstrated public API bypass or cross-practice disclosure.

The implementing agent added a restricted-role regression that failed before
the fix with `DID NOT RAISE IntegrityError`. Additive migration 0019 now requires
an incremented attempt count whenever entering processing, permits entry only
from accepted/retryable states, prevents active claim replacement and prevents
attempt-count changes outside a new claim. Existing deferred evidence checks
and immutable unique attempt tokens then require fresh claim evidence.

Tests cover released-token restoration, active-claim replacement, count changes
on release, stale-token apply denial and successful application using a fresh
claim. The independent reviewer re-read the migration and tests and confirmed
the finding resolved with no additional issue found in the fix. The reviewer
reported no other confirmed defects in the reviewed normal execution paths.

## Evidence and limits

See the November 5 entry in [PROJECT_STATE](PROJECT_STATE.md) for exact executed
checks, migration preservation and counts. The reviewer did not execute tests;
those checks were performed by the implementing agent.

Source coverage evidence, full restart/commit/enqueue-boundary acceptance and
operational monitoring remain incomplete scope. An absence of further findings
is not proof of production readiness or completion of Phase 2C. Ordinary demo
processing remains disabled. No live provider, publication or deployment.
