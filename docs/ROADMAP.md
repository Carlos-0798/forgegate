# Roadmap

## Phase 0 — contract baseline

- [x] Product and independence boundary
- [x] Domain-neutral strict models
- [x] Trust and verification semantics
- [x] Generic sample project/policy
- [x] Threat model and CI definition
- [x] Optional AFE/MSP compatibility boundary
- [x] Complete local verification and freeze the checkpoint
- [x] Reproducible setup, 100% package coverage, schema drift gate, complete
  source distribution, and clean-install release smoke

## Phase 1 — first vertical slice

- [x] Add immutable artifact registry and byte-level SHA-256 verification.
- [x] Implement one adversarially tested JUnit collector.
- [x] Normalize a test summary into evidence without making a release decision.
- [x] Add golden fixtures and audit warnings/rejections.
- [x] Add Cobertura/coverage.py XML with repository/package/module scopes.
- [x] Add LCOV with strict record validation and module scopes.
- [x] Add SARIF 2.1.0 collector with explicit zero-result evidence.
- [x] Add strict generic Benchmark JSON schema and collector.

## Phase 2 — deterministic policy and CLI MVP

- [x] Implement deterministic policy evaluation at an explicit timestamp.
- [x] Enforce trust, verification, age, presence, conflict, and strict operator
  semantics without silent PASS.
- [x] Emit versioned per-rule machine results and CI exit codes 0/1/2/3.
- [x] Add release-candidate lifecycle and legal state transitions.
- [x] Add transactional SQLite persistence and concurrency controls.
- [x] Generate deterministic JSON and Markdown attestations.
- [x] Complete the local CLI MVP around persisted candidates.

## Phase 3 — software-peer compatibility

- [x] Audit the Studio public `result-export.v1` boundary at its upstream freeze
  commit without importing upstream runtime code.
- [x] Commit a consumer-side structural Schema mirror and exact drift gate.
- [x] Implement bounded run/metric/criterion normalization with retained
  limitations, source schemas, artifact identity, and record lineage checks.
- [x] Derive verification levels from upstream evidence sources and cap current
  `BENCH_*` exports at `system_observed`.
- [x] Add CLI, fixture, Golden, adversarial tests, documentation, and
  clean-install smoke.
- [ ] Add an MSP430 compatibility collector only after new hardware progress is
  aligned in this project context and its public report contract is frozen.
- [ ] Revisit human-readable Studio report ingestion only after its Phase 5
  product report contract is implemented and frozen upstream.
