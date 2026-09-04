# Local Dashboard acceptance matrix

## Status

This matrix defines the gate for the planned local Web Dashboard. Every item is
currently `NOT_IMPLEMENTED` unless it explicitly describes an existing CLI/API
prerequisite. Design completion is not UI verification.

## Phase 23 design gate

| ID | Requirement | Current status | Evidence |
|---|---|---|---|
| FGD-D01 | Dashboard is a same-origin local control plane over existing services | DESIGNED | `architecture/LOCAL_WEB_DASHBOARD.md` |
| FGD-D02 | Presentation cannot recalculate policy, lifecycle, or evidence levels | DESIGNED | UX and architecture documents |
| FGD-D03 | Browser receives neither private key nor raw API Bearer token | DESIGNED | Dashboard threat model |
| FGD-D04 | First implementation slice excludes upload, evaluation, plugin run, and trust administration | DESIGNED | Architecture scope |
| FGD-D05 | Evidence, hardware, accessibility, and production claims remain explicit | DESIGNED | UX requirements and threat model |

## Phase 24 automated acceptance

| ID | Test | Expected result |
|---|---|---|
| FGD-A01 | Production launch | Binds loopback only; `/app/` and `/healthz` become ready |
| FGD-A02 | Unsafe launch address | Wildcard and external addresses fail before serving |
| FGD-A03 | Packaged assets | Clean wheel contains and serves the exact hashed asset inventory |
| FGD-A04 | Runtime network inventory | No CDN, remote font, analytics, or other external request |
| FGD-A05 | Production headers | Restrictive CSP, frame denial, no-sniff, referrer, and no-store controls present |
| FGD-A06 | Foreign origin and invalid Host | Dashboard BFF request rejected |
| FGD-A07 | Missing/wrong CSRF | State-changing request rejected without durable event |
| FGD-A08 | Activation success | Signed one-time activation creates one bounded Dashboard session |
| FGD-A09 | Activation replay/expiry | Reuse and expired activation fail without session creation |
| FGD-A10 | Activation binding | Another browser context cannot claim the approved activation |
| FGD-A11 | Credential exposure scan | No private key, raw Bearer token, signature, or secret in DOM, URL, storage, console, or retained report |
| FGD-A12 | Session loss | 401/logout/revocation/restart clears protected state and returns to activation |
| FGD-A13 | Producer authority | Reads permitted; every Dashboard write rejected |
| FGD-A14 | Project scope | Unauthorized project is not listed and direct access fails |
| FGD-A15 | Project pagination | Stable bounded cursors neither omit nor duplicate rows |
| FGD-A16 | Candidate pagination/detail | Exact candidate, profile, revision, commit, track, and status rendered |
| FGD-A17 | Candidate reviewed creation | One explicit confirmation produces one durable candidate/audit event |
| FGD-A18 | Double click/retry | Exact replay returns the same document and does not duplicate audit history |
| FGD-A19 | Idempotency conflict | Changed request with reused key fails visibly and is not retried |
| FGD-A20 | Two-tab stale state | Stale revision produces conflict, reload, and mandatory re-review |
| FGD-A21 | Navigation safety | Refresh/back/forward never issues a mutation |
| FGD-A22 | Untrusted text | HTML/script/URL payloads render inert under the production CSP |
| FGD-A23 | Error semantics | 401/403/409/413/422/429/500 show distinct safe recovery and request ID |
| FGD-A24 | Evidence semantics | Request success, candidate state, decision, verification, hardware, and limitations remain separate |
| FGD-A25 | Bounded UI state | Maximum pages and repeated navigation do not create unbounded cache growth |
| FGD-A26 | API drift | Dashboard contract generation/check fails when committed OpenAPI changes unexpectedly |
| FGD-A27 | Existing product regression | `tools/verify.py` and `tools/release_smoke.py` remain PASS |

## Phase 24 real-browser and manual Windows acceptance

| ID | Scenario | Required observation |
|---|---|---|
| FGD-M01 | First launch | No blank/unfinished frame; loading and unauthenticated state are understandable |
| FGD-M02 | Complete keyboard path | Activate, select project, inspect candidates, create candidate, and inspect audit without a mouse |
| FGD-M03 | Focus behavior | Logical order, visible focus, modal containment, and focus return |
| FGD-M04 | Zoom | No clipped required action or unreachable limitation at 100/125/150/175/200% |
| FGD-M05 | Empty/loading/error/large states | Each state remains distinguishable and recoverable |
| FGD-M06 | Session expiry | User understands what expired, what was cleared, and how to reactivate |
| FGD-M07 | Conflict recovery | Two-tab stale write cannot overwrite; user can reload and review safely |
| FGD-M08 | Claim comprehension | Reviewer can distinguish request success, release decision, evidence level, and no-hardware status |
| FGD-M09 | Process lifecycle | Closing a tab does not falsely claim server shutdown; explicit shutdown is bounded |
| FGD-M10 | Portfolio capture | Screenshot contains only generic ForgeGate data and accurate evidence labels |

Edge and Chrome on the supported Windows host are required. High contrast,
screen reader, Remote Desktop, Firefox, macOS, and Linux are recorded separately
as PASS, FAIL, or NOT_RUN; they are never inferred from Chromium automation.

## Test layers

1. pure state/reducer tests for drafts, review invalidation, submissions,
   session loss, conflicts, and safe navigation;
2. presenter/component tests for action authority, semantic labels, errors,
   focus, and evidence boundaries;
3. BFF/application tests for activation, Host/Origin/CSRF, roles, scopes,
   idempotency, revisions, correlation, and cache headers;
4. real browser end-to-end tests against an installed wheel;
5. adversarial content, multi-tab, slow response, restart, and network-loss
   tests;
6. manual Windows visual, keyboard, zoom, comprehension, and screenshot review.

## Acceptance decision

The Dashboard may be called an implemented local Alpha surface only when every
applicable FGD-A item passes, every required FGD-M item has an expected-versus-
actual record, no critical/high security finding remains open, and the existing
ForgeGate quality/release gates still pass. Any unexecuted environment remains
`NOT_RUN`. UI acceptance never establishes hardware validation, evidence-producer
authenticity, trusted time, non-loopback safety, or production readiness.
