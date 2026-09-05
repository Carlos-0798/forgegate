# Local Dashboard threat model

## Status and scope

This threat model governs the implemented Phase 24 local Dashboard slice.
Origin/Host/CSRF, browser-bound activation, session, role/scope, header, static-
asset, and safe-rendering controls have local automated evidence. The generated
BFF-contract drift gate and portions of the manual browser exit gate remain
incomplete, so this is not a production security approval.

## Assets

- owner-managed Ed25519 private keys and signatures;
- short-lived API and Dashboard sessions;
- project scopes, candidate records, evidence, policy material, attestations,
  plugin receipts, audit history, and security events;
- local paths, user identity, repository metadata, and request diagnostics;
- integrity of the presented decision, limitations, and evidence level.

## Trust boundaries

```text
Internet page / browser extension / other local process
                         |
                  browser origin boundary
                         |
              /app static UI and /app/api BFF
                         |
          authenticator and application/domain services
                         |
            SQLite, artifacts, and plugin-run store
```

The browser, every displayed artifact field, all stored project/evidence text,
and every future upload are untrusted. Loopback reduces network exposure but
does not make the browser, extensions, another local process, or the current OS
user trustworthy.

## Threats and required controls

| Threat | Required control | Phase 24 acceptance evidence |
|---|---|---|
| DNS rebinding or hostile website reaches localhost | Loopback bind, exact Host and Origin allowlist, same-origin BFF, no permissive CORS | Cross-origin and invalid-Host requests rejected |
| Cross-site request forgery | Host-only SameSite=Strict cookie, exact Origin, per-session anti-CSRF value on mutations | Missing/wrong token and foreign Origin rejected |
| Bearer token theft from JavaScript | Raw API token never enters Dashboard JavaScript, URL, Web Storage, IndexedDB, console, or error state | Browser-storage and trace scan |
| Private key disclosure | Signing occurs only in the separate CLI activation helper; server/UI never accept key bytes or a key-path form field | Contract test plus process/log inspection |
| Stored/reflected/DOM XSS from evidence | Context-safe text rendering, no raw HTML, restricted URL schemes, no inline/eval, strict CSP | Malicious project/SARIF/Markdown fixtures remain inert |
| Clickjacking or opener abuse | Deny framing, safe external-link rel attributes, no untrusted popup messaging | Header and browser tests |
| Frontend dependency compromise | Locked build dependencies, license/advisory review, deterministic asset inventory, no CDN/runtime download | Clean reproducible build and inventory check |
| Cached protected data after logout | `Cache-Control: no-store`, bounded in-memory cache, clear on 401/logout/revocation/restart, no service worker | Refresh/back/offline tests expose no protected view |
| Role or project-scope confusion | Server authorization on every query/write; UI derives labels from authenticated principal | Producer write and cross-project read rejected |
| Double submit or network replay | One command-owned idempotency key, submit lock, exact replay rendering | Double click produces one durable event |
| Stale browser overwrites newer state | Exact `expected_revision`, visible 409 recovery, mandatory reload and re-review | Two-tab conflict test |
| Browser back/refresh repeats mutation | No mutation on route load; submitted state uses server response and safe navigation | Back/forward/refresh test |
| API/frontend contract drift | Committed OpenAPI remains authoritative; generated client/types checked in build and CI | Deliberate drift fails the gate |
| Misleading progress or completion | No fabricated progress; final state only after authoritative response/cleanup | Slow/error response tests |
| UI promotes evidence assurance | Render exact retained trust/verification/decision fields and limitations; no client recomputation | Snapshot/semantic assertions for synthetic and unsigned fixtures |
| Sensitive diagnostics leak | Stable code/request ID only; redact token, signature, key, absolute path, header, body, and traceback | Log/DOM/error-fixture scan |
| Unsafe file import | No upload in first slice; later bounded staging contract, strict parsing, create-new publication, cleanup, and no server path input | Route absence plus future separate gate |
| Unbounded list or response exhausts UI | Existing cursor/limit contracts, bounded caches, table virtualization only when required | Maximum page and pagination tests |
| Authentication activation is hijacked | One-time short expiry, browser binding, exact requested principal/scope review, non-secret display code with rate limits | replay, wrong-browser, expiry, and scope-mismatch tests |
| Local server launched on unsafe address | Fixed loopback validation; wildcard/external addresses rejected | launch tests for IPv4/IPv6/wildcard cases |

## Security response headers

The packaged policy enforces a restrictive same-origin Content Security Policy,
no framing, no MIME sniffing, no referrer leakage, and no storage of protected
responses. It must not be weakened to support a development tool in the
packaged product.

## Authentication failure semantics

- `401` clears the Dashboard session and protected state, then offers a new
  activation.
- `403` preserves the session but explains that the identity, role, or project
  scope lacks authority.
- `409` preserves the response and requires reload/re-review; no automatic
  mutation retry occurs.
- `413` states the accepted byte limit before any future file retry.
- `422` maps structured field issues without displaying raw internal objects.
- `429` respects `Retry-After`, disables the affected action for that duration,
  and does not spam retries.
- unexpected failures show one request ID and safe recovery guidance.

## Deferred risks

- hostile administrator, browser extension, or malware under the same OS user;
- TLS, reverse proxy, remote browser, LAN, internet, SaaS, or multi-user use;
- durable/distributed Dashboard sessions and rate state;
- managed key custody, TPM/HSM integration, trusted timestamps, and online
  revocation;
- artifact upload/download publication, remote acquisition, and browser-native
  filesystem integration;
- generalized third-party plugin publisher trust and native plugin execution;
- formal penetration testing, WCAG certification, and production support.

These risks remain explicit limitations. A local Dashboard pass must not remove
them from the repository status, README, screenshots, or portfolio claims.

## Security exit gate

The current candidate-creation write passes the automated controls below, but
the complete Dashboard exit gate remains partial until every applicable item is
recorded in the acceptance matrix:

1. private keys and raw Bearer tokens do not cross into browser JavaScript;
2. foreign Origin, invalid Host, missing CSRF, role, scope, replay, and stale
   revision cases fail closed;
3. untrusted evidence text is inert under the production CSP;
4. protected responses are not persistently cached;
5. clean-wheel startup uses the same headers/assets/contracts as the tested
   build; and
6. security evidence contains no credential, private email, absolute user path,
   or fabricated product/hardware assurance.
