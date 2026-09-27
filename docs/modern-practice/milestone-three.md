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
