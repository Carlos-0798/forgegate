# Local REST API

## Purpose and scope

Phase 5 exposes a small HTTP transport over ForgeGate's existing candidate
domain and SQLite store. It is intended for local tool integration while the
product remains under development. The server is unauthenticated and is
therefore deliberately restricted to the local loopback interface.

The v1 baseline includes:

- `GET /healthz`;
- `POST /v1/candidates`;
- `GET /v1/candidates/{candidate_id}`;
- `GET /v1/candidates/{candidate_id}/history`;
- `GET /v1/candidates/{candidate_id}/evidence`;
- `GET /v1/candidates/{candidate_id}/attestation`.

Candidate creation is the only HTTP write. It requires `Idempotency-Key` and
uses the same durable idempotency record as the CLI. Lifecycle advancement,
evidence binding, evaluation import, and attestation creation remain CLI/store
operations until their HTTP authorization and concurrency contracts are
designed explicitly.

## Shared application boundary

`CandidateApplication` accepts validated commands and delegates to
`SQLiteCandidateRepository`. The candidate-create, show, history,
show-evidence, and show-attestation CLI paths use this service, as do the HTTP
routes. FastAPI handlers do not reimplement candidate identity, persistence,
idempotency, binding, or attestation policy.

The layering is:

```text
CLI command ─┐
             ├─> CandidateApplication ─> candidate domain + SQLite repository
HTTP route ──┘
```

This slice does not move transition/evaluation/binding writes into the service;
those CLI paths retain their existing repository calls until their future HTTP
commands are introduced.

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
library reports `is_loopback`. Wildcard, LAN, public, and unparseable host
values reject before the database or server is opened. This is a safety guard,
not authentication: any process or user able to connect to the loopback port
has the API's current local permissions.

No TLS, identity, authorization, rate limiting, multi-tenant isolation, reverse
proxy trust, or hostile-local-user defense is claimed. The server must not be
forwarded or exposed through a proxy, container port, tunnel, LAN address, or
public interface.

## OpenAPI and verification

`forgegate export-openapi schemas/forgegate.openapi.v1.json` derives the
OpenAPI 3.1 document from the application without starting the server or
touching a database. Development verification compares it byte-for-byte with
the committed contract. Release smoke builds a wheel, installs it outside the
repository, exports OpenAPI again, compares the bytes, and confirms that an
external bind request fails.

Tests cover API/CLI candidate-create parity, exact replay and conflict,
structured validation/store/internal failures, correlation IDs, loopback
addresses, contract paths, and readback of a real durable evidence binding and
release attestation. These are local-host software results only; they do not
exercise AFE runtime code, MSP430 hardware, a network deployment, or remote CI.
