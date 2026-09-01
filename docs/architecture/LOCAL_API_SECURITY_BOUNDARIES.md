# Local API security boundaries

## Scope

Phase 15 closes three local API gaps without changing ForgeGate's deployment
class: it counts actual request bytes, applies authentication endpoint limits
before body-model validation, and persists minimal API-control telemetry. The
service remains loopback-only and does not gain TLS, proxy identity,
distributed sessions, hostile-local-user protection, or production approval.

## Actual request-byte limit

The HTTP middleware first rejects invalid or declared-oversized
`Content-Length`, then reads ASGI `http.request` messages while summing the
actual body bytes. It retains at most 4 MiB and returns
`413 API_BODY_TOO_LARGE` as soon as the next byte crosses the limit. Accepted
messages are replayed unchanged to FastAPI, so strict request parsing still
sees the original body.

This covers requests with no `Content-Length`, including chunked test input,
and detects a body larger than its declared length at the application layer. A
single transport-provided chunk may already have been allocated by the ASGI
server before middleware receives it; transport/server-level denial-of-service
controls remain outside this local application boundary.

## Pre-validation authentication limits

For exact `POST /v1/auth/challenges` and `POST /v1/auth/sessions` paths, the
middleware consumes the existing process-global fixed-window counter before
reading or validating the body. Typed endpoint methods receive an internal
marker so a valid request is not counted twice. Direct `ApiAuthenticator`
calls retain their own default counting behavior.

The counter keys remain fixed and do not include a supplied identity, session,
IP address, forwarded header, or request payload. Malformed JSON can therefore
reach `422` once within a one-event test window and then receives the same
`429 API_AUTH_RATE_LIMITED` response as valid-shaped excess calls.

## Separate API security-event journal

Security-control activity is not release evidence and does not enter the
transactional project/candidate audit chain. SQLite schema v8 adds a distinct
append-only `api_security_events` table with its own monotonically increasing
sequence. The versioned documents are:

- `forgegate.api-security-event.v1`;
- `forgegate.api-security-event-page.v1`.

The journal recognizes only five event types:

- `authentication.rejected`;
- `authentication.rate-limited`;
- `session.logged-out`;
- `session.revoked`;
- `trust-store.reloaded`.

Each event contains server-observed time, a safe request correlation ID, a
stable outcome code, an optional public `forgegate.audit-actor.v1`, and only
the canonical session or trust-store target required for successful controls.
Its content-derived ID excludes the local sequence but covers every semantic
field. Bearer tokens, token digests, signatures, request/response bodies,
private keys, authorization headers, client-selected messages, and arbitrary
metadata are not fields and are not persisted.

## Capacity, query, and failure semantics

The repository default is 10,000 events and accepts an explicit capacity from
1 to 1,000,000. It never deletes or overwrites a row. Once full, new event
writes return a stable repository capacity error; page responses always expose
`recorded_count`, `capacity`, and `saturated` so incompleteness is visible.

`GET /v1/security-events` provides bounded 1-200 pages, a stable exclusive
sequence cursor, and optional event-type filtering. Access requires an active
operator session covering every project in the current trust store because
authentication failures and trust reload are not naturally project-scoped.

Journal writes are intentionally best-effort. A successful logout, revocation,
or reload changes in-memory security state before telemetry is appended. If
the database is unavailable or saturated, the control still succeeds. An
authentication error likewise retains its original response even when event
recording fails. The journal therefore does not claim atomicity with in-memory
session state, completeness, retention, compliance, trusted time, or
administrator-resistant tamper evidence.

## Migration and evidence boundary

Explicit v7-to-v8 migration creates an empty journal. ForgeGate cannot infer
past requests or session controls and fabricates none. Earlier product-state
audit, project, candidate, evidence, policy, and attestation rows are unchanged.

Tests prove local contract validation, append-only triggers, cursor/capacity
semantics, migration, global-operator authorization, event privacy, malformed
body accounting, unknown-length byte limiting, and continued control behavior
when the journal is saturated. These are local host-test claims only; no
hardware, AFE runtime, MSP430, LAN, shared-host, internet, or production
behavior was exercised.
