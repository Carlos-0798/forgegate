# Phase 9 project-profile revisions acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev16
- Scope: append-only project-profile revisions, profile-bound candidate v2,
  SQLite v6, and current/history CLI/REST contracts
- Hardware/device work: none
- Remote/publication work: private repository synchronization only

## Accepted capability

The initial registered project remains immutable profile version one. A caller
may append a complete replacement profile only with the expected current
version, explicit effective time, and an idempotency key. ForgeGate links the
new content-derived revision to its immediate predecessor and advances one
compare-and-swap head without rewriting history.

Every new candidate created through the application, persisted CLI, or loopback
REST API is a `forgegate.release-candidate.v2` document containing the exact
profile ID/version used for authority. Later configuration revisions do not
reinterpret that candidate. Exact retries return the original candidate even
after the profile changes. Track additions/removals apply only to later new
requests.

Validated v1-v5 migration creates a version-one profile only for an existing
registered project. It does not fabricate a profile binding for a legacy v1
candidate.

## Verified controls

- revision content identity, previous-profile linkage, full replacement config,
  project-ID invariance, and monotonic effective time;
- stale expected-version rejection, exact replay, conflicting-key rejection,
  and append-only/CAS database triggers;
- current profile and bounded version-ordered history through repository,
  application, CLI, REST, JSON Schema, and OpenAPI contracts;
- profile-bound candidate identity, lifecycle preservation, durable binding-row
  validation, and fail-closed missing-binding corruption;
- historical candidate resolution after track removal and later-candidate
  authority after track addition;
- explicit v5-to-v6 migration with registration-only backfill;
- installed-wheel project current/history plus full profile-bound candidate,
  evidence, evaluation, and attestation smoke.

## Local verification result

- `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict across package and verification tools: PASS
- pytest: 573 passed, 1 skipped because this Windows host could not create the
  symlink test fixture
- branch-aware coverage: 99.05% across 4,799 statements and 1,284 branches
- 18 canonical versioned document Schemas plus two artifact Schemas: PASS
- committed OpenAPI drift check: PASS
- source distribution, wheel, clean installation, and installed CLI smoke: PASS

These are software/local-host results. No physical device, upstream runtime,
authenticated producer, TLS, authorization, or public deployment was tested.
Private GitHub Actions run
[`33436111147`](https://github.com/Carlos-0798/forgegate/actions/runs/33436111147)
passed `tools/verify.py` and `tools/release_smoke.py` on Windows, Ubuntu, and
macOS for implementation commit `61c7726`.

## Residual and human-intervention boundary

No user action, credential change, board access, serial port, AFE runtime, or
external load was required. The profile authorizes a policy path/name, not the
exact policy-file bytes; that binding remains a Phase 10 task. Rejected-request
audit ingestion, authenticated identity, signatures, retention/export,
administrator-resistant storage, and non-loopback deployment remain
unimplemented. No License, GitHub Release, visibility change, or LinkedIn action
is authorized by this acceptance.
