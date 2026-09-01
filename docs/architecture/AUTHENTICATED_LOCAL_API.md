# Authenticated local API

## Scope

Phase 13 adds caller authentication and project-scoped authorization to the
existing local REST transport. It reuses the Phase 12 Ed25519 signing identity
and external trust-store contracts; it does not introduce passwords, a user
database, remote identity federation, TLS termination, or non-loopback serving.

`forgegate serve` now requires `--trust-store`. Direct application construction
also requires an `ApiAuthenticator`; the contract-only construction path exists
solely to export deterministic OpenAPI and cannot serve authenticated requests.

## Challenge and session flow

```text
client identity + requested role/projects
                  |
                  v
POST /v1/auth/challenges
                  |
                  v
server nonce + instance/trust IDs + 60-second expiry
                  |
       Ed25519 signature by client
                  v
POST /v1/auth/sessions
                  |
                  v
opaque 32-byte Bearer token + short-lived in-memory principal
```

The challenge is canonical JSON under the domain separator
`ForgeGate API session challenge v1`. It binds the server instance, trust-store
ID, identity ID, requested role, exact canonical project set, unpredictable
nonce, and server-issued time window. Challenges are single-use, including
after a failed signature attempt.

The default session lifetime is 15 minutes and may be configured from 60 to
3,600 seconds. Tokens contain 32 random bytes encoded as unpadded base64url.
ForgeGate retains only their SHA-256 digests in memory, compares the digest in
constant time, and loses every challenge and session on process restart. Both
pending challenges and active sessions are capped at 1,000 by default.

`identity sign-api-challenge` signs a bounded strict-JSON challenge file with
an existing unencrypted PKCS8 Ed25519 key. The private key is never sent to or
retained by the API server.

## Authorization

Every protected request must present `Authorization: Bearer <token>`. Health,
OpenAPI, and the two session-establishment routes remain public on loopback.

| Role | Authorized operations |
|---|---|
| `producer` | Read project profiles and project candidates for its exact session project set |
| `operator` | The same reads, all current project/candidate writes, and project-scoped audit queries |

There is no wildcard project authority. A requested session project must be in
the active trust record, and every later route rechecks the exact project. The
project-list route filters to authorized registered projects. Audit queries now
require an explicit `project_id`; cross-project audit enumeration is not
available through the REST surface.

## Audit actor semantics

Each successful authenticated API write passes a
`forgegate.audit-actor.v1` document into the same SQLite transaction as its
existing state-change audit event. The actor records public identity ID and
display name, role, session ID, trust-store ID, and server authentication time.
The event content identity includes this actor, so actor substitution changes
the event ID. Exact idempotent replay still creates no second event and cannot
replace the actor attached to the original durable write.

Legacy and CLI-origin events retain `actor = null`; migration never fabricates
an identity. Bearer tokens and private keys are never written to audit events or
SQLite. Event time remains the operation's existing caller-supplied domain time,
while `authenticated_at` is the server time at session creation. Neither is a
trusted timestamp.

## Residual boundary

The service remains bound to loopback and rejects non-loopback HTTP `Host`
values. Bearer traffic is not protected by TLS, so the design does not defend
against a privileged local packet observer, hostile process under the same
account, debugger, memory reader, or compromised host. There is no logout,
per-session revocation, durable session store, distributed deployment,
rate-based throttling, reverse-proxy trust, online trust-store reload, or
administrator-resistant audit protection.

The trust store is a startup snapshot and its custody/distribution remain
external. This phase is sufficient for authenticated local integration testing,
not for LAN, shared-host, internet, production, AFE runtime, or MSP430 access.
