# Team installation and development

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
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend ruff check patients common/rls
docker compose exec frontend npm run check
docker compose exec frontend npm test -- --run src/lib/modern-practice.test.js
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
- `frontend/src/routes/(app)/patients/` and `growth/`: new web workflows.
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
