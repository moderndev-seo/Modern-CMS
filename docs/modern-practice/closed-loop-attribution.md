# Closed-loop attribution: integration foundation

## Objective and scope

The owner clarified that the product exists to connect marketing strategy to actual collected revenue. General CRM features support that objective. The next priority is automated attribution: capture the introduction, retain a reliable patient link, connect outcomes and collected cash, and expose missing evidence. Websites use a mix of platforms; booking/payment vendors are not yet known. Broad provider support is required, but universal compatibility is not promised.

This increment is an **authenticated sandbox ingestion contract and demonstration**, not a connected provider product. No Google, analytics, website, booking or payment account is connected. No tags are installed, money moved, messages sent or site deployed.

## Implemented

Three additive models reuse existing Patient/Contact, JourneyEvent and Receipt records:

- AttributionConnection: an immutable named sandbox namespace, scoped to a practice. It holds no credentials.
- AttributionIdentity: an immutable connection/external-subject-ID to Patient link. No name/email guessing or cross-connection automatic matching.
- AttributionEvent: an immutable event ID, normalized-request SHA-256 fingerprint and link to the resulting patient/outcome/receipt. It retains actor and received time; raw provider payloads are not archived here.

All three tables have forced PostgreSQL RLS and database relationship/actor checks. Existing data is not backfilled. Migration `0016_attribution_intake` deliberately cannot roll back by deleting audit evidence.

API reads require an active practice administrator through existing JWT authentication. Writes additionally require a practice name starting with `TEST -`. That naming gate is a demo safeguard, not a separate production trust mechanism. PATs, anonymous browser requests and vendor webhooks are not supported by these endpoints. Do not expose an administrator JWT on a website.

A connection lock serializes event processing. One event and its resulting CRM record commit together. An identical event-ID retry returns the original IDs without another payment. Reusing that ID with different normalized request facts returns 409. External IDs are unique within a connection, not across unrelated connections. Adapters must reuse a provider's stable transaction ID even when it emits multiple notifications; changing IDs can still create duplicates.

## Local demonstration

1. Start the existing stack, preserving the environment and volumes. Apply migrations with `docker compose exec backend python manage.py migrate`.
2. Sign in as a practice administrator and select a fictional TEST practice at http://localhost:5181/org.
3. Open http://localhost:5181/attribution and create a clearly named test connection.
4. Click **Run or resume fictional demo**. This intentionally adds one fictional patient and eight events to the selected TEST practice. Do not use real patient information.
5. Inspect the event history and open its patient journey. The original source is Google Ads; the later email touch does not replace it. The chain includes booking, attendance, consultation, completed treatment, USD 1,200 payment and USD 100 refund.
6. View September Growth: http://localhost:5181/growth?start=2026-09-01&end=2026-09-30. The demo adds USD 1,100 net collections to that practice's existing totals. It does not add spend or claim a campaign ROAS. Existing spend may already apply at source level.
7. Run the same connection's demo again: all eight events replay without duplicate patients or cash. Creating another connection intentionally creates another namespace/demo; it is not a global deduplication mechanism.

The UI shows immutable accepted-event evidence, newest received first, in pages of 50. Current patient cash may differ after audited corrections/exclusions; a replay does not undo those decisions. The demo's eight requests are independently atomic, not one batch transaction. If interrupted, earlier accepted events remain and retry resumes safely.

The original Harbor/Cedar smoke command expects exactly three seeded patients per practice. Running this optional demo in those practices deliberately changes that assumption; do not delete your data to make the old fixture assertion pass. The implementation was tested using the isolated PostgreSQL test database without adding demo patients to the saved practices.

## Version-one event contract

Routes:

- `GET/POST /api/patients/attribution/` — list/create sandbox connections; create body: `name`, UUID `request_id`.
- `GET /api/patients/attribution/{connection_id}/events/?page=1` — accepted events.
- `POST /api/patients/attribution/{connection_id}/events/` — ingest one event.

Example fictional lead body:

```json
{
  "event_id": "form-submission-001",
  "subject_id": "test-person-001",
  "kind": "lead",
  "data": {
    "first_name": "Fictional",
    "last_name": "Patient",
    "lead_at": "2026-09-02T12:00:00Z",
    "original_source": "google_ads",
    "original_campaign": "TEST campaign",
    "original_landing_page": "https://example.com/test",
    "original_at": "2026-09-01T12:00:00Z"
  }
}
```

The other kinds are `touch`, `booked`, `attended`, `consultation`, `treated`, `payment`, `refund`. All require the same `subject_id` and an explicit `data.occurred_at`. Touch accepts source/campaign/landing-page fields. Outcome events reuse the journey schema; booking events do **not** create calendar appointments or synchronize their status.

Payment data requires `amount`, `currency: "USD"` and `occurred_at`. Refund data also requires `payment_event_id`, referring to a payment event in this connection for this subject. The server resolves internal links and generates a namespaced receipt reference. No internal patient/payment/practice IDs may be forged through the envelope. Non-USD cash, pending-status fields, future timestamps and excessive or pre-payment refunds are rejected. This sandbox treats a submitted payment kind as a fictional assertion; no processor authentication or settlement verification occurs.

Unmatched subjects/payments return 409; deliver the missing lead/payment first and retry. They are not automatically linked or persisted in a review queue. Validation failures return 400; unauthorized/non-TEST writes return 401/403; foreign connections return 404. The caller currently owns retry and error retention. Success: 201 for new evidence, 200 with `replayed: true` for an identical retry. All errors leave the current event's transaction unchanged.

## Attribution definitions

Original attribution stays immutable; unknown/missing source stays Unknown. Leads use their lead timestamp. Booked/treated counts use distinct patients with those event dates. Cash uses receipt dates and existing exclusions/corrections. Growth dates are inclusive UTC calendar days. Collected revenue is included receipts less linked refunds, never invoice/deal value. First-touch source receives attribution; campaign is retained on the patient but campaign reporting/spend matching is not yet implemented. Missing/zero spend never produces infinite ROAS. This measures attributed revenue, not causal incremental lift.

## Next increments, in order

1. Website intake adapter: consent-aware capture of approved source parameters, dedicated restricted server credentials, form handling for mixed platforms, anti-abuse controls, retention limits and no patient data in marketing tags. This sandbox JWT endpoint is not the public form endpoint.
2. Identity reconciliation: authorized mapping across website/booking/payment connections, review of ambiguous matches and a durable failed/unmatched-event queue. Never merge patients by name alone.
3. One selected booking/payment vendor pair: verified webhook signatures, source-specific money/status semantics, retries, backfill, mapping and reconciliation. Distinguish capture, settlement, refund, chargeback and payout fees; do not count pending authorizations as collections.
4. Google Ads campaign/spend imports: explicit account/practice/campaign mapping, currency and timezone handling, no double counting alongside manual spend. Campaign-level revenue and tracking-coverage reporting.
5. End-to-end staging acceptance: replay actual provider sandbox deliveries, reconcile totals, restart/recover, exercise tenant isolation and validate payload privacy before any real-client pilot.

Implementation choices: sandbox first, admin JWT only, connection-scoped identities, synchronous rejection instead of persistent unmatched queue, current USD/UTC/first-touch rules. These are bounded initial choices, not a declaration that the automation requirement is fulfilled.

## Healthcare data boundary

The full identifiable journey belongs in the protected CRM. Google Analytics must not receive PHI and does not offer a BAA for Analytics. Google enhanced-conversion policies restrict sensitive health conversions. Consent or hashing alone does not make prohibited sharing permitted. A future page/event allowlist must be reviewed against the actual practice website and data flow; no Google tags should be installed in the CRM or patient-facing care/payment flows by this increment.

Official references checked October 12, 2026:
- https://support.google.com/analytics/answer/13297105?hl=en
- https://support.google.com/adspolicy/answer/7475709?hl=en
- https://developers.google.com/tag-platform/security/guides/consent

Production hosting, backups/restoration, independent security/privacy review, load/accessibility checks and human acceptance remain outstanding. A working sandbox does not establish real-client readiness.

## Verification for this increment

The full PostgreSQL patient suite passed all 134 tests, including ten new intake cases and eleven setup-command cases. After adding explicit API refund checks equivalent to the database guards, all ten intake tests and focused Ruff passed again. Svelte check passed with zero errors/warnings; changed-route/sidebar ESLint, backend Ruff, Django system check, migration drift and whitespace checks passed. A complete production build returned exit code 0 with the Node adapter; existing empty-env-chunk and slow-hook notices remain.

All 93 live setup checks passed. All 258 pre-existing practice/table fingerprint groups were unchanged after migration and normal Docker recovery; nine new groups were empty. Existing real-HTTP verification passed 101 isolation rejections and 32 authenticated pages, with unchanged demo totals and snapshot. The new Attribution API/page passed read-only HTTP checks in both TEST practices; anonymous requests and unknown-connection writes were rejected. No saved patient records were added or changed. Successful ingestion/replays/concurrent writes were tested only in the isolated test database.

Browser automation timed out, so visual review and clicking the demo button in a browser remain unverified. Human acceptance, load/accessibility/security/privacy review, private backup restoration and live-provider verification were not performed. Runtime stalls required normal service/Desktop restarts; interrupted runs were not counted as passes.
