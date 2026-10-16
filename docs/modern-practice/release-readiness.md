# Final remediation release review

October 15 review follow-up: the four automated PR findings and verified adjacent authorization paths have been corrected and passed final local regression. The snapshot below is historical and does not validate this new diff. See [PR #1 review remediation](pr1-review-remediation.md) for current results and gates.

Publication update: the owner has authorized a feature-branch commit/push, PR and hosted validation. Historical local-review status below records what had happened at that time; see [current handoff](PROJECT_STATE.md) for the latest authorization. Merge, deployment and next-phase implementation remain prohibited.

Status: **Ready with documented nonblocking limitations — October 14, 2026**. Local review and regression verification are complete; hosted checks and independent review remain PR gates. All changes remain uncommitted on `codex/patient-authorization-ci`, based on public main `11e6d59a0ef79e6cefe6d5fe1a71859099557961`. No publication, deployment, live integration or repository administration changes are authorized.

## A. Verdict

**Ready with documented nonblocking limitations.** No known unresolved merge-blocking defect was found in the reviewed remediation after the corrections below and final local checks. The branch is ready for a deliberate publication/review decision, subject to hosted CI and independent review. This is not production approval. The saved application has not adopted this branch.

## B. Findings and corrections

- **Medium — legitimate shared-record identity hidden.** Case, lead and opportunity serializers were invoked without the profile/request context required by the new fail-closed nested Contact serializer. Authorized staff and administrators received a restricted placeholder. Propagated context through case serialization and the shared account, user-profile, lead and opportunity callers. Regression tests verify visible identities for authorized callers.
- **High — patient-linked record bodies and profile history bypassed revocation.** Redacting the contact name alone left case/sales contents and a user's own historical comments reachable. Shared queryset/object rules now hide patient-linked cases/tasks unless all linked patient contacts are visible, and patient-linked leads/opportunities additionally require finance access because they contain proposed amounts. Profile comment history filters through the actual parent's visible queryset. Unrelated CRM records retain existing rules.
- **High — creator mutation bypass after revocation.** Task, lead and opportunity deletion still relied on creator/admin rules without the new patient boundary. Added current-access checks before the existing narrower delete rules. Generic comment and attachment mutation routes also check the actual patient-linked parent, including IDs submitted through another module's endpoint; invoice interaction routes receive the same guard. Author/uploader identity alone does not retain patient authority.

- **Medium — restricted payment state looked unpaid.** Browser acceptance found that clinical users correctly saw Restricted cash, but the payment milestone rendered an incomplete circle because receipts were intentionally omitted. The milestone now explicitly labels its status Restricted; final checks, production build and clinical browser verification passed.

- **Medium — stale browser title after denied client navigation.** The application error component did not set a title; the browser retained the preceding page title on a 403 transition. Added a neutral status/Modern Practice title so prior patient identity cannot remain in the tab. The fresh production build and browser recheck passed: patient-to-denied-Growth navigation shows `403 | Modern Practice CRM` without the previous patient identity or history.

Affected implementation files: serializer context in `backend/cases/serializer.py`, `backend/accounts/views.py`, `backend/common/views/user_views.py`, `backend/leads/views/lead_views.py` and `backend/opportunity/views/opportunity_views.py`; shared-record visibility/deletion in `backend/contacts/access.py`, `backend/cases/access.py`, `backend/tasks/access.py`, `backend/leads/access.py` and `backend/opportunity/access.py`; generic mutation enforcement in the corresponding contacts/cases/tasks/accounts views, lead/opportunity interaction views and `backend/invoices/api_views.py`. The 26-case acceptance coverage is in `backend/patients/tests/test_release_workflows.py`. The two browser corrections are in `frontend/src/routes/(app)/patients/[id]/+page.svelte` and `frontend/src/routes/(app)/+error.svelte`.

All 47 original remediation files remain present; the complete current change contains 57 modified/untracked files. Both repositories retain their original HEAD and remote, the original checkout retains its 107 dirty/untracked entries, and nothing is staged. These corrections extend the original 47-file remediation; they do not add schema beyond its two additive migrations or begin the next attribution phase. The original files and a private baseline snapshot remain preserved.

## C. Permission compatibility

See [patient permissions](patient-permissions.md) for supported API operations and credential revocation.

| User configuration | Patient identity/history | Outcome recording | Receipt reads | Cash writes, reconciliation, statements | Growth |
| --- | --- | --- | --- | --- | --- |
| Practice administrator | Yes, within practice | Yes | Yes | Yes | Yes |
| Clinical staff: patient + outcome flags | Assigned/shared contacts | Yes | No | No | Only with marketing flag |
| Patient reader: patient flag | Assigned/shared contacts | No | No | No | Only with marketing flag |
| Finance reader: patient + finance flags | Assigned/shared contacts | No unless outcome flag | Yes | No | Only with marketing flag |
| Marketing-only agency member | No | No | No | No | Yes |
| Default regular member | No | No | No | No | No unless explicitly granted |
| Restricted PAT | Same profile/object restrictions plus explicit patient and applicable resource scopes | Requires write scope and outcome capability | Requires finance capability | Only eligible admin with write scope | Existing scope/marketing rules |
| Organization API key | No patient authority | No | No | No patient financial authority | Existing legacy non-patient rules |

Default-false grants are intentional. Existing regular staff require deliberate review/grants and contact assignments before patient workflows resume. Administrators can grant/revoke another member through the current administration API; a permission-management UI is future work. Original attribution remains immutable; receipts less refunds supply collected revenue. Proposed deal values never become cash.

## D. Validation ledger

The final complete-tree security partition passed: **215 passed, zero failed/skipped, 6,294 deselected, 213 warnings, 873.40 seconds** under the restricted PostgreSQL role with migrations. Routing passed: **6,509 = 6,294 compatibility + 215 security; all 188 patient cases routed to security**. PostgreSQL compatibility passed **6,294 tests, zero failures/skips, 215 deselected, 4,781 warnings in 3,877.48 seconds**. SQLite compatibility passed **6,285 tests, nine skips, zero failures, 215 deselected, 4,772 warnings in 3,534.90 seconds**, with **90.33% coverage** (50% required). Compatibility PostgreSQL uses a superuser for legacy tests; only the separate restricted-role security partition supplies RLS evidence. Do not treat the earlier remediation's partition counts as this review's final results.

The nine SQLite skips are the PostgreSQL-only `JSONField __contains` custom-field filter cases for accounts, cases, contacts, invoices, estimates, recurring invoices, leads, opportunities and tasks. All nine passed in PostgreSQL compatibility. Backend warnings include Django 7 EMAIL_BACKEND deprecations, missing collected-static directories and legacy naive datetimes; no warning filter or assertion was weakened for this review.

Completed during this review:

- Focused release workflows: 24 passed, 26 warnings, 0 skipped (before adding two invoice-route regression cases for the final full partition).
- Final frontend type/Svelte check: **zero errors and zero warnings**, including both browser-discovered corrections.
- Frontend unit suite: 822 tests passed across 70 files, one worker, 70.70 seconds before the payment-label correction; the post-correction full rerun had 820 passed and two unchanged ticket-filter import timeouts at 5,000 ms (107.24 seconds); the uncontended final-source retry passed all **822 tests across 70 files in 27.35 seconds**, with no timeout/assertion changes. Final ESLint: zero errors/eight existing warnings (three navigation resolution, three writable-derived, one unused assignment and one reactive URLSearchParams warning). Final Prettier: full-tree pass.
- Final frontend production build passed with exit 0, including Node adapter packaging; its generated empty `chunks/env.js` notice is nonblocking. Website attribution adapter: **14 passed, zero failed/skipped**.
- Final wheel built and reinstalled into the existing isolated dependency environment outside the source tree, passed Django startup and resolved all seven required templates.
- Two workflow YAML files parsed successfully; CI targets main/PRs and its migrated security job has no dependency on compatibility jobs.
- Strict documentation builds passed, including the final report; omitted navigation entries are informational.
- Backend Ruff passed; format check: 824 files already formatted.
- Django system check: no issues; migration drift: no changes detected.
- Disposable setup verification passed, including restricted database role, forced RLS and zero pending migrations.
- Migration rehearsal: clean baseline through prior migrations, representative existing user/patient, then both new migrations; three flags false, patient identity/contact/original source preserved; all 21 index definitions and enabled/forced RLS flags verified; empty tenant context hides the patient.

Intermediate failures are not omitted: three authorized nested-contact failures exposed missing serializer context and were corrected; a subsequent intermediate run had two fixture expectations missing the new explicit financial grant; an expanded regression run initially had seven fixture validation failures (required task status/priority and attachment path), corrected before the 24-pass run. Initial browser startup/navigation attempts timed out. Test harness setup also needed the explicit project import path and a permitted Host header; both were corrected without application changes. An approval-review usage-limit interruption was resolved after the owner resumed. An isolated built frontend subsequently opened successfully against the reviewed backend. Its frontend source was hash-verified unchanged from the prior successful build before the small label fix above. Clinical login/practice selection and consultation submission passed, with Restricted cash and updated activity; administrator API revocation followed by submission of the already-open form produced a clean 403 with no stale patient name/activity. Finance-reader cash/history was visible ($125 fictional receipt), outcome/cash-write forms were absent, and an unknown patient ID produced a clean 404. Marketing-only Growth rendered correctly with missing spend/unavailable ROAS. Marketing patient navigation returned 403. Administrator browser entry of a $25 payment and a linked $5 refund reconciled the patient and Growth views at $150 received minus $5 refunded = $145 net, attributed to the original source. Logout followed by direct patient navigation returned to sign-in without patient data. Those broad workflow checks used the prior built frontend. On the final fresh production build, clinical patient detail showed `— Payment received · Restricted` without cash amounts; client navigation to forbidden Growth showed 403 with a neutral title and no stale patient identity/history. An initial sign-in attempt preceded API startup and showed verification failure; after API readiness, the same valid fictional link completed the normal sign-in and practice-selection flow.

All requested local validation stages are complete. Documentation publication guards passed in both complete compatibility partitions. CodeQL currently covers Python only. Hosted Actions and CodeQL cannot be claimed without a published branch/PR; none has been published.

## E. Migration readiness and rollback

`common.0044` adds three default-false Profile capabilities; `patients.0017` adds 21 `(org_id, created_at DESC)` indexes. Existing rows and source/revenue history are not rewritten. Dependencies must be applied through normal Django migration ordering.

For a later approved release: privately rehearse against a representative backup, verify recoverability and non-superuser/NOBYPASSRLS roles, reserve a maintenance window, stop application/worker writes, apply migrations, deploy compatible application/workers, verify setup and tenant isolation, grant reviewed staff capabilities, then reopen access. Standard index creation can block writes; runtime on this small fictional database is not a production timing estimate. Keep ports 5181/8000 for this local project.

Prefer a forward fix while retaining the additive schema. Dropping the new Profile columns loses permission grants; re-adding them defaults members to denied. Removing indexes changes query performance. Restoring an older application reintroduces the known authorization weaknesses, so do not reopen it to users merely because the schema is backward compatible. A backup restore can discard writes after the backup; reconcile them under a separately approved recovery plan. Never reverse older immutable financial-history migrations as part of this rollback. No saved application database was migrated, restored or modified during this review.

## F. Proposed GitHub review plan

Keep one coherent PR for authorization, necessary shared-route corrections, additive migrations, security tests, routing/CI and operational documentation. Splitting dependent permission/model/serializer changes would create unsafe intermediate states. The architecture roadmap is explicitly planning context, with no service-identity or ingestion implementation included. Exclude all private baseline snapshots, test tokens/logs, database exports, internal decks/reference/output and the original repository's private history.

Proposed title: **Enforce patient permissions across CRM routes and verify forced-RLS CI**.

Proposed description:

> Organization membership and legacy CRM access could expose patient information without an explicit patient grant. This change adds default-deny patient, outcome and finance capabilities; enforces contact/object access and explicit token scopes across patient-linked CRM routes; preserves legitimate administrator/assigned-staff workflows; and closes revocation gaps in shared history and mutations. It also restores 21 indexes and makes the restricted-role PostgreSQL security partition independent of compatibility jobs.
>
> Apply the two additive migrations before starting the updated application, review existing regular-member grants, and allow for standard index-creation locks. Validation results belong in the final ledger above. No live integrations, production rollout or permission-management UI are included.

After explicit publication approval, recheck the remote branch, preserve others' work, publish only this isolated public-history branch, and open a reviewed PR targeting `main`. The local reproduction uses the installed locked dependencies and one frontend test worker for this memory-limited Docker environment; hosted runners remain a separate gate. CI retains its inherited warning-only Prettier step, although the strict local formatting check passed. Recommended required checks: `backend-tests`, `backend-tests-postgres`, `patient-security-postgres`, `frontend-checks`, `package-build`, `docs-build`, and the repository's actual CodeQL check context after confirming its first PR run. Require an independent reviewer with authorization/RLS expertise, fresh approval after material changes, resolved discussions and up-to-date successful checks. Protect `main` against force-push/deletion and unreviewed direct changes. These are recommendations only; no GitHub settings were changed.

## G. Remaining limitations

**Merge blockers:** no known unresolved defect from this review. Hosted CI and independent review remain required PR gates; neither can be completed without separate publication approval. **Production gates:** adoption additionally requires backup/restore rehearsal, deployment timing, explicit staff grant review, human workflow acceptance and privacy/operational review. The inherited TEST-practice Growth banner mentions the September demo seed period even when the date controls select another range; the actual selected UTC controls and calculations were verified, and banner cleanup is a nonblocking follow-up. No broad load test, accessibility audit, independent compliance certification or real-provider verification is claimed.

**Nonblocking scope limitations:** capabilities do not classify arbitrary patient information copied into unrelated notes/files/exports. Aggregate Growth access is a trusted-data grant, with no small-cell suppression. Revocation cannot retract prior downloads or already-rendered pages without a subsequent request. Finance writers remain administrators; API-only permission management and separate messaging permissions are documented future improvements. The website adapter still does not establish cross-device identity or verified lifetime introduction, and attributed cash is not proof of causal incremental marketing lift.

## H. Smallest next milestone (proposal only)

After remediation approval and merge, implement one restricted, revocable server service identity and a durable protected website-event receiver: strict reviewed event schema and consent boundaries, tenant-bound source identity, stable idempotency keys, durable acceptance/error status, bounded retries and an unmatched-event queue. Prove duplicate/conflicting deliveries, revocation, cross-tenant rejection and replay recovery using fictional data. Keep provider connections disabled. This review does not implement that milestone.
