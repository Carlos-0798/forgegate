# Project status

- Date: 2026-08-30
- Version: 0.1.0.dev2
- Stage: Phase 1 standard collectors — JUnit and coverage
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
- Windows/Linux/macOS CI definition;
- immutable-in-session artifact registration with explicit root, size, regular
  file, stable-read, and SHA-256 checks;
- bounded JUnit XML collection into one normalized `test.summary` record;
- explicit collection warnings and rejections with stable codes;
- `collect-junit` CLI preview and committed golden output;
- Cobertura/coverage.py XML collection with observed-count precedence and
  repository/package/module scopes;
- LCOV collection with strict record state, count validation, module scopes,
  and explicit disclosure when only branch summaries are present;
- `collect-coverage-xml` and `collect-lcov` CLI previews and golden outputs.

## Not implemented

SARIF and benchmark collectors, policy evaluation, persistence, attestations,
API, external plugins, GitHub integration, AFE collector, MSP430 collector, and
hardware access.

## Accepted local checkpoint

- PowerShell environment bootstrap: PASS
- direct dependency constraints and `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict: PASS across package and verification tools
- pytest: 164 passed, 1 skipped (Windows symlink creation unavailable)
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
`reports/PHASE_1_COVERAGE_SLICE_ACCEPTANCE_REPORT.md` for the current slice.
