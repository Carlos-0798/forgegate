# Phase 7 project registry and audit-query acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev14
- Scope: immutable local project registration, SQLite v4 audit events, stable
  cursor queries, CLI, and loopback REST endpoints
- Hardware/device work: none
- Remote/publication work: private repository synchronization only

## Accepted capability

ForgeGate can register one exact version-one project profile with caller-owned
idempotency, retrieve it through CLI or REST, and query bounded append-only
audit-event pages by database sequence, project, or candidate. Successful
project/candidate lifecycle writes append content-bound audit metadata in the
same SQLite transaction. Exact retries do not duplicate events.

Validated v1/v2/v3 databases migrate explicitly to v4. Existing candidate,
transition, binding, evaluation, and attestation documents are projected into
deterministically ordered audit events without fabricating project profiles,
evidence, identities, or missing documents.

## Verified controls

- strict `forgegate.registered-project.v1`, `forgegate.audit-event.v1`, and
  `forgegate.audit-event-page.v1` contracts;
- canonical config, registration, subject, and event fingerprints;
- immutable project/audit/idempotency tables and exact replay/conflict behavior;
- transactional audit append for candidate creation, binding, transition,
  evaluation, and attestation writes;
- stable `after_sequence` pagination with 1-200 bounds and exact filters;
- canonical row/document cross-checks and corruption rejection;
- complete v3 binding/evaluation/attestation migration backfill;
- shared application-service behavior across CLI and REST;
- deterministic committed JSON Schemas and OpenAPI 3.1 contract;
- installed-wheel project registration, readback, audit query, and operation-ID
  smoke paths.

## Local verification result

- `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict across package and verification tools: PASS
- pytest: 563 passed, 1 skipped because this Windows host could not create the
  symlink test fixture
- branch-aware coverage: 100% across 4,385 statements and 1,180 branches
- 13 canonical versioned document Schemas plus two artifact Schemas: PASS
- committed OpenAPI drift check: PASS
- source distribution, wheel, clean installation, and installed CLI smoke: PASS

These are local-host software results. GitHub Actions evidence is recorded only
after the final private push completes. No physical device, upstream runtime,
authenticated producer, TLS, authorization, or public deployment was tested.

## Residual and human-intervention boundary

No user action, credential change, board access, serial port, AFE runtime, or
external service was required. The registry is immutable version one and is not
yet enforced as candidate-creation authority. Project updates/listing, audit
export/retention, rejected-request event ingestion, signatures, actor identity,
and administrator-resistant storage remain unimplemented. The REST service must
remain loopback-only.
