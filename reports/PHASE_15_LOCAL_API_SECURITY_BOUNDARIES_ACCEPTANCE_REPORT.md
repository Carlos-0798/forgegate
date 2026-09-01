# Phase 15 local API security boundaries acceptance report

- Date: 2026-08-31
- Version: `0.1.0.dev22`
- Stage: implemented, locally verified, and cross-platform CI verified
- Evidence class: local-host software tests and clean-install packaging smoke

## Accepted scope

Phase 15 closes three bounded local API gaps without expanding ForgeGate beyond
loopback-only use:

1. challenge and session endpoint budgets are consumed before Pydantic body
   validation, including malformed requests;
2. the 4 MiB request ceiling is enforced against the body bytes actually
   received, including absent/unknown declared length;
3. minimal authentication/session/trust-control events use a separate,
   append-only and capacity-bounded SQLite v8 journal with stable-cursor query.

The journal covers authentication rejection/rate limiting, self-logout,
operator session revocation, and trust-store reload. Stored contracts contain
only stable event type/outcome, request correlation, server occurrence time,
safe public actor metadata when authentication succeeded, and canonical target
identity where applicable. Bearer tokens, challenge signatures, request bodies,
private keys, and arbitrary headers are not retained.

## Verification evidence

- `python tools/verify.py`: PASS
- pytest: 656 passed, 1 skipped
- branch coverage: 97.48%
- measured source: 6,453 statements and 1,708 branches
- Ruff, format check, strict mypy, dependency check, committed Schema drift, and
  OpenAPI drift: PASS
- `python tools/release_smoke.py`: PASS, including clean wheel/sdist install,
  installed OpenAPI operation discovery, v8 persistence, and bounded journal
  saturation behavior

The one skipped test is the existing actual Windows symlink-escape fixture;
this host did not permit symlink creation. This does not represent a skipped
Phase 15 API-security test.

## Explicit limitations

- The journal is best-effort. A saturated or unavailable database does not
  block logout, revocation, reload, or the original authentication response.
- Capacity/count/saturation are visible, but retention, rotation, export,
  alerting, and administrator-resistant storage are not implemented.
- Event timestamps are server-observed and are not trusted time.
- Sessions, revocations, challenges, and rate windows remain process-local and
  disappear on restart.
- No TLS, reverse-proxy trust, hostile-local-user defense, LAN/internet
  deployment, hardware validation, MSP430 access, or AFE runtime access is
  claimed.

## Cross-platform evidence

Private `main` implementation commit `3f00d91` triggered GitHub Actions run
[`33465814655`](https://github.com/Carlos-0798/forgegate/actions/runs/33465814655).
Windows, Ubuntu, and macOS all passed both `python tools/verify.py` and
`python tools/release_smoke.py`.
