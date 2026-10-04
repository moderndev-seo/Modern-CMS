# Modern Practice CRM

A practice operations and marketing attribution CRM built on [BottleCRM / Django-CRM](https://github.com/django-crm/Django-CRM). Django REST Framework, SvelteKit, PostgreSQL row-level security, Redis, and Celery power the local development stack. The upstream MIT license and notices are retained in [LICENSE](LICENSE).

## Start here

Requires Git, Python 3, and Docker Desktop with Docker Compose v2 running. No advertising, email delivery, or payment-service account is needed for the demo.

```bash
git clone https://github.com/moderndev-seo/Modern-CMS.git
cd Modern-CMS
python3 scripts/setup_local.py
docker compose up --build -d
docker compose logs -f backend
```

Wait for migrations, administrator creation, and Django startup to finish. First builds can take several minutes. Press Ctrl+C to stop following logs; the containers stay running.

```bash
docker compose exec backend python manage.py seed_modern_practice --member-email admin@localhost
```

Open **http://localhost:5181/login**, enter **admin@localhost**, and request a sign-in link. With the console email backend, no email is sent: find the sign-in URL in `docker compose logs -f backend celery-worker` and open it locally. Select either clearly labeled **TEST** practice at **http://localhost:5181/org**.

- Web app: http://localhost:5181
- API documentation: http://localhost:8000/swagger-ui/
- Patient journeys: http://localhost:5181/patients
- Growth: http://localhost:5181/growth?start=2026-09-01&end=2026-09-30

[Detailed installation, restart, testing, and troubleshooting instructions](docs/modern-practice/team-setup.md).

## What is implemented

- Patient identity linked to existing CRM contacts; searchable intake.
- Immutable original attribution and separate subsequent marketing touches.
- Appointment, consultation and treatment events; chronological patient activity.
- Received payments and refunds, separate from invoice/deal values.
- Growth totals and first-touch attributed revenue/ROAS, manual spend, explicit UTC windows, and Unknown attribution.
- Patient follow-up tasks using the existing CRM task model.
- Booking, rescheduling, cancellation, attendance and no-shows with change history.
- Administrator reopening of cancellations/no-shows without duplicating booking events.
- Patient billing review with separate receipt totals and invoice ledgers by currency, plus explicit administrator matching of equal USD payment records. Audited reversals release mistaken matches for rematching. Split allocations and refund reconciliation remain unfinished.
- Receipt-to-invoice coverage: linked payments and their refunds, unmatched receipts, and changed matches needing review, with totals across all records.
- Audited internal invoice charge credits and full reversals, with adjusted billed values in patient billing review; no cash writes or automatic legacy-invoice changes.
- Practice permissions, PostgreSQL RLS and cross-practice relationship checks.

Existing CRM tools remain accessible. The inherited Flutter app is included as upstream source; Modern Practice's new screens are implemented in the web app, not in that mobile client.

## Demo data and current scope

The rerunnable seed creates two fictional practices. For **September 1–30, 2026**, each starts with 3 leads, 2 booked patients and 1 treated patient. Harbor has $1,100 net collected; Cedar has $700. The seed preserves existing records and does not reset changes. Later manual demo appointments/tasks are not part of the seed.

This is an in-progress development project. Attendance corrections, financial corrections, invoice reconciliation, provider/room availability, timezone configuration, calendar connections and reminders remain unfinished. Messages and Reviews are marked planned. No live advertising, messaging, review or payment integrations have been connected. Production deployment and healthcare compliance review are separate work.

[Milestone 1](docs/modern-practice/milestone-one.md) · [Milestone 2](docs/modern-practice/milestone-two.md) · [Milestone 3](docs/modern-practice/milestone-three.md)

## Working as a team

For current progress, limitations and the next proposed increment, read the [project handoff](docs/modern-practice/PROJECT_STATE.md). [AGENTS.md](AGENTS.md) directs new coding sessions to that handoff. Keep it updated with each completed increment so development can continue without the original chat.

Clone this repository and create a branch for each change. Submit pull requests and review changes before merging. Each developer gets their own local database and fictional seed records; Git does not synchronize databases or turn this into a shared hosted application.

Do not commit `.env` files, actual patient data, database exports, credentials, internal reference PDFs, or executive decks. Public handoff snapshots exclude those files and the old local Git history that contains internal artifacts. Original source code, migrations, tests, assets, dependency lockfiles and license notices are included.

See [team setup and verification](docs/modern-practice/team-setup.md) for the checks to run. Upstream release automation is retained as disabled reference files in the public handoff; it must be deliberately configured before any publishing. Nothing in these setup steps deploys the application.
