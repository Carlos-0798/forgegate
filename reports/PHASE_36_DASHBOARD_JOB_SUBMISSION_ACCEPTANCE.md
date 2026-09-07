# Phase 36 — reviewed browser report jobs

Date: 2026-09-06 America/New_York (browser writes occurred 2026-09-07 UTC).
Scope: Windows local Alpha, synthetic files and temporary test identity. GitHub
was neither inspected nor changed. Original 8131/MSP430 runtime was not accessed
or restarted. An isolated service on 8135 exercised the real local BFF in Edge.

## Delivered

Candidate report selection, exact-byte preview, warning consent, frozen submission
review, idempotent durable queueing, separately confirmed foreground parsing,
result/history inspection and atomic initiating-operator attribution. Existing
CLI creation authority is preserved. One active HTTP parser per app instance;
busy requests do not claim queued work. No automatic retry or worker is installed.

Parsing an uploaded report does not execute project tests, authenticate the report
producer, bind candidate evidence, decide policy PASS or access any device.
See [operation and compatibility boundaries](../docs/DASHBOARD_JOBS.md).

## Host gates

- `tools/verify.py`: 1072 passed, 3 skipped; 95.50% branch-aware coverage across
  11,343 statements and 3,042 branches. Skips require unavailable Windows symlinks.
- Ruff/format and strict mypy pass; 102 source/tool files.
- Frontend type check, build, asset inventory and all 104 host interaction tests
  pass, including 14 new submission/execution cases. These are not OS AT tests.
- 71 focused Python job cases: 32 engine + 16 management + 23 new submission cases.
  New cases cover operator/project/origin/CSRF gates, disabled/v1 stores, payload
  bounds, stale candidates, key replay/conflict/isolation, exact output, warning
  retention/rejection, double execution, actor rollback and sanitized failures.
- Concurrent real BFF host test: one parser blocked with synchronization events;
  second job receives 429 without claim; cancellation wins late publication;
  lock releases and the next task executes. This is not a real-browser race test.
- Frontend 409/413/429/500/503 tests use mocked responses; verify no auto retry,
  no implicit execution/binding, session-change suppression and accurate terminal
  state copy. Native browser error-presentation evidence remains in older phases.
- Contracts: 44 document + 3 artifact schemas, Dashboard BFF 25 paths/27 operations.
- Clean-package checkpoint: PASS; details below.

## Actual Edge acceptance

Start from `tools/manual_dashboard_jobs.py` in a new private directory (27 synthetic
jobs). Configure that directory's candidate/trust/v2 job files on an unused loopback
port and activate its synthetic operator. Do not upload keys, databases or reports
from other projects. Use `2026-09-06T12:00:00Z`, source `synthetic-fixture`, version
`1`, and the fixture's forty-`a` commit for the existing example report files.

| Browser case | Observed result |
|---|---|
| Missing report | Browser retains file-field focus; no preview/submit request |
| Back from final submission | Dialog closes, focus returns to Prepare JUnit task; store stays at 27 jobs |
| `examples/dashboard-junit/fail.xml` | Preview and executed result: total 4, passed 2, failures 1, skipped 1, errors 0, duration 0.5 |
| Separate submission/execution | Confirm submission yields QUEUED revision 0/no result; separate run confirmation yields SUCCEEDED revision 2, not policy PASS |
| JUnit + LCOV | `examples/dashboard-multi-report/tests.xml` yields 4 passed; `coverage.info` yields line and branch 1/2 = 50% at repository and module scopes |
| Warning consent | `warning.xml`: no submission button before explicit retention/re-preview; final review retains 2 warnings; executed summary observed 1 vs declared 2, duration null, both warnings visible |
| Forbidden XML | `rejected.xml`: JUNIT_FORBIDDEN_DECLARATION, no submission action or queued task |
| Identity and retention | All 3 new tasks retain QUEUED/RUNNING/SUCCEEDED events with synthetic operator; creation AUTHENTICATED_DASHBOARD; terminal source bytes released logically |
| Independent readback | Exactly 30 total jobs, 3 browser-created; results match UI; candidate still COLLECTING revision 1, one original transition, no binding/evaluation |
| Visible output | No horizontal document overflow in inspected combined-result view; browser warn/error query empty after test recovery; no exhaustive viewport/OS certification |

Reports remain `unsigned_local / declared`. Hashes prove byte identity, not
authenticity. Preview and execution construct separate timestamped assemblies;
their assembly IDs are not expected to match, but exact source hashes and
normalized outputs must match. No candidate mutation occurred in this phase.

## Screenshots and evidence

Actual viewport captures, not mockups or full-page certification:

- [Final submission review](../docs/assets/phase36-submit-review.png)
- [Retained task state/history](../docs/assets/phase36-task-result.png)
- [Combined output](../docs/assets/phase36-combined-result.png)
- [Explicitly retained warnings](../docs/assets/phase36-retained-warnings.png)

[Companion receipt](PHASE_36_DASHBOARD_JOB_SUBMISSION_EVIDENCE.json) retains synthetic
job IDs, expected outputs and screenshot hashes. Private local fixture databases,
identity key, cookies and raw service logs are not included.

## Corrections and limits

Initial new host tests attempted to mutate frozen models; corrected fixtures to
revalidate copied values. Frontend harness assertions initially read Headers as an
object and did not await async file hashing; fixed harness synchronization and
Header access. These were test defects, not relaxed product gates.

A frontend rebuild underneath the isolated live server produced a new-asset 404:
its startup allowlist still referenced the previous build. Controlled restart of
8135 and fresh activation restored it. Upgrade guidance now explicitly forbids
replacing assets under a running process. Browser control also needed a fresh
agent-created tab after a detached debugger; no browser security settings changed.

Foreground parsing is not a background scheduler, hard timeout or cooperative
stop. API submission requires a valid authorized envelope, not a preview receipt.
Per-instance busy protection is not a cross-process CPU limit. Lost responses can
have committed outcomes; inspect before any new action. Job result export/binding
in the browser, coordinated backups/retention, worker renewal/stop and native high
contrast/spoken screen-reader/Remote Desktop acceptance remain future gates.

## Final package checkpoint

`tools/release_smoke.py` completed with exit 0: sdist/wheel contents, clean install,
installed contracts and assets, CLI assurance flow, startup diagnostics, 12-check
job lifecycle/migration smoke, uninstall isolation and optional serial-dependency
imports pass. The optional import check opens no device. No live broker was run.
The new browser workflow was exercised on the isolated source-environment service,
not represented as a new browser run against the clean installed wheel.

Final `tools/verify.py` rerun also exited 0 with the same 1072/3 and 95.50% figures;
all 104 frontend tests and type checking passed after the final frontend rebuild.
Companion source/screenshot hashes and staged-text privacy checks passed.

Transient package hashes before this documentation-only completion update (not a
published release, signed artifact or hash of a later rebuild):

- Wheel SHA-256: `0cf5da29bfce5c6fe94ff1d53360697534808a401ff7caf65de17c2aeaa226b2`
- Sdist SHA-256: `76ec5de92d2a1bc19e62ccbe5059c12641e18afb6c297bc2f51625356e58858e`
