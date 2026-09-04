# Contributing to ForgeGate

ForgeGate is a private, pre-release engineering project and is not currently
soliciting public contributions. This guide records the review standard for
authorized collaborators and for future public consideration.

## Before proposing a change

1. Read [PROJECT_STATUS.md](docs/PROJECT_STATUS.md),
   [ROADMAP.md](docs/ROADMAP.md), and
   [VERIFICATION_MATRIX.md](docs/VERIFICATION_MATRIX.md).
2. Check the relevant architecture and threat-model boundaries.
3. Define the problem, intended outcome, non-goals, acceptance criteria, and
   evidence needed to validate the result.
4. Do not include credentials, personal email addresses, machine-specific
   absolute paths, private artifacts, or evidence owned by another project.

Security vulnerabilities should follow [SECURITY.md](SECURITY.md) and must not
be disclosed through a public issue.

## Development environment

ForgeGate uses Python 3.12.

```powershell
.\tools\setup_environment.ps1
.\.venv\Scripts\python.exe tools\verify.py
```

For packaging or dependency changes, also run:

```powershell
.\.venv\Scripts\python.exe tools\release_smoke.py
```

Live plugin checks require the separately documented Windows Podman/WSL2
environment. A passing host test or hosted CI job must not be reported as a live
container or hardware result.

## Change requirements

- Keep the core domain-neutral. Integrations consume versioned public artifacts
  rather than importing the AFE or MSP430 project runtime.
- Keep schemas and the committed OpenAPI document synchronized with model or API
  changes.
- Add adversarial and regression tests for trust-boundary changes.
- Preserve deterministic output, explicit time, idempotency, and fail-closed
  behavior.
- Update README, status, roadmap, verification evidence, and limitations only
  when the underlying result is actually established.
- Prefer Conventional Commit subjects such as `feat:`, `fix:`, `test:`, and
  `docs:`.

## Evidence labels

Every claim must state what produced it. Use the narrowest accurate category:

- designed;
- unit-tested;
- successfully built;
- integration-tested;
- local host-tested;
- live local sandbox-tested;
- physically measured; or
- deployed in a real environment.

One category never silently implies another. In particular, simulation,
replay, synthetic fixtures, hosted CI, and host tests are not physical-device
evidence.

## Pull-request evidence

Complete the pull-request template with exact commands and results. Include
links or paths to retained evidence where appropriate, and record skips,
failures, limitations, and corrective work. A green CI badge proves only the
commands executed by that workflow.

## License and publication

No open-source license has been selected. Access to the repository does not
grant redistribution rights, and no contribution, release, or publication
should be represented as accepted without explicit owner approval.
