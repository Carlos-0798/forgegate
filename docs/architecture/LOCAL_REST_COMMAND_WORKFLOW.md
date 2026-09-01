# Local REST command workflow

## Command boundary

Phase 6 completes the local candidate workflow over HTTP without turning the
service into a remote or multi-user system. Phase 13 supersedes the original
transport-only authority model: protected routes now require a short-lived
Ed25519-authenticated session, exact project scope, and an appropriate producer
or operator role. The CLI remains authorized by the local OS account.

The command routes are:

| Route | Durable effect | Concurrency/replay control |
|---|---|---|
| `GET /v1/projects` | None; bounded discovery | Exclusive project cursor |
| `GET /v1/projects/{id}/candidates` | None; bounded project-scoped discovery | Exclusive candidate cursor |
| `POST /v1/candidates` | Create authorized deterministic DRAFT | `Idempotency-Key` + registered project/track |
| `POST /v1/candidates/{id}/transitions` | Append one legal state event | `Idempotency-Key` + `expected_revision` |
| `POST /v1/candidates/{id}/evidence` | Bind one immutable audited assembly | `Idempotency-Key` + state gate |
| `POST /v1/candidates/{id}/evaluate` | Evaluate binding and append terminal event | `Idempotency-Key` + `expected_revision` |
| `GET /v1/candidates/{id}/policy` | Read retained exact policy material | Immutable terminal association |
| `POST /v1/candidates/{id}/attestation` | Persist deterministic attestation | Terminal immutability + exact replay |

All routes retain the existing structured error and request-correlation
contract. Stable store conflicts map to HTTP 409; lifecycle and strict request
failures map to 422 or the existing fail-closed store status.

New product-surface creation requires an immutable registered project and
exactly one project configuration key that normalizes to the requested
canonical hyphen release track. Existing underscore keys remain compatible;
ambiguous underscore/hyphen duplicates reject. This project configuration
check does not authenticate the HTTP caller.

## State and evidence flow

The intended sequence is:

```text
create DRAFT
  -> transition COLLECTING
  -> bind forgegate.evidence-bundle-assembly.v1
  -> transition READY
  -> transition EVALUATING
  -> evaluate persisted binding -> PASS / FAIL / REVIEW / ERROR
  -> persist forgegate.release-attestation.v1
```

The evaluate request supplies a strict `forgegate.policy-material.v1`,
timestamp, expected revision, and idempotency key. It does not supply an
evidence bundle. The application loads the candidate's immutable binding and
evaluates its nested bundle. The repository verifies the material against the
candidate's frozen profile/track/path, verifies the evidence fingerprint, and
commits the material, v2 evaluation, and terminal transition atomically.

A generic transition request may record an explicit fail-closed `ERROR` without
a policy result, matching the existing domain contract. PASS, FAIL, and REVIEW
cannot be manufactured through that route because the lifecycle requires a
matching evaluation document.

## Filesystem and upstream isolation

The bind route accepts the complete strict assembly document, not a path. The
evaluate route likewise accepts the complete self-validating policy-material
document. The API never reopens either document's artifact paths; those bytes
were validated during separate local CLI assembly/materialization operations.

Attestation creation persists the self-validating JSON document in SQLite but
does not accept an output directory or publish JSON/Markdown files. Explicit
filesystem publication remains CLI-only so an HTTP caller cannot choose a
local write target.

Nothing in this workflow imports Analog Validation Studio, opens an MSP430
serial port, or assigns ForgeGate ownership to upstream evidence. Both peers
can later supply versioned artifacts through optional collectors and the same
generic assembly boundary.

## Local transport controls and residual risk

Both the socket bind value and each HTTP Host must identify localhost or a
loopback IP. Non-loopback and wildcard values fail closed. Phase 15 rejects
actual request bodies above 4 MiB, including unknown-length/chunked input,
before model validation. CORS is not enabled.

These controls reduce accidental exposure and ordinary browser-origin access.
Phase 13 authenticates a local key holder and authorizes exact projects, but it
does not defend against a hostile local account, privileged packet observer, or
memory reader. Phase 14 adds memory-only logout, scoped revocation, fixed-path
trust reload, and global authentication request counters. Phase 15 adds the
actual-byte body gate, pre-validation authentication counters, and a bounded
separate security-event journal. Any non-loopback, proxied, tunneled, shared,
or production deployment remains prohibited until TLS/proxy trust,
hostile-local-user defense, durable/distributed session state, security-event
retention/export, per-client rate policy, and transport-layer
designs exist.
