# Team installation and development

## Prerequisites and first run

Install Git, Python 3 and Docker Desktop with Compose v2. Start Docker Desktop. Keep ports 5181, 8000, 5432 and 6379 available. This Compose stack is for local development; do not expose it to the Internet. It uses a documented development database role/password and does not configure production TLS or backups.

Follow the commands in the root README. `scripts/setup_local.py` creates `.env.docker` from its example, generates the Django secret, PostgreSQL bootstrap password and administrator password, and refuses to overwrite existing settings. Keep this file private. `.env.docker.local` is an optional private override. Never replace an existing installation's secrets or database settings with the example.

Docker builds Python and Node dependencies using the checked-in uv and pnpm lockfiles. Django migrations run automatically on backend startup. The database's first initialization creates the non-superuser `crm_user` required for RLS. Do not switch the application to the PostgreSQL superuser to bypass errors.

`PUBLIC_DJANGO_API_URL=http://backend:8000` is the server-to-server Compose address used by the web app. The browser still opens http://localhost:5181. Google login is disabled unless deliberately configured. The console email backend prints login links locally; no mail service is connected.

The default local administrator is `admin@localhost`. The web login uses an emailed link printed to backend logs. The separate Django admin login uses the generated `ADMIN_PASSWORD` in your private `.env.docker`. Do not paste passwords or sign-in links into issues or chat. Existing administrators are not overwritten on restart.

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

After the base seed, run `docker compose exec backend python manage.py seed_modern_practice_billing`. This adds fictional invoice-payment counterparts in the two TEST practices without adding receipts or changing Growth. It is safe to rerun and does not create matches automatically. Open a patient journey → Billing review and verify the matching pair before confirming. Matching requires an administrator, equal USD amounts and a reason. Matches cannot currently be undone; use fictional records only for this rehearsal. Run `docker compose up --build -d` after pulling this update so backend startup applies migration `patients.0004_payment_matches`.
