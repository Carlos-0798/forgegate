# SQLite candidate store

## Scope

The Phase 2 candidate store makes the already-frozen release-candidate
lifecycle durable. Phase 9 adds a profile-bound candidate v2 while retaining
the original v1 document for legacy/stateless compatibility. The store does not
contain upstream AFE/MSP430 internals.

`SQLiteCandidateRepository` owns one local database file. Initialization sets a
ForgeGate application ID, schema version 9, WAL journaling, FULL synchronous
durability, foreign keys, and a bounded busy timeout. A future schema version is
rejected. An existing schema-v1, schema-v2, schema-v3, or schema-v4 store is
never changed by `init-store`; the owner must run the explicit, validated
`migrate-store` operation. Validated schema-v5 through schema-v8 stores
follow the same explicit migration rule.

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
- `candidate_policy_materials` stores exact profile-authorized policy bytes and
  their self-validating material document for a new v7 candidate;
- `candidate_evidence_bindings` stores the complete self-validating assembly
  binding for a new v3 candidate;
- `attestations` stores one exact JSON attestation and deterministic Markdown
  rendering per candidate;
- `projects` stores one immutable registered project profile;
- `project_idempotency_records` binds project-registration retries to exact
  request and response content;
- `project_profiles` stores the canonical append-only registration/revision
  ledger, and `project_profile_heads` selects its current version under CAS;
- `project_revision_idempotency_records` binds one revision request to its exact
  immutable response;
- `candidate_profile_bindings` links every v2 candidate to its exact governing
  profile identity/version without rewriting candidate history;
- `audit_events` stores ordered content-bound metadata for successful durable
  state changes;
- `api_security_events` stores a separate bounded sequence of minimal API
  authentication/session/trust-control metadata without credentials or request
  bodies;
- `forgegate_metadata` identifies the exact storage schema.

Schema v9 retains the v5 `(project_id, candidate_id)` discovery index, v6
version-ordered project-profile index, and v7 policy-material records.

Schema v9 removes the incorrect global uniqueness of policy `material_id`.
That ID identifies profile-authorized content, not a candidate. The candidate
primary key, foreign key, exact material validation and immutable update/delete
guards remain. Migration rebuilds only this table inside one transaction and
copies all five retained columns unchanged; it rewrites no release history.
Stop writers, create and verify a SQLite-consistent backup, then run
`forgegate candidate migrate-store DATABASE` before restarting the upgraded
service. Migration is explicit, never an automatic server-start side effect.

Database triggers reject candidate deletion, identity rewriting, non-unit
current-revision updates, and every update/delete of snapshot, transition, and
idempotency, evidence-binding, policy-material, evaluation, and attestation
rows. Separate triggers reject every update/delete of security-event rows.
These controls
protect accidental or direct SQL mutation;
they are not an authorization boundary against an administrator who can replace
the database file or rewrite its schema.

## Transaction contract

Candidate creation, evidence binding, and advancement use `BEGIN IMMEDIATE`.
Product-surface creation first resolves the current immutable profile and requires
exactly one configured release-track key to normalize to the candidate's
canonical hyphen track. A missing project, missing track, ambiguous normalized
keys, or noncanonical new identity fails before any candidate or audit row is
written. It then creates a v2 candidate containing that exact profile ID/version
and appends the corresponding binding row in the same transaction. The
low-level v1 creation method remains only for compatibility tests and earlier
persisted stores. Exact creation retries resolve their original response before
current authority, so later profile revisions do not reinterpret them.

Project revision also uses `BEGIN IMMEDIATE`: validate exact replay, load the
current profile chain, compare `expected_profile_version`, reject project-ID or
effective-time regression, append the full replacement revision, advance the
head by one, append the audit event, and persist the idempotency response.

Advancement performs the following operations in one transaction:

1. verify the idempotency key or recognize an exact replay;
2. load and validate the entire current snapshot/event chain;
3. compare the caller's `expected_revision` with the current revision;
4. enforce the candidate evidence-binding and policy-material gates, then run
   the pure lifecycle transition and evaluation-binding checks;
5. append the next snapshot and transition and, for an evaluated terminal
   decision, its exact policy material and evaluation document;
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
- immutable identity and current-pointer agreement with the audit chain;
- contiguous project-profile versions, previous-profile links, monotonic
  effective times, and agreement between the initial registration, ledger, and
  current head;
- v2 candidate binding metadata, referenced profile identity/version, and the
  invariant that every lifecycle snapshot preserves one binding;
- v7 candidate material-requirement metadata, exact material bytes and hashes,
  frozen-profile path authority, and v2 evaluation association.

Reopening the database reconstructs authoritative state from durable rows. It
does not rerun collectors or policy evaluation. Evaluation and attestation
loads also verify stored metadata, canonical documents, rendered Markdown, and
association with the current candidate and complete transition chain.
Evidence-binding loads additionally recompute the binding, candidate, and
assembly identities and compare the embedded candidate with revision one.
Corruption fails closed with a stable store error; this checkpoint does not
repair, salvage, back up, encrypt, or replicate a damaged database.

## Explicit v1/v2/v3/v4/v5/v6/v7 migration

`candidate migrate-store DATABASE` accepts only a fully valid schema-v1,
schema-v2, schema-v3, schema-v4, schema-v5, schema-v6, or schema-v7 store. Missing
historical layers are added
before the v4 project/audit objects. Existing immutable candidate documents are
then projected into deterministic audit-event order. The v4-to-v5 step adds
only the project/candidate discovery index and never replays those audit events.
The v5-to-v6 step projects each existing registered project into profile version
one and creates its head. It deliberately does not fabricate a profile binding
for any legacy candidate, evidence, rejected request, or actor identity.
The v6-to-v7 step adds policy-material persistence and defaults every historical
candidate's immutable requirement marker to zero. It never invents historical
policy bytes, hashes, approval, or producer authenticity.
The v7-to-v8 step adds the empty security-event journal and append-only
triggers. It never invents historical rejected requests, control events,
actors, or trusted timestamps.
The operation updates both metadata values and `PRAGMA user_version` in one
transaction, then revalidates the result. Calling it on v8 is an idempotent
validation. Unknown, foreign, or corrupt stores fail closed.

Existing candidates receive an immutable `evidence_binding_required = 0`
marker. This preserves the historical state without fabricating an assembly
binding. Every candidate created under v3 sets the marker to one and must bind
evidence before `READY`.

Historical candidates receive `policy_material_required = 0`. New
product-surface candidates created under v7 set it to one and cannot complete a
policy decision without a matching `forgegate.policy-material.v1` and
`forgegate.policy-evaluation.v2` pair.

A v1 terminal candidate contains only an evaluation reference, not the full
evaluation document. After migration, `candidate import-evaluation` must be
given the exact original `forgegate.policy-evaluation.v1` document. Candidate
ID, commit, decision, timestamp, and evaluation ID must agree before it is
stored. Attestation is refused until this backfill is complete.

## CLI boundary

`candidate init-store`, `migrate-store`, persisted `candidate create
--database`, `list`, `bind-evidence`, `show-evidence`, `advance`, `show`, `history`,
`materialize-policy`, `evaluate`, `show-policy`, `import-evaluation`, `attest`,
and `show-attestation` expose this repository.
`project list` provides the bounded registered-project discovery path;
`project revise`, `current`, and `history` expose the versioned profile ledger.
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
