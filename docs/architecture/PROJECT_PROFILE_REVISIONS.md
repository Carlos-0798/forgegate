# Project-profile revisions and candidate binding

## Scope

Phase 9 makes project configuration versioned without making historical state
mutable. The original `forgegate.registered-project.v1` document remains profile
version one. Every later configuration is a complete
`forgegate.project-profile-revision.v1` replacement linked to the preceding
profile identity. New product-surface candidates use
`forgegate.release-candidate.v2` and record the exact profile ID/version that
authorized their creation.

These identities prove local content association, not repository ownership,
operator identity, policy-file bytes, trusted time, or producer authenticity.

## Revision document

A revision contains:

- immutable `project_id` and an integer `profile_version` of two or greater;
- `previous_profile_id`, which must identify the immediately preceding profile;
- the complete replacement `forgegate.project.v1` configuration and its
  canonical SHA-256 fingerprint;
- an explicit timezone-aware `effective_at` value; and
- a content-derived `revision_id` binding all fields above.

Partial patches are intentionally unsupported. A consumer can reconstruct the
authority used at any version from one immutable document, without replaying a
sequence of field mutations.

## Write and replay semantics

The caller supplies `expected_profile_version`, `effective_at`, and an
idempotency key. Inside one SQLite write transaction ForgeGate:

1. returns an exact prior response when the key and normalized request match;
2. validates the complete current profile chain;
3. rejects a stale expected version, changed project ID, or time regression;
4. appends the revision and advances the profile head from version N to N+1;
5. appends one `project.profile-revised` audit event; and
6. records the immutable idempotency response.

The profile-head trigger permits only a one-version advance. Profile, binding,
idempotency, and audit rows reject update/delete. These controls protect against
accidental SQL changes; an administrator able to replace the file or schema is
outside the authorization model.

## Candidate binding

The persisted create command first checks its idempotency record. A replay
therefore returns the original candidate even when the current project profile
has changed. A new request resolves the current profile, verifies that candidate
time is not before profile effective time, and authorizes exactly one normalized
release track. ForgeGate then creates a v2 candidate whose identity includes:

- `project_profile_id`; and
- `project_profile_version`.

Every transition preserves both values. Every read verifies the matching
`candidate_profile_bindings` row and referenced profile document. Removing a
track blocks only later creation under the revised profile; it neither deletes
nor reinterprets an earlier candidate.

Legacy v1 candidates remain readable with no binding row. Migration never
guesses which historical registration or revision governed them.

## Read contracts and surfaces

`forgegate.project-profile-page.v1` returns at most 200 complete profiles for
one project in increasing version order. `after_profile_version` is a stable
version cursor, not a snapshot token.

CLI:

```text
forgegate project revise DATABASE PROJECT CONFIG
  --expected-profile-version N --effective-at TIMESTAMP --idempotency-key KEY
forgegate project current DATABASE PROJECT
forgegate project history DATABASE PROJECT
  [--after-profile-version N] [--limit N]
```

Loopback REST API:

```text
POST /v1/projects/{project_id}/revisions
GET  /v1/projects/{project_id}/profile
GET  /v1/projects/{project_id}/revisions
```

The POST body contains the complete config, expected version, and effective
time; `Idempotency-Key` remains mandatory. The API does not load config or policy
files from client-supplied server paths.

## Residual boundary

The profile currently authorizes a configured policy path/name, not the exact
policy-file bytes later evaluated. Binding those bytes is deferred to Phase 10.
Profile deletion, rollback, branching/merging, organization ownership,
authentication, signatures, retention, rejected-request auditing, and
non-loopback deployment are not implemented.
