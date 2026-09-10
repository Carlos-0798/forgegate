# Phase 31 — Windows runtime operation acceptance

Date: 2026-09-06. Evidence: **LOCAL_HOST_TEST**. Product: Windows Local Alpha.

## Delivered

- Packaged `dashboard-check`: direct loopback GETs, no proxy/redirect/login,
  strict health shape, exact installed HTML and fixed actionable error labels.
- Source-distributed `tools/start_dashboard.ps1`: existing nonempty database,
  existing trust/interpreter files, literal paths, exclusive-port precheck,
  foreground CLI and child exit propagation. No automatic migration, PID kill,
  reboot persistence, unattended restart or hardware enablement.
- [Windows operations guide](../docs/WINDOWS_DASHBOARD_OPERATIONS.md) covering
  diagnosis, consistent backups, intentional shutdown, restart and activation.

## Expected versus observed

| Case | Expected | Observed |
|---|---|---|
| Actual isolated Dashboard | health 200, HTML 200, exit 0 | `DASHBOARD_REACHABLE` |
| Actual API-only service | health 200, HTML 404, exit 3 | `DASHBOARD_HTTP_ERROR` |
| Owned fixtures stopped | no accepted connection | `CONNECTION_REFUSED` for both |
| Bad health/status/HTML/transport | fixed non-ready reason; no raw payload | Focused cases pass |
| External host, invalid port/timeout | reject before network | Focused cases pass |
| Missing database | no file creation or service start | Windows PowerShell case passes |
| Empty database | reject without initialization | Windows PowerShell case passes |
| Busy port | refuse, preserve sentinel files, kill nothing | Windows PowerShell case passes |
| Spaced arguments and child exit 17 | exact arguments and exit 17 | Native PowerShell shim case passes; no hardware opened |
| Real foreground launcher | run at isolated port 8133 | health/HTML 200/200 |
| Ctrl+C and second start | graceful shutdown and same-store restart | Two starts and two graceful Uvicorn shutdowns observed |
| Post-restart fixture state | original synthetic population retained | 4 candidates, 8 snapshots, 4 transitions, 1 project/profile, 9 audit events; quick-check `ok`, schema 9 |
| Existing user service | do not restart or replace it | Port 8131 still returns health/HTML 200/200 |

The isolated manual starts used no MSP430 flag. The existing user instance was
not restarted and no new serial access, activation, private-key read, firmware
operation or candidate mutation was performed against that instance.

## Evidence and corrections

- Full local `tools/verify.py`: **946 passed, 3 skipped**, **95.28%**
  branch-aware coverage (10,592 statements, 2,852 branches); Ruff, formatting,
  strict mypy across 95 source/tool files, committed assets/contracts and
  **33/33** CLI/API interaction outcomes pass. The three local skips remain
  unavailable Windows symlink-creation cases, not silently accepted tests.
- Clean-wheel installation/runtime smoke: PASS. No new dependency or schema
  migration was introduced by this phase.
- TypeScript check and all 43 frontend host cases pass; these are regressions,
  not new manual-browser evidence. Browser code and assets are unchanged.
- 28 focused tests in `tests/test_dashboard_runtime.py`; three launcher tests
  execute native Windows PowerShell and are intentionally skipped elsewhere.
- [HTTP receipt](PHASE_31_RUNTIME_HTTP_RECEIPT.json), observed at
  `2026-09-06T17:44:50.142963+00:00`, SHA-256
  `52fdf80f90374cc8f747a9f5458b12f04e0865fbf73cef58555016ae06c63715`.
  Only line endings were normalized to UTF-8/LF for Git; data values were not
  changed. The receipt writer now explicitly uses LF for portable byte hashes.
- The same actual-server smoke is part of `tools/release_smoke.py`, executed
  with the clean environment's installed wheel, not source-tree imports.
- Initial PowerShell testing exposed an unavailable script-root value in a
  parameter default. Interpreter resolution was moved into the script body;
  the default-path and explicit-path cases now pass.
- An initial half-second stopped-server smoke timeout expired before Windows
  returned refusal. The default is now three seconds; timeout remains a
  distinct result rather than being mislabeled as a stopped process.
- An empty trust-store smoke fixture was rejected by the existing model. The
  fixture now uses one ephemeral in-memory signer identity; no key is exported
  and no authentication or session creation is exercised by this smoke.

No new screenshot is appropriate for this CLI-only checkpoint. Existing browser
screenshots remain historical, with their original data and acceptance scope.
Do not use this report to claim continuous uptime, exact process/database
ownership, authentication acceptance, new hardware stability, producer
provenance, accessibility conformance, or production readiness.

Remote synchronization remains a private stacked PR while the previously
reported GitHub account billing/spending restriction blocks CI. No check is
bypassed and no License, public visibility or Release is introduced.
