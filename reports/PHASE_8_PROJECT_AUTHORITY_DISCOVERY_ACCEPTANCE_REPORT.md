# Phase 8 project authority and discovery acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev15
- Scope: registered-project candidate authority, normalized release-track
  resolution, bounded project/candidate discovery, and SQLite v5 migration
- Hardware/device work: none
- Remote/publication work: private repository synchronization only

## Accepted capability

Every new candidate persisted through the shared application, CLI, or loopback
REST surface must reference an existing immutable project registration and
exactly one configured release track after documented underscore-to-hyphen
normalization. Missing, noncanonical, and ambiguous authority fails before the
candidate, idempotency response, or audit event is written.

Registered projects and current project-scoped candidates can be queried in
strict pages of 1-200 records with lexicographic cursors. Existing legacy
candidates remain readable by candidate ID without inventing project profiles;
they are not exposed through registered-project discovery until the referenced
project actually exists.

SQLite v5 adds a composite project/candidate index. Explicit v1-v4 migration
preserves earlier data and audit semantics. A v4 migration does not duplicate
already recorded audit events.

## Verified controls

- canonical new-candidate release-track identity with compatibility for valid
  Phase 7 underscore configuration keys;
- rejection of unregistered projects, unconfigured tracks, noncanonical stored
  requests, and normalized-key ambiguity;
- transactional authority check and candidate creation;
- bounded, ordered, scope-checked project and candidate page models;
- application, CLI, REST, JSON Schema, and OpenAPI parity;
- direct legacy candidate read preservation without fabricated registration;
- explicit v4-to-v5 index migration and idempotent migration revalidation;
- installed-wheel rejection, registration, creation, project listing, candidate
  listing, and existing lifecycle smoke paths.

## Local verification result

- `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict across package and verification tools: PASS
- pytest: 568 passed, 1 skipped because this Windows host could not create the
  symlink test fixture
- branch-aware coverage: 100% across 4,501 statements and 1,214 branches
- 15 canonical versioned document Schemas plus two artifact Schemas: PASS
- committed OpenAPI drift check: PASS
- source distribution, wheel, clean installation, and installed CLI smoke: PASS

Cross-platform GitHub Actions run
[33411154421](https://github.com/Carlos-0798/forgegate/actions/runs/33411154421)
completed `verify.py` and `release_smoke.py` successfully on Windows, Ubuntu,
and macOS for implementation commit `6c99d9708b37f0ea4aef52a427e98fda63179d2b`.
These are software results. No physical device, upstream runtime, authenticated
producer, TLS, authorization, or public deployment was tested.

## Residual and human-intervention boundary

No user action, credential change, board access, serial port, AFE runtime, or
external service was required. Project-profile mutation is intentionally not
implemented; the future append-only revision and candidate profile-binding
semantics are documented before that work begins. Discovery cursors are not
snapshot tokens. Rejected-request audit ingestion, authenticated identity,
signatures, retention/export, and administrator-resistant storage remain
unimplemented. The REST service must remain loopback-only.
