# Read-only workspace adoption preflight

Phase 47 adds `forgegate workspace adoption-preflight`. It compares one explicitly
selected coordinated source backup with the exact databases from a completed
recovery rehearsal. **This command does not adopt a workspace.** No service is
stopped/started, live database opened through SQLite, session created, job executed,
hardware accessed, trust file loaded or active-generation descriptor changed.

## Inputs and operator workflow

Keep backups private. Use a source archive made by `workspace backup`, its exact
SHA-256, the original target archive, a new cold directory produced by
`workspace rehearse-recovery`, and the exact SHA-256 of its `REHEARSAL.json`.
The receipt identifies the expected target archive and member bytes. Do not point
at the directory of a running or previously started Dashboard.

```powershell
python -m forgegate workspace adoption-preflight work/source.zip work/target.zip work/rehearsal --source-sha256 SOURCE_ARCHIVE_SHA256 --receipt-sha256 REHEARSAL_JSON_SHA256 --output work/adoption-preflight.json
```

Replace the hash placeholders with the actual 64-character lowercase hashes.
Paths remain local arguments, not fields in the exported report. The output file
must not exist; its parent must exist; output inside the target directory is
refused. Omit `--output` to receive JSON only on stdout.

For archived results, supply the exact original backup files separately for each
side using repeatable `--source-dependency SHA256=PATH` and
`--target-dependency SHA256=PATH`. A mapping valid only for one side must not be
silently reused for the other. Missing, failed, unused or duplicate dependencies
are refused; no partial comparison report is presented as complete.

## Expected results

| Exit | Output | Interpretation |
|---|---|---|
| 0 | `comparison=MATCH` | All supported table row values and accepted schema definitions match |
| 2 | `comparison=DIFFERENT` | At least one row or schema differs; review the source/target direction |
| 3 | Fixed error on stderr | Incomplete, malformed, incompatible, changed, oversized or unavailable inputs; no successful report |

`adoption_authorized=false`, `live_workspace_changed=false`,
`live_source_state=NOT_CHECKED`, `runtime_ownership=NOT_CHECKED` and
`lineage_authenticity=NOT_ESTABLISHED` apply even to MATCH. Counts, matching bytes
and a self-consistent report do not authenticate producer identity or lineage.
This report is an unsigned observation, not a launch plan or process credential.

Each table has source/target counts plus unchanged, changed, source-only and
target-only counts. SOURCE_ONLY means the proposed target lacks a source row;
TARGET_ONLY means the target has a row absent from this source snapshot. CHANGED
means the primary key is shared but at least one exact stored column value differs.
Same counts can still contain different data. Schema-only differences also return
exit 2 even when `differences_total=0` (for example empty v3 versus v4 job stores).

Rows and primary keys are represented by fingerprints; raw idempotency keys,
record bodies, actor details, report payloads and local paths are not exported.
These hashes are not anonymization guarantees. An owner can compare the private
stores by their table and key fingerprints; this is not yet a human-readable
Dashboard row-difference explorer.

## Complete scan, bounded pages

The entire supported inventory is scanned before reporting totals. Use `--limit`
(1-200, default 100) and `--offset` (default 0) to page differences. Follow
`next_offset` until null. Repeat exactly the same archive/receipt hashes and check
that `comparison_id` remains identical; `report_id` changes with check time/page.
A later source backup requires a new comparison, not reuse of an old cursor.
Table summaries are always complete. Out-of-range offsets fail rather than
returning a misleading empty page. MATCH needs no differences page.

Limits are 100,000 rows and 128 MiB of total column bytes per pair, 40 MiB per
cell, and 500,000 nodes/40 levels per JSON cell. Database schema objects/SQL are
bounded before reading table contents. Scans and copy/hash work share the existing
cooperative 30-second deadline (`--timeout-seconds`, maximum 300). OS I/O may exceed
a cooperative deadline; this is not a hard real-time limit. Exceeding a limit
refuses the operation, never silently samples or declares an incomplete scan MATCH.

## What is validated

- Exact archive/member hashes and existing paired-backup integrity, foreign-key,
  job history/result, archival receipt and historical candidate association checks.
- Exact table/index/trigger definitions against disposable current-initializer
  templates: candidate v9 and job v3/v4. Unknown objects or alternative SQL layouts
  are refused even if they might be semantically equivalent. Historical migrated
  layouts are not universally certified; no migration is performed here.
- Every candidate history, current snapshot/profile binding, evidence binding,
  stored evaluation/policy material and any retained attestation, using current
  domain readers. Legacy records missing required durable evaluation material
  fail closed instead of acquiring invented evidence.
- Every project/profile chain and current head; all product-audit rows and their
  exact expected durable subjects; API security-event row/model/sequence coherence.
- All retained project/candidate idempotency response links and metadata. Original
  request bodies are not all retained, so original request-fingerprint
  reconstruction is explicitly **NOT_PERFORMED**. Deleted historical requests or
  jointly rewritten self-consistent data cannot be authenticated by this scan.
- Rechecked source/target external archived result dependencies, without restoring
  their payloads into the current job store.

All 17 candidate tables and jobs/events are compared; the optional v4 archive
table appears as empty for v3, giving 20 consistently named report entries. The
inventory hashes exact stored values, including JSON formatting, not a semantic
merge. A full scan is not broader than the stated invariants and never constitutes
a security, authenticity, compliance or physical-measurement certification.

## Cold-copy safety and the Phase 47 correction

Preflight only hashes the target files; SQLite inspection runs on disposable
copies extracted from the exact target archive. It hashes the target again before
returning. Symlink/junction ancestors, hard links, missing members, changed bytes
and any WAL/SHM/journal sidecars are refused. This detects observed changes but
does not establish continuing availability or exclusive process ownership.

Earlier rehearsal readback opened the new WAL database read-only, which could
leave a zero-length WAL and an SHM file. Phase 47 now copies the actual destination
bytes into disposable readback files and inspects those before publishing the
receipt. New rehearsal directories therefore remain standalone. The retained
member hashes, domain readback and final receipt checks still apply.

Existing directories with sidecars are not repaired or cleaned automatically.
Re-run the existing reviewed rehearsal into another new directory, using the exact
original archives and handoff. Do not delete sidecars to bypass refusal, especially
if a Dashboard may have opened that directory. A leftover hard-linked pending
receipt is also refused rather than treated as owner-authorized cleanup.

## Reproducible acceptance

```powershell
python -m pytest tests/test_adoption_preflight.py tests/test_recovery_rehearsal.py
python tools/adoption_preflight_smoke.py
python tools/verify.py
python tools/release_smoke.py
```

The independent-process smoke creates synthetic temporary stores. Expected:
unchanged comparison exits 0; adding one queued job produces exactly two
source-only differences (`jobs.jobs` and `jobs.events`) and exits 2; an incorrect
source hash exits 3. The job stays QUEUED and the cold directory remains byte-for-
byte unchanged without sidecars. Temporary fixture files are removed afterwards.
Retained results: [Phase 47 evidence](../reports/PHASE_47_ADOPTION_PREFLIGHT_EVIDENCE.json).

Next: existing-only paired startup and owned runtime identity as prerequisites
for the [managed adoption design](WORKSPACE_ADOPTION_DESIGN.md). Full process
fencing, probation, switch/rollback and A01-A24 live fault acceptance remain
unimplemented/unexecuted. Browser, native assistive and MSP430 tests are separate.
