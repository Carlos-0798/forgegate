# Changelog

## 0.1.0.dev7 — 2026-08-31

- Added the versioned local SQLite candidate store with WAL, FULL synchronous
  durability, foreign keys, explicit transactions, and fail-closed schema
  identity checks.
- Persisted canonical candidate snapshots, content-addressed transitions, an
  optimistic current-revision pointer, and immutable idempotency responses.
- Added exact replay semantics, conflicting-key rejection, stale revision and
  compare-and-swap controls, bounded writer contention, restart recovery, and
  read-time audit-chain corruption detection.
- Added persisted candidate create/advance/show/history CLI paths, adversarial
  transaction/concurrency/corruption tests, architecture and threat-model
  updates, and clean-install database smoke coverage.

## 0.1.0.dev6 — 2026-08-30

- Added immutable, versioned release-candidate, transition-event, and
  transition-result contracts for the complete Phase 2 state graph.
- Added deterministic candidate creation, exact lifecycle revisions,
  non-regressing UTC timestamps, terminal-state immutability, and content-bound
  transition SHA-256 identities.
- Required PASS/FAIL/REVIEW terminal transitions to bind a matching policy
  evaluation ID, commit, decision, and timestamp; ERROR may fail closed without
  an evaluation result.
- Added stateless `candidate create` and `candidate transition` CLI previews,
  committed DRAFT/EVALUATING examples, Golden transitions, adversarial tests,
  canonical Schemas, documentation, and installed-wheel smoke coverage.

## 0.1.0.dev5 — 2026-08-30

- Added deterministic `forgegate.policy.v1` evaluation against immutable
  `forgegate.evidence-bundle.v1` inputs at an explicit timestamp.
- Added explicit trust and verification ranking, evidence age gates, filter and
  aggregation semantics, strict operators, conflict detection, and fail-closed
  PASS/FAIL/REVIEW/ERROR precedence.
- Added the versioned `forgegate.policy-evaluation.v1` result contract,
  SHA-256 input/evaluation identities, rule explanations, remediation hints,
  evidence references, and CI-compatible exit codes 0/1/2/3.
- Added PASS/FAIL example bundles, adversarial tests, canonical Schema,
  architecture documentation, and clean-wheel evaluation smoke coverage.

## 0.1.0.dev4 — 2026-08-30

- Added the strict ForgeGate-owned `forgegate.benchmark.v1` artifact schema and
  bounded Benchmark JSON v1 collector.
- Normalized metric name, value, unit, scope, optional baseline, and explicit
  absolute/percent tolerance into provenance-bound `benchmark.metric` evidence.
- Added duplicate-key, unknown-field, finite-number, numeric-range, duplicate
  metric, tolerance/baseline, depth, node, and metric-count rejection gates.
- Added a generic fixture, committed schema drift gate, golden projection, CLI
  path, adversarial tests, architecture/threat documentation, and release smoke.

## 0.1.0.dev3 — 2026-08-30

- Added a bounded, fail-closed SARIF 2.1.0 v1 collector.
- Normalized explicit scan summaries, individual findings, scanner/rule
  metadata, locations, fingerprints, suppression state, and baseline state
  without making policy decisions.
- Required unsuccessful invocations, ambiguous rule references, duplicate JSON
  keys, non-finite numbers, malformed structures, and resource-limit violations
  to reject collection.
- Added a generic SARIF fixture, deterministic golden projection, CLI path,
  adversarial tests, architecture/threat documentation, and clean-install smoke.

## 0.1.0.dev2 — 2026-08-30

- Added strict Cobertura/coverage.py XML and LCOV v1 collectors.
- Normalized repository, package, and module line/branch coverage into
  provenance-bound evidence without applying release thresholds.
- Added bounded parsing, declared-versus-observed audit warnings, LCOV state and
  summary validation, summary-only branch disclosure, golden outputs, and CLI
  collection commands.
- Extended clean-install release smoke coverage to exercise both installed
  coverage collectors.

## 0.1.0.dev1 — 2026-08-30

- Added a root-confined, size-bounded artifact registry with exact-byte SHA-256
  registration and change detection.
- Added the versioned JUnit v1 collector and normalized `test.summary` evidence.
- Added bounded XML parsing, forbidden declaration checks, declared-count audit
  warnings, fail-closed rejections, and deterministic golden output.
- Added the `collect-junit` preview command while keeping policy decisions out of
  the collector.

## 0.1.0.dev0 — 2026-08-30

- Established the domain-neutral Phase 0 repository scaffold.
- Added strict project, policy, and evidence-bundle contracts.
- Added trust/verification semantics and fail-closed mandatory-rule guards.
- Added configuration validation and JSON Schema export CLI commands.
- Added generic sample configuration, tests, CI, and compatibility boundaries.
- Added reproducible setup scripts, direct dependency constraints, release
  smoke verification, complete source-distribution manifest, macOS CI, and a
  95% coverage gate.
- Pinned third-party CI actions to immutable official release revisions and
  disabled checkout credential persistence.
