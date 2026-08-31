# Phase 5 local REST API baseline acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev12
- Scope: shared candidate application service, local FastAPI v1 read/create
  surface, structured failures, loopback serving, and OpenAPI contract
- Hardware/device work: none
- Remote/publication work: none

## Accepted capability

ForgeGate can serve a versioned, local-only REST surface for health,
idempotent candidate creation, and candidate/history/evidence/attestation
readback. CLI and HTTP share `CandidateApplication` and the same candidate
domain plus SQLite repository, so the API does not duplicate candidate or
idempotency policy.

The API is an integration baseline, not a production deployment surface. It
has no authentication or authorization, accepts only loopback binds, and does
not expose lifecycle, evidence-binding, evaluation, or attestation writes.

## Verified controls

- strict request bodies and required idempotency header;
- exact create replay and conflicting-key HTTP 409 behavior;
- candidate, history, binding, and attestation read paths over SQLite v3;
- a full real-store flow through binding, READY/EVALUATING/PASS, attestation,
  and HTTP readback;
- stable store-code mappings across HTTP 400/404/409/500/503;
- fixed structured HTTP 422 validation failures;
- sanitized unexpected HTTP 500 responses with no raw exception detail;
- safe generated, echoed, and invalid caller request-ID behavior;
- IPv4 loopback, IPv6 loopback, and `localhost` acceptance plus external,
  wildcard, and invalid-host rejection;
- deterministic OpenAPI export, exact committed drift check, and installed
  wheel contract comparison;
- byte-equivalent candidate creation through CLI and HTTP.

## Local verification result

- `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict across package and verification tools: PASS
- local API/application focus: 27 passed; 100% across 173 statements and 12
  branches
- full pytest: 550 passed, 1 skipped because this Windows host could not create
  the symlink test fixture
- full branch-aware coverage: 100% across 4,007 statements and 1,106 branches
- committed JSON Schemas and OpenAPI 3.1: exported and drift-checked
- source-distribution required-path manifest: PASS
- repository-external wheel installation: PASS
- installed OpenAPI export and byte comparison: PASS
- installed server external-bind rejection: PASS
- all prior installed collection, assembly, candidate, evaluation, binding,
  attestation, and readback smoke paths: PASS

These are local-host software results. They are not remote CI, hardware,
producer-authentication, authorization, TLS, or public-release evidence.

## Compatibility boundary

The API exposes only ForgeGate-owned candidate documents. It neither imports
Analog Validation Studio nor opens a serial/device interface. Existing AFE
artifact compatibility continues through the generic collection and assembly
boundary, and a future MSP430 collector remains gated on a separate frozen
public artifact contract.

Adding peer-project support does not require a device-specific API route: both
can continue producing optional versioned artifacts that ForgeGate normalizes,
assembles, binds, and evaluates through the same generic workflow.

## Human-intervention and assurance boundary

No human action, MSP430 board interaction, credential, remote account, port
forward, or publication step was required for this phase. The user should not
expose the service outside loopback. Any future authenticated or non-loopback
deployment requires an explicit security design and approval before work
begins.
