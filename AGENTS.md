# Modern Practice CRM continuity

> **Current checkpoint — October 20, 2026:** Phase 2B is merged in PR #4 at `c8c96b97716e198b3c3445b83a7ddd2aac97a68b`. All seven pre-merge checks passed on `7afa53cbbf6ee0c652ba13806fb70111319f529b`. Phase 2C is next and has not started. Architecture 0.2.0 and approved A01–A10 remain unchanged; Group B/C remain pending. No deployment or live-provider connection is implied. See PROJECT_STATE for evidence and current scope; older status snapshots below are historical.

Read [the universal journey index](docs/modern-practice/universal-journey/README.md), decision register J and roadmap I before integration work. The accepted architecture is a specification; preserve existing patient permissions and financial safeguards until a separately reviewed implementation changes them.

When resuming project development, read `docs/modern-practice/PROJECT_STATE.md` first. It records the objective, current milestone, verified baseline, limitations and proposed next work. Use `README.md` and `docs/modern-practice/team-setup.md` for installation and checks; consult milestone documents for the relevant feature history.

## Standing project requirements

- Preserve authentication, organization permissions, PostgreSQL forced row-level security, existing organizations and records. Keep frontend port 5181 and backend port 8000.
- Reuse existing models where appropriate. Explain necessary schema additions and distinguish explicit requirements from implementation choices.
- Preserve original attribution; later touches must not overwrite it. Collected revenue comes from receipts less refunds, never invoice/deal values. Preserve Unknown attribution and unavailable ROAS when spend is missing.
- Use fictional, clearly labeled TEST practices for demos and rerunnable seeds. No live advertising, messaging, review or payment connections; no deployment, Git resets or Docker volume deletion.
- This repository is public. Never publish secrets, real patient data, database exports, internal PDFs/decks, `reference/`, `output/`, or the original local repository's private history.
- Current owner authorization: the October 20 “proceed” authorizes this documentation correction and its checked feature-branch publication/PR. Separate approval is required before merge or future publication. This correction does not start Phase 2C, authorize live services, deployment or repository administration. Inspect remote history before publication; never force-push or publish private history.

## Attribution-first scope

The owner's primary objective is to connect observable marketing interactions through inquiry, booking, care and collected revenue, across supported journey sequences. Every proposed increment must explain how it advances acquisition capture, evidence-based identity/journey linking, clinical milestones, receipt/refund reconciliation or attribution reporting. Security and processing work must support that path; defer unrelated CRM expansion.

Phase 2C remains the bounded processing/recovery step in roadmap I, followed by the approved foundation and domain dependencies. The proposed delivery focus is one provider-tested marketing-to-revenue path before broad vendor expansion, not a replacement for the architecture or approval gates. No provider is selected or verified by this rule. Sandbox/provider access needs separately scoped approval under the current no-live-services restriction.

Clearly distinguish seeded demonstrations, fictional adapter conformance and actual provider-tested evidence. Preserve original attribution and subsequent touches separately. Never infer an unobserved Google Search/Business Profile step, a cross-device identity or a missing source; keep gaps and Unknown explicit. Report collected revenue as receipts less refunds and unavailable ROAS when spend is missing. One verified path is an initial proof, not a claim of universal coverage.

## Maintain the handoff

After each meaningful increment, update `PROJECT_STATE.md` with completed work, exact checks performed, outstanding limitations, proposed next step, and any interrupted/uncommitted work. Keep that update with the implementation; commit/push only after explicit approval under the current override. Record failures and checks not performed; do not turn proposals into completed requirements. Keep private data out of handoff files.

On a new session, compare the handoff against Git status/history, migrations and runtime before changing anything. Preserve existing work and continue from evidence rather than assuming an earlier chat or a clean checkout is available.
