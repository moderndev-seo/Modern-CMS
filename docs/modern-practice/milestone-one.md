# Modern Practice CRM — milestone one

## Requirements and implementation decisions

Both supplied PDFs were read before implementation:

- `reference/Modern Practice CRM (1).pdf`: visual direction: dark practice navigation, pale gray workspace, condensed headings, rounded white panels, magenta actions, colored navigation icons. Its Reviews content is a design reference, not functionality implemented in this milestone.
- `reference/Modern Practice — Marketing Attribution Executive Deck.pdf`: original source → known lead → appointment booked/attended → consultation → completed treatment → amount received. Later touches must not replace the original source. Prove revenue attribution and separation between two practices using fictional records.

The user explicitly requested Patients and Growth, payment/refund accounting separate from invoices/deals, manual spend, date rules, Unknown attribution, idempotent demo data, preserved permissions/RLS, and local verification. No live services are connected.

Implementation choices for this milestone:

- Extend an existing `Contact` with a one-to-one `Patient` journey. Existing contacts can be linked explicitly; entering a new identity creates a Contact. Existing CRM Leads and Contacts are not silently converted. Duplicate contact emails produce a link-existing instruction.
- Four new org-scoped tables: patient identity/immutable first attribution; subsequent journey events; an append-only API payment/refund ledger; daily spend. These reuse UUIDs, audit fields, org membership and RLS helpers.
- The invoice Payment model requires an Invoice and recalculates invoice status. It is intentionally not reused for independent patient cash receipts. No invoice or opportunity amounts enter Growth.
- UTC timestamps and inclusive UTC calendar-day filters; USD only. These choices are shown explicitly even if the existing practice has a different timezone/currency. The existing CRM retains its own locale behavior.
- Fixed source taxonomy (Google Ads, Organic search, Meta Ads, Referral, Email, Direct, Unknown); campaign, keyword, and landing page remain captured text. Multi-touch is recorded, but revenue uses only first touch.
- Any active practice member can read patient/Growth records and create patient journeys/events. Only practice ADMIN members can record receipts/refunds or spend. Existing authentication/middleware and permissions are unchanged.
- Original fields cannot be edited through the patient API. PostgreSQL also rejects original-identity/attribution changes and cross-practice links. Events and receipts have no update/delete endpoints. Corrections to event or original-source mistakes require a future audited correction workflow.
- Receipt reference is unique per practice: repeated submissions cannot duplicate the same receipt reference. Refunds link to a payment belonging to the same patient/practice. Row locking serializes refund-balance checks; the API rejects over-refunds and refunds predating payment.
- Saving spend replaces the one total for that source/day. It does not add a second expense row for the same key.

## Reporting definitions

The selected start/end dates mean `[start 00:00 UTC, day-after-end 00:00 UTC)`.

- Leads: patient journeys whose `lead_at` is in the period.
- Booked: distinct patients with a booked event in the period, not a count of repeated bookings.
- Treated: distinct patients with a completed-treatment event in the period.
- Net collected: payments received in the period minus refunds issued in the period. Both use their own occurrence dates, regardless of lead or treatment date. A period may legitimately be negative.
- First-touch attributed revenue: assign each payment/refund to its patient's original source. Later touches never reassign it. Missing source is Unknown; missing first-touch timestamp remains null.
- Spend: sum manually entered daily totals in the period. No entry means null/Not entered, distinct from a confirmed zero.
- Source ROAS: net collected / entered spend, only if spend is positive. Missing or zero spend means unavailable, never infinity.
- Total ROAS: unavailable when an active source lacks any spend entry, or total spend is zero/missing. Daily data completeness cannot be inferred from partial manual entries; the UI states this limitation. Confirm zero spend explicitly when appropriate.

These are activity-period metrics, not cohort conversion rates. A booking or treatment may belong to an earlier-period lead.

## Local setup and demo

Ports remain frontend 5181 and backend 8000. Existing Docker volumes are retained.

```sh
docker compose exec -T backend python manage.py migrate --noinput
docker compose exec -T backend python manage.py seed_modern_practice --member-email admin@localhost
```

The seed only creates deterministic fictional records in these two practice IDs:

| Practice | ID | September demo net | Google Ads ROAS |
| --- | --- | --- | --- |
| TEST - Harbor Spine & Ortho (fictional) | d0585fb9-0d9c-57a9-90ab-f25cfda641aa | $1,100 ($1,200 - $100) | 5.50× |
| TEST - Cedar Family Dental (fictional) | 9b78caf4-6932-571d-9699-b7b7dafcd0b7 | $700 ($800 - $100) | 3.50× |

Each practice has 3 leads, 2 booked patients, 1 treated patient, a later Email touch, $200 Google Ads spend, confirmed $0 Referral spend, and an Unknown-source lead with missing spend. Total ROAS is therefore unavailable until Unknown spend is explicitly entered. Seed dates are September 1–12, 2026; use September 1–30, 2026 to see all records. Re-running adds no duplicates and does not overwrite edits. `--member-email` must name an existing active user; it adds membership only to these two demo practices and never changes existing practice membership.

1. Sign in using the existing local authentication at http://localhost:5181/login.
2. At http://localhost:5181/org select a **TEST** practice. The sidebar's **Switch practice** link returns here.
3. Open http://localhost:5181/patients and select Alex Rivera. Verify all stages, preserved Google Ads attribution, a later Email touch, payment, and refund.
4. Open http://localhost:5181/growth?start=2026-09-01&end=2026-09-30. Compare the table above. Unknown shows missing spend, not a made-up zero.
5. Create your own fictional patient at http://localhost:5181/patients/new. Record source and timestamps, then add booked, attended, consultation, treated and later-touch events. As a demo administrator, record a payment with a unique reference and optionally a partial refund. Select the same UTC dates in Growth and reconcile the change.
6. Switch to the other TEST practice; the first practice's patient URL must be inaccessible. Return to your original Modern Practice at `/org` whenever needed.
7. Existing CRM modules remain under **Existing CRM tools**. Billing opens existing invoices. Messages and Reviews are clearly marked Planned/Not implemented.

## API

All endpoints use the existing signed bearer JWT and server-derived organization. The client cannot set `org`, `created_by`, or a different `patient` in a nested payload.

| Method | Path under http://localhost:8000 | Purpose |
| --- | --- | --- |
| GET / POST | `/api/patients/` | List (50/page, search) / create or link a contact |
| GET | `/api/patients/{id}/` | Identity, attribution, events, receipts, net collected |
| GET / POST | `/api/patients/{id}/events/` | Read / append an event |
| GET / POST | `/api/patients/{id}/receipts/` | Read / record payment or refund |
| GET | `/api/patients/growth/?start=2026-09-01&end=2026-09-30` | Stored-record dashboard |
| PUT | `/api/patients/spend/` | Set one daily source total |

Timestamps accept ISO 8601 offsets; the frontend entry fields explicitly use UTC. Event kinds: `touch`, `booked`, `attended`, `consultation`, `treated`. Receipt kinds: `payment`, `refund`; amounts are positive decimal USD strings; refunds require `payment` UUID.

## Verification commands

```sh
docker compose exec -T backend python -m pytest patients/tests --no-cov -q
docker compose exec -T backend python manage.py verify_modern_practice --member-email admin@localhost --frontend-url http://frontend:5181
docker compose exec -T backend python manage.py makemigrations --check --dry-run
docker compose exec -T backend python manage.py check
docker compose exec -T backend ruff check .
docker compose exec -T backend ruff format --check .
docker compose exec -T frontend pnpm check
docker compose exec -T frontend pnpm lint
docker compose exec -T frontend pnpm build
```

`verify_modern_practice` checks the unchanged seed over real HTTP and prints a stable snapshot fingerprint for restart comparisons. It sends deliberately invalid cross-practice writes which must be rejected. It is a smoke command for the unchanged demo: legitimate edits/additions will change its expected seed totals.

The PostgreSQL tests require an isolated test database owned by a non-superuser role. During implementation `test_mp_milestone` was created separately from `crm_db`:

```sh
docker compose exec -T -e DBNAME=mp_milestone backend python -m pytest patients/tests --no-cov -q --reuse-db --ds=crm.test_settings_postgres
```

No application database reset or volume removal is required. A normal `docker compose restart` preserves data.

## Remaining scope

No live ad, messaging, review or payment integrations; no automatic identity matching across channels; no multi-touch revenue allocation, campaign/location/service-line reports, automatic ad-cost imports, multi-currency accounting, event correction UI, or clinical chart/EHR functionality. This milestone is for fictional proof-of-concept records. It does not establish readiness for real patient data.

## Verification recorded during implementation

- Focused SQLite suite: 9 passed, 1 PostgreSQL-only test skipped. A rerun with `--no-migrations` followed the initial migrated run to fix a test-helper collision.
- Focused PostgreSQL suite: all 10 passed under `crm_user` (`rolsuper=false`, `rolbypassrls=false`) against the separate `test_mp_milestone` database. This verifies forced RLS, denied direct database writes, immutable attribution, and relationship constraints in addition to API tests.
- Real HTTP API smoke verification: both test practices reconcile; seven hostile cross-practice requests per practice are rejected, including contact linking and refund-payment linking; anonymous access is rejected.
- A normal restart of all six containers preserved every captured per-table count and SHA256 fingerprint across the original practice and both test practices. No volume was removed.
- Django system checks: no issues. `makemigrations --check --dry-run`: no changes detected.
- Full backend Ruff lint: passed. Full backend Ruff formatting: 768 files already formatted.
- Frontend `pnpm check`: zero errors and zero warnings. Earlier concurrent checks exhausted local Docker memory; final checks were run sequentially.
- Authenticated HTTP rendering: Patients, patient detail, Growth, new-patient and planned-module pages returned successfully for both test practices (10 page checks).
- Browser inspection: the existing sign-in screen rendered correctly. A signed-in interactive walkthrough of the new pages was not completed; authenticated server rendering was verified separately.
- Frontend production build (`pnpm build`): passed, including the Node adapter output. The build emitted an empty `env.js` chunk notice.
- Full frontend `pnpm lint`: passed formatting and ESLint with zero errors. Eight warnings remain in untouched existing CRM files (documents, help, leads board, pipeline, business hours, tickets board, and timesheet report); none are in the changed frontend files.
- `git diff --check`: passed. The background workers temporarily stopped for validation were restored.
