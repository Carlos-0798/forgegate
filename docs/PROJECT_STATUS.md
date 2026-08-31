# Project status

- Date: 2026-08-30
- Version: 0.1.0.dev0
- Stage: Phase 0 contract baseline
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

## Not implemented

Collectors, evaluation, persistence, attestations, API, external plugins,
GitHub integration, AFE collector, MSP430 collector, and hardware access.

## Accepted local checkpoint

- Ruff and Ruff format: PASS
- mypy strict: PASS across 9 source files
- pytest: 24 passed
- branch-aware coverage: 92.38%
- three example project/policy documents: VALID
- three canonical JSON Schemas: exported and parsed
- sdist and wheel build: PASS
- repository-external wheel installation and CLI smoke: PASS
- GitHub Actions: NOT RUN because no remote repository exists
