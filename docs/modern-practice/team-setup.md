# Team installation and development

For AI/developer continuity, begin with root `AGENTS.md` and [PROJECT_STATE.md](PROJECT_STATE.md). Review [release readiness](release-readiness.md) and [permission administration](patient-permissions.md) before adopting the remediation branch. Local installation is not production approval.

## Prerequisites and first run

Install Git, Python 3 and Docker Desktop with Compose v2. Start Docker Desktop. Keep ports 5181, 8000, 5432 and 6379 available. This Compose stack is for local development; do not expose it to the Internet. It uses a documented development database role/password and does not configure production TLS or backups.

Follow the commands in the root README. `scripts/setup_local.py` creates `.env.docker` from its example, generates the Django secret, PostgreSQL bootstrap password and administrator password, and refuses to overwrite existing settings. Keep this file private. `.env.docker.local` is an optional private override. Never replace an existing installation's secrets or database settings with the example.

Docker builds Python and Node dependencies using the checked-in uv and pnpm lockfiles. Django migrations run automatically on backend startup. The database's first initialization creates the non-superuser `crm_user` required for RLS. Do not switch the application to the PostgreSQL superuser to bypass errors.

`PUBLIC_DJANGO_API_URL=http://backend:8000` is the server-to-server Compose address used by the web app. The browser still opens http://localhost:5181. Google login is disabled unless deliberately configured. The console email backend prints login links locally; no mail service is connected.

The default local administrator is `admin@localhost`. The web login uses an emailed link printed to local service logs (`docker compose logs -f backend celery-worker`; queued email runs in the worker). The separate Django admin login uses the generated `ADMIN_PASSWORD` in your private `.env.docker`. Do not paste passwords or sign-in links into issues or chat. Existing administrators are not overwritten on restart.

## Fictional demo

```bash
docker compose exec backend python manage.py seed_modern_practice --member-email admin@localhost
```

Select a TEST practice at http://localhost:5181/org. The seed is safe to rerun: it adds missing deterministic fictional records and does not reset existing values or duplicate them. It grants this existing user access only to the two demo practices. No original/local business database is distributed with the source.

Use September 1–30, 2026 in Growth. Harbor: 3 leads, 2 booked patients, 1 treated patient, $1,200 payments minus $100 refunds = $1,100 net collected. Cedar: 3/2/1 and $700 net collected. Historical screenshots/documentation may show manually created tasks or appointments that a fresh seed does not create. The smoke command expects the original three-patient demo baseline.

## Stop, resume, and update

```bash
docker compose stop
docker compose start
# Or start/rebuild after pulling code changes:
docker compose up --build -d
```

Data stays in the local Docker PostgreSQL volume during normal stop/start or restart. Closing a browser does not erase it. Keep Docker running while using the app. Do not remove volumes to troubleshoot: that discards the local database. Source control is not a database backup.

Before pulling updates, save your work on a feature branch. Follow migration notes in the pull request. Do not run multiple copies on the same host ports. If the app shows a temporary 502 after startup, wait for backend startup to complete, then reload.

## Verification

```bash
docker compose exec backend python manage.py check_practice_setup
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend ruff check patients common/rls
docker compose exec frontend npm run check
docker compose exec frontend npm test -- --run src/lib/modern-practice.test.js
docker compose exec backend python manage.py seed_modern_practice_messages
docker compose exec backend python manage.py seed_modern_practice_reviews
docker compose exec backend python manage.py verify_modern_practice --member-email admin@localhost --frontend-url http://frontend:5181
```

The HTTP smoke check expects unchanged seeded patient totals. It checks reporting, original attribution and rejected cross-practice requests; appointment-link checks depend on appointments being present. It does not reset demo data. PostgreSQL tests provide deterministic appointment and RLS coverage.

For a **new developer installation**, create an isolated test database once (never use the application database as the test target):

```bash
docker compose exec db createdb -U postgres -O crm_user test_mp_milestone
docker compose exec -e DBNAME=mp_milestone backend python -m pytest patients/tests --no-cov -q --reuse-db --ds=crm.test_settings_postgres
```

If `test_mp_milestone` already exists, skip `createdb`. Django prefixes `mp_milestone` with `test_`. The test role stays non-superuser without BYPASSRLS; do not substitute postgres. Tests modify only the test database. CI includes the inherited broader tests; this handoff is not a claim that every upstream test or production build has passed for these customizations.

## Repository layout and collaboration

- `backend/patients/`: Modern Practice models, API, reporting, seed, tests and migrations.
- `frontend/src/routes/(app)/patients/`, `growth/`, `messages/` and `reviews/`: new web workflows.
- `frontend/src/lib/modern-practice*`: presentation helpers and styling.
- `docker-compose.yml`, `Dockerfile`, `frontend/Dockerfile`, `docker/`: local stack.
- `docs/modern-practice/`: milestones, rules, validation and limitations.
- `mobile/`: inherited Flutter client, not yet customized for the new workflows.

Use branches and pull requests. Run focused tests for reporting/permission changes and preserve forced RLS and organization checks. Do not silently change first-touch attribution or replace collected revenue with invoice values. Keep unfinished modules clearly marked.

The public snapshot keeps upstream license notices. Internal reference documents, executive decks, local secrets, database contents, caches and generated builds are omitted. Upstream automatic release workflows are moved out of `.github/workflows` into `docs/upstream-workflows/` in the handoff so importing the project does not publish upstream packages. CI remains available; release configuration requires a separate deliberate decision.

## Optional payment-matching demo

After the base seed, run `docker compose exec backend python manage.py seed_modern_practice_billing`. This adds fictional invoice-payment counterparts in the two TEST practices without adding receipts or changing Growth. It is safe to rerun and does not create matches automatically. Open a patient journey → Billing review and verify the matching pair before confirming. Matching requires an administrator, equal USD amounts and a reason. To rehearse a correction, expand **Correct this match**, enter a reason, and confirm reversal. Both records become eligible to match again; the original match and reversal remain in history. No money is refunded or created. Use fictional records for rehearsal. Run `docker compose up --build -d` after pulling this update so backend startup applies migration `patients.0005_payment_match_reversals`. This audit migration is deliberately irreversible: rollback must not erase correction history.

## Internal charge-credit demo

Pull the latest code and run `docker compose up --build -d` to apply `patients.0006_invoice_credit_adjustments`. In a TEST practice, open a patient’s Billing review, expand **Record charge credit** on an issued USD invoice, enter a fictional reason and amount, and confirm. Inspect adjusted billed value and **Charge credit history**. **Reverse this credit** creates a separate full reversal. These internal adjustments do not modify legacy invoice totals/paid/due/status, issue credit-note documents, or refund money. The audit migration is deliberately irreversible; do not roll back by deleting its table/history. Fresh seeds create no charge credits.

## Optional split-allocation demo

Run `docker compose up --build -d` after pulling so startup applies `patients.0007_receipt_allocations`, an irreversible audit migration. After the base and billing seeds, run `docker compose exec backend python manage.py seed_modern_practice_allocations`. It safely adds one USD 400 fictional second invoice per TEST practice without adding cash; existing records remain untouched on rerun.

In Harbor, open Alex → Billing review → Allocate receipt cash → DEMO-harbor-001. Allocate USD 700 to TEST-HARBOR-MATCH and USD 400 to TEST-HARBOR-SPLIT, enter a fictional reason and save. Net collected remains USD 1,100 and unallocated becomes zero. Changing a plan replaces all its lines, preserves prior versions and requires the latest revision. Clearing records an empty version; it does not delete history or money. Allocations are separate from payment matching, invoice paid/due values and Growth. A later refund or changed invoice requires explicit review and replacement of the affected plan. Recorded balances are available only after the reconciliation checks described below pass.

## Refund reconciliation and recorded balances

After pulling, `docker compose up --build -d` applies `patients.0008_refund_allocation_lines`. Existing allocation versions remain; unexplained refunds do not acquire guessed destinations. The audit migration is deliberately irreversible.

For the Harbor split demo, open the receipt allocation editor, keep USD 700 on TEST-HARBOR-MATCH and USD 400 on TEST-HARBOR-SPLIT. Under **Explain recorded refunds**, select DEMO-harbor-REFUND-001, destination TEST-HARBOR-MATCH, amount USD 100, enter a fictional reason and save. This explains the existing refund; it does not issue another. Click **Review recorded balances**. After the original receipt/invoice-payment pair is validly matched, the example shows USD 1,600 billed less USD 1,100 net cash = USD 500 recorded balance. The refund is not deducted twice. If a credit is active or other demo records changed, totals will differ; do not reset records to reproduce the example.

The page withholds amounts and lists reasons when cash/refunds, allocation snapshots, credits, payment matches or currencies are not reconciled. Cedar intentionally remains useful for an incomplete-reconciliation demo. Outstanding and overpaid invoices stay separate; there are no automatic transfers, live charges, or bank/insurance verification. Legacy invoice totals and exports are unchanged. The current one-to-one payment-match requirement can block complex ledger combinations; do not invent matches to bypass it.


## Audited cash amount corrections

Pull the latest code and run `docker compose up --build -d` to apply `patients.0010_receipt_corrections`. This migration adds permanent correction history and cannot be reversed by deleting its audit table. Existing cash is not backfilled or changed.

As an administrator, select a TEST practice, open Patients → Alex Rivera → Billing review → Correct recorded cash amounts. The screen explains any prerequisites: reverse the original payment's active match and clear its latest allocation plan, including refund explanations. Cedar's original demo cash is currently unmatched/unallocated; Harbor's reconciled payment is intentionally blocked until those decisions are released.

For a deliberate fictional rehearsal, expand a record's correction form, enter a different positive amount and a reason, and save. Observe changed collections and Growth in the receipt's original date range. To restore the amount, save its previous value with a new reason. Both entries remain permanently visible in correction history and the patient timeline. These steps modify your local TEST records and are not automatically performed by setup or seeding. Reconcile matches/allocations again afterward. No money moves and legacy invoice/payment records remain unchanged.

Refund totals cannot exceed the original payment, and reducing a payment below its refunds is rejected. Request IDs protect retries; stale versions require reloading. Correction/history controls show the latest 100 cash records and 100 audit entries with counts; reporting includes all records. Deleting duplicates, setting zero amounts, and changing original dates, references or patient links are not supported. Corrections restate past cash reporting rather than creating cash on the correction date.


## Duplicate-payment review

After pulling, run `docker compose up --build -d` to apply `patients.0011_receipt_exclusions`. Existing receipts default to included and existing financial amounts remain unchanged. The permanent audit migration is irreversible.

As a practice administrator, open Patients → a patient → Billing review → Review duplicate payments. Confirm from your source records that two entries describe the same actual payment. Select the duplicate, choose the equal-amount record to retain, and enter the evidence/reason. The duplicate must have no refunds; reverse its active match and clear its allocation plan first. A payment retained by another active exclusion cannot itself be excluded. Exclusion updates original-period collections and Growth, preserves both records, and does not refund money or change invoices. Restoring a payment adds another audit entry and includes it again; reconciliation requires review afterward.

Do not create fake duplicates in an existing practice merely to test this screen. Automated exclusion/restoration tests use the separate test database. The two base TEST demos have no seeded duplicates, so their review screens show why no exclusion is available. New teams may rehearse with their own disposable fictional local records. Decisions persist in their local database and are not erased on restoration or seed reruns.

Limits: same-patient equal-amount payment duplicates without refunds only; no automatic detection, duplicate-refund handling or invoice-ledger cleanup. Choosers/history show the latest 100 entries with counts; reporting uses all included records. Excluded records remain visible in the patient timeline and decision history.


## Correcting a recorded reference

Pull the latest code and run `docker compose up --build -d` to apply `patients.0012_receipt_reference_corrections`. Existing cash values and references remain untouched by migration. Permanent reservations and correction history cannot be removed by rollback.

As a practice administrator, open Patients → patient → Billing review → Correct recorded cash details → Correct this reference. Enter the corrected reference and a reason. Reverse the original payment's active match and clear its allocation plan first; restore an excluded payment before correcting it. Payments and refunds are supported. Amount and reference corrections are separate operations, sharing the same correction version. Reference changes do not affect cash totals, dates or source reporting. Review reconciliation afterward.

Each reference ever used by a receipt remains reserved for that receipt within its practice. Restoring a previous reference is allowed; reusing it on another receipt is rejected. Old request retries cannot reapply earlier values. Past audit snapshots retain their historical references. Seeds use stable IDs, so rerunning them does not reset corrected references. Test successful writes in the isolated PostgreSQL database or your own disposable fictional records; this increment does not add live demo audit entries.


## Essential workflow finish (October 11)

On an existing clone, pull the current public main and run `docker compose up --build -d`. Backend startup applies `patients.0013_receipt_date_corrections`. It adds one nullable audit field and date guards; it does not rewrite existing cash, attendance or attribution. Keep the existing environment and volumes. The migration preserves append-only evidence and is deliberately irreversible.

- **Cash dates:** Patient → Billing review → Correct recorded cash details → Correct this date. Enter UTC, one field per request, and a reason. Future dates and refunds dated before their payment are rejected. A payment cannot move after any of its refunds. Release matches/allocations first. Amount, reference, date share one correction version; old retries do not reapply changes. Date corrections restate both affected reporting periods, preserving lifetime cash and original source. Restore through another correction.
- **Attendance:** Patient → Appointments → closed appointment → Correct a mistaken outcome. Administrators may change attended/no-show/cancelled outcomes with a reason and current version. Attendance must be after the start; no-show after the end. Prior events remain marked superseded. Corrected attendance is recorded at correction time; no treatment or revenue is inferred. Standalone manually entered journey events are independent of appointment corrections.
- **Older records:** Independent page controls expose cash, matches, credits, allocation and correction/decision histories in 100-record pages. They retain other page selections. Choose pages before editing; navigation discards unsaved input. Totals include all records. Allocation invoice and retained-payment choosers include all candidates; full-data search/load optimization is deferred.
- **Financial review:** Patient → Billing review → Internal statement and CSV. All-date adjusted charges include valid internal credits; cash remains receipts less refunds. Unavailable balances stay blank in CSV. Exports include permanent credit/cash correction/exclusion history, sanitize spreadsheet formula-like text and require administrator/contact/practice access. Downloads use private/no-store responses. Live PostgreSQL generation uses a read-only repeatable-read transaction; it is not an accounting close, issued invoice/credit note or proof of bank settlement. Keep exported financial records private; never commit them.

Complete the [Milestone 3 acceptance walkthrough](milestone-three-acceptance.md) using your own disposable fictional records. The owner's shared demonstration was not changed to rehearse successful corrections. GitHub contains code/instructions, not those saved database records. Full accessibility/assistive-technology and load acceptance remain outstanding.

## Local Messages demo

After the base fictional seed has an active administrator in both TEST practices, run `docker compose exec backend python manage.py seed_modern_practice_messages`. It preserves existing conversation edits when rerun. Open http://localhost:5181/messages. See [Milestone 4](milestone-four.md) for the workflow, schema choices, permissions and limitations. Nothing is sent to patients.

## Local Reviews demo

After migration and the base demo seed with an active administrator in both TEST practices, run `docker compose exec backend python manage.py seed_modern_practice_reviews`. Open http://localhost:5181/reviews?start=2026-09-01&end=2026-09-30. Each practice gets three fictional manual reviews (one unrated/Unknown) and one draft-history entry; rerunning preserves edits/statuses. See [Milestone 5](milestone-five.md) for summary definitions, archive/restoration and limitations. Nothing is requested from patients or posted to a provider. The live verification command expects unchanged seeded review counts/averages; it must not reset user edits to satisfy those expectations.

Use the [Messages and Reviews acceptance walkthrough](messages-reviews-acceptance.md) for a team demo and to record a human acceptance decision.

## Read-only local setup check

Run `docker compose exec backend python manage.py check_practice_setup` after startup or pulling updates. Add `--json` for machine-readable output. Success exits zero; failed checks exit nonzero and leave configuration/data unchanged. JSON is printed to stdout; command errors go to stderr. The command reads schema catalogs and migration metadata only, without querying patient rows, printing environment values, granting privileges or applying migrations.

It checks PostgreSQL, a non-superuser application role without BYPASSRLS, enabled and forced RLS plus both expected policy names on every table in the central tenant registry, no pending migrations, and a console/in-memory/dummy email backend. Console is the normal local sign-in backend; dummy/in-memory do not provide sign-in links through worker logs.

If it fails, wait for startup and rerun. For pending migrations, use the normal documented migration/startup process. For role or RLS failures, compare your private setup with the repository instructions and investigate the named table; do not switch to the superuser or disable RLS to make the check pass. Unexpected non-local email settings require investigation before using the fictional demo. A database inspection failure deliberately omits the underlying exception to avoid exposing private connection values.

This is a narrow configuration check, not a production-readiness certificate. It does not validate policy expressions, exercise cross-practice isolation, check web/worker responsiveness, inspect other live-service configuration, verify backups, or replace permission/API tests and human acceptance. Follow the remaining checks above.

## Attribution sandbox

Migration `patients.0016_attribution_intake` adds three protected evidence tables without rewriting existing records. Administrators can open http://localhost:5181/attribution, select a TEST practice, create a test connection and run/resume a fictional lead-to-refund demonstration. This adds data to the chosen TEST practice; it is not a live connector. Read the [contract and demo instructions](closed-loop-attribution.md) before running it. Tests: `docker compose exec -e DBNAME=mp_milestone backend python -m pytest patients/tests/test_intake.py --no-cov -q --reuse-db --ds=crm.test_settings_postgres`.


## Website capture developer demo

Open http://localhost:5181/modern-practice/website-demo.html. This fictional in-memory demo needs no login, creates no CRM records and makes no data requests. Try consent → Google Ads introduction → later email, then withdrawal and an Unknown-first visit. Read [website capture setup and limits](website-intake.md) before adapting it to a site. Run `node --test scripts/test_website_attribution.mjs` from the repository root with Node 20+. Restricted credentials and protected website-to-CRM submission remain pending; never put an administrator JWT on a website.


## Post-audit authorization and CI validation

Read [patient permissions](patient-permissions.md) before adopting the remediation. Regular members need explicit patient capabilities plus existing contact sharing. Migration `common.0044` defaults these capabilities off; `patients.0017` adds the 21 missing organization/creation indexes. No patient or cash records are rewritten. Review the migration diff and use the normal restricted application role after approval. This separate remediation checkout has not been installed into the running demo.

In a backend development environment with dependencies installed:

```bash
# From backend/; SQLite compatibility is not tenant-security evidence.
DJANGO_SETTINGS_MODULE=crm.test_settings uv run pytest -m "not postgres_only"
# PostgreSQL connection variables must point to a disposable test server.
# DBUSER must be LOGIN CREATEDB NOSUPERUSER NOBYPASSRLS for test-db creation.
DJANGO_SETTINGS_MODULE=crm.test_settings_postgres uv run pytest --migrations --no-cov -m postgres_only
uv run python ../scripts/check_test_routing.py
uv run python manage.py makemigrations --check --dry-run
uv run ruff check .
uv run ruff format --check .
uv sync --frozen --group docs
uv run mkdocs build --strict -f ../mkdocs.yml -d site
```

Set a local test-only SECRET_KEY of at least 32 characters. Never point a test runner at production. The security fixture rejects SQLite, superusers and BYPASSRLS roles. CI gives the security job its own PostgreSQL service and no `needs` dependency on other test jobs. The compatibility PostgreSQL job remains a type/constraint check as a superuser and is explicitly **not** evidence of isolation. The routing script proves the two selections are disjoint and cover all collected tests; all patient tests, including future files, go to the policy-bound job. Run focused patient tests with PostgreSQL settings as well. Existing patient staff fixtures explicitly grant capabilities; production migrations do not.

Recommended branch protection (owner approval required): protect `main`, require PR review and current successful checks for `backend-tests`, `backend-tests-postgres`, `patient-security-postgres`, `package-build`, `frontend-checks`, `docs-build` and the actual configured CodeQL analysis check. Prevent force pushes/deletion and prefer resolving review conversations before merge. Check the exact GitHub check names from a real run before configuring them. No branch-protection settings were changed. Badge commits directly to main were removed from CI so that validation does not bypass review. All pushes/PRs to main now trigger CI without path filters, avoiding missing required checks on documentation-only changes.
