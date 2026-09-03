# Windows Alpha delivery

## Test-candidate definition

Phase 22 is a private Windows Alpha test candidate, not a public release or a
production deployment. It closes the original local MVP bootstrap gap with
`forgegate init`, retains the existing PASS/FAIL/REVIEW/ERROR exit contract,
and adds one reproducible clean-wheel acceptance command.

## Installation and bootstrap

From a clean clone on Windows with Python 3.12:

```powershell
.\tools\setup_environment.ps1
.\.venv\Scripts\python.exe -m forgegate init .\work\sample-project `
  --project-id sample-project --project-name "Sample Project"
```

Initialization creates only `forgegate.yaml`,
`policies/pull-request.yaml`, and the `.forgegate`, `artifacts`, `policies`, and
`build/forgegate` directories. It validates the project and policy through the
strict domain models before publication and refuses to overwrite either file.
Its versioned receipt contains only relative paths and records hardware access
as `NOT_REQUESTED`.

## Canonical acceptance

Run:

```powershell
.\tools\verify_windows_alpha.ps1
```

The script performs the full quality suite, builds the wheel and source
distribution, installs them into a temporary clean Python environment, checks
`forgegate init` and overwrite rejection, exercises the established core
candidate/assembly/policy/attestation/portable-bundle chain, installs the
standalone sample plugin, and executes the real CLI plugin chain through
Podman/WSL2. It then proves exact replay, a persisted isolation-evidence
failure, path-free queries, low-trust collection, evidence assembly, a bounded
sample-policy PASS, plugin uninstall independence, and ForgeGate uninstall.

The generated live JSON is local-host evidence. It does not generalize beyond
the pinned host/runtime/image and ForgeGate-owned fixture. The script neither
accesses hardware nor reads, flashes, commands, or measures an MSP430 device.

## Tester-facing limits

- Windows rootless Podman/WSL2 and the exact retained sandbox-control evidence
  are required only for external-plugin execution.
- Core collection and decision commands remain usable without any plugin.
- The API remains loopback-only and requires the existing external trust store.
- No License, public repository, GitHub Release, or production-support promise
  is included in this Alpha.
