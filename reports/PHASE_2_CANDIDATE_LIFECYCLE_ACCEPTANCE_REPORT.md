# ForgeGate Phase 2 release-candidate lifecycle acceptance report

- Date: 2026-08-30
- Version: 0.1.0.dev6
- Environment: Windows, Python 3.12.10
- Scope: immutable candidate creation, state transitions, evaluation binding,
  audit events, and stateless CLI previews

## Decision

**PASS within the release-candidate lifecycle slice.** ForgeGate now implements
the complete one-way candidate state graph with deterministic identities and
fail-closed release-decision binding. SQLite persistence, transactional
concurrency, and attestations remain outside this acceptance boundary.

## Accepted behavior

- deterministic, normalized DRAFT creation for project/version/commit/branch/
  track/time identity;
- exact DRAFT(0) → COLLECTING(1) → READY(2) → EVALUATING(3) → terminal(4)
  graph with no skip, repeat, reverse, or terminal escape;
- timezone-aware UTC service timestamps and non-regression checks;
- immutable result candidates plus content-bound transition IDs;
- before/after candidate fingerprints, reason, revision, time, and evaluation
  references in each transition event;
- PASS/FAIL/REVIEW evaluation ID, commit, decision, and timestamp matching;
- fail-closed ERROR with or without a matching ERROR evaluation;
- strict standalone candidate, transition, and transition-result Schemas;
- stateless candidate create/transition CLI outputs with structural and
  evaluation-bound Golden fixtures.

## Verification

- dependency consistency: PASS;
- Ruff lint and formatting: PASS;
- mypy strict across 25 package and verification-tool source files: PASS;
- pytest: 357 passed, 1 skipped;
- full package coverage: 100% across 2,246 statements and 698 branches;
- candidate lifecycle, canonical hashing, and CLI: 100% statement/branch
  coverage;
- seven canonical versioned document Schema drift checks: PASS;
- wheel/sdist build, external clean install, and installed candidate create,
  structural transition, and evaluation-bound PASS transition smoke: PASS.

The existing skipped test is the actual Windows symlink fixture because this
host cannot create it; it is unrelated to candidate lifecycle behavior.

## Evidence boundaries

- Verification is local host software evidence only.
- The candidate CLI is stateless and does not prove durable ordering,
  concurrency safety, or database recovery.
- Candidate and transition hashes establish content identity, not producer
  authenticity or authorization.
- Example policy evaluations and commits are synthetic fixtures.
- No AFE/MSP430 repository, runtime, serial port, firmware, board, or physical
  measurement was accessed.
- No remote CI ran and no repository was created, pushed, or published.

## Deferred Phase 2 work

- SQLite schema and transactional candidate repository;
- optimistic revision checks, idempotency, and concurrent-writer tests;
- durable append-only transitions/evaluations and recovery behavior;
- deterministic JSON/Markdown attestations and persisted candidate CLI flow.
