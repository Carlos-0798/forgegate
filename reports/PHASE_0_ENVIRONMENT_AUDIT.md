# ForgeGate Phase 0 prerequisite and environment audit

- Date: 2026-08-30 (America/New_York)
- Baseline inspected: `0c38d707dce2c992f9bc1abd412fd64eb9e10b72`
- Host: Windows 11
- Python: 3.12.10
- pip: 25.0.1
- Hardware/serial activity: NOT PERFORMED

## Outcome

**PASS for local Phase 1 software development prerequisites.** No human or
physical intervention is currently required.

## Baseline findings

The existing virtual environment and editable package were healthy, `pip check`
reported no broken requirements, Git was clean on local `main`, and no remote
was configured. The audit found five readiness gaps:

1. source distributions omitted architecture, schemas, examples, and tooling;
2. local setup and full verification required several manual commands;
3. CI omitted macOS, schema drift, source manifest, and clean-wheel checks;
4. direct quality-tool versions and isolated build backends were not frozen;
5. the configured 90% coverage gate was below the Phase 0 specification target.

## Remediation

- added `.python-version`, `.editorconfig`, repository instructions, direct
  dependency constraints, and exact isolated build backend versions;
- added PowerShell and POSIX setup paths;
- added one-command dependency/lint/format/mypy/test/config/schema verification;
- added temporary source/wheel build, manifest assertion, clean virtual
  environment installation, `doctor`, and generic config smoke verification;
- added a complete `MANIFEST.in`;
- expanded CI to Windows, Linux, and macOS with read-only permissions,
  credential persistence disabled, concurrency cancellation, timeouts, pip
  caching, and immutable official action revisions;
- increased the enforced package coverage floor to 95% and added failure-path
  tests.

## Accepted current checks

| Check | Result |
|---|---|
| PowerShell setup path | PASS |
| POSIX setup script syntax | PASS through Git Bash `bash -n` |
| `pip check` | PASS |
| Ruff lint and format | PASS |
| mypy strict on package/tools | PASS |
| pytest | PASS, 32 tests |
| Branch-aware package coverage | PASS, 100% |
| Generic project and two policies | VALID |
| Committed JSON Schema drift | PASS |
| Isolated sdist/wheel build | PASS |
| Required sdist contents | PASS |
| Repository-external wheel installation | PASS |
| Clean-installed `doctor` and config validation | PASS |
| GitHub-hosted Windows/Linux/macOS jobs | NOT RUN; no remote repository |

## Current human-intervention boundary

No action is needed from the owner to continue local ForgeGate Phase 1 work.
Owner input is required before any of the following:

- selecting an open-source license;
- creating a remote repository, pushing, or making it public;
- enabling GitHub-hosted CI and interpreting its first cross-platform run;
- publishing releases, resume/LinkedIn claims, or upstream integrations;
- opening a serial port, flashing or commanding the connected MSP430 board, or
  performing any other physical action.

Linux/macOS setup execution and GitHub Actions remain unverified locally. They
must stay labeled NOT RUN until an appropriate host or owner-approved remote CI
run produces evidence.
