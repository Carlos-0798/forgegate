# ForgeGate Phase 2 SQLite candidate-store acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev7
- Environment: Windows, Python 3.12.10, stdlib SQLite
- Scope: durable candidate snapshots/events, transactions, optimistic
  concurrency, idempotency, restart recovery, corruption detection, and CLI

## Decision

**PASS within the local SQLite candidate-store slice.** ForgeGate can now
persist the frozen release-candidate lifecycle with transactional ordering and
fail-closed consistency checks. This is local-host software evidence, not a
production database, authorization system, trusted provenance service, or
physical verification result.

## Accepted behavior

- explicit schema-v1 initialization with ForgeGate application identity;
- WAL journaling, FULL synchronous durability, foreign keys, busy timeout, and
  explicit read/write transactions;
- canonical revision-zero and subsequent candidate snapshots;
- content-addressed append-only transition events between adjacent revisions;
- one optimistic current pointer updated through caller `expected_revision` and
  SQL compare-and-swap;
- immutable idempotency records binding caller key, normalized request
  fingerprint, and original response;
- exact replay after later state advancement and conflicting-key rejection;
- restart reconstruction with full snapshot/event/fingerprint-chain validation;
- stable errors for missing/foreign/future/corrupt/busy databases;
- persisted create/advance/show/history CLI while preserving stateless preview
  compatibility.

## Adversarial and recovery verification

- rollback injection after candidate insertion and after idempotency insertion;
- rollback injection after transition append, current-pointer update, and
  idempotency insertion;
- forced zero-row compare-and-swap defense and stale revision rejection;
- concurrent writer lock with a zero wait budget and no partial write;
- exact replay versus same-key/different-request collision;
- database triggers rejecting candidate deletion/identity changes and every
  snapshot, transition, and idempotency update/delete;
- rejection of non-ForgeGate databases and unsupported future schema versions;
- detection of application ID, metadata, trigger, journal, foreign-key,
  canonical JSON, current-pointer, and stored-response corruption;
- independent repository reopen and clean-installed CLI processes reading the
  same durable state.

## Verification

- dependency consistency: PASS;
- Ruff lint and formatting: PASS;
- mypy strict across 26 package and verification-tool source files: PASS;
- pytest: 398 passed, 1 skipped;
- full package coverage: 100% across 2,562 statements and 762 branches;
- SQLite candidate repository and persisted CLI: 100% statement/branch
  coverage;
- seven canonical versioned document Schema drift checks: PASS; no public model
  Schema changed in this slice;
- wheel/sdist build, source manifest, external clean installation, and installed
  multi-process create/replay/advance/replay/show/history smoke: PASS.

The existing skipped test is the actual Windows symlink fixture because this
host cannot create it; it is unrelated to SQLite behavior.

## Evidence and safety boundaries

- SQLite ordering, hashes, and triggers establish local consistency; they do
  not authenticate producers, operators, clocks, CI systems, or administrators.
- The store has no user authorization, encryption at rest, backup, repair,
  replication, retention policy, or remote service boundary.
- Policy evaluations are referenced by evaluation ID; this slice does not add a
  separate durable evaluation registry or attestation.
- Tests use synthetic candidates and controlled local database files.
- No AFE/MSP430 repository, runtime, serial port, firmware, board, or physical
  measurement was accessed.
- No remote CI ran and no repository was created, pushed, or published.

## Deferred Phase 2 work

- deterministic JSON and Markdown attestations over persisted candidates;
- durable attestation/evaluation association and output-conflict handling;
- completion of the local CLI MVP around attestation generation;
- optional AFE compatibility only after the generic MVP is independently
  demonstrable and its public artifact contract is frozen.
