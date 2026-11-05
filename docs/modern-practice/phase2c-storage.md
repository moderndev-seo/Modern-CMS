# Phase 2C local processing checkpoint

Architecture 0.2.0 and [roadmap I](universal-journey/I-roadmap.md) remain the
contract. These increments process fictional acquisition observations. They do
not link patients, verify treatment, post cash or establish real-provider coverage.
See [PROJECT_STATE](PROJECT_STATE.md) for exact checks and limitations.

## Durable storage and effects

`IntegrationProcessingWork` is one scheduling companion per immutable 2B pending
marker. It records due time, state, attempt count, lease token/expiry and a safe
reason. `IntegrationProcessingAttempt` retains immutable claim history, unique
by work/attempt number and lease token. Forced RLS, same-practice parent checks,
immutable history and deferred claim/result invariants protect these tables.
Migrations 0010–0014 are additive; none rewrites the earlier receipts or markers.

`IntegrationObservation` records one immutable acquisition observation per work
item with mapping `fixture.normalized/1`, event type, synthetic source UUID,
nullable occurrence time and receipt digest. Its insert and `applied` state must
commit together. Connection generation and lease authority are checked before
insertion; evidence is decrypted and revalidated against the pinned contract.
A missing key or unavailable/corrupt evidence quarantines work without a fact.

A source UUID is not a patient identity or cross-provider business identity.
This slice deduplicates processing of a receipt. Distinct delivery IDs remain
separate observations, with no business or monetary effect. Unknown occurrence
time remains null. Terminal/quarantined work cannot reopen without a later
reviewed replay feature.

## Bounded scheduling and Celery

Internal functions in `integrations.processing` prepare missing companions,
claim due work, retry current leases, recover expired leases and apply normalized
observations. Lock order is Org, connection, work. Deferred guards run before
tenant context restoration. Revocation or generation mismatch prevents effects;
stale owners cannot release or apply another claim. Migration 0019 additionally
enforces fresh claim transitions in PostgreSQL: released tokens cannot be
restored through direct writes, and active claims cannot be replaced. See the
[independent agent review](phase2c-independent-review.md) for the reproduced
finding and resolution.

Fictional choices: at most 100 rows per call (default 25), two-minute leases capped
by the existing 24-hour evidence window, six attempts. Retry jitter is 1 through
min(3600, 30 × 2^(attempt−1)) seconds, with validated Retry-After taking precedence.
A retry beyond retention becomes terminal. These are not live-provider policies.

`integrations.tasks.process_practice` performs one bounded preparation/recovery/
claim/apply batch. Failures attempt a bounded retry; an unavailable database
leaves a durable lease for later recovery. Exceptions become safe aggregate
failure counts without raw error/payload disclosure. `dispatch_practices` queues
one job per allowlisted practice (maximum 100), continues after publication
failure, and runs each minute through Celery Beat. Queue arguments are opaque
organization UUIDs. Capacity, backpressure and operational alert ownership still
need validation. A held practice lock does not block another practice's job.

`INTEGRATION_PROCESSING_ENABLED` defaults false and also requires the foundation
flag and TEST practice allowlist. Isolated tests explicitly enable processing.
Ordinary demo settings remain off. No public processing or review API exists.

## Progress versus coverage

`integrations.coverage.stream_progress` returns a consistent internal snapshot
for one fictional connection's acquisition stream: accepted/applied/unresolved
counts, latest accepted checkpoint, contiguous applied checkpoint and status
`no_data`, `partial` or `caught_up`. Missing companions and quarantined receipts
remain gaps. A later applied receipt cannot advance the applied checkpoint past
an earlier unresolved receipt. No source UUID or payload is returned.

These local checkpoints are derived from durable rows ordered by receipt time
and UUID. They are not external polling cursors. `source_coverage` is always
`unknown` and `provider_cursor` is null: the current fictional ingress contract
contains no provider page token, object revision, expected inventory or historical
coverage boundary. Even `caught_up` describes only known accepted receipts.
The separate fictional page contract in `integrations.pages` now persists
immutable UUID cursors, predecessor links and up to 100 receipt references per
page. Migrations 0015/0016 enforce same-practice, same-connection and current-
generation receipts, active fictional authority, append order and immutability.
The database assigns sequence positions; cursor replay must match its accepted
content. Missing receipts prevent ingestion cursor advancement.

`page_progress` exposes the last accepted fictional page and an applied prefix
that stops at the first unfinished page. Empty pages advance transport progress
without implying zero outcomes or source completeness. Each call verifies at
most 100 pages after a durable applied-prefix checkpoint.
Subsequent calls resume there, so a large backlog can finish over bounded calls.
This internal operation writes the verified cache; it is not a read-only API.
`pages_examined` counts the current batch, and `scan_complete` means that batch
reached the accepted head (not that every receipt is applied). An unfinished
receipt leaves the checkpoint behind the gap until a later call can advance it.

Migrations 0017/0018 add a per-connection applied-prefix cache with forced RLS.
PostgreSQL rejects regressions, identity changes, deletion, advancement over
100 pages, missing pages or unfinished receipts. Previously verified positions
remain sound because page references and observations are immutable. Concurrent
calls serialize within the practice and resume from the committed checkpoint;
rollback does not preserve uncommitted progress. These UUID page tokens belong
only to the fictional adapter contract,
not a vendor integration. Source coverage remains unknown.

## Recovery evidence and remaining work

Ordinary tests include an enabled Celery worker using a dedicated in-memory queue.
The explicit `integrations/tests/rehearsal_redis.py` rehearsal uses real local
Redis database 15, a unique queue, the pytest database and disposable separate
worker processes. It kills only its own worker at five explicit boundaries,
then starts a fresh worker and invokes the real practice dispatcher again. Only
queue routing is overridden to keep all messages on the test's dedicated queue.
The accepted-receipt case first injects a failed publish call and verifies that
no work or observation was created; subsequent dispatch recovers the receipt.
This models a publish exception, not a real broker outage.

| Kill boundary | Durable work before restart | Observation before restart | Final attempts |
|---|---|---|---|
| Before preparation | None | None | 1 |
| After preparation commits | Accepted | None | 1 |
| After claim commits | Processing | None | 2 |
| After observation INSERT, before transaction commits | Processing | None (rolled back on process death) | 2 |
| After applied observation commits | Applied | Exactly one | 1 |

Every case verifies that the restarted worker consumes the recovery job and a
duplicate redispatch, with exactly one final observation. Attempt history shows
recovery only when required. A two-second lease is
used only in the child rehearsal worker to shorten the drill. No Redis flush or
saved-demo database access occurs. Run explicitly with:

```bash
DBNAME=mp_local_checks python -m pytest integrations/tests/rehearsal_redis.py \
  --ds=crm.test_settings_postgres --no-cov --reuse-db -q
```

Run inside the local Compose backend where `redis` resolves. This file is not
part of default `test_*.py` discovery. The drill proves redispatch/sweeper recovery
from worker death; it does not prove Redis durability, backup restoration,
every enqueue failure or production disaster recovery.

Remaining Phase 2C work includes source coverage evidence, remaining
restart/boundary acceptance and broader acceptance checks. The November 5
independent agent review is recorded above; external release approval is separate.
No Phase 2C completion, real-provider attribution or production readiness claim.

## Isolated normal PostgreSQL restart

`integrations/tests/rehearsal_database.py` is an explicit, host-coordinated test,
not part of default discovery. It requires a disposable `mp-restart-*` DB host,
a restricted application role with a precreated `test_*` database, migrations,
and a unique `MP_RESTART_GATE` path inside the backend container. Never point it
at the ordinary demo database.

Run pytest with `--ds=crm.test_settings_postgres --migrations --no-cov --reuse-db`.
When `<gate>.ready` appears, restart only the disposable PostgreSQL container,
wait for restricted-role connectivity, and create `<gate>.resume`. The test waits
at most 90 seconds and checks that PostgreSQL's actual server start time changed.
Use a fresh gate on every run. Stop the owned disposable container afterward;
never delete demo volumes or include its test data in a commit.

The test compares seven integration tables across restart, preserves the applied
page prefix, resumes an existing claim and processes the remaining accepted
receipt without duplicate observations. This normal-server-restart evidence is
separate from the worker-kill rehearsal and does not establish crash/backup or
production recovery readiness. November 5 result: one test passed, zero skips.
