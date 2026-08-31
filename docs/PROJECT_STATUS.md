# Project status

- Date: 2026-08-30
- Version: 0.1.0.dev5
- Stage: Phase 2 deterministic policy-evaluation slice complete
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
- `collect-coverage-xml` and `collect-lcov` CLI previews and golden outputs;
- bounded SARIF 2.1.0 collection with strict JSON parsing, verified-success
  invocation state, rule/location/fingerprint normalization, and explicit
  zero-result summary evidence;
- `collect-sarif` CLI preview, generic fixture, and golden output;
- strict `forgegate.benchmark.v1` artifact contract with deterministic committed
  JSON Schema drift verification;
- bounded Benchmark JSON collection into one `benchmark.metric` evidence record
  per unique scope/name, retaining value, unit, baseline, and tolerance;
- `collect-benchmark` CLI preview, generic fixture, and golden output.
- deterministic policy evaluation over immutable policy/evidence models at an
  explicit timezone-aware timestamp;
- explicit trust, verification, age, presence, filter, aggregation, strict
  operator, conflict, and mandatory decision-precedence semantics;
- versioned `forgegate.policy-evaluation.v1` outputs with canonical
  fingerprints, evidence references, explanations, and remediation hints;
- `evaluate-policy` PASS/FAIL/REVIEW/ERROR exit codes 0/1/2/3 with committed
  generic PASS and FAIL examples.

## Not implemented

Candidate lifecycle, persistence, attestations, API, external plugins, GitHub
integration, AFE collector, MSP430 collector, and hardware access.

## Accepted local checkpoint

- PowerShell environment bootstrap: PASS
- direct dependency constraints and `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict: PASS across 21 package and verification-tool source files
- pytest: 324 passed, 1 skipped (Windows symlink creation unavailable)
- branch-aware coverage: 100% across 2,031 statements and 624 branches
- committed JSON Schema drift check: PASS
- three example project/policy documents: VALID
- four canonical versioned document Schemas plus one Benchmark artifact Schema:
  drift-checked and parsed
- complete sdist manifest and wheel build: PASS
- repository-external wheel installation and CLI smoke: PASS
- Git Bash shell-script syntax check: PASS
- GitHub Actions: Windows/Linux/macOS matrix defined; NOT RUN because no remote
  repository exists

See `reports/PHASE_0_ENVIRONMENT_AUDIT.md` for the prerequisite audit and exact
human-intervention boundary. See
`reports/PHASE_2_POLICY_ENGINE_ACCEPTANCE_REPORT.md` for the current slice.
