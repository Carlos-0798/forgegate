# Durable local collection jobs (Phases 34–38)

Submission/execution use an explicit local task lifecycle, not a worker service,
scheduler or production queue. Phases 35–36 add an opt-in authenticated
[Dashboard management view](DASHBOARD_JOBS.md) with reviewed submission/parsing.
Phase 37 adds exact result export and separately reviewed binding through the
existing candidate-evidence binding service. Phase 38 adds a durable execution
owner identifier, bounded lease-renewal events and cooperative cancellation
checkpoints before any automatic worker. It adds no device access, candidate
transition or policy decision. The candidate store remains schema v9; new job
stores use a separate v3 SQLite file and emit `forgegate.collection-job.v2`
records. Existing browser previews remain ephemeral. Legacy v1/v2 stores require
explicit `jobs migrate STORE` before submission, execution or Dashboard use.

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
The committed request/result v1 and record v1/v2 schemas describe the public
documents. Record v1 remains frozen for historical reads; new records are v2.
The private lease token is never in CLI, Dashboard, review or event output.

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
| QUEUED | `run --revision 0` | `RUNNING`, revision 1, non-credential execution owner plus private five-minute lease |
| RUNNING | Before each report and before assembly | `RUNNING`, revision +1, same owner and renewed five-minute lease |
| RUNNING | Parser result and valid ownership | `SUCCEEDED`, `REVIEW_REQUIRED` or `REJECTED`, revision +1 |
| RUNNING | Execution/candidate recheck fails | `FAILED`, revision +1, sanitized error |
| QUEUED / RUNNING | `cancel --revision CURRENT_REVISION` | `CANCELLED`, terminal |
| RUNNING, lease expired | `recover --revision CURRENT_REVISION` | `INTERRUPTED`, terminal |

`show` and `list` do not recover or run anything. A restarted process can read and
run retained queued jobs. An interrupted running job stays RUNNING until its
five-minute lease expires and an operator explicitly recovers it. The new process
has a different owner ID and cannot adopt, renew or finish the old lease. No
automatic retry, requeue, takeover, scheduler or daemon is installed. Retry means a **new submission
with a new key** after reviewing the failure. Reusing the same key and exact
request returns the existing current record, including terminal records; changed
content with that key fails. Pagination is lexical by ID, not chronological:
pass the previous page's last `job_id` as `--after`.

Transactions serialize claims and compare state/revision. A Dashboard process
uses one random `executor-…` owner ID for its lifetime; an independent CLI run
uses a fresh ID. This value is visible for restart diagnosis but is not a process
ID, host identity, authentication proof or credential. Only the private in-process
token can renew or finish the lease.

Execution renews its lease and checks durable ownership before each report and
before assembly. Cancellation revokes publication rights, releases retained input
logically, and causes the next checkpoint to stop later stages. It **does not
forcibly terminate a collector already inside one bounded parser or assembler**;
in-memory bytes can remain until that call returns. A parser cannot publish with
an expired or revoked lease. Lease timing uses the local wall clock: a detected
backward transition fails closed; this is not a trusted distributed clock,
arbitrary-code preemption, or crash/power-loss certification.

A one-report successful run normally ends at revision 4 (claim, two renewals,
finish); a two-report run normally ends at revision 5. Do not hard-code those
values: review the current revision because cancellation or future bounded stages
can produce a different valid history. At most 62 renewal events and revision 64
are representable; hitting that guard fails closed rather than wrapping history.

Only `SUCCEEDED` produces a bindable assembly. `REVIEW_REQUIRED` retains completed
collections but no assembly because warnings were not accepted. `REJECTED`
retains rejection explanations, never a partial assembly. `FAILED` retains no
result. `jobs run` exits 0 only for SUCCEEDED, otherwise 3; successful management
and result commands exit 0, operational/input failures 3, CLI usage errors 2.

## Evidence and data protection boundaries

- File possession authorizes the CLI: `LOCAL_CLI_NOT_AUTHENTICATED` creation
  authority. Browser management instead requires the authenticated operator and
  project/CSRF checks documented separately; it records actors on new events.
- The candidate must still match before and after parsing. No candidate data,
  audit event, policy decision or binding is written by job execution. Review/export
  an assembly and use the existing separate binding workflow, with its own guards.
  The Phase 37 Dashboard handoff is that explicit separate candidate-store write;
  it leaves the retained job unchanged and does not advance candidate state.
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
- Candidate-only `backup-store` does not include this separate job file. Phase 39
  [workspace backup/recovery](WORKSPACE_RECOVERY.md) snapshots both stores together,
  rejects RUNNING jobs and retains queued input. Retention planning does not purge
  jobs or reclaim quota; never archive active work merely to evade the quota.

Stable errors include `JOB_KEY_CONFLICT`, `JOB_STATE_CONFLICT`,
`JOB_CANDIDATE_CONFLICT`, `JOB_CANDIDATE_ALREADY_BOUND`, `JOB_LEASE_LOST`,
`JOB_LEASE_RENEWAL_LIMIT`, `JOB_RECOVERY_NOT_DUE`, `JOB_CAPACITY_EXCEEDED`, `JOB_STORE_CORRUPT` and
`JOB_RESULT_UNAVAILABLE`. Inspect state/revision first; do not blindly retry
mutations. Exceptions in execution persist only `JOB_EXECUTION_FAILED`.

## Deferred gates

Automatic worker startup/shutdown, scheduled execution, live archival/purge and
private artifact lifecycle/retention UI remain separate future work. Phase 39
provides coordinated backup, restored copies and non-destructive retention plans.
Phase 38 implements cooperative checkpoints only for the existing explicit
foreground parser; it is not a general task cancellation framework. Phases 35–37
browser acceptance is documented separately. Existing
MSP430 live telemetry is not connected to this report queue and does not become
release evidence.
