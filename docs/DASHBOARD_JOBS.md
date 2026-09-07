# Dashboard collection-job management (Phases 35–36)

An opt-in, operator-only view of the separate local job store. It can list and
inspect retained jobs/results, cancel queued or running work after confirmation,
and mark an expired running lease INTERRUPTED. Phase 36 adds reviewed browser
submission and separately confirmed foreground parsing. No automatic worker,
retry, test-command execution, evidence binding or policy PASS is added.

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

- On an unbound COLLECTING candidate, choose **Prepare JUnit task** or
  **Prepare test + coverage task**. Select existing reports and declare their
  original tool/version/time and commit. Preview is ephemeral, not a job.
- Check exact normalized counts and file hashes. Warning consent requires an
  explicit re-preview; rejected or partially valid selections cannot be submitted
  through this UI. Review the frozen bytes, metadata, revision and retention
  boundary, then **Confirm task submission**. Back writes nothing.
- Submission creates only QUEUED. Open **Inspect submitted task**, select
  **Review execution**, then **Confirm execution**. This parses retained reports
  in a foreground HTTP request; it does not run the project's tests or commands.
- Use **Close and refresh jobs** to inspect authoritative output and actors.
  `SUCCEEDED` can contain test failures or explicitly retained warnings.

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
  execute, retry or requeue anything. A new submission is a separate reviewed action.
- A conflicting revision returns 409. Close and refresh before deciding again.
  Network/500 errors can have an unknown write outcome: inspect the retained
  revision/history; never infer failure or blindly retry. There is no auto retry.

Writes use the existing session, same-origin and CSRF gates, project authorization,
and an atomic revision check. The store retains the authenticated operator with the
successful event. CLI-created records retain `LOCAL_CLI_NOT_AUTHENTICATED` creation
authority; unrecorded historical actors stay explicitly unknown. Local SQLite
ownership is not an HTTP credential, and this history is not signed/tamper-proof.

## Submission/execution contract

`POST /app/api/jobs?project_id=...` accepts `forgegate.collection-job-request.v1`
and a required ASCII `Idempotency-Key` (1–128 characters). The store namespaces
keys by authenticated identity/project, separately from CLI keys. Exact replay
returns the retained current record; changed payload with the same key conflicts.
The browser sends once per confirmation and offers inspection, not automatic
resubmission, after an uncertain response. A new confirmation generates a new key.

The server validates the strict bounded report envelope and candidate eligibility;
it does not require a signed preview receipt. Authorized API clients can therefore
enqueue a syntactically valid envelope whose report is later REJECTED by parsing.
The preview-before-submit gate is a browser workflow, not an authorization proof.

`POST /app/api/jobs/{job_id}/run?project_id=...` takes `expected_revision`.
Only one HTTP parser per application instance runs at a time; concurrent attempts
return 429 `DASHBOARD_JOB_RUN_BUSY` without claiming the second task. This is not
a distributed CPU limit, and does not cover independent CLI/preview requests.
SQLite claim/revision checks prevent duplicate publication for a single job.
The five-minute lease limits publication eligibility, not parser CPU wall time.
Closing a tab, request loss, cancellation or session expiry does not forcibly
stop parsing. Cancellation revokes publication; manual recovery handles expired
leases. Busy/error responses have no automatic retry; refresh before acting.

New browser-created records have `AUTHENTICATED_DASHBOARD` creation authority.
The v1 public record enum is extended; older strict readers must be upgraded to
read that value. Historical CLI records are unchanged. Event actors identify the
operator who initiated the request, not proof of an active session at completion.
No migration beyond the existing explicit v2 actor storage is added in Phase 36.

Do not rebuild/replace packaged assets beneath a running server. Static resource
allowlists are loaded at startup; an in-place rebuild can produce new-asset 404s.
Perform a controlled restart and fresh activation after an upgrade. This does not
automatically update the owner's separately running 8131 service.

## Evidence boundaries and acceptance

`SUCCEEDED` means parsing/assembly completed, even when a test summary has failures.
Imported report evidence remains `unsigned_local / declared`; viewing or canceling
a job never promotes it to measured hardware evidence. Warning/rejection results
retain explanations. No result is not an empty successful test run.

See [job lifecycle/quotas](COLLECTION_JOBS.md) and the
[Phase 35 acceptance report](../reports/PHASE_35_DASHBOARD_JOBS_ACCEPTANCE.md).
See also [Phase 36 browser submission acceptance](../reports/PHASE_36_DASHBOARD_JOB_SUBMISSION_ACCEPTANCE.md).
The isolated fixture generator `tools/manual_dashboard_jobs.py` creates 27 synthetic
jobs and a temporary test identity, but starts no server or device. Its expired
lease is seeded, not evidence of an observed crash. Keep its private files local.

Still deferred: reviewed browser job-result export/binding, cooperative parser stop, scheduler,
lease renewal, job backup/restore/retention UI, and new native accessibility tests.
