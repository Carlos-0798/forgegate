# Dashboard collection-job management (Phase 35)

An opt-in, operator-only view of the separate local job store. It can list and
inspect retained jobs/results, cancel queued or running work after confirmation,
and mark an expired running lease INTERRUPTED. Submission and foreground execution
remain CLI-only. No automatic worker, retry, evidence binding or policy PASS is added.

## Explicit configuration

Use owner-restricted files outside source control and synchronized folders.
The candidate database and trust store must already be configured. New `jobs init`
stores use SQLite schema v2. Existing v1 CLI stores require an explicit upgrade:

```powershell
python -m forgegate jobs migrate C:/private-forgegate/jobs.db
python -m forgegate dashboard --database C:/private-forgegate/candidates.db --trust-store C:/private-forgegate/trust.json --job-store C:/private-forgegate/jobs.db --port 8134
```

Replace example paths; this is not an instruction to restart an existing service.
Stop all users of a store and preserve an operator-managed consistent backup before
migration. Candidate-store backup does not cover jobs. The migration is transactional
and idempotent, preserves historical record JSON, and adds nullable event actors;
it cannot invent old authentication. CLI operations without actor attribution still
support v1. Dashboard startup refuses v1, missing, or incompatible files and never
initializes or migrates them automatically. Omit `--job-store` to keep Jobs disabled.

Activate an **operator** session for the exact project through the existing signed
CLI activation flow. Producers cannot read or mutate this workspace. A configured
job's candidate must belong to the same project in the selected candidate database.
Job submission and execution still recheck candidate eligibility separately.

## Interaction and recovery

- Open **Jobs**, select a permitted project, optionally filter by candidate ID.
  Pages contain at most 25 entries, ordered lexically by ID, not creation time.
  Back/Next retain URL filters. This is not a transaction-wide snapshot or total.
- Refresh explicitly to observe external CLI progress; there is no polling worker.
- Inspect the exact state, revision, lease, fingerprints and available result.
  The page shows at most 25 records and 25 issues per collection with truncation
  labels. `jobs result STORE JOB_ID` exports the complete exact retained document.
- Cancellation freezes the reviewed revision and requires confirmation. Escape or
  Back makes no write. It prevents result publication, but does **not** kill a
  parser, change candidate evidence, or securely erase bytes.
- Recovery checks the server's expired lease and records INTERRUPTED. It does not
  execute, retry or requeue anything. A new submission is a separate CLI action.
- A conflicting revision returns 409. Close and refresh before deciding again.
  Network/500 errors can have an unknown write outcome: inspect the retained
  revision/history; never infer failure or blindly retry. There is no auto retry.

Writes use the existing session, same-origin and CSRF gates, project authorization,
and an atomic revision check. The store retains the authenticated operator with the
successful event. CLI-created records retain `LOCAL_CLI_NOT_AUTHENTICATED` creation
authority; unrecorded historical actors stay explicitly unknown. Local SQLite
ownership is not an HTTP credential, and this history is not signed/tamper-proof.

## Evidence boundaries and acceptance

`SUCCEEDED` means parsing/assembly completed, even when a test summary has failures.
Imported report evidence remains `unsigned_local / declared`; viewing or canceling
a job never promotes it to measured hardware evidence. Warning/rejection results
retain explanations. No result is not an empty successful test run.

See [job lifecycle/quotas](COLLECTION_JOBS.md) and the
[Phase 35 acceptance report](../reports/PHASE_35_DASHBOARD_JOBS_ACCEPTANCE.md).
The isolated fixture generator `tools/manual_dashboard_jobs.py` creates 27 synthetic
jobs and a temporary test identity, but starts no server or device. Its expired
lease is seeded, not evidence of an observed crash. Keep its private files local.

Still deferred: browser submission/execution, cooperative parser stop, scheduler,
lease renewal, job backup/restore/retention UI, and new native accessibility tests.
