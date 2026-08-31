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
- [ ] Add generic benchmark JSON collector.

## Phase 2 — deterministic policy and CLI MVP

Implement evaluation, candidate lifecycle, SQLite persistence, JSON/Markdown
attestations, and CI-compatible exit codes. Missing, stale, conflicting, or
insufficient-trust evidence must never silently PASS.

## Later compatibility work

After the generic MVP is independently demonstrable, freeze an Analog
Validation Studio report schema and implement the first optional software-peer
collector. Add an MSP430 compatibility collector only after new hardware
progress is aligned in this project context.
