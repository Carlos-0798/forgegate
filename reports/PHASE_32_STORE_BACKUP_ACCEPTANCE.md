# Phase 32 — local candidate-store backup acceptance

Date: 2026-09-06. Evidence: **LOCAL_HOST_TEST**. GitHub work paused by owner.

## Delivered and tested

`candidate backup-store` creates a new standalone current-v9 snapshot using
SQLite backup from a read-only source connection. `candidate verify-backup`
checks an offline input on a disposable copy, optionally comparing a separately
retained SHA-256. Both print path-free operational receipts. See the
[operations guide](../docs/STORE_BACKUP_OPERATIONS.md) for limits and non-claims.

| Test | Expected and actual result |
|---|---|
| Active WAL with a terminal synthetic candidate | Committed candidate, profile, evidence, policy, evaluation, attestation and audit rows retained exactly across all 17 current tables |
| Concurrent uncommitted schema transaction | Pending table excluded; committed snapshot remains readable |
| Cold application readback | Candidate, evidence binding and attestation equal the source objects |
| Offline verifier | Original input bytes unchanged; expected SHA-256 matches; no input sidecars created |
| Missing, empty, non-SQLite or old-schema source | Reject; no destination published |
| Existing target, same path, directory or sidecars | Reject without overwrite/deletion |
| Target created by a competitor | Other owner's bytes retained; no overwrite fallback |
| Sidecar introduced during copy or before publication | Reject before accepting/publishing the snapshot |
| Wrong hash, corruption and injected integrity failure | Reject, not `VERIFIED` |
| Size limit and injected progress deadline | Reject and clean only owned staging |
| Unsupported hard-link publication | Fail closed; no partially published destination |

27 focused tests pass. The corruption/integrity and deadline injections are host
test controls, not observations of an actual production outage or power loss.
Initial fixture construction was corrected to use the actual attestation command
signature and explicitly closed SQLite connections. A pinned reader is used to
retain real WAL bytes, rather than accidentally testing an already-checkpointed
main file.

Full `tools/verify.py`: **973 passed, 3 skipped**, **95.34%** branch-aware
coverage across 10,730 statements and 2,884 branches; Ruff, formatting, strict
mypy across 96 source/tool files, committed assets/Schema/OpenAPI checks and
33/33 CLI/API interaction outcomes pass. The three skips remain unavailable
Windows symlink cases. The new backup module has **100%** branch-aware coverage
across 120 statements and 32 branches; this is tested coverage, not absence-of-bugs proof.

`tools/release_smoke.py` passes, including the new commands executed from a
clean installed wheel, expected-hash verification and repeated-target rejection.
No dependency or model Schema change was required. Existing frontend behavior
was not changed or manually re-accepted in this checkpoint.

## Local manual CLI sample

The existing **synthetic Phase 31** fixture was copied into a new local backup;
the user database and running 8131 service were not replaced or restarted.
Creation returned `BACKUP_CREATED`; independent verification with the returned
hash returned `VERIFIED` and `expected_hash_matched=true`.

- Size: **253,952 bytes**.
- SHA-256: `4f6f386219099725f8e2f9069c83ec65138cbdddc333209a1671e1b17bc5e358`.
- Retained sample: **4 candidates, 8 snapshots, 4 transitions, 1 project,
  1 profile, 9 release audit events**; this fixture has no evidence binding,
  evaluation or attestation. Those paths are exercised separately by the
  terminal-candidate automated fixture above.
- No backup database is included in the repository or portfolio gallery.
  Hash and aggregate counts describe the exact synthetic local sample only.
- Windows initially rejected `fsync` on a read-only file descriptor. The owned
  staging file is now opened read/write for flushing before publication. It
  does not open the source database for writing.

## Boundaries

No automatic restore, live-path switch, schema migration, record deletion,
raw-artifact export, encryption, producer authentication, serial access or
firmware action occurred. Existing browser pages are unchanged; no old screenshot
is relabeled as a new UI feature. Backups contain private project data and are
not portable assurance bundles. Structural verification does not prove every
domain-history invariant, correct source data or hostile-local-user resistance.
Live WAL read access can update coordination sidecars, but performs no source
logical writes. Filesystem/power-loss behavior outside the tested local setup
is not claimed.
