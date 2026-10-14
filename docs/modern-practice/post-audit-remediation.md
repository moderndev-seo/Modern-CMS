# Post-audit remediation — review record

Publication update: the owner has authorized a feature-branch commit/push, PR and hosted validation. Historical local-review status below records what had happened at that time; see [current handoff](PROJECT_STATE.md) for the latest authorization. Merge, deployment and next-phase implementation remain prohibited.

This is the earlier remediation baseline. The subsequent [final release review](release-readiness.md) records additional corrections and fresh complete-tree validation; use its status for the current working tree.

Status: authorized remediation implemented and local validation completed, **uncommitted and not pushed**. This is a review candidate, not production or merge approval. Architecture work is specification only: [roadmap](post-audit-architecture.md). Operational permission changes are in [patient permissions](patient-permissions.md).

## Safety and baseline

Public base: `11e6d59a0ef79e6cefe6d5fe1a71859099557961` on `moderndev-seo/Modern-CMS`, branch `main`. Work takes place in a fresh local clone on `codex/patient-authorization-ci`. The original `modern-practice/local-poc` checkout at `02eb97466734ef1775b319f7e00fc360ff19f449` and upstream remote were preserved. Its existing dirty milestone work and private decks were not copied into this clone. Public main was rechecked read-only after implementation and remained at the same base commit. No existing remote, repository setting, Docker volume or saved application database was changed. No commit, push, merge, live connection or deployment was performed.

Tests use a new disposable PostgreSQL 16 container, no published database ports and no application volume. The test runner uses `crm_ci`, a LOGIN CREATEDB NOSUPERUSER NOBYPASSRLS role. Only this disposable server receives migrations/test writes. Local runtime versions: Python 3.12.14, Node 24.21.0 and PostgreSQL 16.15. The running demo remains on the previous code at http://localhost:5181 and http://localhost:8000.

## Issues, causes and changes

| Issue/root cause | Remediation | Compatibility |
| --- | --- | --- |
| Patient membership was mistaken for object authorization | Practice capability gate, contact-filtered patient list and shared contact assertion in patient lookup; serializer checks | Regular members need an explicit grant; administrators and properly assigned staff retain access |
| Any member could record treatment/outcome events | Independent outcome capability for intake, events and appointment writes | Existing administrator correction rules remain |
| Patient detail exposed receipts/history regardless of financial authority | Independent financial read capability, receipt checks and omission of inaccessible detail fields; UI Restricted state | Financial writes/reconciliation/export stay admin-only; no false zero |
| Shared Contact, task and invoice routes could reveal linked patient information | Protected contact filtering/redaction, task-contact restrictions, financial document filtering/object checks and serializer request context | Existing unrelated CRM access rules preserved; arbitrary text copied to unrelated records is not classified automatically |
| Wildcard/legacy PAT and org keys could inherit admin patient access | Explicit patient resource scopes; effective credential restriction also follows shared record access; PAT scope check repeated at authentication boundary | Non-patient legacy scope semantics remain; organization keys get no patient authority; sandbox intake JWT-only |
| Credential-driven user administration could grant access indirectly | PAT/org-key writes to user/membership administration require a signed-in session | Intentional restriction on automation that changes users/roles |
| Patient/trigger/RLS tests ran on SQLite or a PostgreSQL superuser; older tenant/pool checks silently skipped | All patient tests plus the legacy RLS class and pool module join explicit postgres_only partition; role guard fails closed; independent security job with real migrations | Compatibility/type checks still run separately; no security assertion removed |
| Patient subclass Meta replaced the base index contract | Additive migration restores 21 org/-created_at indexes | No rows or existing indexes removed |
| Scope inventory missed patients | Registered patients with explicit tests of named/wildcard/legacy behavior | Scope recognition does not grant profile access |
| Environment docs scanner ignored bootstrap command and depended on private env file | Scan the public example and actual admin bootstrap reader; add regression | Correct ADMIN_PASSWORD documentation retained |
| Relocated documentation had broken relative links | Repair upstream overview and handoff links | Strict warnings not suppressed |
| CI/CodeQL PR targets named master instead of main | Correct branch references, independent security job, complete routing proof, remove direct badge commits and path filters | No repository administration setting changed |

Schema additions are implementation choices authorized by the repair request: three default-false Profile capabilities and the missing model-contract indexes. Future agency grants, identity models and inbox queues remain proposed, not implemented.

## Validation record

Measured checks so far (all use fictional isolated test data):

| Check | Result |
| --- | --- |
| PostgreSQL security, real migrations, restricted role | **181 passed** in the complete security run; **8 additional older tenant/pool checks passed** after routing repair; 189 total checks, no security skips |
| Authorization regression cases | **28 passed** within the final 181-test run; the preceding serializer-context rerun also passed all 27 then-existing cases |
| Full SQLite-compatible backend suite | **6,286 passed, 16 skipped**, no failures; 176 PostgreSQL tests deselected at that run's collection point |
| Final routing proof | **6,483 = 6,294 compatibility + 189 security**, disjoint and complete; all 162 patient cases and all 8 legacy tenant/pool checks included |
| Full PostgreSQL compatibility suite | **6,295 passed, 7 skipped**, no failures; all 7 skips subsequently executed in the restricted security partition as described below |
| Frontend Svelte check | **0 errors, 0 warnings** |
| Frontend ESLint | **0 errors, 8 existing warnings** |
| Frontend tests | **822 passed**, all 70 test files, using one worker |
| Frontend production build | **Passed, exit 0**, including Node adapter packaging, on standalone retry |
| Website adapter Node tests | **14 passed** |
| Python Ruff lint and format | Passed; all 823 backend Python files already formatted; new routing script also linted/formatted |
| Migration drift and Django system check | No changes detected; 0 system-check issues |
| Practice setup check against disposable database | **93 checks; passed** |
| Strict MkDocs and publication guards | Strict build passed; **2 guards passed** separately with documentation tooling installed |
| Built wheel installed outside source tree | Passed Django startup and all seven template resolutions using normal production settings; no application database was changed |
| Whitespace/diff check | Passed |

The SQLite run preceded five additional PostgreSQL-only cases; the selected compatibility set remained 6,302. Its two documentation-tooling skips were subsequently executed and passed in the dedicated guard run. Nine database-specific JSON/type checks passed in the PostgreSQL compatibility run. Its seven skips exposed four legacy RLS tests running under a superuser and three pool tests targeting a nonexistent base database. The five-test RLS class (including its formerly passing policy-inventory case) and three pool tests now run as security tests: **all eight passed, with no skips**. Thus the final compatibility partition removes eight existing cases, leaving 6,294, and security gains those same eight. The entire compatibility suite was not repeated after this test-only routing change. No test was removed to get a green result.

Commands used include `pytest -m postgres_only --no-cov --migrations`, `pytest patients/tests/test_authorization.py --no-cov --migrations --reuse-db`, `pytest -m 'not postgres_only' --no-cov`, `python scripts/check_test_routing.py`, `ruff check .`, `ruff format --check .`, `manage.py makemigrations --check --dry-run`, `manage.py check`, `manage.py check_practice_setup --json`, `mkdocs build --strict`, the documentation-guard pytest module, `npm run check`, `npx eslint .`, `npm test`, and `npm run build`. Run backend commands in `backend/` with the correct settings/database role; the routing script path is `../scripts/check_test_routing.py` from there. The runner inherited the repository's existing pytest migration defaults except for explicitly migrated security tests.

### Failures investigated and resolved

Initial PostgreSQL run: 182 passed, one stale follow-up expectation failed because the previously exposed detail now returns 403. The assertion was strengthened to require refusal. Initial new authorization run: 23 passed, one fixture omitted required Task status/priority; the fixture was corrected. Its next run exposed a test using unsupported invoice DELETE (405); the test now attempts the supported PUT to verify write authorization. No database guard or security assertion was weakened. Legacy RLS fixture creation now sets the correct tenant context. The wrong-tenant write test now requires SQLSTATE 42501 and a row-level-security error instead of catching every exception (including its own failed assertion). Policy inventory now requires both enabled and forced RLS and refuses a missing table. Pool tests connect to Django's actual test database, use required dependencies, and fail rather than skip when unavailable.

The first frontend attempt after adding six proxy tests exposed a test hook returning `mockReset()` (a callable), which Vitest invoked as cleanup. The hook now has a block body and returns nothing. All six new tests pass. A later full frontend run passed 816 tests but hit six existing filter-test import timeouts at the unchanged 5-second threshold under concurrent local workloads. A one-worker rerun passed all **822 tests**; no timeout or assertion was relaxed. Its subsequent build compiled the server and client bundles, then was killed with exit 137 during Node adapter packaging under concurrent Docker workloads. After backend validation completed and the disposable database was stopped, the standalone retry completed successfully with exit 0 and Node adapter packaging. The killed run is not counted as a pass. Build output retains its plugin timing advisory.

Initial tooling limitations: the disposable Python image has uv but no pip, so documentation tooling was installed with uv. The running frontend referenced an unavailable old image ID; validation uses the available local frontend image and a private copy of dependencies. Two frontend launch attempts preceded dependency readiness and did not run valid checks. These attempts are not counted as passes.

Existing warnings remain visible: Django EMAIL_BACKEND deprecation, missing test staticfiles directory, upstream naive-datetime warnings, eight ESLint warnings, and the build plugin-timing advisory. These were not suppressed. No failing check remains in the completed local validation; hosted Actions/CodeQL and operational acceptance remain outstanding.

## Security evidence

New regression cases exercise marketing-only/default-off profiles; explicit read without contact access; patient list/search/detail and event/history/receipt/appointment/billing/statement/CSV/correction/exclusion/allocation denial; contact assignment without a patient grant; authorized assigned reads; outcome-only treatment recording; independent receipt read; administrator-only cash writes and exports; self-grant refusal and legitimate administrator grants; unrelated-organization patient IDs and foreign-contact linkage; legacy, wildcard and explicitly scoped PATs; organization keys; shared Contact/task/invoice/search routes; and credential-based privilege administration. Frontend proxy tests verify denied reads and writes propagate 401/403/404 and forged organization fields are not forwarded.

The final credential review also requires explicit patient-write scope for writes through patient-linked shared CRM routes: `patients:read` plus broad CRM write scope cannot edit a patient's Contact. A positive case verifies adding the deliberate write grant restores that authorized workflow. Existing tenant, immutable-history, concurrency, seed and receipt/refund reconciliation tests remain intact in the restricted-role partition.

## Security and release limits

This is not production approval or a compliance certification. Patient read/export auditing, approved new-patient definitions, authoritative cross-system identity, verified settlement, durable live ingestion, backup restoration, operational monitoring, privacy/vendor review, human acceptance, accessibility and load testing remain. Permission-grant administration currently uses the existing administrator API, without a new UI. Aggregate reporting does not implement small-cell suppression. Free-text copies or exports outside patient-linked records need separate data governance.

No GitHub Actions/CodeQL run of these uncommitted changes exists. Local backend runs disabled coverage output for runtime efficiency; routing completeness was verified separately. No browser walkthrough of the remediated UI or production migration/restart/backup drill was performed because the saved application was deliberately left on its existing code. Local unit, type and production-build checks do not substitute for that acceptance. Branch protection is recommended in [team setup](team-setup.md), not applied. **Protected-merge verdict:** review candidate only, not approved to merge. A protected merge requires owner approval to publish the branch, review, actual successful required Actions checks on the proposed commit and resolution of any validation limitations reported here.

## Outstanding decisions and next milestone

See the decision table and bounded acceptance criteria in the [architecture roadmap](post-audit-architecture.md). Recommended next work is protected sandbox service identity and a durable intake/unmatched queue. Vendor selection, approved new-patient definition, collection/retention policy and reporting access remain owner/security decisions. No live advertising, messaging, review or payment connection is part of this remediation.

## Exact changed-file inventory

47 files, relative to the clean public clone; no generated artifact, reference PDF, secret or application database is included.

- `.github/workflows/codeql-analysis.yml`
- `.github/workflows/tests.yml`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `README.md`
- `backend/accounts/views.py`
- `backend/cases/views.py`
- `backend/common/external_auth.py`
- `backend/common/middleware/get_company.py`
- `backend/common/migrations/0044_profile_can_record_patient_outcomes_and_more.py`
- `backend/common/models.py`
- `backend/common/pat_auth.py`
- `backend/common/scopes.py`
- `backend/common/serializer.py`
- `backend/common/tests/test_docs_environment_variables.py`
- `backend/common/tests/test_multitenancy.py`
- `backend/common/tests/test_pool_rls_isolation.py`
- `backend/common/views/user_views.py`
- `backend/conftest.py`
- `backend/contacts/access.py`
- `backend/contacts/serializer.py`
- `backend/contacts/views.py`
- `backend/invoices/api_views.py`
- `backend/invoices/permissions.py`
- `backend/invoices/serializer.py`
- `backend/opportunity/views/opportunity_views.py`
- `backend/patients/access.py`
- `backend/patients/appointments.py`
- `backend/patients/migrations/0017_appointment_mp_appointm_org_id_f48316_idx_and_more.py`
- `backend/patients/models.py`
- `backend/patients/serializers.py`
- `backend/patients/tests/conftest.py`
- `backend/patients/tests/test_authorization.py`
- `backend/patients/tests/test_followups.py`
- `backend/patients/views.py`
- `backend/tasks/access.py`
- `backend/tasks/views/task_views.py`
- `docs/api/tokens-and-api-keys.md`
- `docs/bottlecrm-upstream.md`
- `docs/modern-practice/PROJECT_STATE.md`
- `docs/modern-practice/patient-permissions.md`
- `docs/modern-practice/post-audit-architecture.md`
- `docs/modern-practice/post-audit-remediation.md`
- `docs/modern-practice/team-setup.md`
- `frontend/src/lib/server/modern-practice.test.js`
- `frontend/src/routes/(app)/patients/[id]/+page.svelte`
- `scripts/check_test_routing.py`

In the original development folder, only `AGENTS.md` and `docs/modern-practice/PROJECT_STATE.md` received a continuity pointer to this clone and the latest no-publication instruction. Those pointer edits are not part of this public-clone diff.
