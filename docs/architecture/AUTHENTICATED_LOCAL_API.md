# Authenticated local API

## Scope

Phase 13 adds caller authentication and project-scoped authorization to the
existing local REST transport. Phase 14 adds explicit local session lifecycle,
fixed-path trust reload, and bounded authentication request controls. Both
reuse the Phase 12 Ed25519 identity and external trust-store contracts; neither
introduces passwords, a user database, remote identity federation, TLS
termination, or non-loopback serving.

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

## Session lifecycle

`DELETE /v1/auth/session` removes the caller's current session. An operator may
also call `DELETE /v1/auth/sessions/{session_id}` for a target whose complete
project set is covered by the operator session. Producer sessions cannot revoke
other sessions. An absent or out-of-scope target returns the same not-found
error so the endpoint does not disclose whether that session exists.

Revocation is immediate for later requests in the current process, but it is
not persisted and is unnecessary after restart because every session already
disappears. Logout and revocation responses are not inserted into the durable
candidate/project audit ledger; that ledger remains limited to successful
product state changes.

## Fixed-path trust-store reload

`POST /v1/auth/trust-store/reload` rereads only the trust-store path supplied to
`forgegate serve`; the HTTP caller cannot choose a filesystem path. The caller
must be an operator that remains exactly trusted by the new document, and its
session project set must cover every project mentioned by either the current or
replacement store. This prevents a project-scoped operator from changing trust
for unrelated projects or granting itself a new project during reload.

A changed store invalidates every pending challenge and immediately removes
each session whose exact identity document, role, or project set is no longer
authorized. Compatible sessions remain valid and retain the trust-store ID that
authenticated them for later actor attribution. A byte-identical reload is a
validated no-op. Invalid or unreadable replacement content fails closed without
changing the active store.

## Authentication request controls

The authenticator keeps three fixed-window counters: challenge requests,
session exchanges, and invalid Bearer authentications. Defaults are 60, 60, and
120 events per 60 seconds. State is bounded to those three process-local
counters, and a rejected request receives `429 API_AUTH_RATE_LIMITED` plus an
integer `Retry-After` value. A valid existing Bearer session is not blocked by
the invalid-authentication counter.

These limits do not trust `X-Forwarded-For` or claim per-user/per-process
attribution; all local callers share the same service counters. Strict request
models reject malformed challenge/session bodies before these endpoint-level
counters run, so this is not a complete HTTP denial-of-service control.

## Residual boundary

The service remains bound to loopback and rejects non-loopback HTTP `Host`
values. Bearer traffic is not protected by TLS, so the design does not defend
against a privileged local packet observer, hostile process under the same
account, debugger, memory reader, or compromised host. There is no durable
session or revocation store, distributed deployment, per-client network rate
limiting, reverse-proxy trust, managed online trust distribution, durable
authentication-control audit, or administrator-resistant protection.

Trust-store custody/distribution remain external. Phase 14 is sufficient for
better controlled local integration testing, not for LAN, shared-host,
internet, production, AFE runtime, or MSP430 access.
