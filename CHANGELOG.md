# Changelog

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
