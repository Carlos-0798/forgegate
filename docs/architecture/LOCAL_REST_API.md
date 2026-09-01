# Local REST API

## Purpose and scope

Phase 5 exposes a small HTTP transport over ForgeGate's existing candidate
domain and SQLite store. It is intended for local tool integration while the
product remains under development. Phase 13 adds an authenticated local session
layer, Phase 14 adds memory-only lifecycle/reload/rate controls, and Phase 15
adds byte-accurate body limits plus a separate bounded security-event journal,
while the service remains deliberately restricted to the loopback interface.

The v1 baseline includes:

- `GET /healthz`;
- `GET /v1/projects`;
- `GET /v1/projects/{project_id}`;
- `GET /v1/projects/{project_id}/profile`;
- `GET /v1/projects/{project_id}/revisions`;
- `POST /v1/projects/{project_id}/revisions`;
- `GET /v1/security-events`;
- `GET /v1/projects/{project_id}/candidates`;
- `POST /v1/candidates`;
- `POST /v1/candidates/{candidate_id}/transitions`;
- `POST /v1/candidates/{candidate_id}/evidence`;
- `POST /v1/candidates/{candidate_id}/evaluate`;
- `POST /v1/candidates/{candidate_id}/attestation`;
- `GET /v1/candidates/{candidate_id}`;
- `GET /v1/candidates/{candidate_id}/history`;
- `GET /v1/candidates/{candidate_id}/evidence`;
- `GET /v1/candidates/{candidate_id}/policy`;
- `GET /v1/candidates/{candidate_id}/attestation`.

Project registration/revision and candidate creation, advancement, evidence binding, and evaluation require
`Idempotency-Key` and use the same durable idempotency records as the CLI/store.
Creation also requires the current project profile and the requested track to
match exactly one normalized project configuration key. New candidates retain
that exact profile ID/version. Project revision additionally requires
`expected_profile_version`; its history uses a strict one-to-200 version cursor.
The project/candidate list routes use strict one-to-200 limits and exclusive
stable string cursors; candidate listing requires the project to exist and
never crosses project scope.
Advancement and evaluation also require `expected_revision`. Attestation
creation is deterministic against an immutable terminal candidate and replays
the stored document exactly.

No API command accepts an artifact input path, policy input path, or
attestation output directory. Collection, policy materialization, and
filesystem publication remain explicit CLI operations. Evaluation accepts a
complete self-validating policy-material document.

## Shared application boundary

`CandidateApplication` accepts validated commands and delegates to
`SQLiteCandidateRepository`. Project registration/revision/current/history,
project/candidate list, candidate-create, show, history, show-evidence,
show-policy, and show-attestation CLI paths use this service, as do the HTTP routes. FastAPI
handlers do not reimplement candidate identity, profile authority, persistence,
idempotency, binding, or attestation policy.

The layering is:

```text
CLI command ─┐
             ├─> CandidateApplication ─> candidate domain + SQLite repository
HTTP route ──┘
```

The shared service now owns create, advance, bind, evaluate, attest, and read
commands. Evaluation loads the persisted binding, passes its nested evidence
bundle and supplied validated material to the policy engine, derives the
terminal state from the decision, and uses one repository transaction for the
material, evaluation, and terminal transition.

## Validation and error contract

Request bodies are strict Pydantic models: unknown fields and malformed domain
values reject with HTTP 422. Store failures retain their stable ForgeGate code
and map to 404, 409, 500, or 503 as appropriate. Unexpected exceptions return
HTTP 500 with `API_INTERNAL_ERROR`; raw exception text is not returned.

Every response carries `X-Request-ID`. A caller may supply an eight-to-128
character safe identifier; otherwise ForgeGate generates `req-` plus a random
UUID. Invalid caller values receive a structured HTTP 400 response containing
a replacement safe ID.

## Local serving boundary

`forgegate serve` accepts `localhost` or an IP address for which the standard
library reports `is_loopback`. Wildcard, LAN, public, and unparseable bind
values reject before the database or server is opened. Middleware separately
requires the HTTP `Host` to identify localhost or a loopback IP. Requests with
a declared `Content-Length` above 4 MiB reject before model validation. The
middleware also counts actual ASGI body bytes and rejects requests that cross
the same ceiling even when the declared length is absent or misleading.

These transport guards are separate from authentication. Protected routes
additionally require a short-lived session derived from an Ed25519 challenge
and an external trust store. Phase 14 adds self-logout, scoped operator
revocation, explicit reload from the fixed startup trust-store path, and three
process-global authentication counters. Phase 15 consumes the challenge and
session endpoint budgets before body-model validation, so malformed requests
cannot bypass those two counters. It also writes minimal successful-control and
authentication-rejection metadata to a bounded, append-only SQLite v8 journal.
An active operator covering every current trust-store project may query that
journal through `GET /v1/security-events`; capacity and saturation are visible.
Logging is best-effort and never changes the original control response.

No TLS, per-client network throttling, multi-tenant isolation, reverse-proxy
trust, durable sessions/revocation, complete compliance audit, or
hostile-local-user defense is claimed.
The server must not be forwarded or exposed through a proxy, container port,
tunnel, LAN address, or public interface.

## OpenAPI and verification

`forgegate export-openapi schemas/forgegate.openapi.v1.json` derives the
OpenAPI 3.1 document from the application without starting the server or
touching a database. Development verification compares it byte-for-byte with
the committed contract. Release smoke builds a wheel, installs it outside the
repository, exports OpenAPI again, compares the bytes, and confirms that an
external bind request fails.

Tests cover API/CLI parity, exact replay/conflict, expected-revision races,
invalid states, frozen-profile policy-material mismatch, structured failures,
correlation IDs, loopback bind/Host handling, declared body size, challenge and
session authentication, project/role authorization, audit actors, logout,
targeted revocation, trust reload, authentication rate windows, contract paths,
malformed pre-validation attempts, unknown-length/chunked body size, security
event privacy/capacity/query behavior, and a complete durable candidate
workflow. These are local-host software results only; they do not exercise AFE
runtime code, MSP430 hardware, a network deployment, or remote CI.
