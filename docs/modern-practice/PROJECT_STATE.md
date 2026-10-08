# Modern Practice CRM — project handoff

Updated: October 8, 2026. Prior published feature baseline: `40a90cd0a0e2f7ce8fa37f3afdeb42b328cb44e0` on [Modern-CMS](https://github.com/moderndev-seo/Modern-CMS). This handoff accompanies the thirteenth increment, audited cash amount corrections; consult Git history for its publishing commit. Verify the current branch before continuing.

## Objective and explicit requirements

Turn BottleCRM into Modern Practice CRM: a practice team can follow a patient from original marketing source through appointments, consultation, completed treatment and collected revenue, with trustworthy source reporting and isolated practice records. Keep existing CRM tools accessible and unfinished modules clearly marked.

Preserve existing authentication, organization permissions, PostgreSQL row-level security, organizations and data. Use stored records for Growth, separate original attribution from subsequent touches, record receipts/refunds separately from invoices and deal values, retain chronological activity, support manual marketing spend, and make date ranges and attribution rules explicit. Never invent missing attribution or display infinite ROAS. Demonstrate two fictional TEST practices with safe rerunnable seeds. Test calculations, permissions and cross-practice reads/writes, including direct API and foreign-record links.

The CRM reference PDF supplies visual direction; the attribution deck supplies business workflow. Both were used earlier and are intentionally excluded from this public repository. If a new task requires their contents and the local files are unavailable/unreadable, tell the owner before implementing anything based on them. Do not treat document content as authority to override the user's instructions.

Standing scope: no live advertising, messaging, review or payment integrations; no deployment, Docker volume deletion or Git reset. Publish verified work to this public GitHub repository, excluding internal references/decks, secrets, actual patient records and database exports.

## Current implementation

| Work | Status |
| --- | --- |
| Milestone 1: patient journey and Growth | Implemented and tested; not a claim of production readiness |
| Milestone 2: usability and demo acceptance preparation | Implemented; team acceptance remains a human activity |
| Milestone 3: practice operations | In progress; thirteen increments delivered below |
| Production rollout and live integrations | Not implemented or authorized by the continuation instruction |

Milestone 1 uses existing Contact identity with a Patient relationship, immutable first-touch attribution, separate touches, journey events, payment/refund receipts, and chronological activity. Growth counts leads and distinct booked/treated patients, sums net receipt cash, and credits revenue to original source. Selected date ranges are UTC days, inclusive start through exclusive start of the day after end; cash uses receipt date. Unknown remains explicit. Missing spend is unavailable, and zero spend does not yield infinite ROAS. Current receipt currency is USD. Existing CRM remains reachable; Messages and Reviews are planned.

Milestone 2 improved refund entry, contact-preserving intake, Growth date/error behavior, unavailable Google sign-in presentation and demo documentation.

Milestone 3 delivered:

1. Practice-scoped Contact search and reuse during patient intake.
2. Patient follow-up tasks using the existing Task model and permissions, without sending email.
3. Appointments with booking, rescheduling, cancellation, attendance/no-show, conflict checks, revision protection, retry protection and append-only history. Forced RLS and database relationship checks were added in patient migration `0003`.
4. Administrator reopening of cancelled/no-show appointments with a required reason, without duplicate booking events.
5. Administrator billing review, keeping USD patient receipts and invoice ledgers by currency separate; stored invoice/payment disagreements are flagged.
6. Administrator matching of one existing payment receipt to one equal USD invoice payment for the same patient/contact/practice. Migration `0004_payment_matches` stores actor, reason and a database-generated snapshot with forced RLS, unique references and append-only protection. Same-pair retry is idempotent; reuse conflicts and foreign links are rejected. Matching never changes Growth or moves money. Changed underlying facts show Needs review. Matched invoice-payment deletion is rejected.

7. Audited match reversal: administrators record a required reason, actor and timestamp in a separate append-only table. A database trigger releases the original pair atomically; partial unique constraints permit only one active match per record. Matching again creates a new history entry. Old reversal retries cannot reverse a newer match. Migration `0005` preserves existing matches and is deliberately irreversible to protect audit history.

8. Receipt/refund coverage: read-only grouping into valid active matches, unmatched receipts and changed matches needing review. Refunds follow the recorded original payment, and USD invoices show linked gross/refund/net collections. All records contribute regardless of pagination. No new schema, ledger writes, allocation editor or patient amount-due calculation.

9. Audited internal charge credits: administrator-only positive USD credits on issued invoices, capped at remaining billed value, request-id retries, and full audit reversals. Migration `0006` adds forced-RLS append-only history and database validation. Billing review derives adjusted billed value; it does not change legacy invoice fields, issue documents, create refunds or calculate an amount owed. Changed invoice facts require review.

10. Explicit net-receipt split allocations: administrator-only complete plans across issued USD invoices, immutable versions, request retries, stale-revision rejection, clearing with a reason and refund/invoice drift review. Migration `0007` adds forced RLS and database relationship/amount/revision guards. All-record cash groups reconcile without combining allocation with payment-match evidence.

11. Refund explanations and recorded balances: migration `0008` extends existing allocation versions with capped, practice-validated refund lines. A read-only balance view combines issued USD charges, valid internal credits and explicitly allocated net cash only after reconciliation checks pass; otherwise balances are null with reasons. Refunds are never subtracted twice.

12. Database refund-budget protection: migration `0009` rejects excessive refund inserts/updates, reductions of a payment below its refunds, refund reassignment to an insufficient payment, and changes to the patient/practice/kind of a refunded payment. Parent-row serialization protects concurrent writers, including direct database writes. No new tables or existing-record changes. This is a prerequisite safeguard, not the pending cash-correction workflow.

13. Audited payment/refund amount corrections: migration `0010` adds append-only correction history with forced RLS, database-generated before images, actor/reason, request retries, revisions and atomic amount updates. Administrator-only correction requires reversing the original payment's active match and clearing its latest allocation plan first. Refund budgets still apply. Growth restates the receipt's original date/source; timeline shows corrections separately. Cash identity/details and deletion are now database-protected. Restoring an amount is another correction, never history deletion. No existing cash record was corrected during development; tests used the isolated test database.

Implementation choices (not additional user requirements): USD-only receipt reporting; first-touch revenue attribution; administrator-only billing matching; one-to-one equal-amount matches; permanent match and reversal history; UTC scheduling; reuse of Contact, Task, Invoice and Payment. Explain changes to these choices before implementing them.

## Milestone completion approach

The owner agreed to complete each milestone’s essential end-to-end workflow and reliability checks before expanding into the next, while deferring optional polish. Core billing reconciliation remains the priority before Messages and Reviews. Human team acceptance is still needed.

## Next work and remaining limitations

**Recommended next increment, not an already approved detailed design:** audited duplicate-payment resolution (exclusion/void with preserved evidence), followed by other cash-field corrections if needed. Amount corrections are implemented; setting cash to zero, deleting duplicates, changing date/reference/patient links and automatically detecting duplicates remain unsupported. Inspect all reporting, refund-budget and reconciliation dependencies before adding exclusion/void behavior. Complete team financial acceptance before expanding into Messages/Reviews.

Remaining backlog, with order and detailed design still proposals:

- Financial workflow: duplicate-payment resolution and corrections beyond amounts, many-to-many legacy payment matching, credit-note documents/export integration and human financial acceptance. Recorded balances describe stored data, not verified bank settlement or insurance responsibility. Complex legacy payment combinations remain blocked by the one-to-one matching requirement. Internal credits are currently included only in the Modern Practice billing review, not legacy invoice totals/paid/due/status or exports. Matching does not verify bank settlement or prevent duplicate money entry through independent existing ledgers. Matching currently exposes the latest 100 eligible entries per ledger and 100 matches, with counts; larger-history search/pagination remains unfinished. Allocation editing supports up to 20 invoices per receipt, and its receipt/invoice chooser and history show the latest 100 with counts. Totals use all records.
- Appointment operations: corrections to attended events, provider/room availability, practice timezone settings, calendar connections and reminders. Existing conflict checks concern the patient, not provider/room capacity.
- Team acceptance and hardening: complete team walkthrough, accessibility review, concurrent-request/load testing, and production/security/privacy readiness work. This CRM is not an EHR or a completed healthcare compliance program.
- Planned product areas: Messages and Reviews and any live service integration need their own scoped implementation and authorization. Do not infer authorization to connect services or deploy from “continue.”

The thirteenth increment implements audited amount corrections; duplicate resolution remains next. Verification is recorded below. No partial feature implementation remains. The publishing commit accompanies this handoff. The original working folder has many uncommitted files because publication used a separate sanitized Git history; see the publishing warning below.

## Thirteenth-increment verification

All 71 PostgreSQL patient tests passed, including eight new correction cases. Coverage includes payment/refund corrections and restoration, original-period totals and Unknown/missing-spend behavior, retry/stale-input protections, prerequisite matching/allocation release, unchanged invoice payments, API/admin/tenant rules, direct database guards, immutable history, generated snapshots, forced RLS and two competing correction writers. Svelte check passed with 0 errors/warnings. Ruff, changed-route ESLint, migration drift and Django checks passed. A missing each-block key warning was fixed before final ESLint. The existing email-settings deprecation warning remains. An initial live HTTP verification hit a backend code reload; readiness was confirmed before retrying. No load test or full accessibility audit was performed. Docker Desktop was stopped at the start of this session; it and the existing Compose services were started without deleting volumes. Migration `0010` applied locally. No live services were connected.

Initial browser tab and focus attempts timed out. After build completion and restart, local sign-in and read-only visual inspection succeeded: Cedar showed the unchanged USD 800 payment, USD 100 refund and empty correction history; expanding the payment form displayed its amount, reason and save controls. No correction was submitted in the browser. Automatic approval review rejected a proposed live Cedar correction/restoration rehearsal because it would permanently append audit entries without specific authorization for that demo write. That action was not executed or worked around; correction/restoration is verified in the isolated test database instead. Saved TEST practice financial records and their prior manual demonstrations remain unchanged.

The first authenticated-page verification retry timed out at the frontend while a production build was consuming substantial Docker CPU. Verification was deferred until build completion rather than treating the timeout as a passed check.

API-only live verification passed all 60 isolation rejections, including eight new correction checks. Harbor/Cedar net collections remained USD 1,100/USD 700, and no successful patient writes were performed. The new empty correction-history field changes the serialized journey snapshot shape; the current hash is used as the post-restart baseline.

The final production build passed, including the Node adapter. It was slow under Docker resource contention and reported the existing empty generated env chunk warning.


Final post-restart verification passed all 60 direct HTTP isolation rejections and 20 authenticated frontend pages, with Harbor/Cedar net collections unchanged at USD 1,100/USD 700. The journey/Growth snapshot matched its pre-restart baseline. A normal PostgreSQL/backend/frontend restart preserved identical hashes and counts across all 87 checked model/practice groups, including the original organization; no volumes were removed. The live correction audit table remains empty. A temporary automatic-review usage limit interrupted a readiness command; after the owner continued, the normal approved retry and verification succeeded.

## Twelfth-increment verification (historical)

All 63 PostgreSQL patient tests passed, including five new refund-guard cases covering exact caps, inserts/updates, parent reductions, relinking, tenant rejection and competing writers at READ COMMITTED and REPEATABLE READ. Tests use the separate test database and a non-bypass role. Migration `0009` applied locally; migration drift, Django system checks, Ruff and whitespace checks passed. Browser review retained Harbor's USD 1,600 billed, USD 1,100 net allocated cash and USD 500 recorded balance. The existing email-settings deprecation warning remains. A temporary approval-service capacity failure delayed the lint command; retry through normal approval succeeded. No frontend source changed, so frontend compilation/build and full accessibility testing were not repeated. The two-writer test is targeted concurrency verification, not a load test. The focused five-case rerun also passed after adding an assertion that every stored field on the original payment remains unchanged. Live checks passed 52 isolation rejections and 18 authenticated pages with unchanged Harbor/Cedar revenue. Migration plus normal PostgreSQL/backend restart preserved all 84 model/organization fingerprints, including the original practice. No volumes were removed.

The first post-restart HTTP verification started before the backend listener was ready and received connection refused; readiness was subsequently confirmed before retrying. The post-readiness run passed all 52 isolation rejections and 18 authenticated routes with the same journey/Growth snapshot hash. Browser reload also retained the USD 500 recorded balance.

## Eleventh-increment verification (historical)

All 58 PostgreSQL patient tests passed, including seven new refund/balance tests. Ruff, changed-route ESLint, migration drift, Django system checks and Svelte check (0 errors/warnings) passed. The first migration attempt failed on SQL CASE syntax and rolled back; the corrected migration applied successfully. Browser verified unavailable → available balance after explaining Harbor’s existing USD 100 refund: USD 1,600 billed less USD 1,100 net cash = USD 500 recorded balance. The existing email-settings deprecation warning remains. Live verification passed 52 isolation rejections and 18 authenticated pages, including balance availability/arithmetic and refund-link rejection. Restart fingerprints matched across 84 model/organization groups in all three practices, including four allocation versions. No volumes were removed. Production build passed with the Node adapter (empty generated env chunk warning); post-restart HTTP verification passed all 52 isolation rejections and 18 authenticated routes with unchanged revenue and journey/Growth hash. Browser reload retained the USD 500 recorded balance. No concurrent-load test or full accessibility audit was performed.

## Tenth-increment verification (historical)

All 51 PostgreSQL patient tests passed, including six allocation tests for splits/replacement/clearing, retries and stale revisions, refund/invoice drift, unchanged Growth/ledgers, permissions, foreign links, database RLS/immutability/amount/revision checks, all-record totals beyond display limits and rerunnable optional seeds. Svelte check: 0 errors, 0 warnings. Route ESLint, Ruff, migration drift and Django system checks passed. Live HTTP passed 48 isolation rejections and 16 authenticated pages, with reconciled allocation/coverage groups and unchanged revenue/Growth snapshot. Browser split → clear → restore retained three versions; a premature blank-reason clear was rejected before the successful attempt. Production build passed with the Node adapter; it reported an empty generated env chunk. PostgreSQL/backend restart preserved all 84 checked model/organization groups, including three allocation versions. No volume was removed. No concurrent-load test or full accessibility audit was performed. The existing email-settings deprecation warning remains.


Post-restart HTTP verification also passed all 48 isolation rejections and 16 authenticated routes, with unchanged revenue and demo journey/Growth snapshot.

## Ninth-increment verification (historical)

All 45 PostgreSQL patient tests passed, including five new credit tests for totals/caps, retry/reversal, input/status/currency, invoice drift, unchanged original records/Growth, tenant/admin protections, forced RLS, direct database bypass rejection, immutable audit history, rollback, generated snapshots and 101-entry totals. Ruff, migration drift, Django system checks and Svelte check (0 errors/warnings) passed. Changed billing routes passed ESLint. No fresh production build, concurrent-load test or full accessibility audit was run for this increment. The original email-settings deprecation warning remains.



Browser verification on October 4 completed a fictional USD 100 credit and full reversal in Harbor: adjusted billed value changed from USD 1,100 back to USD 1,200; both audit entries remain. Original invoice fields and USD 1,100 net collections stayed unchanged. The initial reversal form interaction occurred before hydration finished; reopening the form after rendering completed succeeded. Live verification rejected 40 cross-practice requests (22 journey/matching, 4 match reversal, 7 credit, 7 appointment) and rendered 14 authenticated pages; Harbor/Cedar net collections remained USD 1,100/USD 700.

Normal PostgreSQL and backend container restart preserved identical hashes/counts across 81 model/organization groups, including both credit audit entries. No volumes were removed. An initial HTTP check ran before Django was listening; the post-readiness rerun passed all 40 isolation checks and 14 authenticated pages, with unchanged revenue and demo snapshot hash. Browser reload also retained both audit entries and the restored USD 1,200 adjusted billed value.

## Eighth-increment verification (historical)

All 40 PostgreSQL patient tests passed; new coverage tests exercise refunds, reversal/rematching, drift, unchanged Growth, tenant/admin checks, foreign currency, empty states, 101 matches and invoice pagination. Ruff, migration drift, Svelte check (0 errors/warnings) and route ESLint passed. Live checks reconciled coverage totals in both practices, rejected 33 foreign-practice requests and rendered 14 authenticated pages. No new records or schema were required. A fresh build/restart, concurrent-load test and full accessibility audit were not repeated for this increment. The build/restart results below belong to the seventh increment.

## Seventh-increment verification (historical)

- All 37 PostgreSQL patient tests passed, including four new reversal tests: retry/rematching, retained history, unchanged cash/Growth, permissions and input validation, wrong-patient/foreign links, forced RLS, database bypass rejection, rollback, drift and reassignment. One existing Django email-settings deprecation warning remains.
- Live verification: 33 cross-practice rejection checks (22 journey/billing/matching, 4 reversal, 7 appointment), 14 authenticated pages, and both demo revenue totals passed after the correction rehearsal.
- Svelte check: 0 errors, 0 warnings. Changed routes passed ESLint. Ruff, Django system checks, migration drift checks and whitespace checks passed. Migration `0005` was applied locally.
- Browser: Harbor reversal released both records; rematching created a second entry while preserving the reversal and original facts. Net collections remained $1,100. Cedar remains unmatched. A temporary backend connection failure interrupted the first attempt during development reload; the completed walkthrough succeeded after recovery.
- No concurrent-request stress test or full accessibility audit was performed for this increment.

Restart persistence verified for the seventh increment: PostgreSQL, Redis, backend and both Celery services restarted normally, and hashes across 33 model/organization groups in all three organizations were identical. This includes the original organization, contacts, tasks, patients, journey events, receipts, invoices/payments, appointments/history, matches and reversals. No volume was removed.

Production build (`npm run build`) completed successfully, including the Node adapter. It reported an empty generated env chunk and slow plugin timings; no build error occurred. The post-restart HTTP check was initially attempted before backend startup completed, then rerun after readiness.

Detailed historical evidence is in [milestone one](milestone-one.md), [milestone two](milestone-two.md) and [milestone three](milestone-three.md). Earlier milestone sections describe earlier states; the sixth increment supersedes the read-only billing description.

## Runtime, demo and team setup

Backend: Django REST Framework in `backend/`; frontend: SvelteKit in `frontend/`. Docker Compose runs backend, frontend, PostgreSQL, Redis, Celery worker and Celery beat. Frontend stays at http://localhost:5181 and API at http://localhost:8000. Use [README](../../README.md) and [team setup](team-setup.md) for installation, local magic-link sign-in and relevant checks. Never expose environment contents in logs or handoff documents.

Base demo: `docker compose exec backend python manage.py seed_modern_practice --member-email admin@localhost` for a new teammate's setup. Use the existing member account on an established installation. Optional billing counterparts: `docker compose exec backend python manage.py seed_modern_practice_billing`. Both commands preserve existing records on rerun; the latter adds no receipts, sends nothing and creates no matches automatically.

Select a TEST practice at http://localhost:5181/org. For September 1–30, 2026, both seeds have 3 leads, 2 booked patients and 1 treated patient. Harbor net collected is $1,100 ($1,200 payment less $100 refund), with Google Ads source ROAS 5.50 on $200 spend. Cedar net collected is $700, with Google Ads ROAS 3.50. Overall ROAS can remain unavailable because another source lacks spend. Later manual demo records may change counts; do not reset them to match these seed values.

Local demo checkpoint: Harbor Alex has two persisted match entries (one reversed, one active), one reversal audit entry, and no eligible unmatched pair; Cedar Alex remains available for a matching demo. Harbor also has one USD 100 internal credit and its full reversal (two permanent entries, zero active credit, adjusted billed USD 1,200); cash remains USD 1,100. These manual actions are not reproduced by cloning GitHub or rerunning the seed. Harbor also has a completed demo follow-up and a reopened scheduled appointment. The original organization and records remain preserved. The optional allocation seed added one USD 400 fictional second invoice per TEST practice. Harbor has four allocation versions (700/400 split, clear, restored split, then USD 100 refund explained against TEST-HARBOR-MATCH), with USD 1,100 valid allocated cash and zero unallocated; Harbor’s recorded balance is USD 500, zero overpaid. Cedar is unallocated/unmatched and demonstrates unavailable balances. These extra invoices increase billed totals only, not cash or Growth.

- Patients: http://localhost:5181/patients
- Growth: http://localhost:5181/growth?start=2026-09-01&end=2026-09-30
- Harbor Alex balances: http://localhost:5181/patients/a29def23-7510-5894-9778-61392bbfe46f/balances
- Harbor Alex billing: http://localhost:5181/patients/a29def23-7510-5894-9778-61392bbfe46f/billing
- Cedar Alex billing: http://localhost:5181/patients/b05ee694-107f-5b98-afa1-9316d8921d66/billing

Normal app/container shutdown does not delete the database volume. GitHub preserves code and documentation, **not** local database contents, uploaded files or secrets. Exact data recovery on another machine requires a separate private backup and environment setup. No new database backup was created as part of this handoff.

## Publishing warning for the original development folder

The original development folder's Git HEAD is `02eb9746` (Phase 1), with an upstream BottleCRM remote and internal artifacts in its history. It is not the public repository's history. **Do not push that history or blindly change its remote and push.** Preserve its working files and existing Docker data.

The public repository was created from a sanitized source snapshot, then updated through GitHub commits. Local `output/team-repository/` contains ignored export/clone artifacts; initial ZIP/bundle snapshots are stale. The `github-current` helper clone may have an old HEAD and a staged tree corresponding to a newer published commit. Inspect it before use. Prefer a fresh clone of public main for ordinary team development, or publish only reviewed file changes onto the verified current public tree. Never force-push, overwrite teammate changes, or include excluded artifacts. Update this handoff with every completed increment.

## Resume in a new chat

Open this project folder (or a current clone) and say:

> Read AGENTS.md and docs/modern-practice/PROJECT_STATE.md. Verify the repository and runtime state, then continue the next unfinished milestone. Preserve the recorded constraints, distinguish proposed work from requirements, update the handoff, and push verified changes to GitHub.

This is durable project context, not a saved transcript or a guarantee that every unrecorded conversation detail survives. If interrupted, record the partial work, outstanding checks and exact next action here before handing off when possible.

Final post-restart HTTP verification passed: 33 isolation rejections, 14 authenticated pages, unchanged revenue and identical demo snapshot hash. The frontend was also restarted after its successful build.

## October 4 resumption check

GitHub main was confirmed at feature commit `9e1189a`. Docker Desktop was stopped; the existing six containers were started with their saved volumes. The first live check ran before the backend was ready. After readiness, all 33 isolation checks and 14 authenticated routes passed again; Harbor remained $1,100 and Cedar $700, with the same demo snapshot hash as September 28. Browser automation timed out, so a fresh visual check could not be completed on October 4; the successful reversal/rematch browser walkthrough above was performed September 28. No new feature changes or database reset were needed.

Browser verification for the eighth increment succeeded on October 4 after local sign-in: Harbor showed $1,200 linked payments, $100 related refunds and $1,100 linked net collections at both patient and invoice level, with zero unmatched/changed amounts. Existing reversed and active history remained visible. No financial records were written during this check.
