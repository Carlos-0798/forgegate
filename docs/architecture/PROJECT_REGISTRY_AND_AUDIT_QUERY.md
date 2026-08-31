# Project registry and audit-event query

## Scope

Phase 7 adds a domain-neutral, local project registry and a read-only query
surface over durable audit events. It does not authenticate a project owner,
producer, operator, repository, commit, or clock. The API remains loopback-only.

`forgegate.registered-project.v1` stores the exact strict
`forgegate.project.v1` profile, its canonical SHA-256 fingerprint, a
content-derived registration ID, profile version one, and a caller-supplied
timezone-aware registration time. Registration is immutable. Exact retries are
idempotent; a different registration under the same project ID fails closed.
Project updates, deletion, and policy distribution are deferred. Phase 8 adds
bounded listing without changing this immutable registration document.

The registry does not retroactively become evidence. Phase 8 makes it
authoritative for new application/CLI/REST candidate creation while retaining
the low-level legacy read/persistence boundary. A candidate's `project_id` is
retained in audit events, but migration never invents a project profile.

## SQLite v4

Schema v4 adds:

- `projects`, containing one canonical immutable registration per project ID;
- `project_idempotency_records`, binding caller keys to exact registration
  requests and responses;
- `audit_events`, containing ordered canonical event documents and indexed
  project/candidate query fields.

Update/delete triggers protect all three tables. Successful project
registration, candidate creation, evidence binding, candidate transition,
evaluation persistence, and attestation persistence append their audit event
inside the same SQLite write transaction. Exact idempotent replay appends no
second event. A rollback leaves neither the domain write nor its audit event.

Explicit migration accepts validated v1, v2, or v3 databases. It first adds the
missing historical schema layers, then deterministically projects existing
immutable candidate documents into v4 audit events ordered by recorded time,
event class, and subject ID. This projection records what the database already
contains; it does not reconstruct absent evidence, project profiles, operator
identity, or rejected requests.

## Audit contract

`forgegate.audit-event.v1` contains:

- an SQLite-local monotonically increasing `sequence` cursor;
- a content-derived event ID that excludes the storage sequence;
- event type and timezone-aware occurrence time;
- project and optional candidate association;
- subject schema, subject ID, and canonical subject fingerprint.

The event does not duplicate the complete subject document. Consumers use the
subject metadata for ordering and integrity-aware correlation, then retrieve
the authoritative project/candidate resource separately. SHA-256 detects
content mismatch; it is not a signature or identity proof.

`forgegate.audit-event-page.v1` returns strictly increasing events, the last
returned sequence as `next_after_sequence`, and `has_more`. Queries accept
optional exact project/candidate filters, `after_sequence >= 0`, and a limit of
1-200. The sequence is a stable cursor only within that database lineage; it is
not portable across restored, independently migrated, or rebuilt databases.

## Product surfaces

CLI:

```text
forgegate project register DATABASE CONFIG --registered-at TIME --idempotency-key KEY
forgegate project show DATABASE PROJECT_ID
forgegate audit events DATABASE [--project ID] [--candidate ID]
                              [--after-sequence N] [--limit N]
```

Loopback REST API:

```text
POST /v1/projects
GET  /v1/projects/{project_id}
GET  /v1/audit-events
```

The POST requires `Idempotency-Key`. Query endpoints are read-only and share
the same application and SQLite validation boundary as the CLI.

## Residual boundary

The durable audit log currently covers successful state changes. Validation
failures, parser warnings before durable candidate binding, rejected API
requests, local process logs, and collector-only results are not automatically
inserted into SQLite audit events. Persisting those safely requires a separate
bounded event-ingestion/redaction contract and authenticated actor semantics.
No claim is made that v4 is administrator-resistant, append-only outside
SQLite, remotely replicated, retained for a fixed period, or suitable for
compliance logging.
