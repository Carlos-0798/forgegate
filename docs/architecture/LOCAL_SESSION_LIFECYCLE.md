# Local session lifecycle and abuse controls

## Scope

Phase 14 strengthens ForgeGate's Phase 13 authenticated loopback API without
changing its deployment class. All lifecycle, trust, and rate state remains in
one server process. The phase does not add TLS, proxy identity, remote serving,
durable sessions, or protection from a hostile process under the same OS
account.

## Session termination

```text
Bearer session
      |
      +--> DELETE /v1/auth/session
      |          -> remove exactly the caller's session
      |
      +--> operator DELETE /v1/auth/sessions/{session_id}
                 -> require every target project in caller scope
                 -> remove exactly the target session
```

Self-logout is available to both producer and operator roles. Targeted
revocation is operator-only. An unknown target and a target outside the
operator's project authority both return `API_SESSION_NOT_FOUND`; the response
does not reveal target identity, role, projects, or existence.

Termination removes the token digest and principal from memory before the
success response is returned. Later use of the raw token therefore fails, but
the action is not durable and no token is ever written to SQLite. Restart
already removes every session, so no migration or database schema change is
required.

## Trust-store reload

`forgegate serve` captures an absolute version of its `--trust-store` argument
at startup. `POST /v1/auth/trust-store/reload` rereads only that path; the HTTP
request contains no path or replacement document.

Reload authorization is deliberately global:

1. The caller must be an active operator under the current store.
2. Its session must cover every project in the current and replacement stores.
3. The same exact signing-identity document, operator role, and session project
   set must remain authorized by the replacement store.
4. The replacement document must pass the existing bounded strict-JSON loader
   before active authority changes.

A changed store clears every pending challenge because each challenge embeds
the old trust-store ID. Existing sessions are retained only when their exact
identity document, role, and project set remain authorized. A byte-identical
store produces a validated no-op. Reload failure leaves the old store,
challenges, and sessions unchanged.

This is local file reload, not managed online revocation. Trust distribution,
file ACLs, atomic replacement, rollback policy, and key custody remain operator
responsibilities.

## Fixed-window controls

The authenticator owns three process-global counters:

| Scope | Default events | Default window |
|---|---:|---:|
| Valid challenge request reaching the authenticator | 60 | 60 seconds |
| Valid session-exchange request reaching the authenticator | 60 | 60 seconds |
| Invalid or missing Bearer authentication | 120 | 60 seconds |

The counter set has three fixed keys and cannot grow with attacker-supplied
identity, token, IP, or header values. An exceeded window returns
`API_AUTH_RATE_LIMITED`, HTTP 429, and integer `Retry-After`. A valid current
session does not consume the invalid-Bearer counter.

The service does not trust forwarded-address headers and does not distinguish
local client processes. Pydantic rejects malformed authentication bodies before
the typed endpoint invokes its counter, so those validation failures are not
rate-limited by Phase 14. This control bounds selected authentication work; it
is not a general HTTP denial-of-service defense.

## Audit and evidence boundary

Logout, targeted revocation, trust reload, rate rejection, and unsuccessful
authentication do not modify release state and are not inserted into the
durable project/candidate audit ledger. The endpoint responses and tests prove
process behavior only. They are not a compliance log, trusted timestamp,
production observation, or physical evidence.
