# Durable local collection jobs (Phase 34)

This is an explicit **local CLI** task lifecycle, not a Dashboard task center,
authenticated worker API, scheduler, service, or production queue. It adds no
device access. The candidate store remains schema v9; jobs use a separate v1
SQLite file. Existing browser previews remain ephemeral and unchanged.

## Small reproducible acceptance

From the repository's configured Python environment:

```powershell
python tools/collection_jobs_smoke.py
python -m pytest tests/test_collection_jobs.py
```

The smoke starts a new CLI process for each command in a temporary, synthetic
project. Expected receipt: `result=PASS`, four tests with **one failure**, exact
source SHA-256, queued readback, idempotent replay, completed result export,
explicit cancellation, and unchanged candidate history. `SUCCEEDED` means
collection/assembly completed, **not that all tests or release policies passed**.
No HTTP port or device is opened. The installed-wheel release smoke also runs it.

## Operator workflow

Prepare an existing **COLLECTING, unbound** candidate and use its exact commit
and current revision. Store files in an owner-restricted directory, outside the
repository, cloud-sync folders and evidence gallery. This implementation inherits
directory permissions; it does not install ACLs or encrypt files.

```powershell
python -m forgegate jobs init C:/private-forgegate/jobs.db
python -m forgegate jobs submit C:/private-forgegate/jobs.db C:/private-forgegate/request.json --database C:/private-forgegate/candidates.db --key collection:review-001
python -m forgegate jobs list C:/private-forgegate/jobs.db --limit 25
python -m forgegate jobs show C:/private-forgegate/jobs.db JOB_ID
python -m forgegate jobs run C:/private-forgegate/jobs.db JOB_ID --database C:/private-forgegate/candidates.db --revision 0
python -m forgegate jobs result C:/private-forgegate/jobs.db JOB_ID
python -m forgegate jobs result C:/private-forgegate/jobs.db JOB_ID --assembly
```

Replace example paths and `JOB_ID`; the parent directory must already exist.
`init` exclusively creates a new file; it will never overwrite, migrate or adopt
an existing database. Interrupted initialization can leave a file that requires
inspection; do not retry by deleting an unidentified file.

The dedicated `jobs submit` loader accepts this strict JSON envelope (replace
candidate ID, commit, revision, report metadata and base64 with actual values):

```json
{
  "schema_version": "forgegate.collection-job-request.v1",
  "candidate_id": "cand-000000000000000000000000",
  "collection": {
    "expected_revision": 1,
    "reported_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "retain_warnings": false,
    "reports": [{
      "format": "junit",
      "content_base64": "REPLACE_WITH_CANONICAL_BASE64_OF_EXACT_REPORT_BYTES",
      "source_tool": "actual-test-runner",
      "source_version": "actual-version",
      "collected_at": "2026-09-01T00:00:00Z"
    }]
  }
}
```

Generate canonical base64 in PowerShell with
`[Convert]::ToBase64String([IO.File]::ReadAllBytes('C:/reports/tests.xml'))`.
Do not infer collection time or producer authenticity from the filename.
This envelope is validated by the jobs loader, not generic `validate-config`.
The three committed `forgegate.collection-job*.v1` schemas describe public
requests, records and results; the private lease token is never in CLI output.

Reports reuse the existing [bounded collection contract](DASHBOARD_COLLECTION_CONTRACT.md):
one or two reports; JUnit and/or one Cobertura/LCOV coverage family; no duplicate
family or exact input bytes; at most 1 MiB per decoded report and 512 normalized
records per report; exact safe-integer counts. The request file is limited to
4 MiB, 1,000 JSON nodes and depth 12; duplicate keys and non-finite JSON numbers
are rejected. Warning retention requires an explicit `retain_warnings=true`.

## State, ownership and restart behavior

| From | Explicit operation | Result |
|---|---|---|
| New | `submit`, unused idempotency key | `QUEUED`, revision 0 |
| QUEUED | `run --revision 0` | `RUNNING`, revision 1, private five-minute lease |
| RUNNING | Parser result and valid ownership | `SUCCEEDED`, `REVIEW_REQUIRED` or `REJECTED`, revision 2 |
| RUNNING | Execution/candidate recheck fails | `FAILED`, revision 2, sanitized error |
| QUEUED / RUNNING | `cancel --revision CURRENT_REVISION` | `CANCELLED`, terminal |
| RUNNING, lease expired | `recover --revision 1` | `INTERRUPTED`, terminal |

`show` and `list` do not recover or run anything. A restarted process can read and
run retained queued jobs. An interrupted running job stays RUNNING until its
five-minute lease expires and an operator explicitly recovers it. No automatic
retry, requeue, renewal or daemon is installed. Retry means a **new submission
with a new key** after reviewing the failure. Reusing the same key and exact
request returns the existing current record, including terminal records; changed
content with that key fails. Pagination is lexical by ID, not chronological:
pass the previous page's last `job_id` as `--after`.

Transactions serialize claims and compare state/revision. Cancellation revokes
publication rights and discards late results; it **does not terminate a running
parser process**. A worker cannot finish with an expired or revoked lease. Lease
timing uses the local wall clock: a detected backward transition fails closed;
this is not a trusted distributed clock or crash/ power-loss certification.

Only `SUCCEEDED` produces a bindable assembly. `REVIEW_REQUIRED` retains completed
collections but no assembly because warnings were not accepted. `REJECTED`
retains rejection explanations, never a partial assembly. `FAILED` retains no
result. `jobs run` exits 0 only for SUCCEEDED, otherwise 3; successful management
and result commands exit 0, operational/input failures 3, CLI usage errors 2.

## Evidence and data protection boundaries

- File possession authorizes this local tool: `LOCAL_CLI_NOT_AUTHENTICATED`.
  No browser role or Ed25519 producer identity is implied.
- The candidate must still match before and after parsing. No candidate data,
  audit event, policy decision or binding is written by a job. Review/export an
  assembly and use the existing separate binding workflow, with its own guards.
  Two databases are not a distributed atomic transaction; later candidate
  changes cannot be ruled out by a completed job record.
- Canonical fingerprints link retained input, result and assembly; model checks
  require assembly receipts/evidence to match the collections. History inserts
  and current records commit together; event update/delete triggers discourage
  accidental edits. This is not signed, tamper-proof or hostile-local-user audit.
- Pending requests retain base64 report bytes locally. Terminal transitions
  NULL their input and private lease fields atomically. `released_logically`
  does **not** mean secure erasure: SQLite free pages, backups, request files,
  process memory or external copies can retain bytes.
- Results retain normalized evidence, artifact hashes and warnings, not original
  XML/LCOV bytes. Keep source reports separately if later replay is required.
- Each store allows 100 jobs, 16 MiB total pending serialized input, 4 MiB per
  result and 32 MiB aggregate retained result JSON. Metadata/events are retained;
  no purge, rotation or automatic archival exists. These are logical quotas,
  not a physical database-file-size ceiling.
- Candidate `store backup` does not include this separate job file. No coordinated
  job backup/restore is delivered. Do not copy a live SQLite file as a certified
  backup, publish it, or archive active jobs merely to evade the quota.

Stable errors include `JOB_KEY_CONFLICT`, `JOB_STATE_CONFLICT`,
`JOB_CANDIDATE_CONFLICT`, `JOB_CANDIDATE_ALREADY_BOUND`, `JOB_LEASE_LOST`,
`JOB_RECOVERY_NOT_DUE`, `JOB_CAPACITY_EXCEEDED`, `JOB_STORE_CORRUPT` and
`JOB_RESULT_UNAVAILABLE`. Inspect state/revision first; do not blindly retry
mutations. Exceptions in execution persist only `JOB_EXECUTION_FAILED`.

## Deferred gates

Authenticated, project-scoped Dashboard job list/detail/submission/cancellation,
safe browser warning review, cooperative worker shutdown, scheduled execution,
lease renewal, private artifact lifecycle/backup UI, and real-browser task
acceptance remain separate future work. Existing MSP430 live telemetry is not
connected to this report queue and does not become release evidence.
