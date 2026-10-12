# Milestone 4 — local Messages and patient follow-ups

## Scope and design choices

The owner authorized continuing into Messages after the essential Milestone 3 workflows. Standing requirements preserve authentication, patient permissions, forced PostgreSQL RLS, existing records and ports 5181/8000; no live messaging service is authorized. Both local reference PDFs were readable when this increment began. The CRM PDF informs the dark navigation, pale workspace, white panels and magenta actions. The attribution deck requires an intact patient-to-collected-revenue journey; it does not specify a detailed messaging workflow.

Conversation statuses, staff ownership, plain-text templates, shared local drafts and a task queue are implementation choices for the first usable Messages workflow. They are not claimed as explicit PDF requirements. Existing Contact/Patient identity and Task follow-ups are reused. Existing EmailMessage records depend on a mailbox and delivery metadata, so separate local-only models avoid representing a saved draft as an actual sent or received message.

Migration `0014_local_messages` adds four practice-scoped tables: LocalConversation, LocalMessage, ConversationChange and LocalMessageTemplate. All have forced RLS. Database triggers enforce same-practice links, append-only entries/change history and revision-controlled conversation updates. No existing patient, receipt, invoice or attribution schema is changed.

## What the team can do

- Open **Messages**, filter open/waiting/resolved conversations and all/mine/unassigned ownership, or search patient names and subjects. Counts cover accessible conversations across all dates (and the selected patient, if any). Lists have finite pages.
- Start a patient-linked conversation from a name search or **Local messages** on the patient journey. Subject and patient link are fixed after creation.
- Record an internal note, manually logged incoming message or manually logged outgoing message, with an actual UTC event time and recording actor. These entries are staff reports, not evidence of delivery. Corrections require a clarifying entry.
- Save/clear a shared local draft, optionally appending a plain-text practice template. Draft revisions retain before/after text. Concurrent/stale changes are rejected; exact retried requests do not duplicate records.
- Assign an active member who already has access to the patient; choose open, waiting or resolved. Reopen before adding entries/editing drafts. Ownership never grants contact access.
- Create a patient follow-up using the existing Task workflow. The queue shows accessible unfinished patient tasks, due today/overdue in UTC or all unfinished tasks. Conversation filters do not filter the practice-wide task queue. No reminders are sent.
- Administrators add, archive or reactivate templates. Text is immutable: create a replacement to revise wording. Archived text already inserted into drafts remains unchanged.

## Setup and demonstration

After the usual installation and base seed with an existing demo member:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_modern_practice_messages
```

This seed requires the two exact fictional TEST practices, their existing Alex patients and an active administrator in each. It does not create accounts, grant access or change patient/financial records. Each practice gets one explicitly labeled fictional conversation, one incoming manual entry, one saved draft and one template. Rerunning preserves staff edits and archived templates.

1. Open http://localhost:5181/messages and select a TEST practice in the practice switcher.
2. Open **TEST - Fictional treatment follow-up**; review its manually recorded entry and local draft.
3. Append a template, personalize and save a local draft. Refresh and inspect change history.
4. Assign yourself, set Waiting, then create a dated follow-up. Review it in Messages/Tasks.
5. Resolve and reopen the conversation. Switch to the other TEST practice: its conversation is separate.
6. Review http://localhost:5181/growth?start=2026-09-01&end=2026-09-30. Messages do not alter patient attribution or cash totals.

Use fictional text only. Successful editing tests run in an isolated test database; browser smoke checks of the saved demo can be read-only. Team acceptance requires a human reviewer/date/findings/decision; automated tests do not supply that decision.

## Limits and proposed next work

No email/SMS inbox synchronization, sending, delivery/read receipts, automatic reminders, attachments, patient portal or live providers. Manual outgoing logs do not send anything. There are no template variables or automatic personalization. There is one shared draft per conversation; drafts are visible to authorized patient staff and previous text remains in history. There is no automatic save, editing lock or full-text history search. Choosing a page/navigation can discard unsaved text. Ownership is an operational label, not a security boundary or subscription.

Conversation entries and subjects cannot be edited/deleted through this workflow; add a clarification or start another conversation. Templates have revision checks for active state but no separate historical archive/reactivate event list. Follow-ups retain existing Task semantics and are patient-linked, not a conversation-specific task model. Appointment scheduling, finances and Growth are unchanged. This is not a claim of healthcare compliance, production readiness, scalability or team acceptance.

Next: team walkthrough of this local Messages workflow and any concrete fixes, then scope Milestone 5 local review tracking. Later proposed work is pilot readiness/security/backup validation, followed only by separately authorized integrations and deployment.
