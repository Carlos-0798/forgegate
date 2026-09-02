# Phase 18 Windows sandbox readiness report

- Date: 2026-09-01 (America/New_York)
- Version: 0.1.0.dev26
- Scope: Windows-only external-plugin sandbox capability gate and container
  creation specification
- External plugin execution: NOT PERFORMED
- Hardware/serial activity: NOT PERFORMED

## Outcome

**PASS for the Windows sandbox readiness/code gate; BLOCKED for adversarial
runtime verification.** ForgeGate now has a strict, content-derived Windows
capability report, a read-only diagnostic CLI, and a shell-free Podman
container creation specification. The actual workstation correctly reports
`RUNTIME_MISSING`, `PLUGIN_ISOLATION_UNAVAILABLE`, execution prohibited, and
isolation tier `NONE`.

This is not a sandbox-success claim. WSL2 and Podman are not installed, no OCI
image was pulled, and no container or plugin process was started.

## Host audit

| Item | Observed result |
|---|---|
| Operating system | Windows 11 Home, 64-bit, build 26200 |
| Processor | AMD Ryzen 9 8940HX; firmware virtualization enabled |
| Hypervisor | Present |
| Memory | Approximately 16 GB |
| WSL | Command present; WSL feature/distribution not installed |
| Podman/Docker | Runtime executable not installed |
| Administrative boundary | Windows feature inspection/enablement requires elevation |

A non-interactive user-scope `winget` attempt for Podman 5.8.3 returned
`No applicable installer found`; it did not open UAC or install anything.

## Implemented

- `forgegate.windows-plugin-sandbox-capability.v1` with content-derived identity,
  stable readiness reasons, required/observed controls, and mandatory
  `PROHIBITED`/`NONE` execution claims;
- `forgegate plugins sandbox-status` with no plugin import or container start;
- bounded Podman JSON probing for a loopback-only default connection, running
  WSL provider, rootless runtime, and safe version field;
- a strict `windows-podman-wsl2` container-create argument builder requiring a
  matching plan, pinned image, broker roots, and resource limits;
- unit/adversarial tests for unsupported/missing/failed/malformed/remote/
  rootful/non-WSL states and unsafe command inputs;
- public configuration loading, JSON Schema drift coverage, and clean-wheel
  diagnostic smoke.

## Local verification

| Check | Result |
|---|---|
| Windows sandbox readiness focus | PASS — 12 tests |
| Full pytest | PASS — 715 passed, 3 Windows-symlink skips |
| Branch-aware package coverage | PASS — 96.26% across 7,588 statements and 2,074 branches |
| Ruff lint and format | PASS |
| mypy strict | PASS — 66 source files |
| Contract drift | PASS — 36 document plus 2 artifact Schemas and OpenAPI |
| Plugin/container execution | NOT PERFORMED |

## Open-source/runtime review

Podman `v5.8.3` at commit
`3a2e1c7e9c15a218768206af59ab2974271ebf4f` was selected as the Windows runtime
baseline. Podman and Podman Desktop are Apache-2.0 licensed. Official Windows
documentation confirms that WSL2 is the default Windows provider, supports all
Windows 11 editions, and requires administrator rights for initial Windows
feature enablement. No Podman source or binary was copied into the repository.

## Required owner action

An administrator must enable WSL2 once and restart Windows:

```powershell
wsl --update
wsl --install --no-distribution
```

After restart, ForgeGate development can install Podman 5.8.3, create the
rootless WSL machine, pull the exact pinned probe image, and run the remaining
hostile-fixture verification. Acceptance of that later verification must
record the exact runtime/image identities and every denial/resource result.

No repository visibility, License, Release, LinkedIn, or hardware action is
part of this requirement.
