# ForgeGate Phase 2 deterministic attestation acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev8
- Environment: Windows, Python 3.12.10, stdlib SQLite
- Scope: durable policy evaluations, deterministic release attestations, and
  completion of the local persisted CLI MVP

## Outcome

**PASS within the local deterministic-attestation scope.** ForgeGate can take a
fully persisted terminal candidate, load its authoritative transition history
and policy evaluation, create one self-validating versioned attestation, retain
it durably, and publish byte-stable JSON and Markdown files. Exact retries
replay safely; conflicting stored or filesystem content fails closed.

This is a local unsigned record. It is not a signature, producer identity,
release authorization, trusted timestamp, CI attestation, remote service, or
hardware-verification claim.

## Accepted implementation

- `forgegate.release-attestation.v1` embeds the terminal candidate, four ordered
  transitions, policy evaluation when required, and independent content
  fingerprints;
- model validation recomputes candidate/event association, evaluation identity,
  commit/decision/time binding, mandatory rule precedence, rule uniqueness,
  evidence references, and attestation identity;
- deterministic sorted JSON and escaped Markdown match committed Goldens;
- SQLite schema v2 stores immutable evaluation and attestation documents with
  append-only triggers and read-time corruption detection;
- schema v1 requires explicit migration; legacy terminal candidates require the
  exact original evaluation document before attestation;
- output publication uses create-only staging files and an atomic directory
  rename, rejects unsafe targets, and verifies byte-identical replay;
- the CLI now includes `migrate-store`, `import-evaluation`, `attest`, and
  `show-attestation` in addition to the existing persisted lifecycle commands.

## Verification evidence

- dependency check: PASS;
- Ruff and Ruff format: PASS;
- mypy strict: PASS across 30 package and verification-tool source files;
- pytest: 427 passed, 1 skipped;
- package statement and branch coverage: 100% across 2,944 statements and 856
  branches;
- model, rendering, publication, SQLite migration, transaction rollback,
  append-only, corruption, and CLI adversarial tests: PASS;
- committed eight versioned document Schemas plus the Benchmark artifact
  Schema: drift check PASS;
- source distribution manifest, wheel build, clean environment installation,
  terminal persisted lifecycle, attestation publication, exact replay, and
  readback: PASS;
- Git Bash setup-script syntax: PASS.

The one skipped test attempts a real Windows symlink escape fixture; this host
does not permit symlink creation. Symlink-reporting and unsafe-target behavior
are still covered through deterministic filesystem simulations. No Linux or
macOS execution and no GitHub Actions run occurred because the project remains
local with no remote repository.

## Transaction and recovery boundary

The SQLite attestation row commits before filesystem publication. ForgeGate
does not claim a distributed transaction across the database and output
directory. If publication fails, an exact rerun reads the durable attestation
and either publishes the expected content-addressed bundle or rejects
conflicting bytes. It never silently overwrites a target.

SQLite hashes, canonical documents, triggers, and validations establish local
consistency. An administrator who can replace the database, package, or schema
is outside this tamper-resistance boundary.

## Compatibility and hardware boundary

The accepted core imports no Analog Validation Studio or MSP430 implementation.
It operates only on ForgeGate public contracts. No AFE repository files, MSP430
repository files, board connection, flashing, measurement, device control, or
electrical validation was performed. Therefore the highest evidence remains
`LOCAL_HOST_TEST`; there is no physical evidence in this report.

The next compatibility step is to freeze a versioned Analog Validation Studio
public report contract and implement an optional software-peer collector. An
MSP430 collector remains gated on a future project-progress alignment in this
conversation.

## Deferred work

- REST API and authenticated multi-user service boundaries;
- signing, key custody, revocation, trusted timestamps, and CI identity;
- database authorization, backup, repair, encryption, and replication;
- external plugin execution and GitHub integration;
- Analog Validation Studio and MSP430 compatibility collectors;
- any production deployment or public release.
