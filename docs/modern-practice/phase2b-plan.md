# Phase 2B — Durable acceptance implementation plan

Status: local acceptance and retention increments after PR #3 merge, October 19, 2026. Inbox/pending/conflict schema, validation/encryption, explicit receive scope and transactional HTTP acceptance are implemented locally. No worker or domain projection exists. See [acceptance increment](phase2b-acceptance.md). See [storage increment](phase2b-storage.md). Baseline main: `9b61c4d8d217e8c2e40c2885b2505142749141fb`. Local branch: `codex/integration-durable-acceptance-2b`.

See the [validation and acceptance evidence map](phase2b-validation.md) for release checks and review gates.

## Requirements carried forward

[Roadmap I](universal-journey/I-roadmap.md) defines durable acceptance after 2A: acknowledge only committed records, return the original receipt for identical retries, reject changed content under a delivery key, reject malformed/oversized input and unauthorized clinical assertions, and never report success after database failure. [Contract D](universal-journey/D-data-and-events.md) separates transport delivery, validated input and canonical observations. [Decisions J](universal-journey/J-product-decisions.md) preserves the fictional boundary and separately scoped phases. The owner's merge-and-proceed instruction authorizes continuation; it does not supply live-provider or pending Group B/C policy approvals.

Reuse Org, ProviderNamespace, IntegrationConnection, IntegrationCredential, signed service-principal authentication, transaction-local tenant context and the existing forced-RLS test partition. Keep current probe credentials probe-only. Do not reinterpret existing grants or mutable caller fields as receipt authority. Human/PAT/org-key/portal authentication cannot call service ingress.

No original attribution, patient, contact, appointment, journey event, receipt, invoice or Growth calculations change. No sender network calls, worker, patient linkage, canonical clinical/financial decisions, automatic communications or real payloads in this increment. Original demo and saved databases stay untouched. Ports remain 5181/8000.

## Proposed implementation choices

These are implementation choices, now partly implemented locally as described in the increment reports; they do not expand approved business policies:

1. Add a versioned fictional ingress capability and explicit receive scope. Do not modify immutable 1.0 manifest snapshots or silently widen already-issued credentials. New connection/credential selection is explicit; existing fixtures and probe behavior remain compatible.
2. Add a practice-bound immutable inbox/delivery receipt carrying namespace, connection, issuer credential, delivery key, input schema/adapter versions, server receipt time, authorization generation, transport digest and semantic digest. Use a bounded unique namespace/delivery key so reconnects cannot silently duplicate the same source delivery; document why this key is transport identity, not patient or economic identity.
3. Keep safe validated replay input separate from canonical observations. Bound fields and byte size, reject arbitrary text/unknown fields, and accept only synthetic fixture identifiers. Follow D's encrypted minimal-input requirement; select and document a versioned encryption/key configuration before storing replay content. Never derive a claim of live-data protection merely from fictional test acceptance. Retention/purge behavior must not erase receipt identity or allow an expired delivery to be reaccepted as new.
4. Atomically create immutable receipt evidence and a durable pending-work marker; Phase 2C later owns leases, scheduling, attempts and normalization. A 2B receipt means accepted for later processing, never applied or verified. Avoid a live enqueue dependency at acknowledgment time.
5. Acquire the established practice/connection locks, revalidate credential and connection generation in the acceptance transaction, and finalize deferred guards before restoring tenant context. A success response leaves the transaction only after commit; exceptions fail closed without payload/secret logging.
6. Duplicate same-key/same-semantic-hash input returns the original receipt without another work item. Same-key/changed-semantic-hash returns 409 and safe bounded conflict evidence. Source observation uniqueness and irreversible financial effects remain later, distinct contracts.
7. Add self-contained migrations with forced RLS, immutable receipt fields and same-org relationship checks; retain namespace/connection identity. Do not reuse the append-only lifecycle audit table as an arbitrary payload store. Decide a typed ingress audit extension only for safe accepted/conflict metadata.

## Acceptance sequence

- Baseline existing 2A and patient access tests before expanding scope.
- Restricted PostgreSQL API and direct SQL tests for wrong-practice reads/writes/FKs, forged tenant/verification fields, unauthorized scope/source type and disabled or revoked connection.
- Concurrent identical and changed-content deliveries: one receipt/work marker, deterministic replay or 409, no patient/cash effects.
- Failure injection at insert, deferred guard and commit: no success or partial receipt/work pair; subsequent retry succeeds exactly once.
- Missing/malformed/oversized/unsupported-version input: bounded rejection with no retained arbitrary body or sensitive log output.
- Credential rotation/revocation races: namespace stable; no stale positive authentication grants new receipt after revocation wins.
- Fictional migration upgrade and normal persistent test-container restart: old snapshots unchanged, accepted receipts and pending work survive. No demo volume operations.
- Exact test routing, lint/format, migration drift, compatibility, package and documentation checks; fresh hosted evidence only after separately authorized publication. Review all newly surfaced findings before proposing merge.

Next task: complete full compatibility checks and requirements/independent review; retention migration/restart, fictional key lifecycle and package verification have passed locally. [Retention increment](phase2b-retention.md) implements a fictional 24-hour window and bounded operator purge with permanent receipt identity. Phase 2B is not release-approved. Phase 2C workers, 2D review/health and 2E two-adapter conformance remain subsequent increments.
