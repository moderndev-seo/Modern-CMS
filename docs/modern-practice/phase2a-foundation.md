# Fictional integration foundation — Phase 2A

This API-only foundation is implemented locally and awaiting final review/publication. It does not receive events, connect vendors, create patients, or record money. Keep it disabled for saved practices and production. Frontend/backend ports remain 5181/8000.

## Configuration and identity

The [environment reference](../reference/environment-variables.md#fictional-integration-foundation) documents the disabled-by-default feature flag, explicit TEST organization UUID allowlist and signed audience. Use only an isolated fictional database for acceptance work. A practice is selected solely from a verified credential; supplied organization selectors in body/query fields are rejected with 403, including matching values, and conflicting organization headers are rejected. JSON command bodies are limited to 16 KiB. These restrictions never grant access to an unallowlisted practice.

An active administrator's human JWT manages metadata. Staff, PATs, organization keys, portal credentials and service credentials cannot manage it. Service credentials can only call the metadata probe. They cannot read patient, Contact, finance or other existing CRM routes. Service identity is distinct from a human User/Profile.

## API surface

All paths below are relative to `/api/integrations/v1/`. Commands require a UUID `request_id`; connection/credential mutations also require the current `expected_revision`. Responses are private/no-store. There are no PATCH, DELETE, bulk-export or event-ingestion routes.

| Path | Method | Purpose |
| --- | --- | --- |
| `namespaces/` | GET, POST | List or establish an immutable fictional provider/account namespace. |
| `namespaces/{id}/` | GET | Administrator detail, including the synthetic account binding. |
| `connections/` | GET, POST | List or establish a fictional connection with a fixed versioned manifest. |
| `connections/{id}/` | GET | Read current metadata and revision. |
| `connections/{id}/state/` | POST | Pause, resume or terminally revoke, with a fixed reason. |
| `connections/{id}/credentials/` | GET, POST | List nonsecret metadata or issue/rotate a probe credential. |
| `connections/{id}/credentials/{key}/revoke/` | POST | Revoke a selected credential for retirement/operator action. Use connection revocation for compromise so all keys are revoked. |
| `connections/{id}/audit/` | GET | Read paginated immutable lifecycle audit. |
| `service/probe/` | GET | Service-only authentication probe returning limited connection metadata. |

Credential expiry is required and at most 30 days. At most two non-revoked credentials occupy slots, including expired credentials until explicitly revoked. Rotation permits zero overlap or at most 24 hours, never extending the old expiry or an earlier retirement cutoff. The old credential is denied at and after `retire_at`; no background job is needed. Connection revocation revokes every credential. Signing-key verification fallback never bypasses stored revocation.

Issuance returns the raw credential once. An identical command retry returns its recorded nonsecret result without redisclosing or regenerating it. If the response is lost, revoke the orphaned credential and issue with a new request ID. Never put credentials in URLs, documentation, public repositories or screenshots. List/detail responses omit hashes and raw credentials. General namespace lists omit account bindings.

## Failure monitoring

Rejected integration requests receive an opaque server-generated `X-Integration-Request-ID`. Caller-supplied IDs are not trusted for monitoring. `integrations.monitoring` emits only a fixed reason and that ID; it does not log headers, tokens, bodies, practice identifiers or exception text. Validation responses are generic so rejected values cannot be echoed. Unexpected integration view exceptions roll back and return generic 503.

The five counter labels are `invalid_authentication`, `authorization_denied`, `unavailable_route`, `service_unavailable` and `request_rejected`. Counters are thread-safe, process-local and saturating; they reset on process restart. Their internal snapshot is not a public API. This is bounded fictional-phase instrumentation, not centralized metrics, durable alerting, a request-rate limit, or a system-wide logging audit. Production monitoring remains separate work.

## Verification and limitations

Use the repository's restricted PostgreSQL security job: `python -m pytest -m postgres_only --no-cov --migrations`. SQLite is not security/RLS evidence. [The validation report](phase2a-validation.md) and [current handoff](PROJECT_STATE.md) record exact runs, corrected failures, migration/restart evidence and remaining gates.

The schema adds four practice-scoped metadata tables and self-contained immutable/relationship/RLS guards. Existing patient attribution and receipt semantics are unchanged. Upgrade and restart rehearsals used only fictional data. Disable the feature as the operational rollback; do not drop audit-bearing tables or reverse the guard migration. No production recovery, live vendor compatibility or deployment is implied by the local rehearsal.

Architecture 0.2.0 and A01–A10 remain unchanged. No Phase 2B inbox, worker, review queue, clinical or financial projection is included. Independent review and separate publication/merge approval remain required.
