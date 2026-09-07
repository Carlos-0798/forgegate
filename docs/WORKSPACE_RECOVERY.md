# Coordinated workspace backup and recovery

Phase 39 adds owner-operated CLI protection for the candidate **v9** and report-job
**v3** databases together. The Dashboard continues to use these same stores.
Backup, verification, restored-copy creation and retention planning are local
operations; no browser file paths or service-control endpoint is added.

## Create and verify a backup

Pause submissions and foreground parsing during maintenance. Wait for running
jobs to finish, or review their existing cancel/expired-recovery operations.
Running jobs cause `WORKSPACE_RUNNING_JOBS`; backup never cancels them for you.
Queued jobs are retained with their exact pending request bytes.

Use existing owner-restricted local directories. The examples assume the Python
3.12 environment is active and `work/backups` already exists:

```powershell
python -m forgegate workspace backup work/candidates.db work/jobs.db work/backups/checkpoint.zip
python -m forgegate workspace verify-backup work/backups/checkpoint.zip --sha256 EXACT_SHA256_FROM_CREATION_RECEIPT
```

Keep the creation receipt separately from the archive. Verification without
`--sha256` checks internal hashes and structure, but reports
`expected_hash_matched=false`. A supplied hash binds bytes to that earlier
receipt; it does not authenticate the original producer or sign the backup.

The ZIP contains exactly `candidates.db`, `jobs.db` and a canonical
`forgegate.workspace-backup.v1` `manifest.json`. Members are stored without
compression. The manifest records both member sizes/hashes, store versions,
local creation time and scope. The receipt includes counts and the archive hash,
without absolute paths or record content. It is an operational receipt, not a
release attestation.

The implementation acquires `BEGIN IMMEDIATE` reservations in job-then-candidate
order, then copies both stores with separate read connections and SQLite's backup
API while both reservations remain held. This prevents ordinary SQLite writers
from committing between the two snapshots. The source transactions always roll
back and change no logical records. WAL coordination sidecars may change.
A competing writer causes bounded `WORKSPACE_BUSY`; no target is published.
The pair is a stable committed state, not a distributed business transaction.

After releasing the reservations, validation checks SQLite integrity/foreign keys,
current required schemas/objects, job quotas, canonical current/event/result
documents, event revisions and state/time ordering. Every job must resolve to its
exact historical COLLECTING candidate snapshot and matching project/commit.
Referenced candidate histories use the existing domain reader. A candidate that
has since advanced is valid historical association, not permission to run or bind
an old queued task. Execution and binding still recheck current state.

Unreferenced candidate histories, all audit/idempotency payloads, and exact trigger
SQL are not exhaustively replayed. A structurally valid backup is not a blanket
proof of all historical records or administrator-resistant integrity.

Publication uses a same-filesystem hard link into a new target name. Existing
files, directories or sidecars are refused. There is no overwrite fallback.

## Restore a separate copy

```powershell
python -m forgegate workspace restore work/backups/checkpoint.zip work/recovered --sha256 EXACT_SHA256_FROM_CREATION_RECEIPT
```

Restore requires the expected archive hash and a **new directory**. Validation
completes on disposable copies before the destination is reserved. Both databases
are copied and rehashed, then `RESTORED.json` is published last. The command
reports `WORKSPACE_RESTORED_COPY` only on completion. Existing live database paths
and launch configuration are never replaced or updated. Nothing executes a job,
creates a browser session, opens UART or changes trust-store/key files.

For owner acceptance:

1. Check successful exit `0`, `expected_hash_matched=true`, and `RESTORED.json`.
2. Compare candidate IDs, revisions, history, evidence and attestation with the
   expected records using existing `candidate` and `jobs` read commands.
3. Verify queued/completed/cancelled task counts and exact retained result values.
4. If a Dashboard rehearsal is needed, stop the intended old service deliberately,
   then use the [existing launcher](WINDOWS_DASHBOARD_OPERATIONS.md) with **both**
   restored database paths, the appropriate external trust store and a fresh
   browser activation. Select another port for an isolated side-by-side rehearsal.
5. Explicitly review any queued execution. Do not run both copies as interchangeable
   live workspaces: they can diverge and reuse the same historical identities/keys.

`WORKSPACE_RESTORE_INCOMPLETE` means a newly reserved directory can contain partial
files. Do not launch from it or retry into it. Retain it for inspection and retry
into another new directory after diagnosing the failure. Abrupt interruption may
leave `.RESTORED.pending` or temporary staging files. An error during cleanup after
marker publication can coexist with a complete copy; independently inspect it.
No automatic deletion of unknown directories is attempted. This is a recovery
rehearsal mechanism, not power-loss certification, automatic failover or repair.

## Retention planning

```powershell
python -m forgegate workspace retention-plan work/backups/checkpoint.zip --sha256 EXACT_SHA256_FROM_CREATION_RECEIPT --as-of 2026-09-08T00:00:00Z --terminal-before 2026-09-01T00:00:00Z
```

Supply offset-bearing timestamps. `as-of` must not predate the snapshot or any job;
the cutoff cannot be later than `as-of`. These are explicit local observations,
not trusted time. The cutoff is exclusive: equality is retained.

| Snapshot observation | Plan |
|---|---|
| Queued job | RETAIN / ACTIVE_JOB |
| Result exactly matches the candidate's immutable evidence binding | RETAIN / BOUND_EVIDENCE |
| Terminal job updated at or after cutoff | RETAIN / WITHIN_RETENTION_WINDOW |
| Older terminal job with no matching binding | REVIEW_ARCHIVAL / TERMINAL_UNBOUND_REVIEW |

The plan changes no data and is **not executable deletion authority**. It retains
all audit and idempotency records; `capacity_reclaimed=0`. `REVIEW_ARCHIVAL` does not
mean safe to delete: exports, external consumers and compliance requirements are
not discoverable from this snapshot. Later purge design must recheck the live
revision/binding, retain historical identity/replay semantics, and demonstrate
archive readback. Backup rotation, automatic cleanup and live quota reclamation
remain separate work.

## Limits and private-data handling

- Combined database payload: at most **1 GiB**; archive: at most 1 GiB + 128 KiB;
  manifest: 16 KiB. The ZIP central directory is bounded before parsing. Exact
  members, sizes, hashes, storage method and canonical manifest are validated;
  traversal names, extra/duplicate members and unsupported formats fail closed.
- Default cooperative deadline: 30 seconds, `--timeout-seconds 0.1..300`.
  Lock acquisition waits at most 0.1 seconds per database. OS I/O or native library
  operations can exceed a cooperative deadline; this is not a hard real-time bound.
- Exit `0` means the requested operation succeeded, `3` is a sanitized operational
  refusal, and `2` is invalid CLI syntax/ranges. Inspect state before retrying.
- Backups and temporary copies are **unencrypted** and inherit directory access
  controls. Use owner-controlled local storage with sufficient space for snapshots,
  archive, verification copies and restored copies. Network/cloud-sync storage and
  hostile path replacement are not validated deployment modes.
- Candidate records, job results, pending report bytes and audit identities are
  private. SQLite free pages may retain logically released data, including old
  request/lease material. This workflow does not redact, securely erase, install
  ACLs or implement encrypted key custody. Never commit these ZIPs/databases or
  include them in portfolio screenshots.
- Signing keys, external trust/identity files, original terminal-report files,
  plugin-run databases and broker outputs, browser sessions and UART history are
  not collected. Retain those separately as required; no path embedded in a
  database record is dereferenced.
- Schema migration is explicit and separate. Older candidate/job stores are
  refused; the [candidate-only backup](STORE_BACKUP_OPERATIONS.md) remains available
  for its documented scope. No historical owner, actor or result is fabricated.

## Reproduce the acceptance

```powershell
python -m pytest tests/test_workspace_backups.py
python tools/workspace_backups_smoke.py
```

The smoke uses new CLI processes and synthetic stores, compares all table rows,
verifies no-overwrite behavior, then runs a restored queued report. Expected result:
four tests, three passed, **one failed**, duration 0.5 seconds; job collection
completes successfully while the evidence status remains `failed`. It leaves the
original synthetic workspace unchanged and emits PASS only after temporary cleanup.
The same smoke is included in clean-wheel installation acceptance.

Implementation references: [SQLite backup API](https://www.sqlite.org/backup.html),
[SQLite transaction reservations](https://www.sqlite.org/lang_transaction.html),
and [Python 3.12 ZIP handling](https://docs.python.org/3.12/library/zipfile.html).
These define the storage primitives; ForgeGate's application guarantees are
bounded by the tests and limitations above.
