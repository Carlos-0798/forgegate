# Phase 38 — durable foreground job execution lifecycle

Date: 2026-09-07 America/New_York. Scope: Windows Local Alpha, synthetic
report/job/candidate data and an ephemeral test identity. GitHub and MSP430
hardware were not accessed. The previously used port 8136 was unavailable on a
final read-only check and was not used; an isolated service on port 8137 was
started for this acceptance and stopped afterward.

## Delivered

Foreground report parsing now has a durable, bounded execution lifecycle before
any scheduler or automatic worker is introduced:

- new jobs emit frozen `forgegate.collection-job.v2` public records;
- one random `executor-…` identifier names the Dashboard process lifetime without
  acting as a credential, host identity or authentication proof;
- the private lease token remains in the job store only and is absent from CLI,
  Dashboard and append-only event records;
- execution renews and validates the five-minute lease before each report and
  before assembly;
- explicit cancellation is observed at those cooperative checkpoints and always
  prevents late result publication;
- revision 64 and 62 renewals are hard bounds that leave one terminal revision;
- explicit transactional v1/v2-to-v3 store migration preserves historical record
  bytes and fabricates neither owner nor actor; and
- a restarted process receives a different owner and cannot adopt, renew or
  finish a lease without its private token. Expired recovery remains manual.

This is still foreground parsing. It is not a scheduler, daemon, distributed
queue, arbitrary-code preemption or crash/power-loss certification.

## Actual browser acceptance

The Codex in-app browser exercised the built production Dashboard against an
isolated local BFF. A synthetic queued JUnit job was reviewed and explicitly run.

| Observation | Actual result |
|---|---|
| Initial state | `QUEUED`, revision 0, no owner, zero renewals |
| Confirmation copy | Named foreground-only parsing, bounded checkpoints, no test command/plugin/device/binding and no automatic retry |
| Completion | `SUCCEEDED`, revision 4 |
| Durable execution identity | `executor-cf3794f9fdcdcadfba7112e3a3716dfe` |
| Lease history | Two renewals; event revisions 0, 1, 2, 3, 4 |
| Actor history | Synthetic operator retained on claim, both renewals and finish; revision 0 remains explicitly unattributed |
| Exact synthetic output | total 4, passed 3, failures 1, errors 0, skipped 0, duration 0.5 |
| Evidence boundary | `unsigned_local / declared`; completion explicitly remained “not a policy PASS” |
| Candidate mutation | `NOT_PERFORMED` |
| Browser diagnostics | No warning/error console entries; document width 1265/1265 with no horizontal overflow |
| Independent readback | CLI and direct SQLite agreed on v2 state, owner, renewal count, result and actor presence |

The browser screenshot showing the owner and renewal count was captured in the
Codex task (84,663 PNG bytes). The browser capture interface did not supply a
repository file path, so it is intentionally not claimed as a committed GitHub
asset. A portfolio screenshot can be recaptured when GitHub work resumes.

## Automated and packaging gates

- `tools/verify.py`: 1,101 passed, 3 skipped; 95.46% branch-aware coverage across
  11,466 statements and 3,076 branches. All skips require unavailable Windows
  symlink creation.
- Ruff, format checking and strict mypy passed; mypy checked 102 source/tool files.
- The focused job chain contains 99 Python cases: 37 core lifecycle, 18 Dashboard
  management, 23 reviewed submission/execution and 21 result-handoff cases.
- All 127 frontend interaction tests passed; TypeScript, Vite production build and
  the five-file asset inventory passed.
- The cross-process installed/working-tree smoke retained the exact four-test,
  one-failure fixture, source SHA-256, candidate non-mutation, explicit migration,
  owner visibility, private-token exclusion and bounded renewal behavior.
- JSON Schema and both OpenAPI contracts passed committed-byte drift checks.
- `tools/release_smoke.py` built sdist/wheel, installed into clean environments,
  found the new v2 record schema, ran the job smoke, imported the optional serial
  dependency without opening a device, and completed with exit 0.

## Corrections found during acceptance

The first production asset build stopped before regenerating
`asset-inventory.json` because the unactivated shell used a global Python that
could not import ForgeGate. The asset build itself was valid; regeneration was
rerun with the repository virtual environment and the five-file inventory passed.

The real CLI help also still called `--job-store` a v2 store and said execution
was unavailable. It now accurately requires v3 and distinguishes explicit
foreground execution from absent scheduling/background execution; a regression
test protects that wording.

## Remaining boundaries

- No automatic worker, scheduler, retry, job takeover or mid-parser termination.
- No coordinated candidate/job backup, retention policy, purge or archival UI.
- No producer authentication, raw report export or hostile-local-user proof.
- No candidate transition, policy evaluation, release publication or GitHub action.
- No MSP430 command, UART observation, physical measurement or hardware evidence.
- Existing spoken screen-reader, Windows high-contrast and real Remote Desktop
  gates remain separate from this feature acceptance.

The isolated 8137 service was stopped. Automatic deletion of its dedicated system
Temp directory was denied by the execution policy, so the synthetic databases and
ephemeral key were left for OS/user cleanup rather than bypassing that control.
They are outside the repository and were not packaged or committed.

See the [machine-readable receipt](PHASE_38_JOB_EXECUTION_LIFECYCLE_EVIDENCE.json)
for the exact retained identities, counters and evidence boundaries.
