# Phase 20 Windows production plugin broker acceptance report

- Date: 2026-09-03 (America/New_York)
- Version: 0.1.0.dev28
- Scope: Windows-only installed external-plugin broker, runner, output, audit,
  replay, recovery, and clean-wheel execution path
- Hardware/serial activity: NOT PERFORMED

## Outcome

**PASS for the Phase 20 Windows production-plugin broker gate using the
ForgeGate-owned generic pure-Python fixture.**

ForgeGate now executes that installed plugin only inside the verified rootless
Podman/WSL2 container. The core does not import the plugin entry point. A
successful receipt advertises `SANDBOXED` for its exact authorized run, while
accepted evidence remains `unsigned_local` and `declared`.

This is not a production-readiness, publisher-authentication, general
third-party compatibility, Linux/macOS, bench, device, or hardware claim.

## Implemented controls

| Boundary | Accepted behavior |
|---|---|
| Authorization | exact Phase 19 evidence identity and 14 controls; current capability/runtime/image rechecked |
| Distribution | exactly one matching name/version/entry point/manifest; pure-Python top package only |
| Core separation | external module imported only by the isolated trusted runner, never the host core |
| Inputs | exact ArtifactRegistry bytes copied to private read-only logical paths |
| Protocol | canonical plan-bound `START`, `READY`, and terminal `RESULT`/`ERROR` |
| Outputs | private tmpfs copied twice; exact members/bytes/digests/schema/kinds/input lineage checked |
| Evidence trust | `forgegate.plugin-output.v1` permits only `unsigned_local` and `declared` |
| Registration | accepted bytes rehashed and atomically moved under a broker-owned output root |
| Audit | separate append-only SQLite plans, idempotency, transitions, and immutable receipts |
| Recovery | exact completed replay does not re-execute; incomplete run closes as `ERROR` after cleanup |
| Cleanup | failure to remove the container or staging becomes `PLUGIN_CLEANUP_FAILED` and accepts no output |

## Live Windows evidence

The standalone sample plugin v0.2.0 performed fixed generic checks from inside
the production container. All 13 broker-level checks passed:

- declared input read succeeded;
- input mutation, root write, undeclared host read, outbound network, and child
  process attempts were denied;
- the environment contained only the explicit run-plan identity plus CPython's
  deterministic locale key;
- the three-message protocol completed;
- double-snapshot output validation and low-trust evidence validation passed;
- container/staging cleanup passed; and
- durable receipt readback and exact replay passed without re-execution.

The path-free record is
[`PHASE_20_WINDOWS_PLUGIN_BROKER_LIVE_EVIDENCE.json`](PHASE_20_WINDOWS_PLUGIN_BROKER_LIVE_EVIDENCE.json).
It reports `hardware_access=NOT_PERFORMED` and was regenerated from an isolated
ForgeGate wheel plus the independently built sample-plugin wheel.

- Verification ID:
  `sha256:a4fc24e4dba4af903110d5d848c6a7a9f4076742683d6b5f40677657345b9ea9`
- Successful receipt ID:
  `sha256:4242fdb5cf72b99b7860a5da8536a131688a647f2464477147eb3c0bd5832066`

## Failures found and corrected

1. Initial PowerShell wildcard copying did not select the staged file. The
   verifier now uses exact broker-managed paths.
2. Installed distribution inventories included `__pycache__`/`.pyc` residue.
   The broker explicitly excludes bytecode and stages source inventory only.
3. The earlier discovery fixture intentionally failed on package import. The
   package root is now inert while its runtime callable remains external and is
   loaded only inside the container.
4. Windows read-only staged files initially prevented directory deletion. The
   broker cleanup handler restores only delete-required write permission and
   verifies the complete staging root is absent.

These corrections are retained because metadata discovery and low-level
container tests alone did not prove the full installed-plugin path.

## Verification

| Check | Result |
|---|---|
| Execution-contract model focus | PASS — 8 tests |
| Production broker/store focus | PASS — 18 tests |
| Committed live-report validation | PASS — 1 test |
| Production broker controls | PASS — 13/13 |
| Full pytest | PASS — 743 passed, 3 Windows-symlink skips |
| Branch-aware package coverage | PASS — 95.28% across 8,270 statements and 2,276 branches |
| Ruff lint and format | PASS |
| mypy strict | PASS |
| Schema and OpenAPI drift | PASS — 38 document plus 2 artifact Schemas |
| dev28 sdist/wheel plus standalone plugin wheel | PASS |
| Clean-wheel production broker execution | PASS — local Windows Podman/WSL2 |
| Hosted cross-platform CI | PENDING for this commit; latest baseline remains Phase 19 |

## Residual risks and next gate

The production path has been demonstrated only with the controlled generic
pure-Python fixture. Publisher signatures, dependency packaging, native
extensions, remote install/acquisition, hostile third-party diversity, direct
CLI/REST execution, and Linux/macOS backends remain unsupported. WSL's
machine-level Windows-drive mounts remain a defense-in-depth limitation even
though no such path is mounted into the disposable plugin container.

No MSP430, serial port, device, or physical measurement was accessed. No
administrator intervention is currently required. Repository visibility,
License, Release, LinkedIn, new-remote creation, and hardware operations remain
owner-authorized actions.
