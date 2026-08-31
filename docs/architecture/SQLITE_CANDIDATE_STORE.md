# SQLite candidate store

## Scope

The Phase 2 candidate store makes the already-frozen release-candidate
lifecycle durable. It does not change the release-candidate, transition, or
transition-result document schemas and does not store upstream AFE/MSP430
internals.

`SQLiteCandidateRepository` owns one local database file. Initialization sets a
ForgeGate application ID, schema version 4, WAL journaling, FULL synchronous
durability, foreign keys, and a bounded busy timeout. A future schema version is
rejected. An existing schema-v1, schema-v2, or schema-v3 store is never changed by
`init-store`; the owner must run the explicit, validated `migrate-store`
operation.

## Tables and ordering

- `candidates` holds immutable identity fields and the compare-and-swap pointer
  to the current revision;
- `candidate_snapshots` appends the canonical candidate JSON and SHA-256
  fingerprint for every revision, including revision zero;
- `candidate_transitions` appends the canonical content-addressed event between
  adjacent revisions;
- `idempotency_records` binds one caller key to the canonical request
  fingerprint and response document;
- `candidate_evaluations` stores the exact terminal policy evaluation and its
  canonical fingerprint;
- `candidate_evidence_bindings` stores the complete self-validating assembly
  binding for a new v3 candidate;
- `attestations` stores one exact JSON attestation and deterministic Markdown
  rendering per candidate;
- `projects` stores one immutable registered project profile;
- `project_idempotency_records` binds project-registration retries to exact
  request and response content;
- `audit_events` stores ordered content-bound metadata for successful durable
  state changes;
- `forgegate_metadata` identifies the exact storage schema.

Database triggers reject candidate deletion, identity rewriting, non-unit
current-revision updates, and every update/delete of snapshot, transition, and
idempotency, evidence-binding, evaluation, and attestation rows. These controls
protect accidental or direct SQL mutation;
they are not an authorization boundary against an administrator who can replace
the database file or rewrite its schema.

## Transaction contract

Candidate creation, evidence binding, and advancement use `BEGIN IMMEDIATE`.
Advancement performs the following operations in one transaction:

1. verify the idempotency key or recognize an exact replay;
2. load and validate the entire current snapshot/event chain;
3. compare the caller's `expected_revision` with the current revision;
4. enforce the candidate evidence-binding gate, then run the pure lifecycle
   transition and evaluation-binding checks;
5. append the next snapshot and transition and, for an evaluated terminal
   decision, its exact evaluation document;
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
does not rerun collectors or policy evaluation. Evaluation and attestation
loads also verify stored metadata, canonical documents, rendered Markdown, and
association with the current candidate and complete transition chain.
Evidence-binding loads additionally recompute the binding, candidate, and
assembly identities and compare the embedded candidate with revision one.
Corruption fails closed with a stable store error; this checkpoint does not
repair, salvage, back up, encrypt, or replicate a damaged database.

## Explicit v1/v2/v3 migration

`candidate migrate-store DATABASE` accepts only a fully valid schema-v1,
schema-v2, or schema-v3 store. Missing historical layers are added before the
v4 project/audit objects. Existing immutable candidate documents are then
projected into deterministic audit-event order. No project profile, evidence,
rejected request, or actor identity is fabricated. The operation updates both
metadata values and `PRAGMA user_version` in one transaction, then revalidates
the result. Calling it on v4 is an idempotent validation. Unknown, foreign, or
corrupt stores fail closed.

Existing candidates receive an immutable `evidence_binding_required = 0`
marker. This preserves the historical state without fabricating an assembly
binding. Every candidate created under v3 sets the marker to one and must bind
evidence before `READY`.

A v1 terminal candidate contains only an evaluation reference, not the full
evaluation document. After migration, `candidate import-evaluation` must be
given the exact original `forgegate.policy-evaluation.v1` document. Candidate
ID, commit, decision, timestamp, and evaluation ID must agree before it is
stored. Attestation is refused until this backfill is complete.

## CLI boundary

`candidate init-store`, `migrate-store`, persisted `candidate create
--database`, `bind-evidence`, `show-evidence`, `advance`, `show`, `history`,
`import-evaluation`, `attest`, and `show-attestation` expose this repository.
The original `candidate create`
without `--database` and `candidate transition` remain deterministic, stateless
preview paths.

The attestation database insert commits before filesystem publication. Those
two resources are not one distributed transaction. If publication fails, the
durable attestation remains authoritative and an exact rerun safely publishes
or verifies the same content-addressed bundle; conflicting bytes fail closed.

The database proves local transaction ordering and content consistency. It does
not prove producer identity, operator authorization, trusted time, CI identity,
or physical verification.
