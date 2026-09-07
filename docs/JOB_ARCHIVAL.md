# Reviewed job archival

Phase 40 adds owner-operated, one-job-at-a-time **logical** archival. Terminal,
unbound tasks can release their live job slot and normalized-result quota only
after an exact, verified workspace backup and an explicit plan confirmation.
This is maintenance tooling, not a scheduler, browser deletion API or automatic purge.

## What changes, and what does not

| Item | After archival |
|---|---|
| Job identity, state, revision, timestamps and result fingerprint | Unchanged |
| State events and recorded actors | Retained byte-for-byte |
| Duplicate-request key and request fingerprint | Retained; resubmission returns the original task |
| Normalized result in the live job row | Set to NULL in the same transaction as the receipt insert |
| Original normalized result | Retained in the explicitly selected pre-archive workspace ZIP |
| Candidate state, evidence binding, policy and attestation | Unchanged |
| Receipt | Immutable metadata identifying the reviewed plan and original backup SHA-256 |
| Physical database size / secure erasure | Not performed; free pages and external copies may retain bytes |

`SUCCEEDED` still means parsing/assembly completed, not that tests passed. An
archive receipt is local CLI authority, not an authenticated operator signature.
Database triggers and canonical fingerprints detect accidental inconsistency;
they are not protection against a hostile owner who can rewrite the database.

## Owner workflow

Pause submissions, binding and execution during maintenance. Finish or explicitly
cancel/recover running jobs first; backup refuses RUNNING tasks. Keep all files
in owner-restricted local storage. The commands assume an active ForgeGate Python
environment and existing `work/backups` directory. Replace uppercase placeholders
with the values you reviewed; do not run these on a live workspace as a demo.

```powershell
python -m forgegate workspace backup work/candidates.db work/jobs.db work/backups/before-archive.zip
python -m forgegate jobs enable-archiving work/jobs.db
python -m forgegate workspace plan-job-archive work/candidates.db work/jobs.db work/backups/before-archive.zip JOB_ID --sha256 BACKUP_SHA256 --revision TERMINAL_REVISION --terminal-before OFFSET_TIMESTAMP --output work/archive-plan.json
```

`jobs enable-archiving` explicitly migrates v3 to v4; repeating it is a no-op.
For v1/v2, first use the existing `jobs migrate` command. Startup never migrates.
The v4 migration retains historical job/event bytes, creates immutable archive
metadata and protects archived rows from ordinary UPDATE/DELETE operations.
Keep the pre-migration backup; do not downgrade the v4 file or run older binaries
against it. `jobs init` continues to create v3 for compatibility.

Review the emitted plan: job/project/candidate, expected revision, result size,
result/assembly identities, source row/event fingerprints, current candidate
fingerprint, cutoff, original backup hash and manifest fingerprint. The plan
file is created exclusively; an existing output is never overwritten. Review is
read-only for both databases. Copy its `plan_fingerprint` into the confirmation:

```powershell
python -m forgegate workspace archive-job work/candidates.db work/jobs.db work/backups/before-archive.zip work/archive-plan.json --confirm-plan REVIEWED_PLAN_FINGERPRINT
python -m forgegate jobs archive-info work/jobs.db JOB_ID
```

Apply re-verifies the supplied ZIP, then reserves writers in job-then-candidate
order. It checks the exact current job row/events against the backup, terminal
state, revision, cutoff, result/assembly identity, candidate fingerprint and
current evidence binding. A result already bound to its candidate is protected,
including bindings that did not advance candidate revision. Future cutoffs and
naive timestamps are rejected. Candidate reservation stays held through the
single job-store transaction commit. A write/timeout failure rolls the result
and receipt back together.

An exact repeated apply returns the original receipt, without reclaiming another
slot. A different plan conflicts. Replay still requires the original verified
ZIP; inspect `archive-info` when the backup is unavailable. After an ambiguous
I/O result, inspect the receipt before retrying. A plan is not an authorization
token, and it does not freeze the workspace between review and confirmation.

## Readback and recovery

```powershell
python -m forgegate workspace archived-result work/backups/before-archive.zip JOB_ID --sha256 BACKUP_SHA256
python -m forgegate workspace archived-result work/backups/before-archive.zip JOB_ID --sha256 BACKUP_SHA256 --assembly
```

These read from a verified disposable copy; they do not rehydrate live records,
bind evidence or recursively open paths from a receipt. `--assembly` refuses
results with no assembly. Failed/cancelled tasks without a result can still be
archived, but cannot produce an invented result. `jobs result` on an archived
task explicitly returns `JOB_RESULT_ARCHIVED`.

New v4 workspace backups use `forgegate.workspace-backup.v2`; existing v3 backups
retain the unchanged v1 manifest contract. Verification/restore receipts list
`external_archive_dependencies`: SHA-256 identities of earlier ZIPs referenced by
archived tasks. **A newer ZIP does not contain those earlier ZIP payloads.** Keep
them separately, check their availability and hashes, and retain their private
creation receipts. Structural validation of a newer ZIP does not verify the
availability of every external dependency. Restoring a v4 pair preserves archive
receipts, not external payloads. Losing the earlier ZIP can make those result
bytes unavailable. Restore remains new-directory-only, with no automatic startup.

Live binding checks apply at the archive commit. A caller that previously
exported an assembly, or an already in-flight binding request, can bind that
assembly later through the existing separate workflow. Archival does not revoke
external evidence, prohibit future binding or create a distributed transaction.
Later snapshots recognize such bindings and retain the original archive dependency.

## Quotas and Dashboard

v3 permits 100 total tasks. v4 permits 100 unarchived tasks plus at most 1,000
archive receipts. The existing 16 MiB pending-input, 4 MiB single-result and
32 MiB aggregate live-result quotas still apply. Each archived job frees one
logical slot; its former result bytes no longer count toward the live result
quota. History remains bounded and retained. At 1,000 receipts, archival refuses
further work; no automatic rotation/deletion or quota bypass is implemented.

The Dashboard accepts v3/v4 and returns archive metadata in project-authorized
job details. It shows the original backup hash, archive time and logical result
size, keeps history visible, and offers no result export/binding for archived
tasks. A stale client attempting those operations receives a conflict. There is
no archive/restore button or browser-controlled file path. Restart the Dashboard
and activate a fresh session after an application upgrade; do not rebuild assets
under a running server.

Phase 41 adds [read-only capacity and archive visibility](JOB_CAPACITY.md): the
local CLI reports store-wide logical quotas, while the Dashboard exposes only
project-scoped usage and filters. Dependency availability and physical database
size remain explicitly unverified.

## Reproduce safely

```powershell
python -m pytest tests/test_job_archival.py tests/test_workspace_backups.py
python tools/workspace_backups_smoke.py
python tools/manual_dashboard_jobs.py work/new-archive-demo --archive-complete
```

The last command creates a **new synthetic** workspace, archived fixture and
ephemeral identity, but starts no service/device. Keep its key/database/ZIP files
out of Git and screenshots. See the [Phase 40 acceptance report](../reports/PHASE_40_JOB_ARCHIVAL_ACCEPTANCE.md)
for actual browser evidence and the scope of tested failure cases. Native screen
reader/high-contrast/RDP acceptance, encryption, physical compaction, automatic
workers and real hardware validation remain separate gates.
