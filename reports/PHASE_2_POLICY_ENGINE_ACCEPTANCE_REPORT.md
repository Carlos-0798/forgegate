# ForgeGate Phase 2 deterministic policy-engine acceptance report

- Date: 2026-08-30
- Version: 0.1.0.dev5
- Environment: Windows, Python 3.12.10
- Scope: in-memory policy evaluation and CI-compatible CLI decision contract

## Decision

**PASS within the deterministic policy-evaluation slice.** Validated immutable
policy and evidence inputs now produce a versioned decision at an explicit
timestamp. Candidate lifecycle, persistence, and attestations remain outside
this acceptance boundary.

## Accepted behavior

- exact kind selection plus explicit trust and verification ranking;
- future/stale evidence review with optional inclusive maximum age;
- record, tag, execution-context, and normalized-value filters;
- strict value/count/all/any aggregation and all eight v1 operators;
- no vacuous all/count PASS without kind-level evidence;
- duplicate agreement, conflicting-value REVIEW, and expression ERROR;
- mandatory ERROR > FAIL > REVIEW > PASS precedence;
- optional outcomes remain visible without blocking mandatory PASS;
- versioned output, canonical input fingerprints, evaluation identity,
  evidence IDs, explanations, and remediation hints;
- CLI exit codes PASS=0, FAIL=1, REVIEW=2, ERROR/config/system=3;
- committed generic PASS and FAIL evidence-bundle examples.

## Verification

- dependency consistency: PASS;
- Ruff lint and formatting: PASS;
- mypy strict: PASS;
- pytest: 324 passed, 1 skipped;
- full package branch coverage: 100% across 2,031 statements and 624 branches;
- Policy Engine package and evaluation CLI: 100% statement/branch coverage;
- 1,000-record in-memory evaluation target: PASS under 2 seconds on this host;
- committed JSON Schema drift checks: PASS;
- wheel/sdist build, repository-external clean install, and installed PASS/FAIL
  evaluation smoke: PASS.

The actual Windows symlink fixture remains the one existing skipped test because
this host cannot create it. This is unrelated to in-memory policy evaluation.

## Evidence boundaries

- Results prove local host behavior for ForgeGate software only.
- Example evidence and identity metadata are synthetic and unauthenticated.
- SHA-256 fingerprints identify normalized inputs; they do not authenticate the
  producer or prove that the stated tool ran honestly.
- No AFE/MSP430 workspace, runtime, serial port, firmware, board, or physical
  measurement was accessed.
- No remote CI ran and no repository was created, pushed, or published.

## Deferred Phase 2 work

- release-candidate state machine and legal transitions;
- transactional SQLite persistence and concurrency handling;
- deterministic JSON/Markdown attestations;
- persisted candidate-oriented CLI workflow and recovery behavior.
