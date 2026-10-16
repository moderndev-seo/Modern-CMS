# PR #1 review-finding remediation

Status: local implementation and final regression validation complete — October 16, 2026. Delivery targets the existing PR #1 branch; the PR review summary records the exact published head and hosted results. Earlier-head checks are historical. Independent human review and separate owner merge approval remain required. No merge or deployment is authorized.

## A. Four review findings

- Opportunity Kanban and line-item handlers used independent query/ownership checks. They now use the central deal visibility/access guards, including patient/contact visibility, finance access and credential ceilings.
- Case watching and analytics used raw case querysets; merge/unmerge relied on creator/admin status. These paths now enforce central current patient visibility, and merge/unmerge check both records. Unmerge checks source visibility before exposing merge state.
- Member creation validated patient capability fields but only saved role. The administrator endpoint now persists validated Profile values. Missing grants remain false, and non-JWT credentials and ordinary members cannot administer grants. The actual collection endpoint is `/api/users/`.
- Comment serializers lacked trusted reader context. Case, task, opportunity, contact, invoice, account and lead comment handlers now pass request context. The fail-closed author restriction remains enabled.

Affected files (relative to `backend/`):

| Finding | Implementation files | Regression cases |
| --- | --- | --- |
| Opportunity subresources | `opportunity/views/kanban_views.py`, `opportunity/views/line_item_views.py` | Revoked Kanban and collection reads; 10 line-item verb/capability cases; scoped PAT/org-key, administrator, unrelated and foreign-practice checks |
| Alternate cases | `cases/access.py`, `watcher_views.py`, `analytics_views.py`, `merge_views.py`, `unmerge_views.py`, `bulk_views.py`, `views.py` | Watching, merge, both-side unmerge, four alternate lists/exports, five metric counts, service PAT scope, bulk delete and foreign-practice checks; existing constant-query regression |
| Member grants | `common/views/user_views.py` | One explicit-grants creation, one restrictive-default creation and three unauthorized-actor cases |
| Portal authors | `accounts/views.py`, `cases/views.py`, `contacts/views.py`, `invoices/api_views.py`, `leads/views/lead_views.py`, `lead_interactions.py`, `opportunity/views/opportunity_views.py`, `opportunity_interactions.py`, `tasks/views/task_views.py` | Case author plus five parent-detail cases; missing context and unauthorized readers remain restricted |

Direct regressions live in `backend/patients/tests/test_review_findings.py`. Seven pre-fix API cases reproduced the original defects and the adjacent bulk-delete bypass. An additional pre-fix goal-detail test returned 250 from a protected deal after finance revocation.

## B. Adjacent routes

Compatibility testing found an additional query per merged source after the new permission check. Mergeability now has a central queryset form, and detail summaries fetch permitted IDs in one batch. The existing constant-query regression and 18 analytics/visibility cases passed together (19 tests). The patient regression also asserts that a restricted merged source cannot advertise unmerge permission.

Case bulk deletion now reuses the same patient-aware delete predicate as individual deletion. Goal list/detail/leaderboard/history aggregation filters protected opportunities using the reader's current patient, contact and finance authority. Existing team/org calculations for unrelated deals are retained. These are proposed implementation choices within the requested authorization boundary, not new attribution rules. Deal amounts remain distinct from collected revenue.

Goal/notification corrections are in `backend/opportunity/models.py`, `backend/opportunity/views/goal_views.py` and `backend/opportunity/tasks.py`.

Existing case board moves, bulk updates, opportunity moves/exports, and generic comment/attachment mutations already call the central guards. Final regression results will establish compatibility; source inspection alone is not a passing test.

Three in-memory mailbox regressions reproduced assignment, stale-deal and goal-milestone notices still revealing protected deal information after revocation. Assignment and stale notices now filter by current patient/contact/finance access; milestone notices are suppressed for recipients who cannot read all underlying protected deals, because even the milestone percentage reveals a hidden contribution. Goal milestone flags remain goal-wide; this change does not add per-recipient delivery/replay tracking. No external mail is sent by these tests.

## C–D. Validation

| Final local check | Result |
| --- | --- |
| Migrated restricted PostgreSQL security | **281 passed**, zero failures/skips, 6,294 deselected, 281 warnings; includes all **66 new regressions** and all **254 patient cases** |
| PostgreSQL compatibility (separate test superuser; not RLS evidence) | **6,294 passed**, zero failures/skips, 281 deselected, 4,781 warnings |
| SQLite compatibility/coverage | **6,285 passed**, **9 expected PostgreSQL JSON-filter skips**, zero failures, 281 deselected, 4,772 warnings; **90.35% coverage**; skipped cases passed on PostgreSQL |
| Test routing | **6,575 = 6,294 compatibility + 281 security**; every patient case included in the independent security partition |
| Backend | Ruff; all 825 files formatted; Django system check; migration drift; whitespace checks passed |
| Frontend | **822 tests/70 files passed**; types zero errors/warnings; ESLint zero errors/eight existing warnings; full formatting and production Node build passed |
| Documentation | Strict MkDocs build and two exclusion guards passed (2 tests, one deprecation warning); final report build repeated before publication |

The security role is NOSUPERUSER/NOBYPASSRLS; 89 tables have enabled and forced RLS. Security tests exercise authorization, current grants and Contact visibility, finance boundaries, PAT/org-key ceilings, cross-practice APIs and database relationships, and immutable attribution/cash history. Compatibility success under a superuser is not isolation evidence. All named cases in section A passed within the final 66-case regression file; all legacy shared-CRM cases passed in compatibility.

Warnings are inherited EMAIL_BACKEND deprecation, missing collected staticfiles, and naive-datetime test fixtures. Frontend retained eight existing lint warnings, an empty generated env chunk and plugin-timing notices. No warning was suppressed to pass these checks.

Intermediate failures: seven original/bulk-delete pre-fix cases, one goal disclosure and three in-memory notification disclosures reproduced defects. Initial test setup/path/context/assertion errors were corrected. A new per-source mergeability query violated an existing constant-query test; the batched correction passed that test and the complete final suites. An overnight security run and an interrupted SQLite run each logged an expired JWT; two PostgreSQL SLA assertions used a module-level clock aged by the interruption. Fresh unchanged clock/expiry tests passed. No expiry, permission, SLA or query-count assertion was weakened. Earlier interrupted runs are not final validation.

Docker's isolated test database was rebuilt after a restart; saved demo databases were not touched. Read-only dependency/cache attempts failed, and stalled duplicate type checks required restarting only the disposable frontend container. A bounded clean type-check retry passed after the production build. Temporary dependency links/cache were removed; shared dependencies remain untouched. No new schema is introduced in this increment.

No new browser walkthrough, saved-data restart/backup drill, production migration, load/privacy acceptance or live-provider test was performed. Frontend source is unchanged; its tests/types/build verify the same source through the final backend-only batching correction. Earlier browser evidence remains historical. This bounded review is not a new repository-wide architecture or security certification.

## E–F. Publication and independent review

Existing branch: `codex/patient-authorization-ci`; existing [PR #1](https://github.com/moderndev-seo/Modern-CMS/pull/1). Publication uses the connected GitHub API because Git CLI has no credentials. The published tree must match the reviewed local Git tree exactly, and the branch update must be a fast-forward from the inspected head. The PR review summary supplies the exact commit SHA, four review-thread responses and hosted results. Required checks on that exact head: backend-tests, backend-tests-postgres, patient-security-postgres, frontend-checks, package-build, docs-build and Python CodeQL. Do not substitute the previous head's checks. Independent qualified human approval and separate owner merge approval remain required; implementing a fix does not resolve a thread by independent review.

## G–H. Preserved work and next milestone

The original local checkout and saved demo remain preserved. Private architecture packages are not included in this public change. Architecture v0.2.0 and approved A01–A10 remain the baseline; Group B/C remain pending. No new schema, live service, deployment, repository setting or production change is part of this increment.

Next: after publication and seven successful exact-head checks, PR #1 is ready for independent qualified human approval and subsequent separately authorized merge. Review must cover route completeness, revocation, credentials, nested serializers, grants, tenant isolation, the original PR migrations and compatibility. No human approval is claimed; stop at that gate. The separate architecture documentation PR and conditional fictional Phase 2A remain subsequent work, gated on required security and documentation merges.
