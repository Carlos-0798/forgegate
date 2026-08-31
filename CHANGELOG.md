# Changelog

## 0.1.0.dev13 — 2026-08-31

- Added local REST commands for optimistic/idempotent candidate transitions,
  audited evidence-assembly binding, bound-evidence policy evaluation, and
  durable attestation creation.
- Expanded `CandidateApplication` so CLI and HTTP share advance, bind, and
  attest paths; API evaluation computes from the persisted binding before the
  atomic terminal transition.
- Required policy evaluation names to match the candidate release track and
  retained exact revision, evidence fingerprint, decision, and timestamp gates.
- Added loopback Host validation, a declared 4 MiB request-length gate,
  adversarial state/concurrency tests, expanded OpenAPI, and clean-wheel
  operation checks.
- Made Schema and OpenAPI export bytes platform-independent by writing canonical
  UTF-8/LF output, with Windows regression coverage after the first GitHub
  Actions run exposed a CRLF-only clean-wheel mismatch.

## 0.1.0.dev12 — 2026-08-31

- Added a FastAPI-based, versioned local REST API with health, idempotent
  candidate creation, candidate/history, evidence-binding, and attestation
  read endpoints.
- Introduced a shared `CandidateApplication` service so HTTP and CLI candidate
  creation and reads use the same domain and SQLite paths.
- Added structured fail-closed error envelopes, request correlation IDs,
  loopback-only serving, strict request models, and sanitized unexpected-error
  responses.
- Committed and drift-checked the OpenAPI 3.1 contract, added API/CLI parity and
  durable evidence/attestation integration tests, and extended clean-wheel
  release smoke coverage.

## 0.1.0.dev11 — 2026-08-31

- Added self-validating `forgegate.candidate-evidence-binding.v1` documents
  covering the revision-one candidate snapshot, complete audited assembly,
  canonical fingerprints, binding time, and content-derived identity.
- Upgraded the SQLite candidate store to schema v3 with immutable binding rows,
  idempotent `bind-evidence`, validated `show-evidence`, and read-time
  candidate/assembly/audit-chain checks.
- Required new v3 candidates to bind evidence before `READY` and required the
  terminal policy evaluation to fingerprint the bound assembly's nested
  evidence bundle.
- Added explicit v1/v2-to-v3 migration without fabricating historical bindings,
  plus Schema, Golden, corruption/migration/CLI tests, architecture/threat
  documentation, and clean-wheel end-to-end binding smoke.

## 0.1.0.dev10 — 2026-08-31

- Added strict, bounded loading of collector `CollectionResult` JSON plus exact
  revalidation of every referenced source artifact.
- Added `forgegate.evidence-bundle-assembly.v1`, retaining raw result identity,
  normalized fingerprints, collector versions, artifact references, ordered
  evidence IDs, and warnings under a content-derived assembly ID.
- Added `assemble-evidence`; warnings fail closed unless explicitly retained,
  and duplicate results, conflicting artifacts, commit mismatches, and temporal
  inconsistencies are rejected.
- Allowed `evaluate-policy` to consume a validated assembly while preserving
  compatibility with direct evidence bundles.
- Added canonical Schema, deterministic Golden, adversarial tests,
  architecture/threat documentation, and clean-wheel assembly/evaluation smoke.

## 0.1.0.dev9 — 2026-08-31

- Added the optional, artifact-only Analog Validation Studio
  `result-export.v1` collector without an upstream runtime dependency or device
  access path.
- Mirrored and drift-checked the frozen public structure, revalidated TestRun,
  criteria, point, source, and raw-record lineage, and normalized run, metric,
  and criterion facts without recalculation.
- Derived verification levels from upstream evidence sources and capped current
  `BENCH_*` labels at `system_observed` with an explicit warning because the
  schema lacks mandatory instrument/calibration provenance.
- Added the `collect-analog-validation` CLI, sample artifact, deterministic
  Golden, adversarial/resource tests, compatibility/threat documentation, and
  clean-wheel smoke coverage.

## 0.1.0.dev8 — 2026-08-31

- Added a self-validating `forgegate.release-attestation.v1` document containing
  the terminal candidate, complete transition chain, policy evaluation, and
  content fingerprints.
- Added deterministic JSON and Markdown rendering plus atomic, conflict-safe
  local bundle publication with exact replay semantics.
- Upgraded the SQLite candidate store to schema v2 with durable append-only
  evaluation and attestation documents, explicit v1 migration, and legacy
  evaluation backfill.
- Completed the local persisted CLI flow with store migration, evaluation
  import, attestation generation, and attestation readback commands.
- Added committed Goldens, adversarial filesystem/database tests, schema drift
  coverage, architecture/threat-model updates, and installed-wheel smoke.

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
