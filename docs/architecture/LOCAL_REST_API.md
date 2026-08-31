# Local REST API

## Purpose and scope

Phase 5 exposes a small HTTP transport over ForgeGate's existing candidate
domain and SQLite store. It is intended for local tool integration while the
product remains under development. The server is unauthenticated and is
therefore deliberately restricted to the local loopback interface.

The v1 baseline includes:

- `GET /healthz`;
- `POST /v1/candidates`;
- `POST /v1/candidates/{candidate_id}/transitions`;
- `POST /v1/candidates/{candidate_id}/evidence`;
- `POST /v1/candidates/{candidate_id}/evaluate`;
- `POST /v1/candidates/{candidate_id}/attestation`;
- `GET /v1/candidates/{candidate_id}`;
- `GET /v1/candidates/{candidate_id}/history`;
- `GET /v1/candidates/{candidate_id}/evidence`;
- `GET /v1/candidates/{candidate_id}/attestation`.

Candidate creation, advancement, evidence binding, and evaluation require
`Idempotency-Key` and use the same durable idempotency records as the CLI/store.
Advancement and evaluation also require `expected_revision`. Attestation
creation is deterministic against an immutable terminal candidate and replays
the stored document exactly.

No API command accepts an artifact input path or attestation output directory.
Collection and filesystem publication remain explicit CLI operations.

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

The shared service now owns create, advance, bind, evaluate, attest, and read
commands. Evaluation loads the persisted binding, passes its nested evidence
bundle to the policy engine, derives the terminal state from the decision, and
uses one repository transaction for the evaluation plus terminal transition.

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
a declared `Content-Length` above 4 MiB reject before model validation.

These are safety guards, not authentication: any process or user able to
connect to the loopback port has the API's current local permissions. The body
limit does not yet enforce an exact streaming ceiling for unknown-length or
chunked requests.

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

Tests cover API/CLI parity, exact replay/conflict, expected-revision races,
invalid states, release-track policy mismatch, structured failures,
correlation IDs, loopback bind/Host handling, declared body size, contract
paths, and a complete durable candidate workflow. These are local-host
software results only; they do not exercise AFE runtime code, MSP430 hardware,
a network deployment, or remote CI.
