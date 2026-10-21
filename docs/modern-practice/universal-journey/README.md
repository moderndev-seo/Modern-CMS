# Universal patient journey architecture

> **Execution status:** [PROJECT_STATE](../PROJECT_STATE.md) is authoritative for the current milestone, validation and authorization. Phase 2B is merged in PR #4; Phase 2C is next and unstarted at the October 20, 2026 checkpoint. Architecture 0.2.0 and A01–A10 remain unchanged; Group B/C remain pending. Dated adoption, validation and publication statements below are historical specification records, not current implementation status or new authorization.


> **Historical adoption record 1 — superseded by approval record 2:** The owner accepted design **0.2.0 as the technical baseline**, subject to unresolved policy approvals in J. This supersedes the earlier “final validation draft / technical approval pending” status only. Proposed policy defaults remain pending. Phase 2A planning is authorized; implementation and GitHub publication actions are not. See [adoption and Phase 2A handoff](I-roadmap.md#adoption-and-phase-2a-handoff) and [owner approval register](J-product-decisions.md#group-a-owner-approval-register).


**Historical design review — version 0.2.0, October 14, 2026:** The specification was prepared for owner approval at that date. Subsequent A01–A10 approval and merged implementation through 2B are recorded in J and PROJECT_STATE; the specification alone does not prove working provider integrations.

## Objective and current boundary

Connect observed acquisition to verified patient outcomes and attributable collected revenue across different practice vendors. Keep Django/DRF, SvelteKit, PostgreSQL forced RLS, Redis/Celery, existing Contact/Patient identity, original attribution and immutable financial safeguards. A practice remains the protected-data tenant. Preserve frontend5181/backend8000.

Historical architecture publication baseline: merged security commit `1e00ae5d175e0ace627b2dc5fc68e25a73cb41dd` on main. The original architecture assessment used `3858f46f9e80960f1f4d5f0627459d863e5a65e9`; subsequent security corrections are recorded in [the remediation report](../pr1-review-remediation.md). This documentation does not implement a connector or change permissions.

## Authoritative reading order

| Document | Owns |
|---|---|
|[A — Executive assessment](A-executive-assessment.md)|Implemented/partial/proposed distinction and verdict|
|[B — Journey architecture](B-journey-architecture.md)|Lifecycle and module/data-flow diagrams|
|[C — Vendor capabilities](C-vendor-capabilities.md)|Research evidence, access uncertainty and selection gates|
|[D — Data and events](D-data-and-events.md)|Canonical entities/events, code mappings, migrations/invariants, inbox/replay|
|[E — Identity and attribution](E-identity-and-attribution.md)|Identity/newness/source decisions and original-evidence semantics|
|[F — Revenue and reporting](F-revenue-and-reporting.md)|Money predicates, metric populations, dates/currencies/completeness|
|[G — Security and privacy](G-security-and-privacy.md)|Proposed grants/service authority, sensitive flows and operations|
|[H — Acceptance scenarios](H-acceptance-scenarios.md)|A–O scenario oracles plus P–X critical edge cases; not executed tests|
|[I — Roadmap](I-roadmap.md)|Phases and reviewable2A–2E foundation increments|
|[J — Decision register](J-product-decisions.md)|Pending defaults/alternatives, implications, dependencies and blockers|
|[Validation report](VALIDATION_REPORT.md)|Corrections, scope of checks, remaining limits and adoption plan|

Read [PROJECT_STATE](../PROJECT_STATE.md) first in a new session. [Current patient permissions](../patient-permissions.md) describes implemented access, including administrator-only finance actions; proposed roles here do not grant new powers. [Existing roadmap entrypoint](../post-audit-architecture.md) points here instead of maintaining duplicate future definitions. [Sandbox intake](../closed-loop-attribution.md), [local capture](../website-intake.md), [release review](../release-readiness.md) and [team setup](../team-setup.md) remain the implemented/history/setup references.

## Approval and change control

Explicit owner invariants are mandatory. A01–A10 defaults are approved; remaining J Group B/C slices remain pending. “Documented vendor capability” is not credential entitlement, sandbox validation or healthcare data-use permission. Acceptance scenarios are future test specifications. Prior security/regression results are historical, not rerun for this documentation assignment.

The framework subset in J is approved for 2A; 2B–E still need separate authorization. Real vendor, newness, cash, reporting and privacy policies can be resolved at their stated later gates. No live account or patient data is required for the fictional shadow foundation. Independent approval/merge of PR #1 and separate implementation authorization are hard gates.

Future architecture decisions use `ADR-NNN-title.md` in this directory, linked from J: status proposed/approved/rejected/superseded, decision ID, approver/date, rationale, alternatives, security/business consequences, affected spec/schema/mapping/metric versions, migration impact and acceptance tests. No ADR is approved merely because it is written. D/E/F/G own definitions; examples and vendor adapters cannot override them. Breaking semantics need a contract/metric version change and replay/restatement plan.

Publication requires a separately authorized docs-only branch from main after PR #1 merges, revalidation against the actual merged tree and a new PR. Do not update the security branch or publish the original development repository/private history. No source code, migrations, accounts, secrets, database exports or private decks belong in this package.

## Adoption review entrypoints

Start with the [consolidated A–G adoption handoff and Phase 2A specification](I-roadmap.md#adoption-and-phase-2a-handoff), then read the recorded [ten foundation approvals](J-product-decisions.md#group-a-owner-approval-register). The technical baseline and A01–A10 are approved; implementation awaits the two required approved merges. Preserve the historical validation report when recording later decisions.
