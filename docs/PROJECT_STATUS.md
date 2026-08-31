# Project status

- Date: 2026-08-31
- Version: 0.1.0.dev15
- Stage: Phase 8 project authority and bounded-discovery slice implemented
- Product maturity: local CLI/API MVP with software-peer collection, audited aggregation, durable lifecycle binding, authoritative project registration, and bounded state discovery; not production-ready
- Highest ForgeGate-owned evidence: LOCAL_HOST_TEST
- Hardware evidence: not applicable; no device access performed
- Remote/publication status: synchronized to private `Carlos-0798/forgegate`;
  no public release, License, or LinkedIn publication authorized

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
- strict, versioned release-candidate, candidate-transition, and transition-result
  contracts;
- deterministic DRAFT creation plus the complete legal state graph with exact
  revision, timestamp, terminal-state, and transition-fingerprint invariants;
- PASS/FAIL/REVIEW terminal transitions bound to matching policy evaluation ID,
  commit, decision, and timestamp;
- stateless `candidate create` and `candidate transition` CLI previews with
  generic DRAFT/EVALUATING fixtures and structural/evaluation-bound Goldens;
- SQLite candidate-store schema v5 with ForgeGate application identity, WAL,
  FULL synchronous durability, foreign keys, exact-version validation, and
  explicit read/write transactions;
- append-only canonical candidate snapshots, content-addressed transitions,
  compare-and-swap current revision, and immutable idempotency responses;
- exact replay, conflicting-key rejection, stale revision protection, bounded
  writer contention, restart recovery, rollback fault injection, and corruption
  detection;
- persisted candidate create/advance/show/history CLI flow while retaining the
  stateless preview commands;
- explicit, validated SQLite v1/v2/v3/v4-to-v5 migration plus exact legacy
  terminal evaluation and audit backfill where applicable;
- durable append-only policy-evaluation and release-attestation documents bound
  to the authoritative candidate audit chain;
- self-validating `forgegate.release-attestation.v1` with candidate,
  transitions, policy evaluation, content fingerprints, and unsigned-local
  assurance disclosure;
- deterministic JSON and Markdown rendering with committed Goldens;
- atomic directory publication, exact output replay, conflict rejection,
  symlink/unsafe-target defenses, and stable filesystem errors;
- persisted `candidate migrate-store`, `import-evaluation`, `attest`, and
  `show-attestation` CLI paths.
- frozen consumer-side structural mirror of Analog Validation Studio's public
  `result-export.v1` contract at upstream commit
  `9ac23494b86212928185de9b0eef1c1a82a8c0ea`;
- bounded, strict `collect-analog-validation` artifact path with no upstream
  package import, serial access, analysis rerun, or device operation;
- retained TestRun outcome, limitations, source schemas, metrics, criteria,
  point/evidence/raw-record lineage, exact bytes, and SHA-256 identity;
- automatic evidence-source mapping with current `BENCH_*` capped at
  `system_observed` and warned rather than promoted to physical verification;
- committed sample, Golden normalization, compatibility Schema, adversarial
  tests, architecture/security documentation, and clean-install smoke path.
- strict, bounded loading of collection-result JSON with UTF-8, duplicate-key,
  finite-number, depth, node, and exact-model gates;
- exact re-registration of every referenced artifact so missing, replaced, or
  metadata-conflicting bytes fail before assembly;
- versioned `forgegate.evidence-bundle-assembly.v1` containing a normal
  candidate-bound bundle plus one audited receipt per collector output;
- raw result file SHA-256, normalized result fingerprint, collector identity,
  original artifact references, ordered evidence IDs, and warnings retained;
- duplicate result/source, artifact conflict, evidence ownership, commit, time,
  and content-derived assembly identity invariants;
- `assemble-evidence` plus policy-CLI compatibility with direct bundles and
  validated assemblies;
- committed assembly Schema, Golden, adversarial tests, architecture/threat
  documentation, and clean-install assembly-to-policy smoke path.
- strict `forgegate.candidate-evidence-binding.v1` contract embedding the
  revision-one `COLLECTING` snapshot and complete audited assembly;
- canonical candidate, assembly, and binding fingerprints plus commit and
  monotonic-time invariants on every construction and load;
- immutable/idempotent SQLite binding persistence with candidate-chain metadata
  validation and append-only triggers;
- `candidate bind-evidence` and `show-evidence` CLI paths;
- mandatory binding before new v3 candidates reach `READY`, and terminal policy
  evaluation enforcement against the bound nested evidence bundle;
- explicit legacy semantics that preserve v1/v2 candidates without inventing a
  historical binding;
- committed binding Schema, Golden, migration/corruption/adversarial tests,
  architecture/threat documentation, and clean-wheel end-to-end binding smoke.
- shared `CandidateApplication` service for CLI and REST candidate creation and
  candidate/history/evidence/attestation reads;
- local FastAPI v1 health, idempotent candidate-create, and persisted read
  endpoints with strict request models;
- structured request/domain/store/internal error envelopes, stable status-code
  mapping, safe request correlation IDs, and exception-detail sanitization;
- loopback-only `serve` command supporting localhost, IPv4 loopback, and IPv6
  loopback while rejecting external and wildcard binds;
- deterministic `export-openapi`, committed OpenAPI 3.1 bytes, verification
  drift gate, and clean-wheel comparison;
- API/CLI creation parity plus full durable evidence-binding, terminal
  attestation, and history readback integration coverage.
- shared application commands for candidate advancement, evidence binding,
  policy evaluation, and durable attestation creation;
- REST transition commands with caller-owned idempotency keys and optimistic
  `expected_revision` control;
- REST evidence binding that accepts a strict assembly document but no path
  from which the API loads an assembly or artifact;
- REST evaluation that uses only the candidate's persisted binding and commits
  the resulting terminal transition atomically;
- release-track/policy-name matching in the candidate lifecycle boundary;
- REST attestation persistence with deterministic replay and no filesystem
  output parameter;
- loopback HTTP Host enforcement, declared 4 MiB request-length rejection, and
  state/concurrency/error adversarial tests.
- immutable `forgegate.registered-project.v1` profiles with canonical config
  fingerprints, content-derived registration IDs, and exact idempotent replay;
- SQLite candidate-store schema v4 with append-only project, project-idempotency,
  and audit-event tables plus indexed project/candidate cursors;
- transactional audit events for successful project registration, candidate
  creation, evidence binding, transitions, evaluation persistence, and
  attestation persistence, with no duplicate event on exact replay;
- explicit v1/v2/v3-to-v4 migration with deterministic audit projection and no
  fabricated project profile, evidence, or actor identity;
- bounded `forgegate.audit-event-page.v1` queries by stable local sequence,
  project, and candidate through shared application, CLI, and REST paths;
- committed project/audit Schemas, expanded OpenAPI, corruption/trigger/
  pagination/adversarial tests, and clean-wheel smoke coverage.
- application/CLI/REST candidate creation authorized by an existing immutable
  project profile and exactly one normalized configured release track;
- canonical hyphen candidate/policy track identity with documented compatibility
  for existing underscore project keys and fail-closed ambiguity rejection;
- bounded `forgegate.registered-project-page.v1` and
  `forgegate.release-candidate-page.v1` discovery contracts through CLI/API;
- SQLite v5 composite project/candidate index and explicit v4 migration without
  duplicate audit projection;
- documented append-only, compare-and-swap project-profile revision semantics,
  intentionally preceding any mutation implementation.

## Not implemented

Authenticated/non-loopback API deployment, HTTP artifact collection and file
publication, project profile revisions and candidate profile-version binding,
rejected-request/warning audit ingestion, audit export/retention,
external plugins, GitHub integration,
signatures/key management, database authorization, backup/repair, MSP430
collector, Studio Phase 5
human-readable report ingestion, authenticated provenance/signatures, portable
attestation embedding of assembly receipts, and hardware access.

## Accepted local checkpoint

- PowerShell environment bootstrap: PASS
- direct dependency constraints and `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict: PASS across package and verification-tool source files
- pytest: 568 passed, 1 skipped (Windows symlink creation unavailable)
- branch-aware coverage: 100% across 4,501 statements and 1,214 branches
- local API/application/network focus: 34 passed; 100% across 282 statements
  and 28 branches
- Analog Validation collector focus: 59 passed; 100% across 431 statements and
  106 branches
- evidence-assembly focus: 20 passed; 100% across 218 statements and 70
  branches
- candidate evidence-binding/store focus: 71 passed; 100% across 526 statements
  and 138 branches
- committed JSON Schema and OpenAPI drift checks: PASS
- project/policy/candidate/transition example documents: VALID
- fifteen canonical versioned document Schemas plus Benchmark and Analog
  Validation artifact Schemas: drift-checked and parsed
- complete sdist manifest and wheel build: PASS
- repository-external wheel installation and CLI smoke: PASS
- Git Bash shell-script syntax check: PASS
- GitHub Actions: Phase 8 run 33411154421 PASS on Windows, Ubuntu, and macOS;
  each platform completed `verify.py` and `release_smoke.py`
- private GitHub synchronization: `main` pushed with noreply commit identity;
  repository visibility, default branch, About, and ten Topics read back

See `reports/PHASE_0_ENVIRONMENT_AUDIT.md` for the prerequisite audit and exact
human-intervention boundary. See
`reports/PHASE_6_LOCAL_REST_COMMAND_WORKFLOW_ACCEPTANCE_REPORT.md` for the
previous REST command slice and
`reports/PHASE_7_PROJECT_REGISTRY_AUDIT_QUERY_ACCEPTANCE_REPORT.md` for the
project-registry baseline and
`reports/PHASE_8_PROJECT_AUTHORITY_DISCOVERY_ACCEPTANCE_REPORT.md` for the
current slice.
