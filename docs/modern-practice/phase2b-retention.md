# Phase 2B fictional replay retention — local increment

This extends [receipt acceptance](phase2b-acceptance.md). It remains uncommitted and unpublished; it is not a live-provider feature or Phase 2B release approval.

## Requirements and implementation choices

The architecture requires bounded retention of replay evidence without forgetting delivery identity or allowing duplicate effects. The implementation chooses a fixed **24-hour window from server receipt creation**, identified by `fixture-24h-v1`, for fictional TEST inputs only. This is not an approved retention policy for real patient data. Source timestamps do not extend the window.

Two additive inbox fields record the immutable retention policy and nullable `replay_purged_at`. No existing patient, receipt, attribution or other business schema changes. The purge timestamp is a permanent tombstone on the original receipt, not a new clinical event. Existing local inbox rows receive the same policy and retain their original creation time.

`open_receipt` re-reads the row in the current tenant context and rejects missing, unknown-policy, purged or expired evidence. The exact boundary is `now >= created_at + 24 hours`. Missing keys and invalid ciphertext also fail closed. The lower-level `open_envelope` remains a cryptographic primitive; a future authorized replay consumer must use the policy-enforcing entry point. There is no replay API or worker yet.

## Operator cleanup

From the configured backend environment, select one explicitly allowlisted fictional TEST practice:

```sh
python manage.py purge_integration_evidence --org TEST_PRACTICE_UUID --limit 100
```

Use its actual UUID; the placeholder is deliberately invalid. The command requires trusted operator shell access and the existing database configuration. It grants no HTTP or service-credential maintenance authority. Limits are 1–1,000 rows per transaction; default 100. Repeat until the reported count is zero. No automatic schedule is installed.

Cleanup works with intake disabled or replay keys unavailable. It locks the practice and eligible receipts, removes only expired ciphertext, and records a database-stamped purge time. PostgreSQL rejects early/partial purge, restoring ciphertext, clearing/replacing the timestamp, changing the receipt identity or deleting the row. Batch failures roll back. Forced RLS and same-practice link guards remain active.

Receipt IDs, namespace/delivery identity, original times, hashes, credential/source bindings and pending markers remain. An identical later delivery still returns the original 200 receipt without new work. This acknowledges historical acceptance; it does not restore evidence or claim processing completed. A changed-content delivery remains a conflict. Retaining metadata indefinitely is a current fictional implementation choice, not a production deletion policy.

## Verification and limitations

The integration suite passed all 159 tests, including 17 retention cases: exact expiry, early/partial purge denial, database timestamp ownership, irreversible tombstones, preserved identities and pending markers, same-key retry after purge, tenant isolation, batch bounds, reruns, missing-key/disabled-intake cleanup and rollback. The full restricted PostgreSQL security partition passed all 440 tests, with zero failures/skips. Lint, 33-file formatting, migration-drift, strict documentation build and excluded-artifact inspection passed. See PROJECT_STATE for durations, warnings and remaining checks.

Expiry denies replay even if maintenance has not run; physical ciphertext remains until cleanup. Purging database ciphertext does not erase backups, already copied ciphertext or encryption keys. Key backup/recovery, production retention approval, automatic maintenance, monitoring and worker handling of expired pending work remain unresolved. The subsequent isolated rehearsal applied 0008/0009 while preserving every pre-existing inbox column and legacy fingerprints. A normal test-database restart and fresh process preserved unexpired evidence, purge tombstones and pending identity. Missing/wrong-key denial and correct-key restoration passed; this does not prove production backup restoration or disaster recovery. No live provider, patient matching, treatment verification, financial posting, browser change or production readiness is claimed.

### Subsequent recovery and package checks

Two additional key lifecycle/stale-object regressions bring the full integration suite to 161 passes, zero failures/skips (127 warnings). Old and new key versions can coexist; changing the active encryption version does not rewrite earlier receipts. Removing or replacing an older key prevents decrypting its evidence; restoring the exact key recovers unexpired, unpurged evidence. Purge remains irreversible through the application even when an old object still contains ciphertext. Keep historical keys available for evidence that remains eligible; there is no automated safe-key-retirement manager yet.

Wheel/source builds and outside-checkout installed-wheel imports, Django checks and seven templates passed using existing runner dependencies. Full compatibility suites and independent release review remain pending. See PROJECT_STATE for exact checks and private evidence locations.
