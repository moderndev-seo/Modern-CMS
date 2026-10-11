# Milestone 3 — essential workflow acceptance

October 11, 2026. The owner requested completion of essential workflows while deferring additional scheduling enhancements. The implementation boundary below is an engineering choice for that request, not a claim that every item previously discussed was an explicit requirement. Team acceptance is pending; do not mark these boxes complete merely because automated tests pass.

## Essential boundary

The daily workflow is: find/reuse a patient contact → follow-up → book/change an appointment → record or correct its outcome → review receipts/refunds independently of invoices → match/reverse evidence and allocate cash → explain refunds and internal credits → see a guarded recorded balance → correct entry mistakes without deleting history → review/export the recorded financial position.

Implemented correction scope: positive cash amounts, references and dates; simple equal-amount duplicate payments without refunds; closed appointment attendance/no-show/cancellation outcomes. Complex duplicate cases and legacy ledger cleanup remain deliberately blocked rather than guessed.

## Start and read-only walkthrough

1. Follow [team setup](team-setup.md). On an existing installation, keep its environment and database volumes. Open http://localhost:5181/login and choose a TEST practice at http://localhost:5181/org.
2. Open http://localhost:5181/patients. Choose Alex Rivera. Check original source, separate subsequent touch, appointment/treatment events, receipts/refunds and chronological history.
3. Open http://localhost:5181/growth?start=2026-09-01&end=2026-09-30. Base demo net cash is Harbor USD 1,100 and Cedar USD 700. Unknown and unavailable ROAS must remain explicit. Additional manual records may change counts; never reset them to fit the example.
4. Open Patient → Billing review → Internal statement and CSV. Compare net collections with Growth, adjusted charges with internal credit history, and balances with allocations. Download the CSV. An unavailable balance must be blank, never zero. Credits are not cash refunds.
5. In the owner's saved Harbor example, adjusted billed is USD 1,600, allocated net cash USD 1,100 and recorded balance USD 500. Saved Cedar remains unmatched/unallocated and correctly shows unavailable balances. These manual allocations/matches are not reproduced by a fresh clone or base seed.
6. Inspect Correct recorded cash details and Review duplicate payments without submitting changes to shared demo finances. Review prerequisite messages. For histories over 100 records, use the named page controls; totals do not change with pages. Invoice allocation and retained-payment choosers include all linked candidates. Save work before navigating pages.

## Disposable fictional workflow rehearsal

Use a teammate's local database and a new fictional patient in a TEST practice. These actions leave permanent audit records. Do not use real patient data or modify an existing shared demonstration just to satisfy this checklist. No live services are needed.

- [ ] Reuse a contact, create/complete a follow-up, book an appointment, reschedule and cancel it. Administrator reopening requires a future slot and a reason.
- [ ] After the scheduled time, record attendance; as an administrator correct it to no-show (after the end) or cancellation, then restore attendance if appropriate. The original event stays visible as superseded. Exactly the latest valid attendance marks progress. Booking counts, treatment and cash stay unchanged. A separately entered manual attendance event remains independent.
- [ ] Record consultation, completed treatment, payment and a linked refund. Later marketing touches must not overwrite original attribution.
- [ ] Review billing; match only equal USD records representing the same payment. Reverse mistaken evidence before rematching. Allocate net cash and explain refunds; keep unavailable balances unavailable until every blocker is resolved.
- [ ] Create an internal charge credit with a reason and reverse it. Verify adjusted billed values and the internal statement/CSV, while original invoice documents, stored paid/due and cash remain unchanged.
- [ ] Correct a payment/refund amount, reference and date separately, with reasons. First reverse the parent payment's match and clear its allocation plan. A refund cannot precede its payment; dates cannot be future dates. Moving a date across a month boundary moves cash between those UTC reports without changing lifetime collections or source. Restore a previous value through a new correction.
- [ ] For a separately created simple fictional duplicate, select the included equal-amount payment to retain, exclude the duplicate and restore it. Both records/history remain; no money moves. Refunded duplicates and duplicate refunds are unsupported.
- [ ] Review the whole journey and export. A second practice must not see or link these records. Administrators can correct financial records/outcomes; ordinary members cannot gain those actions by making direct API requests.
- [ ] Restart normally with `docker compose restart db backend frontend`, wait for readiness, sign back in and confirm the saved records/history persist. Never remove volumes.

## Acceptance record

Reviewer, date, practice, observations, issues and decision: **not yet recorded**. Confirm the workflow fits front-desk, practice-manager and financial-review needs. Record defects as follow-up work before accepting Milestone 3. Do not infer team approval from the developer's tests.

## Deferred or limited

- Refunded/complex duplicate resolution, duplicate refunds, separate legacy invoice-payment cleanup, many-to-many legacy matching and patient reassignment. Keep unsupported cases blocked and balances unavailable where required.
- Issued credit-note/PDF documents and legacy invoice-export integration. The new CSV is an internal review with credits, cash and audit evidence, not a replacement legal invoice/credit note.
- Provider/room capacity, practice timezones, recurring visits, waitlists, calendar connections and reminders. Scheduling stays UTC and checks patient conflicts only.
- Financial page search, large-data performance and load testing. Pages expose older histories; some all-record calculations and choosers still load full collections. Allocation plans retain the 20-invoice / 100-refund-line limits.
- Full screen-reader, zoom/contrast and assistive-technology acceptance, broader concurrency/load testing, backup/recovery operations, production/security/privacy/compliance readiness, and human financial acceptance.
- Messages, Reviews and live advertising/messaging/review/payment integrations require separate scope and authorization. Nothing here deploys the app or verifies bank settlement/insurance responsibility.
