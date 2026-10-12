# Milestone 5 — local review tracking

## Scope and model choices

The owner continued after the proposed local Reviews module. Standing requirements preserve authentication, patient/contact permissions, forced PostgreSQL RLS, original organizations/records and ports 5181/8000. No review provider or messaging connection is authorized.

Both reference PDFs were readable. The CRM PDF supplies the Reviews visual direction: an overall rating/distribution, source cards, recent reviews and follow-up actions. Its mockup includes connected requests/public replies and automation; those are not implemented or implied by this local milestone. The attribution deck remains the business-workflow reference, not a detailed specification for review management.

This increment implements manually entered review records, honest rating summaries, shared reply drafts, local statuses and existing Task follow-ups. These are implementation choices for a useful local first increment. It reuses Contact/Patient identity and permissions. The inherited CsatSurvey model represents emailed ticket surveys with tokens/expiry; using it here would falsely imply a survey was sent. Migration `0015_local_reviews` instead adds PracticeReview and ReviewChange, both practice-scoped with forced RLS, same-practice link validation and database-protected immutable facts/audit history.

## Working flow

1. Open http://localhost:5181/reviews and select a TEST practice. The default date range is the last 30 UTC days, inclusive of today. For stable demonstration results use http://localhost:5181/reviews?start=2026-09-01&end=2026-09-30.
2. Search a patient name (at least two characters) or use **Local reviews** on a patient journey. Enter known review facts: source, actual UTC review date, optional 1–5 star rating and optional text. At least a rating or text is required. Unknown source and missing rating remain explicit. Patient association is an internal staff link; authorship is not verified.
3. Open a review, save an internal reply draft and choose Needs attention, In progress or Handled locally with a reason. No reply is generated, sent or published. Handled locally is an internal status, not confirmation of a public response.
4. Create an existing patient Task for the next step. It is assigned to the current staff member. Review status does not complete the Task and no reminder is sent. Review tasks appear in Tasks and the existing Messages patient follow-up queue according to Task permissions.
5. Archive a mistaken/duplicate local entry with a reason, then record a replacement if needed. Archiving affects only this local record; it never removes an external review. Restore by selecting a non-archived status and recording a reason. Original facts, statuses and draft versions remain in history.

Review facts (patient/source/rating/text/date) are immutable in this workflow. Draft and status changes use a shared revision; stale or competing writes are rejected. Retried create/change requests do not duplicate records. Archived drafts cannot be edited until restored. Saving an empty draft clears its current text while preserving earlier versions.

## Summary definitions

The summary includes accessible, non-archived records whose **review date** falls from the start date at 00:00 UTC through, but not including, 00:00 UTC the day after the end date. It optionally narrows to the selected patient. List-only status/source/text filters and pagination do not change summary totals. All ratings, including low ratings, contribute equally; no sentiment-based routing is implemented.

Count is all included records; rated count is records with a known 1–5 rating; unrated count is the remainder. Average is the arithmetic mean of known ratings, displayed to one decimal. No ratings means unavailable, not zero. The histogram counts each known star rating. Source summaries follow the same rules. Needs attention counts Needs attention and In progress records. Archived records are excluded from all summary counts/averages in their original review period; restoring includes them again. These are **manual record statistics**, not verified ratings from Google, Healthgrades, Yelp or another provider. No invitation count, response rate or provider total is inferred. Review source never changes marketing attribution, Growth or revenue.

## Demo setup

After the normal base seed with an active demo administrator in both TEST practices:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_modern_practice_reviews
```

The command requires the exact existing fictional TEST practice names and patients. It grants no access, contacts no providers and preserves all existing facts/edits/statuses when rerun. It adds three explicitly fictional reviews and one local draft revision per practice. September 2026 examples: Harbor has ratings 5 and 2 plus an unrated Unknown-source record (average 3.5); Cedar has ratings 4 and 1 plus an unrated Unknown-source record (average 2.5). Existing patient, appointment, message, financial and attribution records are untouched. These examples are not real provider reviews.

## Remaining work and acceptance

No provider synchronization, review invitations, invitation consent/preferences, delivery tracking, response-rate measurement, automated reminders, public reply posting, private feedback form, automated reply/privacy screening, attachments or portal. No unlinked/anonymous review record: this first workflow requires an existing patient association. No external review ID or automatic duplicate detection; request IDs prevent request retries, not two separately entered copies. Staff must verify facts and use local archive/replacement for mistakes. Archival is not deletion and does not remove public feedback.

One shared draft per review; no automatic save or editing lock. Prior draft text is retained, and confirming navigation discards unsaved text; the guard below now asks first. Existing Task behavior/permissions apply. No full accessibility or load acceptance, healthcare compliance/security audit, private backup/restore drill or human team acceptance is implied.

Next: team walkthrough and concrete fixes; then explicitly scope review-request preparation and preferences if needed before pilot readiness. Sending, external connections and deployment require separate authorization. Human acceptance needs a reviewer/date/findings/decision and remains pending for this workflow and the earlier milestones.

## Draft navigation protection

Messages and Reviews now warn before navigating away or submitting another form while their local draft differs from the saved text. Cancel keeps the edit; OK discards it. Saving the draft remains available. Reload/close prompts use browser-controlled wording and are not guaranteed on every device or crash. No autosave, browser storage, protection for other form fields or editing lock was added. See the [team acceptance walkthrough](messages-reviews-acceptance.md); human acceptance remains pending.
