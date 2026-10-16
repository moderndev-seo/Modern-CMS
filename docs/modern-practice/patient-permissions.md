# Patient permissions after audit remediation

This is an intentional tightening of authorization. Organization membership and existing sales/marketing flags no longer grant patient information by themselves. Existing administrators keep their workflows. The migration adds three Profile booleans, default false; it does not promote existing regular members, alter contact sharing or rewrite patient records.

| Capability | Regular member requirement | Administrator |
| --- | --- | --- |
| Identifiable patient reads, contact lookup, local Messages/Reviews and follow-up work | `has_patient_access` **and** existing contact creator/assignment/account-sharing permission; existing task permissions also apply | Existing practice-wide authority |
| Patient intake, journey touches/outcomes, booking and appointment changes | Above plus `can_record_patient_outcomes` | Allowed; existing outcome correction/reopening rules retained |
| Receipt/refund reading and financial fields on patient detail | Above plus `has_patient_finance_access` | Allowed |
| Receipt writes, financial correction/reconciliation, billing review and statement exports | Administrator only | Existing safeguards still apply |
| Growth aggregates | `has_marketing_access` | Allowed |
| Marketing spend writes | Administrator only | Allowed |

Read-only patient staff can still work local conversations/reviews/follow-ups where contact/task rules allow; these are not treatment outcome writes. Separate fine-grained messaging roles are deferred. Aggregate access is a deliberate grant to trusted staff, not public anonymization; no small-cell suppression is implemented.

An active practice administrator may grant these booleans to **another** member through the existing user-management API (`CreateProfileSerializer`, the same privilege-grant checks as role). Self-edit endpoints cannot grant them, and a PAT cannot manage credentials or privileged user administration. There is no new role-management screen in this remediation. Use an authenticated administrator session and the documented user API; review every grant and contact assignment before permitting real data. Revoking patient access also makes the outcome/finance flags ineffective. The booleans never grant access across organizations.

## Response and compatibility changes

Patient lists include only visible contacts. A same-practice restricted detail/event request is denied, and foreign-practice IDs remain not found. Contact linking uses the same visibility queryset. Receipt endpoints enforce finance access independently. Patient detail omits `receipts`, `corrections`, `exclusions` and `net_revenue` when finance access is absent; it returns explicit `can_read_finance` and `can_record_outcomes` flags. The web journey shows Restricted, not a fabricated zero.

Contact lists/details, global contact search and nested contact serializers protect patient-linked identities. Patient-linked task access requires visibility of its protected contacts. Patient-linked invoice/estimate/recurring document access additionally requires financial read and contact access; financial writes remain administrator-only. Unrelated CRM records retain their existing rules. Nested patient contacts without a verified serializer profile fail closed with a restricted placeholder.

This does not inspect arbitrary text copied into unrelated legacy CRM notes, imported files or existing exports. Administrators must not distribute patient information through those unrelated resources. Read/export logging, data inventory/classification, broader privacy controls and operational review remain necessary before production.

## Credentials

JWT requests use the same capability/object rules. A PAT needs an **explicit** `patients:read` scope to access patient information, including patient-linked shared contacts and financial records, and `patients:write` for writes to either patient APIs or patient-linked shared records. Both are needed for patient write workflows that first open the patient. Token scopes are a ceiling, never an additional staff grant. Existing empty scope lists and `*:read`/`*:write` do not include the patient resource implicitly. Legacy CRM-only credentials must be reviewed and reissued with deliberate scopes if patient access is intended.

Organization keys select an arbitrary admin and therefore never acquire patient authority. They cannot reach the patient resource or open patient-linked contacts, tasks or financial documents. They retain legacy non-patient read behavior. Sandbox attribution intake remains JWT-only and administrator-only; explicit PAT scopes do not unlock it. None of these credentials is approved for website JavaScript or live integration intake.

## Safe adoption

Review the remediation PR diff and the [remediation report](post-audit-remediation.md). Run both test partitions, migration drift, lint/format, frontend and strict docs checks. After approval, apply the normal additive migrations using the existing restricted application role and review regular staff grants. Keep existing backups and database volumes. The separate remediation checkout does not change the currently running app; port 5181 continues to display the previous published code until this work is deliberately adopted. Do not run a second Compose stack on the same ports.

## Practice roles and shared records

Recommended grants are deployment choices, not automatic role presets. Clinical staff normally receive patient and outcome access; finance readers receive patient and finance access; agency analysts receive marketing access only. Contact assignment/sharing is still required for every regular member. Administrators retain practice-wide access. Finance readers cannot enter cash, reconcile billing or export internal statements; those operations remain administrator-only.

Patient-linked cases and tasks require access to every linked patient contact. Patient-linked leads and opportunities additionally require finance access because their bodies expose proposed amounts. Their existing creator/assignment edit rules still apply; proposed sales values never become collected revenue. Lists, details, deletion, nested serializers and profile comment history use these restrictions. Generic comment/attachment mutation routes inspect the actual parent record, including when its ID is submitted through another CRM module. Revocation takes effect on subsequent requests; it cannot retract information already viewed or downloaded.

## Administrative API procedure

Use a practice administrator's JWT issued for the intended practice (select it in the application, or use `POST /api/auth/switch-org/`). The signed token supplies organization context; a client-supplied organization header cannot change it. Verify the target member through `GET /api/user/`; the detail URL takes the **User UUID**, not the Profile UUID. Grant another member with `PATCH /api/user/<user-uuid>/`, JSON body:

```json
{
  "has_patient_access": true,
  "can_record_patient_outcomes": true,
  "has_patient_finance_access": false,
  "has_marketing_access": false
}
```

Confirm the response and contact assignments. To revoke all patient workflows, PATCH `has_patient_access` to false; also clear the other two patient flags to express the intended future policy. Marketing access is independent and must be revoked separately if appropriate. Changes affect existing JWT and PAT requests without issuing a new token. Ordinary members cannot grant themselves these capabilities; administrators cannot use self-edit to grant privileges. There is no permission-management UI in this increment.

For an intentionally restricted PAT, the member uses JWT-authenticated `POST /api/profile/tokens/` with `name`, explicit `scopes` (for example `["patients:read"]`) and an optional expiry. Store the returned raw token securely; it is shown once. Shared CRM routes also require the corresponding CRM resource scope. The member can revoke with `DELETE /api/profile/tokens/<token-uuid>/`; an administrator can revoke with `DELETE /api/org/tokens/<token-uuid>/`. Revoking staff capabilities also restricts existing tokens. Never embed PATs in website JavaScript. Organization keys and sandbox attribution intake are not a substitute for the future dedicated service identity.

## PR #1 alternate-route correction

The October 15 correction applies the same rules to opportunity Kanban and line items, case watching/analytics/merge/unmerge/bulk deletion, and goal list/detail/leaderboard/history. Goal progress includes only permitted patient-linked deals while preserving unrelated CRM aggregation. Assignment/stale notifications exclude restricted patient-linked opportunities; a goal milestone notice is suppressed when its total includes a protected deal the recipient cannot read. Milestone tracking remains goal-wide, without per-recipient retries.

Administrator member creation at `/api/users/` persists explicitly validated capability grants; omission retains false defaults. Portal comment serializers receive trusted reader context; missing context still yields a restricted author placeholder. No additional migration or attribution/cash calculation change is introduced. Final verification status is recorded in [the review remediation report](pr1-review-remediation.md).
