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

1. Add immutable artifact registry and byte-level SHA-256 verification.
2. Implement one adversarially tested JUnit collector.
3. Normalize a test summary into evidence without making a release decision.
4. Add golden fixtures and audit warnings/rejections.
5. Add coverage, SARIF, and benchmark collectors only after the JUnit slice
   closes its acceptance gate.

## Phase 2 — deterministic policy and CLI MVP

Implement evaluation, candidate lifecycle, SQLite persistence, JSON/Markdown
attestations, and CI-compatible exit codes. Missing, stale, conflicting, or
insufficient-trust evidence must never silently PASS.

## Later compatibility work

After the generic MVP is independently demonstrable, freeze an Analog
Validation Studio report schema and implement the first optional software-peer
collector. Add an MSP430 compatibility collector only after new hardware
progress is aligned in this project context.
