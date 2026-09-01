# Phase 14 local session lifecycle acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev21
- Evidence level: LOCAL_HOST_TEST
- Hardware evidence: none; no device access was performed
- Deployment boundary: authenticated loopback only; not production-ready

## Accepted scope

- `DELETE /v1/auth/session` removes the authenticated caller's exact in-memory
  session before returning.
- `DELETE /v1/auth/sessions/{session_id}` requires operator role and complete
  target-project coverage; missing and out-of-scope targets are indistinguishable.
- `POST /v1/auth/trust-store/reload` reads only the fixed startup path and
  requires the caller to remain an exact trusted operator covering every
  project in both store versions.
- A changed trust store clears challenges bound to the old store and removes
  sessions whose identity, role, or project authority is no longer valid.
- Challenge, session-exchange, and invalid-Bearer fixed windows use three
  bounded process-global counters and return HTTP 429 with `Retry-After`.
- OpenAPI and installed-wheel smoke exercise the new public contracts without
  importing AFE/MSP software or touching hardware.

## Adversarial cases

- logged-out token reuse;
- operator exact-target revocation and caller survival;
- producer targeted-revocation denial;
- cross-project target concealment;
- unknown session concealment;
- invalid and unavailable reload sources;
- insufficient global reload scope;
- byte-identical no-op reload;
- removal of a now-untrusted session;
- invalidation of a challenge tied to the old trust-store ID;
- challenge, session-exchange, and invalid-Bearer rate exhaustion;
- retry-window reset and `Retry-After` response propagation;
- unsafe constructor bounds for rate count/window configuration.

## Verification result

- dependency consistency: PASS
- Ruff and formatting: PASS
- strict mypy: PASS across source and verification tools
- pytest: 649 passed, 1 skipped because Windows symlink creation was unavailable
- branch-aware coverage: 97.83% across 6,232 statements and 1,642 branches
- Phase 14 authentication focus: 25 passed; authentication module 96.60%
- committed JSON Schemas and OpenAPI: generated, parsed, and drift-checked
- sdist, wheel, clean installation, installed lifecycle smoke, and existing
  release-assurance workflow: PASS
- GitHub Actions run 33461739673 PASS on Windows, Ubuntu, and macOS for Phase
  14 implementation commit `d226816`

## Explicit limitations

- no TLS, reverse-proxy trust, non-loopback serving, shared-host approval, or
  hostile-local-user defense;
- no durable/distributed session or revocation state;
- no managed online trust distribution, key rotation, or trusted time;
- no durable audit event for rejected authentication, logout, revocation,
  reload, or rate rejection;
- no per-client/IP rate identity and no trust in forwarded-address headers;
- malformed bodies rejected before typed endpoint execution are not covered by
  the Phase 14 authentication counters;
- no database-administrator-resistant tamper evidence;
- no AFE runtime integration, MSP430 collector, serial access, firmware action,
  bench measurement, or production evidence.

Phase 14 improves local session control only. It does not authorize LAN,
internet, shared-host, or production deployment.
