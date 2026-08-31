# Project status

- Date: 2026-08-30
- Version: 0.1.0.dev1
- Stage: Phase 1 JUnit evidence slice
- Product maturity: pre-MVP
- Highest ForgeGate-owned evidence: LOCAL_HOST_TEST
- Hardware evidence: not applicable; no device access performed
- Remote/publication status: local only; no remote repository created

## Implemented

- repository/package scaffold;
- strict project, policy, and evidence-bundle contracts;
- safe configuration loader;
- `doctor`, `validate-config`, and `export-schemas` CLI surface;
- generic sample project and policies;
- architecture, evidence, security, compatibility, roadmap, and verification
  documentation;
- Windows/Linux CI definition.
- immutable-in-session artifact registration with explicit root, size, regular
  file, stable-read, and SHA-256 checks;
- bounded JUnit XML collection into one normalized `test.summary` record;
- explicit collection warnings and rejections with stable codes;
- `collect-junit` CLI preview and committed golden output.

## Not implemented

Policy evaluation, persistence, attestations, API, external plugins, GitHub
integration, non-JUnit collectors, AFE collector, MSP430 collector, and hardware
access.

## Accepted local checkpoint

- PowerShell environment bootstrap: PASS
- direct dependency constraints and `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict: PASS across package and verification tools
- pytest: 88 passed, 1 skipped (Windows symlink creation unavailable)
- branch-aware coverage: 100%
- committed JSON Schema drift check: PASS
- three example project/policy documents: VALID
- three canonical JSON Schemas: exported and parsed
- complete sdist manifest and wheel build: PASS
- repository-external wheel installation and CLI smoke: PASS
- Git Bash shell-script syntax check: PASS
- GitHub Actions: Windows/Linux/macOS matrix defined; NOT RUN because no remote
  repository exists

See `reports/PHASE_0_ENVIRONMENT_AUDIT.md` for the prerequisite audit and exact
human-intervention boundary. See
`reports/PHASE_1_JUNIT_SLICE_ACCEPTANCE_REPORT.md` for the current slice.
