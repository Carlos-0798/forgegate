# Phase 44 — reviewed recovery rehearsal

Date: 2026-09-07 America/New_York (actual rehearsal completed 2026-09-08 UTC).
Evidence: LOCAL_HOST_TEST_SYNTHETIC. GitHub synchronization remains paused.

## Delivered

`workspace rehearse-recovery` consumes an exact-hash READY handoff, freshly
verifies the root ZIP and explicit originals, exclusively creates a new directory,
copies the paired stores and verifies exact bytes plus existing SQLite/job and
referenced-candidate history checks. It publishes `REHEARSAL.json` only after
all checks succeed. The strict content-addressed receipt binds reviewed and fresh
observations, source manifest, post-copy member identities and job/event totals.

The deadline is shared through all stages. Existing targets are never adopted;
precheck failures write no destination, and partial copy/publication failures
retain a non-completed directory for inspection instead of deleting user data.
This is a local CLI addition, not a new browser restore button or a service switch.
See [operator instructions and manual checklist](../docs/RECOVERY_REHEARSAL.md).

## Verification

- 38 new rehearsal tests pass, including v3/v4 empty stores, archived completed
  and cancelled jobs, exact table/source preservation, blocked/missing/wrong/unused
  dependencies, replaced root, mismatched reviewed manifest, handoff hash/size/
  UTF-8/duplicate/non-finite/depth/schema rejection, existing destinations, missing
  parent, copy/readback/hash/deadline/publication failures and receipt coherence.
- 160 combined rehearsal/readiness/workspace/archival cases pass. Rehearsal module:
  104 statements, 12 branches, 100% branch-aware coverage; readiness also 100%.
- Full `tools/verify.py`: PASS, 1,285 passed and 3 skipped; 95.76% branch-aware
  coverage across 12,488 statements and 3,238 branches. Skips require unavailable
  Windows symlink creation. Ruff, formatting, strict mypy (110 source/tool files),
  54 document/3 artifact schemas, OpenAPI drift and packaged asset checks pass.
- All 139 production-TypeScript host interaction tests pass. No frontend source
  was changed and no new browser or assistive-technology session was performed.
- Independent-process `tools/workspace_backups_smoke.py`: PASS. Exact tables,
  fresh dependencies, final receipt, missing-dependency rejection and existing-
  destination rejection are exercised alongside earlier backup/archive recovery.
- Clean-install `tools/release_smoke.py`: PASS, exit 0 with the final PASS marker,
  including the new installed CLI rehearsal, exact readback and both refusal
  cases. Optional MSP430 extra install/import passes without hardware access.
  Tested wheel SHA-256:
  `8a9501c90701361b7b77ddcef17cd28430c96447d7f621168a26b19f657c110f`;
  tested sdist SHA-256:
  `26a2005d58bad8d2d1e3249e2cab34e3fce337f4067848bb699cac7dd0ae840f`.
  These identify tested packages; final acceptance prose was updated afterwards.

## Actual retained handoff to restored copy

The command used the actual handoff downloaded through native Edge in Phase 43,
not a replacement generated to bypass the browser. Its exact file SHA-256 is
`c74b57d88f6af6d19adb78c273ed5ad608cea94d8037e6548bbc4e22df308c2d`.
The input ZIP and its original archived-result ZIP were supplied explicitly.

Actual output: `RESTORED_COPY_VERIFIED`, 27 tasks, 43 events, one archived task,
one external dependency freshly VERIFIED and one exact original result payload.
The result remains external; the restored store still retains the archival receipt.

Independent CLI `jobs show` returned the archived task as SUCCEEDED revision 4.
`workspace archived-result` returned the expected summary exactly:

| Value | Expected | Actual |
|---|---:|---:|
| Tests | 4 | 4 |
| Passed | 3 | 3 |
| Failures | 1 | 1 |
| Errors / skipped | 0 / 0 | 0 / 0 |
| Duration (seconds) | 0.5 | 0.5 |

Both restored database files equal the original ZIP members byte-for-byte.
Both ZIPs and restored databases remained unchanged during independent readback.
The final marker hash is
`5dfdb55522082076c8042437f3877344a2a0c510dcaba4ac4362af7ab2221aeb`.
The path-free [machine evidence](PHASE_44_RECOVERY_REHEARSAL_EVIDENCE.json)
retains the full strict receipt and expected/actual results. Local databases,
original ZIPs, identity files and keys remain untracked/private.

## Failures retained and corrected

The first fault-injection test left the fake expired clock installed when checking
retry refusal; it consequently observed deadline rejection before directory
rejection. Resetting the injected fault before the independent retry made the
test check the intended path. No production timeout guard was relaxed.

The first clean-install run exposed a smoke-helper assumption that every exit-3
case must be `WORKSPACE_DESTINATION_EXISTS`. The new missing-dependency case
correctly returned `REHEARSAL_DEPENDENCIES_INCOMPLETE`; the helper now asserts
the exact expected sanitized error line per case. The first package run is not
counted as a pass. Development cross-process smoke passed after this correction.
The complete clean-install smoke was then rerun and passed as well.

## Unchanged boundaries

No live workspace replacement, automatic worker, archived-payload rehydration,
external key/trust/raw-artifact/plugin-store recovery, producer authentication,
encryption, complete candidate-domain replay or power-loss certification.
No hardware, firmware, new browser screenshot, GitHub or publication action.
Task SUCCEEDED means collection succeeded: its one failing test is deliberately
retained and is not a policy PASS. A receipt is a local observation, not durable
availability or production acceptance.

Next bounded slice: read-only Dashboard review of completed rehearsal receipts,
without server-side file browsing or automatic recovery.
