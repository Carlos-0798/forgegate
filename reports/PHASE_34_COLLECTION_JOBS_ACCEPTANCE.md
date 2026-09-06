# Phase 34 — durable local report jobs

Date: 2026-09-06. Baseline: `43693ee`. Scope: Windows local CLI, synthetic
JUnit/Cobertura/LCOV-compatible report pipeline. No GitHub operation, existing
8131/MSP430 restart, serial access or new browser acceptance was performed.

## Delivered capability

An explicitly initialized, separate SQLite v1 job store retains queued report
inputs and a transactional state/event trail. `jobs submit/show/list/run/cancel/
recover/result` provide a local foreground workflow with canonical identities,
idempotent replay, revision checks, exclusive execution claim and a five-minute
lease. Queued work can be read by a new process. Interrupted work requires an
expired lease and explicit recovery; nothing silently restarts.

Completed jobs export a separately reviewable assembly. Candidate state,
evidence binding, policy evaluation and device operation are never changed by
the job engine. Candidate-store schema stays v9. No authenticated HTTP job
endpoint or Dashboard task-management UI is delivered in this phase.

## Expected-versus-actual acceptance

| Input/action | Expected result | Observed |
|---|---|---|
| Submit, exit process, read in another process | Same QUEUED record, revision 0 | PASS |
| Repeat exact request/key | Same job, no duplicate | PASS |
| Reuse key with changed request | JOB_KEY_CONFLICT; no second job | PASS |
| Two simultaneous claims | Exactly one running owner | PASS, host threads with separate SQLite connections |
| Four tests, one failure | Collection succeeds; total 4/failures 1; no policy decision | PASS, subprocess output and exact SHA-256 |
| Warning-producing report without consent | REVIEW_REQUIRED, no assembly | PASS |
| Same warning input with explicit retention | SUCCEEDED with retained warnings | PASS |
| Forbidden XML declaration | REJECTED, no partial assembly | PASS |
| Cancel pending/running job | CANCELLED; late publication refused | PASS |
| Recover unexpired lease | JOB_RECOVERY_NOT_DUE | PASS |
| Recover expired lease | INTERRUPTED; pending input/lease logically released | PASS, injected host clock |
| Wrong commit or changed candidate fingerprint | Reject submission or retain FAILED execution; no candidate mutation | PASS |
| Corrupt stored record/input/result or inconsistent result assembly | Reject; do not emit a usable assembly | PASS |
| Input/job/result quota exhausted | Bounded failure; no partial result publication | PASS |
| JSON duplicate key, invalid schema, non-finite or excessive nesting | Reject without echoing private input | PASS |
| Read result then separately bind it | Original candidate history unchanged until explicit binding | PASS |
| Finish smoke and clean up temporary databases | No live SQLite initialization handle remains | PASS after the correction below |

The committed [synthetic receipt](PHASE_34_COLLECTION_JOB_SMOKE.json) matches the
actual current smoke output. Its ten checks include successful temporary-store
cleanup. Source report SHA-256:
`c841ced91447cdecc82ce8e942f86f7307d391342a85ed78a514d82f60488b5d`.
The receipt's PASS describes its checks, not a release decision for that report.

## Defect found and corrected

The first clean-wheel run completed the job assertions but failed during
temporary-directory cleanup with Windows `WinError 32` on the job database.
SQLite's connection context manager commits/rolls back but does not close the
connection. Initialization now uses explicit closing; a regression holds a
reference to the connection and proves it is closed, so garbage collection
cannot hide the defect. The smoke now emits PASS **after cleanup**, never before.
No retry, ignored cleanup error, GC workaround or relaxed gate was added.

## Reproduction and retained evidence

| Gate | Final result |
|---|---|
| Full Python suite | 1,033 passed; 3 Windows symlink-creation skips |
| Branch-aware coverage | 95.49%; 11,164 statements, 2,994 branches |
| New job tests | 32 passed; store module 98.89%, jobs CLI 100.00% branch-aware coverage |
| Static checks | Ruff/format PASS; strict mypy PASS, 100 source/tool files |
| Contracts | 44 document + 3 artifact schemas and both OpenAPI drift gates PASS |
| Frontend regression | 73 passed; TypeScript check PASS; no new browser execution |
| Existing CLI/API interaction | 33/33 expected outcomes PASS |
| Clean-wheel/sdist release smoke | PASS after handle correction, process exit 0, including installed job smoke |
| Final source distribution | Required Phase 34 schemas, tests, tool, contract and retained evidence included |

```powershell
python tools/verify.py
python tools/collection_jobs_smoke.py
python tools/release_smoke.py
pnpm test:dashboard
pnpm check:dashboard
```

Current acceptance results are also summarized in the
[verification matrix](../docs/VERIFICATION_MATRIX.md) and
[project status](../docs/PROJECT_STATUS.md). Local detailed logs, deliberately
not portfolio uploads, are `work/phase34-verify-retest.log`,
`work/phase34-release-retest.log`, `work/phase34-frontend.log`,
`work/phase34-interaction.log`, and `work/phase34-job-smoke.json`.
`work/phase34-release.log` retains the initial failed packaging acceptance.

No new page was built or tested, so no screenshot is presented as evidence for
this CLI-only capability. Existing browser screenshots remain historical and
must not be relabeled as a task-center demonstration.

## Limitations and next gate

Read [operations and data boundaries](../docs/COLLECTION_JOBS.md) before use:
local file access is authority, not an authenticated identity; no encryption,
secure erasure, hostile-administrator audit, scheduler, lease renewal, parser
termination or coordinated job backup exists. The 100-job quota retains
metadata/events; logical byte quotas are not a physical file-size guarantee.
Tested restart/readback and simulated lease expiry do not certify sudden power
loss, indefinite uptime, distributed execution or real-device stability.

Next: authenticated, project-scoped Dashboard job visibility and reviewed
actions, with explicit store configuration and genuine browser acceptance.
This must preserve warning review, cancellation semantics, candidate isolation
and separate immutable evidence binding. GitHub synchronization remains paused.
