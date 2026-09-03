# Phase 22 private Windows Alpha acceptance report

- Date: 2026-09-03 (America/New_York)
- Version: 0.1.0a1
- Scope: project initialization, source distribution, wheel installation,
  complete core assurance smoke, Windows plugin workflow, and clean uninstall
- Hardware/serial activity: NOT PERFORMED

## Outcome

**PASS for a private, testable Windows Alpha delivery candidate.**

The built `0.1.0a1` wheel was installed into an isolated Python 3.12
environment. From that installed wheel, ForgeGate initialized and strictly
validated a new project, exercised the existing evidence/policy/candidate/
assurance/authentication chain, installed an independently built generic
plugin, ran the plugin through the real Podman/WSL2 broker, replayed and
queried the receipt, collected and assembled its evidence, evaluated a PASS
policy, persisted a deliberately failed run, removed both packages, and proved
that `forgegate` was no longer importable.

This is a private Alpha checkpoint, not a GitHub Release, public publication,
production-readiness claim, or hardware validation.

## Live Windows result

All 18 retained controls passed:

- input read; input/root/host-write or read denials; network and subprocess
  denial; sanitized environment; protocol and double-snapshot validation;
- cleanup, durable receipt readback and exact replay;
- path-free show/page queries and complete two-run paging;
- successful collection, retained low evidence trust, evidence assembly and
  policy handoff; and
- persistence of the deliberate failure path.

The content-addressed, path-free record is
[`PHASE_22_WINDOWS_ALPHA_LIVE_EVIDENCE.json`](PHASE_22_WINDOWS_ALPHA_LIVE_EVIDENCE.json).

- Verification ID:
  `sha256:97e99613c63f7bd168849c83a66923a9fd505a1632c3bd3f02b17aa399eca1f6`
- Successful receipt ID:
  `sha256:45259d795b395ff83a7486b532e8c359e059640c12fb2b552a0d1628298c037c`
- Run-plan ID:
  `sha256:e679ad1deaeb93efd0201e724b3faa7e1cfac2491a4a2e63b92ce7f7632b2e40`

## Verification

| Check | Result |
|---|---|
| Dependency consistency | PASS |
| Ruff lint and format | PASS |
| mypy strict | PASS - 73 source/tool files |
| Full pytest | PASS - 760 passed, 3 Windows-symlink skips |
| Branch-aware package coverage | PASS - 95.06% across 8,706 statements and 2,424 branches |
| Schema and OpenAPI drift | PASS - 41 document plus 2 artifact Schemas |
| Source distribution manifest | PASS |
| Clean-wheel initialization and overwrite refusal | PASS |
| Existing core assurance/authentication chain | PASS |
| Installed standalone plugin chain | PASS - 18/18 local Windows controls |
| Clean package uninstall | PASS |
| Hosted cross-platform CI | PASS - run 33811734474 on Windows, Ubuntu, and macOS plus generic Action smoke |

## Residual limits

Publisher authentication, remote acquisition, dependency-rich/native plugins,
broad hostile third-party diversity, Linux/macOS plugin backends, and the
plugin REST surface remain outside this Alpha. WSL machine-level Windows-drive
mounts remain a defense-in-depth limitation even though the disposable plugin
container receives no such mount.

No administrator or manual action is required for this checkpoint. No MSP430,
serial port, device, or physical measurement was accessed. Repository
visibility, License, public Release, LinkedIn publication, and hardware
operations remain owner-authorized actions.
