# Project authority and discovery

## Scope

Phase 8 makes an immutable registered project profile authoritative for every
new candidate created through `CandidateApplication`, the persisted CLI, or the
loopback REST API. It also adds bounded discovery of registered projects and
their current candidate snapshots. Stateless candidate preview and low-level
legacy persistence remain separate compatibility paths; existing candidates
remain readable by exact candidate ID after migration.

Registration does not authenticate a repository, commit, operator, producer,
policy file, or clock. The API remains unauthenticated and loopback-only.

## Candidate-creation authority

The product write path performs project and release-track checks inside the
same SQLite transaction used for candidate creation:

1. the referenced `project_id` must have one valid immutable registration;
2. the candidate release track is represented canonically with hyphens;
3. exactly one configured release-track key must normalize to that identity;
4. the usual candidate identity, idempotency, conflict, snapshot, and audit
   controls then execute.

Project configuration v1 permits underscore and hyphen track keys. To preserve
valid Phase 7 registrations, authority matching treats underscores in a
configuration key as the hyphen form used by candidates and policy names. Zero
matches rejects as not configured; multiple normalized matches reject as
ambiguous. ForgeGate never chooses one ambiguous policy path silently.

An exact retry returns the originally persisted response before resolving the
current profile, so a later revision cannot change retry meaning. Initial
registrations and later profile revisions cannot be deleted or rewritten in
schema v6. A legacy candidate may be read directly without a fabricated
registration or profile binding, but project-scoped discovery requires the
project to exist.

## Discovery contracts

`forgegate.registered-project-page.v1` returns at most 200 complete immutable
registrations in increasing `project_id` order. Its cursor is the final returned
project ID.

`forgegate.release-candidate-page.v1` returns at most 200 current validated
candidate snapshots for one registered project in increasing `candidate_id`
order. Every item must match the page project, and its cursor is the final
returned candidate ID. Candidate history remains available from the existing
per-candidate endpoint.

These lexicographic cursors are stable for existing identifiers, but they are
not snapshot tokens. A project or candidate inserted later with an identifier
before a caller's cursor is not retroactively returned by that traversal.
Callers requiring a complete contemporaneous change stream should use the
database-local audit sequence instead.

CLI:

```text
forgegate project list DATABASE [--after-project ID] [--limit N]
forgegate candidate list DATABASE --project ID
                         [--after-candidate ID] [--limit N]
```

Loopback REST API:

```text
GET /v1/projects
GET /v1/projects/{project_id}/candidates
```

## SQLite v5

Schema v5 adds the composite
`candidates_project_candidate(project_id, candidate_id)` index. It supports the
bounded project-scoped traversal without changing candidate documents or
fabricating project associations. Explicit migration accepts validated
v1/v2/v3/v4 stores. A v4-to-v5 migration adds only the index and does not replay
existing audit events; earlier migrations retain the Phase 7 deterministic
audit projection.

## Phase 9 realization of the frozen revision direction

Phase 9 implements the previously frozen semantics as follows:

- `project_id` is permanently immutable;
- a revision supplies the complete replacement profile, caller idempotency key,
  expected current profile version, previous registration identity, and an
  explicit timezone-aware effective time;
- storage appends a new profile row and advances a compare-and-swap current
  pointer; it never updates or deletes a historical profile document;
- the revision identity binds the previous identity, full new configuration,
  canonical fingerprint, version, and effective time;
- the v2 candidate contract binds the exact project-profile identity and
  version used at creation, so later track changes cannot reinterpret an older
  candidate;
- removed tracks affect only later candidates; historical candidates and audit
  subjects continue to resolve through their frozen profile identity;
- conflicting expected versions, idempotency reuse, project-ID changes, time
  regression, and ambiguous normalized tracks fail closed.

The detailed document, storage, CLI, and REST contracts are in
`PROJECT_PROFILE_REVISIONS.md`. The original registration remains the immutable
version-one profile; revisions append version two and later documents.

## Residual boundary

Discovery is local database navigation, not authorization. Results are current
validated state, not a signed inventory, remote registry, or compliance export.
Rejected requests are still not inserted into the durable audit log. Profile
deletion, organization ownership, authentication, policy-file byte binding,
retention, signatures, and non-loopback operation remain deferred.
