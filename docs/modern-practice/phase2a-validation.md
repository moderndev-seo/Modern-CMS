# Phase 2A local validation — October 18, 2026

Status: locally verified review candidate, uncommitted on `codex/integration-foundation-2a`, based on merged architecture commit `100ae08cabd4b6bb11d2332fb67ffdb569fd4ba8`. Independent review and publication/merge approval remain outstanding; this is not production readiness. Current owner instructions require explicit approval before publication; no commit, push, remote change or merge occurred in this increment.

## Final local review snapshot — October 19, 2026

**357 restricted PostgreSQL security cases passed, zero failures/skips**, including all **76 integration cases**. 6,294 compatibility tests were deselected and 351 inherited warnings were reported. The run's 14,654.27-second wall-clock interval spans the overnight interruption and must not be treated as an execution-speed benchmark. Earlier 333/350-test snapshots below are historical.

Completed the outstanding selector and monitoring requirements: body/query organization selectors are denied before tenant selection, failures receive opaque server-generated IDs and fixed bounded counters, and no caller values are used as labels. Integration validation errors no longer echo input. Added signing-key replacement/fallback, exact expiry, disabled-practice, empty-context and waiting-issuance/revocation cases. Review also corrected revocation response/retry metadata to preserve an existing retirement timestamp. Fixed-label monitoring is explicitly process-local; see the operator guide for limitations.

These changes add no new schema, frontend behavior, live service or patient/cash effect. Final lint and 840-file formatting pass. Routing covers 6,651 tests (6,294 compatibility + 357 security), including all 254 patient and 76 integration cases. Migration drift reports no changes. Final strict docs/reference guards: 8 passed, one warning, 21.44 seconds. Final wheel and source builds pass; installed services/monitoring and seven templates load outside the checkout with a clean Django system check. Whitespace and 28-path artifact/private-key-block checks pass. Full compatibility runs below predate the last integration-only boundary changes; their sole documentation failure was corrected and checked separately. The final security suite covers the current boundary; no fresh full-compatibility claim is made. Independent review and exact published-head hosted checks are pending, and publication requires approval.

## Broader regression results — October 18, 2026

- Restricted PostgreSQL security: **333 passed**, zero failures/skips; 6,294 deselected, 328 inherited warnings, 141.41 seconds.
- PostgreSQL compatibility: **6,293 passed and one failed**, zero skips; 333 deselected, 4,781 inherited warnings, 564.29 seconds. The sole failure was the environment-variable documentation guard, which found the three new integration settings absent from the reference.
- SQLite compatibility with repository coverage: **6,284 passed, nine skipped and one failed**; 333 deselected, 4,772 inherited warnings, 722.73 seconds. The failure was the same documentation guard. Coverage was **89.32%**, above the unchanged 50% requirement. PostgreSQL remains the source of security/JSON-filter evidence.
- Corrected the public environment-variable reference with the exact defaults and fictional-only meaning of `INTEGRATION_FOUNDATION_ENABLED`, `INTEGRATION_TEST_ORGS` and `INTEGRATION_AUDIENCE`. PostgreSQL rerun of the six reference tests and two strict documentation/publication guards: **8 passed**, one inherited warning, 13.09 seconds. No application code changed in response to these runs. Targeted SQLite reference confirmation: **6 passed**, one inherited warning, 1.37 seconds, using `--no-migrations` for these filesystem-only checks (not RLS evidence).

The full compatibility runs above are reported as actually observed, not relabeled as fresh all-green runs after a documentation-only correction. Their sole failure is checked separately after correction; unrelated application tests were not repeated. There was no security skip or reduced assertion/coverage threshold.

## Upgrade, restart and package rehearsal — October 18, 2026

A separate persistent fictional database was created for this rehearsal; the existing test server uses tmpfs and cannot supply restart-persistence evidence. No database port was exposed and no existing volume was deleted. The rehearsal application role is NOSUPERUSER/NOBYPASSRLS.

1. Migrated an empty database to all existing application migration leaves except `integrations`. Confirmed no integration namespace table existed, then seeded the two clearly labeled TEST practices and a fictional administrator.
2. Captured row counts and SHA-256 fingerprints of all fields in Org, Profile, User, Contact, Patient, Receipt, JourneyEvent and MarketingSpend records, using each practice's RLS context.
3. Applied the two additive integration migrations. All legacy fingerprints matched; all four integration tables had RLS enabled and forced.
4. Issued a fictional credential through the real admin API and captured all four integration models' fingerprints. The probe returned 200. With the feature disabled, service and admin integration routes returned 404 while the existing patient-list API returned 200; no fingerprints changed.
5. Performed a normal restart of only the dedicated persistent database container. A new Django process verified identical legacy/integration fingerprints, successful authentication with the previously issued credential, and the same feature-disable behavior.

The rehearsal passed. It demonstrates upgrade preservation and normal database restart, not backup restoration, application-server failover or production recovery. Fictional rehearsal storage and private evidence are preserved outside the public source tree. Original demo databases and containers were not modified.

Wheel and source builds passed using `python -m build --no-isolation`. Installed the wheel without dependency changes in a separate temporary target; from outside the checkout, confirmed the integration module loaded from that target, Django system checks passed, and all seven repository-required templates resolved. The existing runner supplied dependencies; this was not a fresh dependency installation or lockfile reproducibility test.

Both documentation publication guards passed, including strict MkDocs builds: **2 passed**, one inherited email-backend deprecation warning, 144.86 seconds. Final broader test outcomes are recorded in the handoff after their runs complete. Hosted CI, independent review, production rollout and live integrations remain unperformed.

## Concurrency and failure-boundary increment — October 18, 2026

The final focused suite now passes **52 tests**, no failures/skips, 49 inherited warnings, in 14.17 seconds. New tests use separate PostgreSQL connections and actual commits: simultaneous issuance/rotation with the same revision yields exactly one success and one conflict; a blocked probe is denied after revocation commits; context setup failure rolls back its local setting; context reset failure discards the connection and a subsequent connection has no tenant context.

A fictional-secret canary reproduced a traceback-log disclosure from an unexpected integration view exception. Integration views now intercept unexpected exceptions, mark the transaction for rollback, emit only a fixed error message without traceback/request data, and return generic 503. The canary passes after this correction. This is scoped to integration views; it is not a system-wide logging audit. Backend lint and 839-file formatting pass.

The first concurrency run passed 50 cases and failed the revocation assertion with 503. Its test acquired the connection lock before the practice lock, unlike the HTTP boundary. The corrected test follows the application's practice-before-connection order and verifies the probe blocks before returning 401 after commit. The first standalone canary intentionally failed before the error-handler correction. No failure was converted to a skip or a weaker success assertion.

These results extend, rather than replace, the earlier 326-case security run below. Full compatibility and security-suite reruns on the finished tree, controlled upgrade/baseline-preservation, container restart/feature-disable rehearsals, installed-package/docs checks and independent review remain pending. Current tests cover selected concurrency/context/secret failure cases; complete requirement-by-requirement acceptance review remains necessary. Work is local/uncommitted, with no saved/demo data changes or live connections.

## Scope and corrections

The approved specification requires four additive metadata tables: provider namespaces, connections, credentials and append-only audit events. These hold integration identity and lifecycle evidence separately from existing patient and cash records. The implementation remains fictional, explicitly allowlisted and disabled by default. It adds no event receiver, worker, live provider or patient/financial write.

This increment corrects transaction ordering: the three deferred integration audit guards run while their authenticated practice context is active, before restoring the caller's context. This is an implementation choice to satisfy forced RLS and atomic audit requirements. Failed SQL explicitly marks the transaction for rollback so context cleanup does not mask the original failure. Django-converted server errors also roll back and return bounded 503 responses. Unknown command fields now produce a structured validation error instead of a serializer exception. A missing test import and formatting were corrected.

Regressions cover unaudited-write rejection/rollback, returning to another practice's context, and credential persistence across an actual transaction commit and database reconnection. A reconnect test is not a container-restart rehearsal.

## Verified checks

- Final focused PostgreSQL integration suite: **46 passed**, no failures/skips, 45 warnings, 9.43 seconds. Command: `python -m pytest integrations/tests --no-cov --migrations --reuse-db -q --tb=short`.
- Broader restricted-role security suite before adding the final reconnect test: **326 passed**, 6,294 compatibility cases deselected, no failures/skips, 323 warnings, 116.53 seconds. Command: `python -m pytest -m postgres_only --no-cov --migrations --reuse-db -q --tb=short`. The additional reconnect test passed in the final focused suite.
- Backend Ruff lint passed; formatting passed across 839 files.
- `manage.py makemigrations --check --dry-run`: no changes detected. `manage.py check`: no issues.
- Whitespace check passed. Complete test-routing verification is recorded in the current handoff after its final run.

Tests used only the isolated PostgreSQL container, with `crm_ci` verified by the security fixture as NOSUPERUSER/NOBYPASSRLS. The disposable database was empty after Docker restarted; its restricted test role was recreated and migrations rebuilt the test schema. No saved/demo/production database was migrated. The original demo containers remain stopped; this increment started only the isolated database and runner.

Warnings include the inherited Django email-backend deprecation and absent collected static files in the backend-only runner. No warning suppression or security assertion relaxation was introduced.

## Failed and interrupted checks

The first connection attempt failed because the disposable database's role/data had not survived its prior shutdown. One initial migration/setup run was interrupted for diagnosis; it is not counted as passing. The next lifecycle run reproduced one passed test with a teardown error, `Namespace requires audit`, establishing the deferred-context defect. After that correction, the 45-case suite exposed three failures: unknown-field validation, failed-SQL cleanup and the related malformed-body case. Corrections yielded 45 passes, then the final 46 passes above. The first routing check ran while a new test was added and correctly rejected inconsistent inventories; its later stable-tree rerun passed (6,627 cases: 6,294 compatibility and 333 security). Formatting initially identified two configuration/routing files and later the new test; those were formatted and rechecked.

## Remaining release gates and limits

Local acceptance evidence is mapped below, including the completed selector/monitoring corrections and final 357-case security run. Independent qualified review, explicit publication approval, exact-head hosted checks and separate merge approval remain. No production rollout, live provider validation, centralized monitoring, production backup/restore drill or later-phase ingestion is included. Browser acceptance was not performed because the milestone is API-only. Earlier validation snapshots are retained as history, not current outstanding-work instructions.

## Acceptance evidence map for reviewer

The following maps the approved Phase 2A acceptance families to local evidence. It is an implementation review aid, not independent certification. Tests are in `backend/integrations/tests/test_foundation.py`; the suite also exercises real API/middleware and restricted PostgreSQL triggers. Inspect parameterizations and assertions rather than interpreting a family label as exhaustive testing of every possible request.

| Family | Evidence |
| --- | --- |
| 2A-01: feature/allowlist | `test_disabled_and_direct_view_fail_closed`, `test_disabled_practice_denies_existing_credential`; feature-disable rehearsal retained patient access. |
| 2A-02: practice isolation | `test_real_foreign_links_and_credential_reads`, `test_db_forced_rls_and_foreign_link`, `test_no_tenant_context_sees_no_integration_metadata`, selector rejection before tenant context. |
| 2A-03: principal restrictions | `test_regular_and_foreign_practice`, `test_nonhuman_credentials_cannot_manage`, `test_service_cannot_read_legacy_or_manage`, human-denied probe in lifecycle coverage. |
| 2A-04: invalid credentials | `test_service_credential_failures`, bounded monitoring canary, invalid locator denied before context, signing-key replacement/fallback test. |
| 2A-05: validity boundaries | Lifecycle, exact expiry, retirement-before/at/after, immediate retirement predicate, disabled-practice and feature tests. |
| 2A-06: authority/scopes | `test_reject_credential_escalation`, pinned-manifest authority evaluation, database manifest/scope guards. |
| 2A-07: rotation/retries/slots | Issue retry/conflict, zero/nonzero overlap, concurrent issuance/rotation, slot-limit/replacement tests, revocation retry retains retirement metadata. |
| 2A-08: races/state | Separate-connection probe/issuance waits for committed revocation, stale revision and terminal lifecycle coverage. |
| 2A-09: SQL integrity | Append-only namespace/audit checks, immutable manifest/scope/expiry guards, foreign links and unaudited-write rollback; role assertions in the security fixture. |
| 2A-10: context failures | Setup/reset fault injection, discarded reset-failure connection, clean subsequent context, cross-practice restoration and direct DRF denial. |
| 2A-11: disclosure | Metadata secret/hash exclusions, no-store, unexpected-exception and validation-value canaries; opaque monitoring IDs with fixed labels and no caller values. |
| 2A-12: atomicity/idempotency | Issue retry/conflict, audit-failure rollback, unaudited-write denial, preserved revocation replay facts. |
| 2A-13: namespace/adapter | Same-namespace replacement and immutable account tests; both fictional adapter families' pinned capability tests. No identity matching inferred. |
| 2A-14: preservation/recovery | Restricted-role pre-integration upgrade fingerprints, four forced-RLS tables, real database restart, persisted credential/audit/legacy fingerprints, feature-disable rehearsal. |
| 2A-15: no domain effects | `test_no_domain_effects_and_no_receiver`, unchanged legacy fingerprints through setup/upgrade/probes and disabled-feature reads. |

The [operator guide](phase2a-foundation.md) records current routes and monitoring limits. No frontend changes, live connection, vendor conformance, production backup recovery or later-phase event processing are included. Operational production telemetry remains deferred; local counters are explicitly process-local and reset on restart. Separate independent review and owner publication/merge decisions remain required.
