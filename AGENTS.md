# Modern Practice CRM continuity

When resuming project development, read `docs/modern-practice/PROJECT_STATE.md` first. It records the objective, current milestone, verified baseline, limitations and proposed next work. Use `README.md` and `docs/modern-practice/team-setup.md` for installation and checks; consult milestone documents for the relevant feature history.

## Standing project requirements

- Preserve authentication, organization permissions, PostgreSQL forced row-level security, existing organizations and records. Keep frontend port 5181 and backend port 8000.
- Reuse existing models where appropriate. Explain necessary schema additions and distinguish explicit requirements from implementation choices.
- Preserve original attribution; later touches must not overwrite it. Collected revenue comes from receipts less refunds, never invoice/deal values. Preserve Unknown attribution and unavailable ROAS when spend is missing.
- Use fictional, clearly labeled TEST practices for demos and rerunnable seeds. No live advertising, messaging, review or payment connections; no deployment, Git resets or Docker volume deletion.
- This repository is public. Never publish secrets, real patient data, database exports, internal PDFs/decks, `reference/`, `output/`, or the original local repository's private history.
- The owner has requested that completed, verified work always be pushed to `moderndev-seo/Modern-CMS`. Inspect the checkout, remote and remote branch before publishing. Never force-push or overwrite others' work. The original development folder has different Git history from the public repository: follow the handoff's publishing warning.

## Maintain the handoff

After each meaningful increment, update `PROJECT_STATE.md` with completed work, exact checks performed, outstanding limitations, proposed next step, and any interrupted/uncommitted work. Push that update with the implementation. Record failures and checks not performed; do not turn proposals into completed requirements. Keep private data out of handoff files.

On a new session, compare the handoff against Git status/history, migrations and runtime before changing anything. Preserve existing work and continue from evidence rather than assuming an earlier chat or a clean checkout is available.
