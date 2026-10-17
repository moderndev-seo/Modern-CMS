# Modern Practice CRM continuity

> **Current publication status — October 16, 2026:** Design 0.2.0 and bounded A01–A10 are approved for fictional, isolated Phase 2A; Group B/C remain pending. The owner confirmed independent human review without outstanding blockers and authorized security PR #1 to merge; GitHub records merge `1e00ae5d175e0ace627b2dc5fc68e25a73cb41dd`. All seven checks passed on reviewed head `81ecc87672e35a00d45a9c40b2f83d578a364f2a`. This separate documentation PR is authorized for publication after checks. Phase 2A remains unimplemented and gated on documentation review, separate owner merge approval and actual merge. No live connections, deployment or Phase 2B–E implementation. Earlier gate/status snapshots below are historical, not current instructions.

Read [the universal journey index](docs/modern-practice/universal-journey/README.md), decision register J and roadmap I before integration work. The accepted architecture is a specification; preserve existing patient permissions and financial safeguards until a separately reviewed implementation changes them.

When resuming project development, read `docs/modern-practice/PROJECT_STATE.md` first. It records the objective, current milestone, verified baseline, limitations and proposed next work. Use `README.md` and `docs/modern-practice/team-setup.md` for installation and checks; consult milestone documents for the relevant feature history.

## Standing project requirements

- Preserve authentication, organization permissions, PostgreSQL forced row-level security, existing organizations and records. Keep frontend port 5181 and backend port 8000.
- Reuse existing models where appropriate. Explain necessary schema additions and distinguish explicit requirements from implementation choices.
- Preserve original attribution; later touches must not overwrite it. Collected revenue comes from receipts less refunds, never invoice/deal values. Preserve Unknown attribution and unavailable ROAS when spend is missing.
- Use fictional, clearly labeled TEST practices for demos and rerunnable seeds. No live advertising, messaging, review or payment connections; no deployment, Git resets or Docker volume deletion.
- This repository is public. Never publish secrets, real patient data, database exports, internal PDFs/decks, `reference/`, `output/`, or the original local repository's private history.
- Current owner authorization: publish the separate architecture documentation PR after checks. Security PR #1 is merged. Documentation merge needs separate approval; fictional Phase 2A implementation and verified feature-branch publication are conditionally authorized only after documentation approval/merge. No deployment, live providers, production database or repository administration changes. Inspect remote history before publication; never force-push or publish private history.

## Maintain the handoff

After each meaningful increment, update `PROJECT_STATE.md` with completed work, exact checks performed, outstanding limitations, proposed next step, and any interrupted/uncommitted work. Keep that update with the implementation; commit/push only after explicit approval under the current override. Record failures and checks not performed; do not turn proposals into completed requirements. Keep private data out of handoff files.

On a new session, compare the handoff against Git status/history, migrations and runtime before changing anything. Preserve existing work and continue from evidence rather than assuming an earlier chat or a clean checkout is available.
