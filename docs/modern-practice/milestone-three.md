# Milestone 3 — Daily operations (in progress)

## First increment: patient intake

Staff can now search the current practice's contacts by name or email from **Patients → Add patient**. Contacts with an existing patient journey offer **Open journey**. Contacts without a journey offer **Select contact**, which reuses the existing identity when the patient form is submitted. The selected name and email are displayed; copying a contact UUID is no longer required.

The search is read-only, limited to 25 results, and requires 2–100 characters. Multiple words narrow the results; search matches are suggestions, not proof that people are the same. Inactive contacts are labeled. A staff member still decides which identity to use. Existing server-side protections reject duplicate contact journeys and duplicate email identities within a practice. This does not add fuzzy identity matching, automatic merging, or a guarantee against duplicates without an email.

Search uses the existing signed-in organization context. Both Contact and Patient queries explicitly filter by that practice. An organization parameter supplied by the caller cannot change the scope. Contact descriptions and other unrelated fields are not returned. Existing authentication, membership checks, PostgreSQL RLS, and cross-practice link rejection remain in place. No schema migration was needed.

Search preserves unsaved intake fields in the JavaScript interface. Selection is retained after failed creation. The original attribution rules are unchanged. The contact's displayed label is only form presentation; the backend resolves and validates its ID.

## Demo

1. Open http://localhost:5181/org and select either fictional TEST practice.
2. Open http://localhost:5181/patients/new.
3. Search **Alex Rivera**. Choose **Open journey** to see the existing record rather than start a duplicate.
4. Return to Add patient and search **Taylor**. Choose **Select contact** for **Taylor Intake Demo**. The identity is selected without copying an ID.
5. Enter the known-lead timestamp and only the attribution facts you know. **Create patient journey** persists a real demo journey and changes reporting counts for that date. For a read-only rehearsal, stop before this step.

The rerunnable `python manage.py seed_modern_practice` now also adds a deterministic Taylor contact in each fictional practice. It never creates a journey for Taylor or overwrites an existing record. The original practice and all prior records are preserved. The original three-patient September baseline remains unchanged until someone submits a new demo journey. The existing `verify_modern_practice` smoke command expects that baseline and will report a mismatch after extra journeys are created.

## Roadmap status

Contact lookup, patient follow-ups, and basic appointment operations are now implemented as described below. Administrator reopening of cancellations and no-shows is now implemented. Corrections to recorded attendance and financial records, and invoice reconciliation remain outstanding. Team acceptance of terminology, roles, and reporting conventions is still pending; continuing development does not imply that review occurred. No live service, deployment, remote push, or credential change is included.

## Second increment: patient follow-ups

The patient page now lists the newest 50 visible tasks linked to the patient's CRM contact and lets authorized staff create a follow-up or change its status. This reuses the existing Task model and contacts relationship. A title and due date are required; priority defaults to Medium. Creation assigns the task to the current practice membership and records the creating user. The endpoint does not send assignment emails or invoke a messaging service.

Existing task permissions are reused: organization administrators, the task creator, and task assignees can see and update a task. Creating a follow-up also requires the CRM's existing access to that contact. Contact search and direct patient/contact linking now apply the same contact-access rule, including restrictions within a practice, rather than relying only on organization membership. The patient journey's existing practice-level visibility is unchanged.

Tasks remain accessible under Existing CRM tools → Tasks. Status changes on either screen affect the same task. Follow-ups are operational reminders; completing one does not create appointment, consultation, treatment, payment, or attribution events. Existing Task due dates are calendar dates, and no new timestamp, reminder engine, or recurrence model was added. Task editing and assignment outside this patient interface use the existing Tasks workflow. That existing workflow can send assignment notifications according to its configuration; this increment does not change it.

To try it, open Alex Rivera in a fictional practice, find **Follow-up tasks**, enter a clearly labeled fictional task and a due date, and choose **Create follow-up**. Change it to **In Progress** or **Completed**, then open its linked Task page to see the same record. A saved task persists and remains separate from Growth totals. No existing task or financial record is replaced.

The third increment below adds appointment scheduling and rescheduling. Audited corrections and invoice reconciliation remain outstanding; these increments do not complete the entire daily-operations milestone.

## Validation

- Intake increment: 13 PostgreSQL tests passed, Svelte check had 0 errors/warnings, changed-route ESLint passed, Ruff and Django checks passed, and the real-HTTP smoke command confirmed both September revenue totals plus 14 cross-practice rejections and 10 authenticated route renders.
- Follow-up increment: 17 PostgreSQL tests passed, including Task reuse and self-assignment, completion/reopening, unchanged Growth, within-practice contact/task restrictions, forged fields, cross-practice requests, and PostgreSQL RLS. Existing journey, refund, attribution, and rerunnable-seed tests also passed. One existing Django email-settings deprecation warning remains.
- Intake browser checks covered existing-journey results, unsaved draft retention, selecting Taylor, and retaining selection after a rejected future timestamp. The demo seed added only the two new fictional contacts; no patient journey was created during those checks.
- Follow-up frontend: Svelte check passed with 0 errors and 0 warnings; changed patient routes passed ESLint. The final task-title/contact-label adjustment was checked with ESLint and inspected in the browser. Ruff checks and formatting passed for the patient app; `git diff --check` passed.
- Signed-in browser: created **DEMO - Follow-up workflow check** for Harbor's Alex Rivera, due October 5, 2026; marked it Completed; opened the same completed record in Tasks; returned to the patient view and inspected its layout. The task remains saved as fictional demo data. Alex's net collected remained $1,100. No patient communication was sent.
- At completion of the intake and follow-up increments, production build, container-restart persistence, load tests, and a full accessibility audit were not rerun. Those two increments added no migrations. Appointment validation is recorded separately below.
- Final real-HTTP verification after the saved follow-up: Harbor $1,100 and Cedar $700 net collected remained unchanged; all 14 cross-practice rejection checks and 10 authenticated route renders passed again.


## Third increment: appointment operations

From a patient journey, authorized staff can open **Appointments**, book a future visit, reschedule it, cancel it, or record attendance or a no-show. A required reason accompanies each change. The history records the actor, server timestamp, previous values, and new values. Closed appointments retain their history. The fourth increment below adds administrator reopening of cancellations and no-shows; attended outcomes remain closed.

The explicit project requirements are to preserve authentication, organization permissions and RLS, store booked/attended events, retain chronological activity, and keep revenue based on received payments and refunds. The following are implementation choices for this increment: a separate appointment record for the changing schedule, append-only change records, UTC times, patient-specific overlap prevention, revision checks against stale edits, and retry-safe booking using a request ID. Provider availability and a calendar view are outside this increment.

Two tables were necessary: **Appointment** stores the current scheduled time and outcome; **AppointmentChange** preserves changes without rewriting the journey's historical events. They reuse the existing Patient and organization models. Migration `patients.0003_appointments` installs both tables, forced PostgreSQL RLS, cross-practice link checks, immutable appointment identity, and an append-only audit constraint. The API checks existing contact access within the current practice. It rejects caller-selected patients/organizations in payloads. No existing authentication or permission model was replaced.

Booking creates one booked journey event at the server recording time. Rescheduling does not create another booked event. Cancellation and no-show retain the historical booking count; Growth counts distinct patients booked during its selected event-date window, not active appointments on the calendar. Attendance creates an attended event at its recording time and is rejected before the scheduled start. No-show is rejected before the scheduled end. Neither action creates treatment or collected revenue. Existing original-source attribution and receipt-date accounting remain unchanged.

The API is `/api/patients/{patient_id}/appointments/` (list/book) and `/api/patients/{patient_id}/appointments/{appointment_id}/` (detail/change). Lists are paginated at 20 appointments; history is chronological. Booking retries with the same request ID and values return the existing appointment. A reused ID with different values or an outdated revision returns a conflict. Patient-specific scheduled overlaps are rejected; adjacent appointments are allowed.

### Demo steps

1. Open http://localhost:5181/org and select **TEST - Harbor Spine & Ortho (fictional)**.
2. Open http://localhost:5181/patients/a29def23-7510-5894-9778-61392bbfe46f/appointments.
3. Inspect **DEMO - Appointment workflow check**. It was booked, rescheduled, then cancelled during verification. Its three history entries remain saved.
4. To try a new booking, enter a fictional title and future start/end times in UTC. Select the appointment, reschedule it with a reason, then cancel it. These actions save demonstration records.
5. Open Growth for September 1–30, 2026. The existing demo's collected revenue is still $1,100 for Harbor and $700 for Cedar. Additional bookings for an already-booked patient in that same window do not increase the distinct-patient booking total.

### Appointment validation

- All 22 patient-app PostgreSQL tests passed. After a small validation-message change, all five focused appointment tests passed again. Coverage includes booking retries, stale edits, overlap and adjacency, reschedule/cancel history, attendance/no-show time guards, unchanged revenue/treatment totals, membership/contact restrictions, forged payloads, cross-practice API requests, forced RLS, foreign-record links, and append-only audit protection. One existing Django email-settings deprecation warning remains.
- Svelte check: 0 errors and 0 warnings. Changed appointment and patient-detail routes passed ESLint. Patient-app Ruff checks and formatting passed. Migration drift check found no changes.
- Browser: booked a fictional appointment, verified early attendance was rejected, rescheduled it, cancelled it, and inspected version 3 plus the three chronological history entries. Desktop layout was visually inspected.
- A normal restart of all six Compose services preserved the fingerprints of every registered organization-scoped table in all three practices, including the saved appointment and its three change records. The original organization also matched its pre-migration fingerprints. Initial HTTP attempts during backend startup received connection refusals; allow the backend to finish its startup checks before opening the app.
- Post-restart real HTTP verification passed: Harbor $1,100 and Cedar $700 net collected; 14 existing cross-practice checks plus six appointment checks (including foreign appointment reads/writes); 12 authenticated frontend route renders. Browser reload also displayed the saved cancelled appointment, version 3, and all three history entries.
- Applying the migration left fingerprints of all preexisting organization-scoped tables unchanged in the original organization and both test practices.

### Remaining limitations

This is a basic patient appointment workflow, not a complete scheduling system. There is no provider/room capacity check, practice timezone configuration, calendar integration, reminder delivery, recurrence, or retrospective booking. Titles and locations cannot currently be edited after creation. Administrators can now reopen cancellations and no-shows as described below; recorded attendance cannot yet be corrected. Appointment change history is not paginated. Load/concurrent-request stress tests, a full accessibility audit, and a new production build were not performed for this increment. Team acceptance is still pending. Invoice reconciliation and broader audited corrections remain future milestone work. No live services, deployment, or remote push were performed.


## Fourth increment: reopen cancellations and no-shows

Practice administrators can now reopen a cancelled or no-show appointment recorded in error. They must provide a reason and valid future start/end times. The restored appointment becomes Scheduled; its version increases and an additional **Reopened** history entry records the actor, reason, old status/times and new status/times. Previous history remains unchanged. History is ordered by revision so changes with identical timestamps remain in the correct sequence. For a genuinely separate visit, create a new appointment instead.

This reuses Appointment and AppointmentChange, their forced RLS and append-only history constraint. No schema addition or migration was necessary. The existing nested PATCH endpoint accepts `action: reopened`, `revision`, `reason`, `starts_at`, and `ends_at`. The detail response supplies `can_reopen` for the UI, but the server independently enforces the administrator requirement. Existing patient/contact access and practice scoping still apply. Stale versions, forged fields, overlapping patient appointments, non-future times, empty reasons, and reopening Scheduled or Attended outcomes are rejected without changing records.

Preserving permissions, attribution, chronological records and collected-revenue accuracy are explicit project requirements. Administrator-only reopening and requiring a future slot are implementation choices for this increment. This is a deliberately limited correction workflow: it does not remove a historically recorded booking, reverse attendance, backdate visits, modify financial entries, or send reminders. Reopening adds no journey event, so it cannot duplicate booking counts or change collected revenue, treatment counts, or original attribution. Subsequent attendance creates the normal attended event.

### Try the correction workflow

1. Select **TEST - Harbor Spine & Ortho (fictional)** at http://localhost:5181/org as a practice administrator.
2. Open http://localhost:5181/patients/a29def23-7510-5894-9778-61392bbfe46f/appointments.
3. The saved **DEMO - Appointment workflow check** now has a Reopened entry and is Scheduled, version 4. Its original three history entries are still present.
4. To rehearse again, cancel the fictional appointment with a reason, then enter a future time and reason and choose **Reopen appointment**. This persists real changes to the fictional demo record.
5. Review the status transition and old/new times in Change history. Non-admin staff cannot perform this correction, even with a direct API request.

### Scope still outstanding

Recorded-attendance corrections need rules for superseding historical events and report dates; they are not implemented here. Financial corrections and invoice reconciliation also remain unfinished. No new production build, restart test, load/concurrency stress test, or full accessibility audit was performed for this increment. The third increment's persistence check remains historical evidence. No live services or remote publishing were used.


### Fourth-increment validation

- Eight focused PostgreSQL appointment tests passed after fixing equal-timestamp history ordering. The other 17 patient tests passed in the preceding regression run. New coverage includes admin-only reopening, required reasons/future times, overlap and stale-version rejection, forbidden foreign-patient links, unchanged Growth and booking-event counts, no-show → reopened → attended, and refusal to reverse attendance. The existing PostgreSQL RLS and immutable-history test also passed. The existing Django email-settings deprecation warning remains.
- Svelte check completed with 0 errors and 0 warnings. Ruff checks and formatting passed. No schema changed.
- Browser: reopened the saved fictional cancelled appointment, confirmed Scheduled/version 4, and inspected the new Reopened entry alongside all three previous entries. The demo remains saved for the team to inspect.
- An initial test invocation omitted the isolated database name and stopped at setup; rerunning with `DBNAME=mp_milestone` used the existing test database. A live smoke run was interrupted by the development server reloading the history-ordering edit; this was a transient verification interruption.
- Final live HTTP verification passed: Harbor $1,100 and Cedar $700 net collected; 14 journey isolation checks plus seven appointment isolation checks, including a forbidden foreign-appointment reopening; 12 authenticated frontend routes rendered successfully. The changed appointment page passed ESLint, and `git diff --check` passed.


## Fifth increment: patient billing review (read-only)

Administrators can open **Billing review** from a patient journey. The screen compares two separate sets of records: patient receipts (payments, refunds and net collected, in USD) and existing invoices linked to that patient's Contact. It does not match, allocate, import, alter, or duplicate money records. No schema migration was necessary: this reuses Invoice, Payment, Patient, Receipt, existing administrator permissions and Contact relationships.

The explicit requirements are to preserve practice permissions/RLS, preserve existing records, and keep received payments/refunds separate from invoice values. A read-only administrator review, all-recorded-dates scope, and currency-separated invoice summaries are implementation choices. This is the first part of invoice reconciliation, not a completed reconciliation workflow.

Billed totals include Sent, Viewed, Partially Paid, Overdue and Paid invoices. Draft, Pending and Cancelled invoices are listed but excluded from billed totals. Invoice payment entries are summed from Payment rows across all invoice statuses. Each currency remains separate; no currency conversion is attempted. The patient receipts panel remains USD under the existing milestone-one rule. The screen does not subtract patient receipts from invoices to imply a reconciled balance.

Invoice rows show their total, actual invoice Payment entry sum, stored paid and stored due values. A disagreement between Payment entry sums and stored paid is flagged for review without repairing records. These are invoice-ledger figures, not proof that a payment matches a patient receipt. Invoices are linked through the exact Contact within the current practice; names/emails are not used to infer relationships. The list is paginated at 20 rows, and currency totals cover all pages.

`GET /api/patients/{patient_id}/billing/` requires an active practice administrator and contact access. It explicitly scopes invoices, payments, receipts and patient to that practice. There are no write methods or caller-selected contact/invoice links. Unsupported writes return 405. Non-admin members receive 403; foreign patient URLs return 404. Existing billing pages remain accessible through each invoice link.

### Try it

1. Select **TEST - Harbor Spine & Ortho (fictional)** at http://localhost:5181/org.
2. Open http://localhost:5181/patients/a29def23-7510-5894-9778-61392bbfe46f/billing as a practice administrator.
3. Review USD 1,200 payments, USD 100 refunds and USD 1,100 net collected. The existing seed has no invoice linked to Alex, so that panel correctly shows an empty state. No invoices or money records were added for this browser check.
4. Existing invoices whose Bill To contact is this patient's exact Contact appear here automatically. Creating/editing invoices remains the existing CRM workflow; recording a payment there does not create a Growth receipt.

### Validation and remaining work

All 28 patient-app PostgreSQL tests passed, including three new billing tests for currency/status calculations, invoice-ledger mismatch detection, unchanged Growth and stored financial values, admin-only access, foreign-practice rejection, ignored scope-forging parameters, read-only methods, and pagination with all-page totals. Existing RLS and cross-practice relationship tests also passed. One existing Django email-settings deprecation warning remains. Ruff checks passed and migration drift check found no changes.

The signed-in desktop browser rendered the receipt totals and empty-invoice state correctly. Populated invoice calculations were exercised in the PostgreSQL test database; no populated invoice browser walkthrough was performed. No fresh production build, container restart, load test or full accessibility audit was performed for this increment.

Receipt-to-invoice matching/allocation, duplicate-payment resolution, reconciled patient balances, financial corrections and attendance corrections remain unfinished. This increment makes the existing records visible together without pretending these workflows are complete. Nothing was deployed. This billing review is included in the subsequent payment-matching GitHub update.

Final live HTTP check for the fifth increment: Harbor $1,100 and Cedar $700 net collected remained unchanged; 16 journey/billing isolation checks and seven appointment isolation checks passed; 14 authenticated pages rendered, including both billing-review pages. No successful writes were performed by this check.

Frontend validation: Svelte check completed with 0 errors and 0 warnings. Changed routes passed ESLint; a missing currency-list key warning was corrected and the page rechecked. `git diff --check` passed.


## Sixth increment: explicit payment matching

Administrators can match one existing patient payment receipt to one existing invoice payment for the same patient/contact and practice. Both must have the same USD amount; the invoice must be issued and not cancelled. A required reason records the evidence the administrator reviewed. Equal amounts do not prove identity: dates and references must be checked by the person recording the match. This is bookkeeping metadata; it never creates a receipt, payment, refund, or money transfer, changes original attribution, or adds invoice amounts to Growth.

The new `PaymentMatch` table is necessary to retain this relationship, actor, timestamp, reason and a snapshot of the original matching facts independently of the two ledgers. Both references are unique, preventing reuse of either side. Migration `0004_payment_matches` adds forced PostgreSQL RLS, database checks for equal USD amounts and same patient/practice, and an append-only constraint. PostgreSQL generates the snapshot from stored records. Existing records are preserved. Attempts to delete matched invoice payments return a conflict; the references are protected. Changed underlying facts are flagged as Needs review on the billing screen rather than silently repairing financial data.

The explicit requirements are tenant isolation, protected attribution and accurate collected revenue. One-to-one equal-amount matching, administrator-only access, USD-only scope and permanent match history are implementation choices. This is not complete allocation/reconciliation: refunds remain separate; split payments, currency conversion, match reversal/reassignment, and reconciled patient balances are unfinished. The UI shows the latest 100 eligible entries from each ledger and latest 100 matches, with total counts. Larger-history searching/pagination is not implemented. Matching does not verify bank settlement or prevent somebody recording duplicate money through the separate existing ledger workflows.

`POST /api/patients/{patient_id}/billing/matches/` accepts only receipt ID, invoice-payment ID and reason. Tenant/contact checks run on the server. Matching the same pair again is idempotent; trying to reuse either side for another match returns 409. Foreign or wrong-patient links are rejected. Receipt refunds are not eligible for matching. A refund recorded after a match reduces collected revenue normally and does not rewrite the original payment match.

### Fictional billing demo

After the base seed, optionally run `docker compose exec backend python manage.py seed_modern_practice_billing`. It adds one clearly fictional invoice, line item, account and invoice payment to each TEST practice for the existing Alex payment. It sends nothing, charges nothing, adds no patient receipt, and does not create matches automatically. Reruns leave existing records unchanged. Existing invoice records are reused through the established models/calculations. The invoice payment is a counterpart of the already-recorded fictional receipt; adding it does not increase Growth revenue.

Open the Harbor Alex billing review and choose the existing patient receipt and the invoice payment under **Match existing payments**. Check the amount, dates and references, enter a fictional demonstration reason, and confirm. The history retains the match while both eligible-choice counts decrease. This match is permanent in this increment; do not use real patient records for the demo.

### Validation

The 32-test PostgreSQL patient suite passed, including four matching tests for unchanged cash/Growth, retries, duplicates, permission checks, foreign links, amount/currency/status validation, refunds, drift detection, forced RLS and append-only history. After adding the demo command and payment-deletion protection test, all five matching tests passed. The latter verifies seed reruns preserve records and deleting a matched invoice payment returns 409. One existing Django email-settings deprecation warning remains.

Svelte check passed with 0 errors and 0 warnings; changed matching routes passed ESLint. Production build, load/concurrent-request stress tests and a full accessibility audit were not repeated. Attendance corrections and broader financial corrections remain separate unfinished work.

The live migration was confirmed applied. The fictional billing seed was run twice: first run added counterparts in both TEST practices; the second left them unchanged. In the signed-in browser, Harbor's USD 1,200 receipt was matched to TEST-HARBOR-MATCH after reviewing its reference/date/amount. The history showed one match, both unmatched counts became zero, and net collected stayed USD 1,100 after the existing USD 100 refund. Cedar remains available for an unmatched demonstration. No live charge or communication occurred. Matching persistence was verified by reloading the page; a further post-match container restart was not performed.

Final live HTTP verification after matching passed: both demo revenue totals unchanged; 22 journey/billing/matching isolation rejections plus seven appointment rejections; 14 authenticated pages rendered. The first expanded smoke run exposed an outdated expected-status list in the verification command; the expected list was corrected and the full live check passed. Django system checks and migration drift checks passed.


## Seventh increment: audited match reversal

Administrators can correct a mistaken payment match from Billing review → Correct this match. A required reason, administrator and timestamp are stored in a new `PaymentMatchReversal` record. The original match facts remain immutable. PostgreSQL validates the same-practice relationship, enforces append-only reversal history and atomically clears only the original match's active flag. Partial unique constraints keep at most one active match for each receipt and invoice payment. Existing matches start active; no financial rows are replaced.

The released records can be matched again using the existing equal-USD validation. That creates a new match entry, including when the same pair is selected again. Reversing an old match again returns its original reversal and never reverses a newer match. Reversal also works when the original matching facts have drifted; a subsequent match must meet current validation. Historical invoice-payment references stay protected from deletion.

Tenant isolation, accurate collected revenue and preservation of existing records are explicit requirements. Administrator-only two-step reversal then rematching, separate immutable correction evidence and retaining deletion protection for historical matches are implementation choices. Reversal is bookkeeping: it does not issue a refund, change either ledger, change attribution or change Growth. Reassignment is not an atomic swap; another administrator could match released records before the next action, so normal uniqueness checks still apply.

`POST /api/patients/{patient_id}/billing/reversals/` accepts only `match` and `reason`. Migration `0005_payment_match_reversals` adds the audit table, forced RLS and database guards. It is deliberately irreversible because dropping correction history would erase audit evidence. Normal application upgrades run it through the existing backend startup migration step. No services were connected or deployed.

### Verification

All 37 PostgreSQL patient tests passed, including four new tests covering reversal/retry/rematching, unchanged Growth/cash, retained history, administrator permissions, wrong-patient and foreign-practice links, strict inputs, forced RLS, direct database bypass attempts, transaction rollback and reassignment after drift. Ruff and migration drift checks passed; Django system check found no issues. Svelte check reported 0 errors and 0 warnings, and the changed billing routes passed ESLint. One existing Django email-settings deprecation warning remains.

The browser verified the Harbor fictional reversal and rematch: unmatched counts went from zero to one and back to zero, history now has one reversed match and one active match, and collections remained $1,200 received less $100 refunded = $1,100 net. Cedar remains available for a new matching demo. An initial browser attempt encountered a temporary backend connection failure during development reload; the completed walkthrough succeeded after service recovery.

Split allocations, refund reconciliation, reconciled balances and history beyond the latest 100 entries remain unfinished. No concurrent-request stress test or full accessibility audit was performed.

Restart persistence verified for the seventh increment: PostgreSQL, Redis, backend and both Celery services restarted normally, and hashes across 33 model/organization groups in all three organizations were identical. This includes the original organization, contacts, tasks, patients, journey events, receipts, invoices/payments, appointments/history, matches and reversals. No volume was removed.

Production build (`npm run build`) completed successfully, including the Node adapter. It reported an empty generated env chunk and slow plugin timings; no build error occurred. The post-restart HTTP check was initially attempted before backend startup completed, then rerun after readiness.

Final post-restart HTTP verification passed: 33 isolation rejections, 14 authenticated pages, unchanged revenue and identical demo snapshot hash. The frontend was also restarted after its successful build.


## Eighth increment: receipt and refund coverage

Billing review now partitions all patient payment receipts and their related refunds into valid active matches, no active match, and changed matches requiring review. A valid active match provides the existing link to an invoice; refunds follow the original receipt recorded in `Receipt.payment`. Each USD invoice shows linked gross payments, associated refunds and linked net collections. Reversed matches are excluded; a later match is counted once. A changed amount, reference, currency, status or other snapshotted matching fact moves that receipt and its refunds to Needs review rather than claiming a reliable invoice link.

No schema addition or new money record is needed. This read-only increment reuses Receipt, PaymentMatch, its reversal state, and Invoice/Payment. Explicit requirements are accurate collected revenue, tenant isolation and preservation of existing records. Deriving invoice coverage from valid existing matches and original refund relationships is an implementation choice. It is the first reconciliation reporting step, not an allocation editor or a completed balance workflow.

All three groups add back to patient collections. Totals cover all recorded dates, all receipts and all active matches, independent of the latest-100 history limit or invoice pagination. Non-USD invoice coverage is unavailable; no conversion occurs. These figures never issue a refund or invoice credit, update invoice paid/due values, or change Growth. The UI does not claim an amount owed. Split allocations, invoice credit adjustments, explicit refund reconciliation and final patient balances remain unfinished.

Validation: all 40 PostgreSQL patient tests passed, including three new tests for payment/refund partitioning, reversal/rematching, changed evidence, unchanged Growth, tenant/admin permissions, empty states, foreign currency, 101 matches and multi-page invoices. Ruff and migration drift checks passed; no migrations were generated. Svelte check had 0 errors and 0 warnings; changed-route ESLint passed. Live verification reconciled both practices' receipt groups and invoice links with net collections, rejected 33 cross-practice requests and rendered 14 authenticated pages. One existing Django email-settings deprecation warning remains. No fresh production build, container restart, load/concurrency test or full accessibility audit was run for this read-only increment; the previous increment's build/restart evidence remains historical.

Browser verification for the eighth increment succeeded on October 4 after local sign-in: Harbor showed $1,200 linked payments, $100 related refunds and $1,100 linked net collections at both patient and invoice level, with zero unmatched/changed amounts. Existing reversed and active history remained visible. No financial records were written during this check.


## Ninth increment: audited internal charge credits

An administrator can record a charge reduction against an issued USD invoice from Patient → Billing review → Linked invoices → Record charge credit. The amount must be positive, have at most two decimal places, and fit within the original invoice total less active credits. A reason is required. A UUID request identifier prevents duplicate submission; reuse for different details is rejected. Corrections record a full reversal with its own reason, actor and timestamp. Partial credit reversals are not implemented; reverse then record the corrected amount.

The new `InvoiceCreditAdjustment` table is needed because the existing invoice models have no separate credit audit ledger. It retains patient/invoice relationships, amount, actor, reason, request ID and a database-generated invoice snapshot. Reversals reference the original record. Migration `0006_invoice_credit_adjustments` enables forced RLS, enforces practice/patient/invoice consistency, serializes credit writes on the invoice, rejects excess cumulative credits and prohibits updates/deletes. It is deliberately irreversible to preserve audit history. Existing invoices, receipts, payments, matches, attribution and organizations are preserved.

Explicit requirements are tenant isolation, accurate collected revenue and preservation of records. Administrator-only USD credits, separate internal adjustments, full reversal and per-invoice adjusted billed values are implementation choices. These entries do not issue/send a credit-note document, change legacy invoice total/paid/due/status, create a cash refund, or alter Growth. The original invoice ledger remains visible. Adjusted billed value means original billed value less active charge credits; it is not a patient balance and does not subtract payments or determine a refund due. Invoice lists/exports outside this Modern Practice billing review do not include these internal credits yet.

Changed invoice total/contact/number/currency or an ineligible status causes active credit review warnings and hides adjusted billed value. New credits are blocked until the conflicting active credits are reversed. Reversal remains possible after invoice changes within the practice. History shows the latest 100 entries with a total count; calculations use all credit records. Credits do not automatically associate with refunds. Split allocations, invoice-credit documents and final reconciled balances remain unfinished.

APIs: `POST /api/patients/{patient_id}/billing/credits/` accepts only invoice, amount, reason and request_id; `POST /api/patients/{patient_id}/billing/credit-reversals/` accepts only credit, reason and request_id. Current patient/contact permissions and administrator role are checked before writes. Both endpoints are practice-scoped; no scope supplied by a caller is trusted.

Validation: all 45 PostgreSQL patient tests passed, including five new credit tests for calculations, retries, reversals, input/amount/status/currency rules, changed invoices, unchanged original financial records/Growth, tenant/admin checks, database RLS/relationship/immutability/cap enforcement, rollback, snapshot generation, and 101-entry totals. Ruff, migration drift and Django system checks passed. Svelte check reported 0 errors and 0 warnings; billing-route ESLint passed. The existing Django email-settings deprecation warning remains. A fresh production build, concurrent-request stress test and full accessibility audit were not performed for this increment.


Browser verification on October 4 completed a fictional USD 100 credit and full reversal in Harbor: adjusted billed value changed from USD 1,100 back to USD 1,200; both audit entries remain. Original invoice fields and USD 1,100 net collections stayed unchanged. The initial reversal form interaction occurred before hydration finished; reopening the form after rendering completed succeeded. Live verification rejected 40 cross-practice requests (22 journey/matching, 4 match reversal, 7 credit, 7 appointment) and rendered 14 authenticated pages; Harbor/Cedar net collections remained USD 1,100/USD 700.

Normal PostgreSQL and backend container restart preserved identical hashes/counts across 81 model/organization groups, including both credit audit entries. No volumes were removed. An initial HTTP check ran before Django was listening; the post-readiness rerun passed all 40 isolation checks and 14 authenticated pages, with unchanged revenue and demo snapshot hash. Browser reload also retained both audit entries and the restored USD 1,200 adjusted billed value.
