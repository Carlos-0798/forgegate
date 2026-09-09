# Phase 48 — existing-only paired startup and runtime correlation

Date: 2026-09-08. Evidence: LOCAL_HOST_TEST, synthetic isolated Windows inputs.
Local uncommitted checkpoint on top of `81710fb`, including earlier Phase 46/47
work. GitHub synchronization remains paused.

## Delivered scope

Explicit `dashboard --existing-pair` and PowerShell `-ExistingPair -JobStore`
require candidate v9 plus job v3/v4 files. Preparation and lifespan validation
never initialize or migrate either store. Missing/empty/foreign/old-schema,
required-object, alias, namespace-overlap, replacement and foreign-key failures
refuse rather than repair. Candidate existing-operation opens now use SQLite
`mode=rw`, closing the accidental creation window after the existence check.

The private in-memory binding records selected paths and filesystem file IDs.
Each startup publishes new opaque runtime/pair labels; optional `dashboard-check`
expectations compare the same health response headers. Health refuses detected
file replacement. No path, token, key, raw report or OS process ID is exported.

Public correlation is explicitly **not authenticated process ownership**. The
original Phase 48 wording included owned runtime identity; that part is left
open for the private child-control channel rather than claimed from public IDs.
Existing reviewed business writes remain enabled: this is not probation mode.

## Expected versus actual

| Input | Expected and observed |
|---|---|
| Existing v9/v3 and v9/v4 pair | Startup and health accepted without initialize; protected API still requires authentication |
| Missing/empty/foreign/old/incomplete store | Refused, no creation or schema repair |
| Same file, hard link, injected reparse fixture, actual Windows directory junction, sidecar overlap | Refused before serving; real junction creation/removal is isolated to the temporary fixture |
| Different candidate application path | Construction refused, no new database |
| Missing job-store flag or hardware option | Explicit pair mode refused |
| Committed WAL contains incompatible version | Rejected even while main-file bytes still show the old compatible version |
| File replaced between preparation and startup | Lifespan refused |
| File replaced after startup | Health 503; no runtime identity headers, not a global write fence |
| Exact current start IDs | Real CLI probe exit 0, MATCH_NOT_AUTHENTICATED |
| Wrong pair or earlier-start IDs | Real CLI probe exit 3, RUNTIME_IDENTITY_MISMATCH |
| Partial/malformed expected IDs | Rejected before network access |

The [machine record](PHASE_48_EXISTING_PAIR_EVIDENCE.json) retains two actual
temporary CLI startups, two wrong-pair checks, one prior-start refusal and one
missing-file refusal. The fixture stops only its own `Popen` children, never a
process discovered by PID, name or port. This is HTTP/CLI testing, not browser
interaction or a shipping managed-process implementation.

## Verification

- Focused startup/runtime/Dashboard regression: **98 passed**, warnings treated
  as errors. This includes 36 newly added startup cases and prior regression cases.
- Focused startup module branch-aware coverage: **98.68%** (113 statements,
  38 branches). The remaining branch is a sidecar itself detected as a reparse
  point; native parent-directory junction and sidecar hard-link rejection pass.
- Final `tools/verify.py`: **PASS**, exit 0; **1,380 passed, 3 skipped**,
  **95.88%** branch-aware coverage over 13,037 statements and 3,400 branches.
  The three historical symlink-creation skips remain; the new native directory
  junction fixture passed. Ruff, formatting and strict mypy (116 files) pass.
  All 56 document/3 artifact schemas, direct/BFF OpenAPI and assets pass drift
  checks; CLI/authenticated REST expected results remain **33/33**.
- TypeScript type check and **148/148** production-TypeScript host tests pass.
  Node reports its existing experimental type-stripping warning; these are not
  native browser or assistive-technology tests.
- Final `tools/release_smoke.py`: **PASS**, exit 0, including the real paired
  startup/restart/refusal CLI smoke against the clean-installed wheel. Source
  distribution includes the new tool and tests. No live serial port is opened;
  the optional-dependency check imports the installed module only.
- 250 local documentation links resolved before the final results were added.

Retained independent-process JSON SHA-256:
`4ac130e8c559f9fd97f730223c22a7fe753466a23ef1866a9c9107a7e7afa5b5`.

Final tested wheel SHA-256:
`4eccecc19894bcc99557ec6f2ff93765f13fceffdbfe3f0d19faa773bdeded18`.
Final tested sdist SHA-256:
`6091f25854fb400122433f2f96c0e04bd1d55c13df77f9ee9b78f681685fca44`.
These are temporary locally tested packages, not published release artifacts.
Final numeric documentation was updated after building; runtime code was frozen
before the final full-suite and package runs. The retained standalone JSON
predates the final path-resolution-race exception wrapper; the same six CLI
checks subsequently passed against the final installed runtime.

Reproduce:

```powershell
python -m pytest tests/test_dashboard_startup.py tests/test_dashboard_runtime.py tests/test_dashboard.py -q -W error
python tools/dashboard_pair_smoke.py
python tools/verify.py
python tools/release_smoke.py
```

The first regression caught a new eager-import cycle through the job module;
the startup validator now imports that constant only when invoked, preserving
the existing import-order regression. Strict typing also caught the smoke
reader's stream annotation; it was corrected, not suppressed.

## Remaining limits

Schema checks cover current required objects/columns, IDs/metadata, SQLite quick
integrity and foreign keys, not exact trigger SQL, every domain record, source
authenticity, historical association or stable generation lineage. SQLite may
manage WAL/SHM during real startup; this is not cold-file preservation. File-ID
checks have check/open races and cannot detect all in-place changes or hostile
same-user activity. No cross-store writer reservation/fence persists.

No owned private control channel, manager, service registration, live adoption,
rollback, trust transfer, automatic task execution, hardware connection or remote
operation was performed. The 24 complete adoption scenarios remain NOT RUN.
No new frontend exists in this slice, so no new screenshot/browser/assistive
acceptance is claimed; earlier screenshots retain their original scope.
