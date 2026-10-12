# Messages and Reviews — team acceptance walkthrough

Status: **human acceptance pending**. This checklist helps the practice owner and staff assess the local workflows; automated checks do not count as their approval. Use fictional TEST practices only. Successful saves create retained history, so use a dedicated fictional conversation/review for editing exercises. Do not reset existing examples to make the checklist pass.

## Open the current build

Start the existing Docker stack with `docker compose up -d`, sign in at http://localhost:5181/login and choose a TEST practice at http://localhost:5181/org. Setup and rerunnable demo commands are in [team setup](team-setup.md). Keep this browser session open for the checks below.

## Messages

1. Open http://localhost:5181/messages and the fictional treatment follow-up conversation. Confirm the TEST label, patient link, saved draft and local-only explanation are clear.
2. Edit the draft or append a template. The page should say **Unsaved draft**. Click Messages or Switch practice, then Cancel: the text must remain. Repeat and choose OK to discard: navigation should complete. Reopen the conversation and confirm its saved draft is unchanged.
3. Edit a draft, then attempt another valid form submission on the page (such as a status change). Cancel the discard prompt: neither action should be submitted. Restoring the exact saved draft text removes the unsaved indicator. Save local draft intentionally when ready; reload and inspect history.
4. On a separate fictional conversation, add a manual entry, assign a staff owner, set Waiting, create a follow-up task, resolve and reopen. Confirm these actions do not send a message or grant patient access to the owner.

## Reviews

1. Open http://localhost:5181/reviews?start=2026-09-01&end=2026-09-30. Before any edits, Harbor has average 3.5 and Cedar 2.5: each has two rated and one unrated review. Unknown source remains visible. Provider cards without ratings say Not available.
2. Filter the list by source/status/text. Summary totals should still cover all accessible non-archived records in the selected review-date period; list filters do not remove low ratings from the summary.
3. Search a fictional patient or open Local reviews from their journey. Record a new fictional review with either a known rating or text. Missing rating/source must remain missing/Unknown. Review facts are immutable; correction uses archive with a reason and a replacement.
4. On the new record, repeat the unsaved-draft navigation/cancel/discard exercise above. Save a draft intentionally, reload, and inspect the retained revision. Set In progress or Handled locally with a reason, then archive and restore. The summary should exclude/include that record accordingly. No action changes a public review site.
5. Create a follow-up task and locate it in Tasks/Messages. Review status and task completion remain separate actions.

## Practice boundaries and reporting

Switch to the other TEST practice. Its patient conversations/reviews must be separate. Attempting a bookmarked detail URL from the first practice must show unavailable/not found. Staff visibility follows existing patient/contact permissions. Backend tests also cover direct foreign-record links and writes; this walkthrough is not a replacement for those tests.

Open http://localhost:5181/growth?start=2026-09-01&end=2026-09-30. Editing messages/reviews must not change original marketing attribution or collections. The unchanged base examples are Harbor USD 1,100 and Cedar USD 700; later legitimate financial demo edits can change these values.

## Limits to acknowledge

Warnings protect local drafts while JavaScript is running. They do not save text, protect other unsaved form fields, guarantee a warning on browser/OS crashes or every mobile tab closure, or add an editing lock. Browsers control reload/close warning text. There is no browser-storage draft copy. Shared-draft conflicts remain protected by server revisions.

No message transport, inbox sync, review invitations, provider synchronization, public reply posting, reminders or portal. No production deployment or live integrations. Accessibility/load/security/compliance and backup/restore acceptance remain separate work. See [Messages](milestone-four.md) and [Reviews](milestone-five.md) for complete workflow limitations.

## Record the decision

Record only fictional examples in the public repository. Keep confidential observations in the team's private system.

- Reviewer and role:
- Date and Git commit:
- TEST practice and workflow checked:
- Passed steps:
- Failed steps, reproduction and expected result:
- Decision: pending / accepted for local demonstration / changes needed
- Follow-up owner and target date:

Acceptance for a local demonstration is not approval for live patient use or external connections.
