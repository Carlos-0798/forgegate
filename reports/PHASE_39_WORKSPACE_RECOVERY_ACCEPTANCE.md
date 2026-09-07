# Phase 39 — coordinated workspace backup and recovery

Date: 2026-09-07. Scope: Windows Local Alpha, isolated synthetic stores and local
CLI acceptance. No owner database, running Dashboard, GitHub repository, MSP430
device or firmware was modified. No real-browser/OS accessibility test is claimed
for this CLI-only addition.

## Delivered behavior

`workspace backup` captures candidate v9 and job v3 databases while holding both
SQLite writer reservations. Running jobs block backup; queued input, completed
results and historical events remain intact. A strict three-member stored ZIP
includes a versioned manifest with both database hashes. Publication cannot
overwrite a competing target.

`workspace verify-backup` validates a private disposable copy, exact member/hash
contracts, SQLite structure and job-to-historical-candidate associations.
`workspace restore` requires a separately retained archive hash, creates a new
directory, rehashes both copied databases and publishes `RESTORED.json` last.
It does not alter launch settings, replace live data, run tasks or import keys.

`workspace retention-plan` evaluates an explicit cutoff against a verified
snapshot. Active, bound and recent tasks are retained; old unbound terminal tasks
are marked for archival review only. Audit/idempotency records are retained and
no storage quota is reclaimed. Live archival/purge remains the next engineering
slice and requires renewed authoritative-state checks in its implementation.

The existing job-history reader was extracted for reuse on a pinned read
transaction, avoiding unnecessary writer acquisition during backup validation.
It also now checks the SQL event revision against the canonical event record.
Existing Dashboard/CLI routes and schema versions are preserved.

## Expected versus actual

| Test condition | Expected and observed |
|---|---|
| Two stores, three job states | 1 SUCCEEDED, 1 QUEUED, 1 CANCELLED; 8 event rows |
| Snapshot/restore readback | All candidate and job table rows equal to the originals |
| Independent CLI recovery | Backup, hash verification, restore and planning pass in separate processes |
| Restored queued execution | SUCCEEDED revision 4; original queued task stays QUEUED |
| Synthetic test output | total 4, passed 3, failures 1, errors 0, skipped 0, duration 0.5 s; evidence status failed |
| Concurrent writers during copying | Both database writer attempts are rejected while reservations are held |
| Existing writer or running job | Backup refuses and publishes no archive |
| Committed WAL and terminal candidate | Exact retained records, evidence and PASS attestation readable after cold restore |
| Candidate advanced since submission | Exact historical association retained; current execution guards remain separate |
| Warning/rejected job results | REVIEW_REQUIRED and REJECTED survive recovery without fabricated assemblies |
| Existing backup/restoration directory | Refused; existing content retained |
| Corrupt/unsafe archive | Hash mismatch, traversal, wrong members, duplicates, malformed manifest and unsupported compression refused |
| Copy interrupted before readiness | WORKSPACE_RESTORE_INCOMPLETE; no RESTORED.json, original stores unchanged |
| Retention | Active/bound/recent retained; old unbound terminal marked REVIEW_ARCHIVAL; zero deletions |

The retained independent-process [JSON receipt](PHASE_39_WORKSPACE_RECOVERY_EVIDENCE.json)
records an exact synthetic archive hash and test values. Its private databases and
ZIP were temporary and removed by the smoke; they are not portfolio assets or a
user recovery point. Hashes vary with local creation times and random job IDs.

## Verification

- 48 focused workspace regressions pass.
- Workspace backup/CLI modules: 100% branch-aware coverage, 323 statements and
  36 branches. This is test coverage, not proof of all failure scenarios.
- 103 combined workspace/core-job/Dashboard-job regressions pass.
- `tools/verify.py` completes with exit 0: 1,149 passed, 3 skipped; 95.57%
  branch-aware coverage over 11,794 statements and 3,112 branches.
- Ruff and formatting pass (283 files); strict mypy passes (105 source/tool files).
- 127 existing frontend host interaction tests pass. Production assets are
  unchanged; their five-file inventory and both OpenAPI drift gates pass.
- 46 document and 3 artifact JSON Schema contracts pass committed-byte checks.
- Existing CLI/authenticated REST smoke matches all 33 expected results.
- `tools/release_smoke.py` completes with exit 0 and final PASS: sdist/wheel build,
  required source manifest, independent clean installation and the new workspace
  recovery smoke all pass. The installed smoke reproduces the same exact test
  summary and original-store preservation. Existing temporary HTTP startup/shutdown
  checks also pass; optional serial import opens no device.

During development, initial checks caught missing foreign-key configuration on
the reservation connection and the CLI framework's default rejection of timezone
suffixes. Both were corrected before acceptance. The synthetic smoke initially
looked for evidence status inside the numeric summary; it now asserts the actual
contract's separate status field as well as every expected numeric value.

## Limits and follow-up

These backups include private project data and queued report bytes; they are not
encrypted or redacted. SQLite free pages can retain logically released material.
Source directories must be owner-controlled local storage. Temporary files can
remain after abrupt interruption; directory-entry power-loss durability, automatic
failover and network/cloud storage operation are not certified.

Verification replays referenced candidate histories and job consistency checks,
not every unrelated candidate/audit/idempotency document or administrator-edited
trigger body. Hashes establish byte integrity and declared association, not source
producer authentication. Signing keys, trust files, original terminal-report
files, plugin-run storage and UART history are outside the archive.

No live purge, scheduler, background worker, automatic service restart, hardware
measurement, GitHub synchronization or production recovery is added. Existing
spoken Narrator, Windows high contrast and real Remote Desktop gates remain open.

For operator reproduction and manual acceptance, follow
[WORKSPACE_RECOVERY.md](../docs/WORKSPACE_RECOVERY.md).
