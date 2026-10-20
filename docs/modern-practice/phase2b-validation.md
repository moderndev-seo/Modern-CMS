# Phase 2B — Durable acceptance validation

The owner authorized publication for review on October 19, 2026. The candidate is based on merged PR #3 (`9b61c4d8d217e8c2e40c2885b2505142749141fb`) on `codex/integration-durable-acceptance-2b`. Separate independent review, hosted checks on the published head and owner merge approval remain gates. No live-provider or production-readiness claim.

## Scope and choices

This is a fictional acquisition-only receiver, disabled by default and restricted to explicit TEST practices. It reuses the Phase 2A service principal, Org/connection locks and forced RLS. Inbox, pending-work and conflict models are additive; existing patient, clinical, financial and attribution records are not projected into or altered. Seven additive migrations extend the existing integration schema. New immutable 1.1 receive manifests and single receive grants preserve legacy 1.0/probe behavior.

Implementation choices are documented in [storage](phase2b-storage.md), [acceptance](phase2b-acceptance.md) and [retention](phase2b-retention.md): strict synthetic UUID-only envelope, separate semantic and transport hashes, dedicated versioned Fernet encryption, one immutable pending marker per receipt, conflict digest metadata and a fixed fictional 24-hour replay window. No real retention policy is implied. Worker leases/attempts/normalization and canonical observations remain Phase 2C; introducing empty canonical-domain tables in 2B would add no exercised behavior.

## Acceptance evidence map

This is an implementation self-review and test map, not independent certification. Tests live under `backend/integrations/tests/`.

| Requirement | Evidence |
| --- | --- |
| Commit before acknowledgment; database failure cannot acknowledge | `test_commit_failure_never_acknowledges`; pending/encryption/deferred failures roll back the pair; outer tenant transaction commits before response escapes. |
| Same key/hash returns original receipt; changed hash conflicts | `test_accept_retry_conflict_audit_and_no_new_work`, `test_concurrent_deliveries_one_receipt`; append-only deduplicated conflict metadata, original receipt unchanged. |
| Namespace identity survives rotation and reconnect | Rotation/revocation tests, database reconnect and normal container restart rehearsals. |
| Practice isolation and same-practice relationships | Foreign parent-link tests, context-free denial, forced-RLS inventory, conflict links, same delivery ID independence across practices. |
| Separate authority and immutable manifest grants | Legacy receive-scope denial in API and SQL, receive cannot probe/impersonate human, forbidden authority fields and acquisition clinical assertions denied. |
| Bounded input and encrypted safe replay | Invalid/oversized/duplicate-key/unknown-field input coverage; transport versus semantic hashing; receipt/org/digest binding and tamper/key failures. |
| Expiry and purge preserve idempotency | Exact 24-hour boundary, early/partial purge denial, SQL timestamp ownership, irreversible tombstones, stale-object denial, bounded reruns and duplicate retry after purge. |
| Key lifecycle | Old/new versions coexist; removing or replacing an old key denies decryption; restoring the correct key recovers eligible evidence without rewriting receipts. |
| No domain effects; legacy preservation | No patient/cash writes, legacy all-field fingerprints through upgrade, retained patient access with receive disabled. |
| Persistence | Restricted-role 2A-to-2B upgrade and subsequent 0008/0009 upgrade; normal isolated database restart with fresh-process fingerprint checks, pending identity, active evidence and permanent purge facts. |

## Verification record

Final restricted PostgreSQL security: **442 passed**, zero failures/skips, 6,294 deselected, 406 inherited warnings, 196.09 seconds. PostgreSQL compatibility: **6,294 passed**, zero failures/skips, 442 deselected, 4,781 inherited warnings, 534.31 seconds. This includes the strict documentation and environment-reference checks without skips. SQLite compatibility: **6,285 passed, nine database-specific skips**, zero failures, 442 deselected, 4,772 inherited warnings, 781.62 seconds; **88.77% coverage**, above the unchanged 50% gate. No security cases were skipped. Test routing passed: 6,736 total = 6,294 compatibility + 442 security, including all 254 patient and 161 integration cases. Earlier focused integration run: 161 passed, zero failures/skips. Lint and 856-file formatting passed. Wheel and source builds passed; installed-wheel imports, Django checks and seven templates passed outside the checkout using existing runner dependencies. The strict docs build and excluded-artifact inspection passed; complete documentation tests are part of compatibility verification.

Test and rehearsal databases were isolated fictional environments. The security role was NOSUPERUSER/NOBYPASSRLS; the separate PostgreSQL compatibility role is not security evidence. No Docker volumes were deleted and the original demo was not migrated. Private scripts/logs and generated fixture keys remain outside the public clone.

## Limitations and review gates

No UI change or browser acceptance; no worker, retry scheduler, canonical observations, patient matching, clinical verification, financial posting, new reporting or live vendor adapter. Two pinned fixture transports are declarations; full two-adapter conformance remains Phase 2E. Receipt acceptance is not successful processing.

Cleanup is an operator command, not automatically scheduled. Expired ciphertext remains until cleanup; receipt metadata is retained indefinitely in this fictional implementation. Purging does not erase backups or previously copied ciphertext. Key restoration tests are not production key escrow, backup restoration or disaster-recovery certification. A future replay consumer must use the retention-enforcing entry point and add its own authorization; the cryptographic helper alone does not enforce retention. Group B/C business policies and live gates remain pending.

Independent technical review is still required; publication approval is not review approval or permission to merge. Any review findings must be fixed and checked on the corrected head. Hosted results must identify that head; local results cannot be relabeled as hosted checks.
