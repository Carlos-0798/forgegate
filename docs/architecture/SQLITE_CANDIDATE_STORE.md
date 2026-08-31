# SQLite candidate store

## Scope

The Phase 2 candidate store makes the already-frozen release-candidate
lifecycle durable. It does not change the release-candidate, transition, or
transition-result document schemas and does not store upstream AFE/MSP430
internals.

`SQLiteCandidateRepository` owns one local database file. Initialization sets a
ForgeGate application ID, schema version 1, WAL journaling, FULL synchronous
durability, foreign keys, and a bounded busy timeout. A future schema version is
rejected; this checkpoint intentionally has no implicit migration path.

## Tables and ordering

- `candidates` holds immutable identity fields and the compare-and-swap pointer
  to the current revision;
- `candidate_snapshots` appends the canonical candidate JSON and SHA-256
  fingerprint for every revision, including revision zero;
- `candidate_transitions` appends the canonical content-addressed event between
  adjacent revisions;
- `idempotency_records` binds one caller key to the canonical request
  fingerprint and response document;
- `forgegate_metadata` identifies the exact storage schema.

Database triggers reject candidate deletion, identity rewriting, non-unit
current-revision updates, and every update/delete of snapshot, transition, and
idempotency rows. These controls protect accidental or direct SQL mutation;
they are not an authorization boundary against an administrator who can replace
the database file or rewrite its schema.

## Transaction contract

Candidate creation and advancement use `BEGIN IMMEDIATE`. Advancement performs
the following operations in one transaction:

1. verify the idempotency key or recognize an exact replay;
2. load and validate the entire current snapshot/event chain;
3. compare the caller's `expected_revision` with the current revision;
4. run the pure lifecycle transition and evaluation-binding checks;
5. append the next snapshot and transition;
6. update the current pointer with `WHERE current_revision = ?`;
7. append the immutable idempotency response.

Any exception, busy writer, validation failure, or zero-row compare-and-swap
causes connection close/rollback before the error crosses the repository
boundary. Exact replay returns the originally stored response even if later
revisions now exist. Reuse of the same key for different normalized inputs
fails with `STORE_IDEMPOTENCY_CONFLICT`.

## Recovery and corruption detection

Every read is a consistent SQLite transaction and validates:

- ForgeGate application ID, exact schema version, required tables/triggers,
  metadata, WAL/FULL/foreign-key settings, and foreign-key integrity;
- canonical stored JSON and strict Pydantic document validity;
- snapshot count and exact revision ordering;
- transition metadata and before/after fingerprint links;
- immutable identity and current-pointer agreement with the audit chain.

Reopening the database reconstructs authoritative state from durable rows. It
does not rerun collectors or policy evaluation. Corruption fails closed with a
stable store error; this checkpoint does not repair, salvage, back up, encrypt,
or replicate a damaged database.

## CLI boundary

`candidate init-store`, persisted `candidate create --database`, `candidate
advance`, `candidate show`, and `candidate history` expose this repository.
The original `candidate create` without `--database` and `candidate transition`
remain deterministic, stateless preview paths.

The database proves local transaction ordering and content consistency. It does
not prove producer identity, operator authorization, trusted time, CI identity,
or physical verification.
