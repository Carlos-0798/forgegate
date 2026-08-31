# Phase 10 profile-authorized policy materialization acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev17
- Scope: exact policy material, material-bound evaluation v2, SQLite v7, and
  CLI/path-free REST workflow
- Hardware/device work: none
- Remote/publication work: private repository synchronization only

## Accepted capability

Every new persisted candidate retains the exact immutable project-profile
identity that authorized it. The CLI can now resolve that profile's selected
release-track policy only through an explicit project root and emit a
self-validating `forgegate.policy-material.v1` document containing exact bytes,
media type, size, SHA-256, parsed policy, and content-derived identity.

Terminal evaluation for a new product candidate requires the material rather
than accepting policy-name equality alone. `forgegate.policy-evaluation.v2`
binds the decision to the material ID, artifact hash, frozen profile ID/version,
evidence fingerprint, and explicit evaluation time. SQLite v7 commits material,
evaluation, transition, audit events, current pointer, and idempotency response
inside one rollback boundary.

The REST API accepts the complete validated material document and never opens a
client-selected policy path. Validated v1-v6 migrations set no historical
material requirement and create no material row, policy bytes, producer
identity, approval, or authenticity claim.

## Verified controls

- exact-byte base64, size, SHA-256, parsed-policy, fingerprint, track, profile,
  and material-ID consistency;
- UTF-8, duplicate-key, unsupported media, unsafe path, malformed content, and
  detached embedded-document rejection;
- semantically equal policies with different bytes receive different material
  and artifact identities;
- candidate/profile/version/track/path authority and v2
  material/evidence/timestamp association;
- rejection of legacy v1 evaluation for a new v7 product candidate;
- exact evaluation replay plus material readback through application, CLI, and
  loopback REST contracts;
- injected rollback after material insertion, transition append, pointer
  update, and idempotency insertion;
- explicit v6-to-v7 migration without fabricated historical material;
- committed JSON Schema/OpenAPI drift checks and installed-wheel workflow.

## Local verification result

- `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict across package and verification tools: PASS
- pytest: 585 passed, 1 skipped because this Windows host could not create the
  symlink test fixture
- branch-aware coverage: 98.48% across 5,085 statements and 1,380 branches
- 20 canonical versioned document Schemas plus two artifact Schemas: PASS
- committed OpenAPI drift check: PASS
- source distribution, wheel, clean installation, and installed CLI smoke: PASS

These are software/local-host results. No physical device, AFE runtime, MSP430
board, authenticated producer, TLS, authorization, or public deployment was
tested. Cross-platform GitHub Actions evidence is recorded only after the
private remote run completes; local success is not described as remote or
hardware verification.

## Residual and human-intervention boundary

No user action, credential change, serial port, AFE runtime, or hardware access
was required. The current release attestation embeds the material-bound v2
evaluation and material ID but not the complete policy bytes; the v7 database
and policy read endpoint retain them. Portable material bundling, rejected-
request audit ingestion, authenticated identity, signatures, retention/export,
administrator-resistant storage, and non-loopback deployment remain
unimplemented. No License, GitHub Release, visibility change, or LinkedIn action
is authorized by this acceptance.
