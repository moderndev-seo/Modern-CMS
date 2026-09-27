# Milestone 2 — Demo and workflow validation

Milestone 2 is the proposed demo-validation phase of the roadmap. It does not introduce daily-operations modules or change the business rules established in milestone 1. Team acceptance remains pending: automated checks cannot confirm that doctors and practice staff find the workflow appropriate.

## Delivered

- Signed-in browser walkthrough of Patients, Alex Rivera's chronological journey, and Growth.
- Refund selection shows the remaining refundable balance after linked refunds. Fully refunded payments are unavailable; backend validation remains authoritative.
- Existing-contact mode and the entered contact ID survive a rejected patient submission.
- Invalid reporting ranges show a recoverable error with editable dates, instead of replacing the dashboard with an error page. No zero-valued report is fabricated.
- Marketing spend defaults to a date no later than today, even when the report ends in the future.
- Negative ROAS no longer receives positive green styling; keyboard focus and long-text wrapping improved.
- Google sign-in is hidden when the required frontend OAuth configuration is absent. Existing magic-link authentication and configured Google authentication remain in place.

These are implementation choices informed by the walkthrough, not additional requirements claimed from the reference PDFs. No schema additions were needed. Authentication, organization authorization, PostgreSQL policies, source immutability, and backend financial calculations were not changed.

## Five-minute team demonstration

Start Docker Desktop, then run `docker compose up -d` from the project directory. Open http://localhost:5181/org using your existing signed-in browser. Select **TEST - Harbor Spine & Ortho (fictional)**. If the session has expired, use http://localhost:5181/login; the current local console-email setup requires retrieving the generated magic link from backend/worker logs. It does not deliver an email to an inbox.

1. Open http://localhost:5181/patients. Explain that these are fictional records in an isolated test practice.
2. Open Alex Rivera. Show Google Ads as the preserved original source, the later Email touch, and the booked → attended → consultation → treatment events.
3. Show $1,200 received minus $100 refunded = **$1,100 net collected**. Open Refund issued to see **$1,100 refundable**; do not submit during the read-only rehearsal.
4. Open http://localhost:5181/growth?start=2026-09-01&end=2026-09-30. Expect **3 leads, 2 booked patients, 1 treated patient, $1,100 net collected**. Google Ads has **$200 spend and 5.50× ROAS**. Unknown attribution remains visible; overall ROAS is unavailable because applicable spend is missing.
5. Use Switch practice at http://localhost:5181/org, select **TEST - Cedar Family Dental (fictional)**, and reopen the same Growth URL. Expect **$700 net collected and 3.50× Google Ads ROAS**, with the same 3/2/1 counts.
6. Explain that Billing is the existing invoice feature, separate from actual collections. Messages and Reviews are explicitly planned modules.

These expected figures assume the seeded September records have not subsequently been changed or supplemented. Demo writes are persistent. Rerunning the seed command preserves existing records; it does not reset the demonstration.

## Team decisions before daily-operations work

- Do the event names match staff language, and who records each event?
- Is the current administrator-only permission for payments, refunds, and spend appropriate?
- Who owns correcting an incorrectly entered receipt or original attribution? An audited correction workflow is still needed.
- Confirm activity-date reporting and first-touch attribution as the initial business convention. This is not a conversion-cohort report, clinical outcome measure, or proof of incremental advertising impact.
- Prioritize contact search/duplicate prevention, appointment operations, follow-up tasks, and invoice reconciliation for milestone 3.

## Limitations and boundaries

This remains a local proof of concept. Marketing capture, appointment events, payments, refunds, and spend are manually entered; no live advertising, messaging, review, or payment services are connected. USD and UTC are fixed. Partial spend completeness is not automatically detected. Records are append-only without audited corrections; no appointment scheduling/rescheduling engine or patient identity matching was added. New contacts can still be duplicated by identity; the existing-contact route currently requires a contact ID. Successful form submissions use normal page navigation; an event submission can be repeated by a user. Payment references prevent duplicate receipt references within a practice.

Doctor/staff usability acceptance, production security/compliance review, backup/restore drills, performance/load testing, and production deployment remain outstanding. Browser checks in this phase do not replace the earlier direct-API and PostgreSQL isolation tests. Closing the browser does not erase records, but Docker must be running to reopen the application. Do not delete Docker volumes.

The GitHub handoff remains separate and unfinished; these changes have not been pushed. Internal reference PDFs and decks must stay out of the public repository.

## Verification performed on September 27, 2026

- Focused Vitest calculation checks: 2 passed (linked partial refunds, cent precision, fully refunded payments, empty receipts).
- `npm run check`: 0 errors, 0 warnings.
- `verify_modern_practice --member-email admin@localhost --frontend-url http://frontend:5181`: both demo totals matched; 14 direct HTTP isolation checks and 10 authenticated route renders passed. No successful patient writes were performed.
- Interactive browser: existing sign-in and Harbor practice selection, patient list and Alex's complete timeline, refund balance, duplicate-contact rejection with form-mode retention, invalid report range recovery, desktop Growth and a 390-pixel responsive inspection.
- `git diff --check`: passed. All six containers remained running, PostgreSQL and Redis healthy.
- No new migration, production build, container-restart persistence test, full PostgreSQL suite, or real-device accessibility audit was run for this frontend-only increment. Milestone 1 documents the earlier database isolation and restart results; they are not represented as newly rerun here.
- `npm run lint`: formatting passed; ESLint reported 0 errors and 8 pre-existing warnings in untouched routes.
