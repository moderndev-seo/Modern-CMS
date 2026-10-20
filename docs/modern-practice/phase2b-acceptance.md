# Phase 2B fictional receipt acceptance — local increment

Uncommitted implementation on `codex/integration-durable-acceptance-2b`, based on merged PR #3. Publication needs explicit approval. This extends the [storage increment](phase2b-storage.md); it is not Phase 2B release approval or a live integration.

## Explicit requirements and implementation choices

Architecture v0.2.0 requires practice-bound authorization, durable commit before acknowledgment, stable delivery identity, original receipt on identical retry, changed-content conflict, no clinical authority from acquisition sources and no patient/cash side effects. These are implemented through the existing Org/connection lock order, service principal and forced RLS.

The implementation chooses new immutable manifest IDs `fixture_a:acquisition:ingress-v1` and `fixture_b:acquisition:ingress-v1`, version 1.1. All original 1.0 snapshots remain unchanged. Existing connections cannot change manifest; a new explicitly selected connection is needed. Issuing the single scope `integration.receive` requires a receive-capable manifest, enforced in both the application and PostgreSQL guard. Legacy probe grants remain probe-only. Receive grants cannot probe, administer metadata or access patient/CRM routes. No human JWT, PAT, organization key or portal credential is accepted by the receiver.

The new append-only `IntegrationDeliveryConflict` table stores the accepted inbox reference, submitting credential and attempted semantic digest. It stores no rejected raw body. Same receipt/credential/digest retries create one conflict record. SQL guards enforce same-practice and namespace links and immutable history. Accepted receipt evidence is already immutable and includes the authenticated source credential.

## API and configuration

`POST /api/integrations/v1/service/events/` accepts the exact bounded `fixture.ingress/1` synthetic envelope described in the storage document. The receive flag is separate and defaults off. Foundation flag, TEST UUID allowlist, dedicated audience, explicitly issued receive credential and dedicated replay encryption key remain necessary. See [environment configuration](../reference/environment-variables.md#fictional-receipt-acceptance-phase-2b-local-development). Tests/rehearsals use isolated fictional practices only.

| Outcome | HTTP | Meaning |
| --- | --- | --- |
| First valid delivery | 202 | Receipt and durable pending marker committed; not normalized, linked, applied or verified. |
| Same namespace/delivery ID and canonical content | 200 | Original receipt ID and received time; no extra work or evidence row. |
| Same key with changed canonical content | 409 | Conflict metadata committed; original receipt/evidence unchanged. |
| Wrong source authority or grant | 403 | No accepted receipt. |
| Revoked/expired/retired credential | 401 | No positive authorization cache. |
| Malformed/oversize/unsupported input | 400 | No accepted receipt or arbitrary rejected payload retention. |
| Feature disabled | 404 | Receive unavailable. |
| Encryption, database, deferred-constraint or commit failure | 503 | No success acknowledgment or partial receipt/work pair. |

Only opaque receipt/delivery IDs, server receipt time and `status=accepted` are returned. Responses are private/no-store. The outer middleware transaction completes before returning the response; the pending-work deferred constraint is checked while the authenticated tenant context remains selected. Practice locking serializes deliveries, credential changes and reconnects; namespace uniqueness remains the database backstop.

Equivalent UTC times and JSON formatting normalize to the same semantic hash; the original transport-byte digest remains separate. Rotation preserves namespace/delivery identity. Different practices have independent delivery identities. Old receipt replay does not require decrypting its stored evidence, and does not claim that evidence remains replayable if the operator has removed its key.

## Verification and remaining boundaries

Current exact results are in PROJECT_STATE: 421 broad security passes, then 142 final integration passes including two additional test-only cases; zero skips/failures. Six environment-reference checks and lint/format/schema-drift checks passed. The isolated 2A-to-2B upgrade preserved all-field legacy fingerprints. A normal persistent test-database restart and fresh process preserved receipt identity, pending work, encrypted evidence and decryption, and unchanged legacy/metadata fingerprints. Disabling receive preserved existing patient access. Tests include duplicate/conflicting concurrency on separate database connections, forced real commit failure, pending/deferred/encryption rollback, credential rotation and a revocation that wins before waiting receipt acceptance, database reconnect persistence, wrong-tenant reads and conflict links, same delivery ID in different practices, and SQL denial of receive scope on a legacy manifest.

The subsequent [retention increment](phase2b-retention.md) adds expiry and one-way purge while retaining delivery identity. Pending before full Phase 2B completion: full compatibility checks and final release review (retention migration/restart, fictional key recovery, package and strict docs checks now passed locally), and independent review/authorized publication with hosted checks. No worker, retry scheduler, normalization, canonical observations, identity review, patient linkage, treatment confirmation, financial posting, attribution reporting changes or live vendor support. Two pinned fixture transports exist; full two-adapter conformance remains Phase 2E. No frontend change or browser acceptance is claimed.
