# Phase 24 authenticated local Dashboard acceptance report

- Date: 2026-09-04
- Version: 0.1.0a1
- Platform: Windows 11, Python 3.12.10
- Decision: **IMPLEMENTATION PASS / FULL MANUAL EXIT GATE PARTIAL**
- Hardware evidence: **NOT_PERFORMED**
- Remote/publication action: **NOT_PERFORMED**

## Outcome

ForgeGate now has an operational local Web Dashboard rather than a design-only
placeholder. The narrow slice provides one-time CLI-approved browser
authentication, Overview, authorized Projects, and project-scoped Candidates
with reviewed creation, detail, and append-only audit inspection.

The implementation, security boundary, focused automation, full repository
quality gate, packaging smoke, one real Microsoft Edge keyboard path, an
installed-wheel Edge read path, and the follow-up in-app-browser manual
interaction run pass.
The follow-up run also passed complete Edge modal focus behavior, a six-page
large-data traversal, browser-rendered 422 recovery, and another authoritative
candidate write/readback. This report does not mark Phase 24 fully accepted
because Chrome, the exact zoom matrix, assistive-technology checks, and every
browser error state were not executed.

The detailed input/output record is in
`reports/PHASE_24_MANUAL_INTERACTION_ACCEPTANCE_2026-09-04.md`.

## Implemented boundary

- `forgegate dashboard` validates a loopback host, initializes the existing
  application/store, serves `/app/`, and leaves service shutdown explicit.
- `forgegate dashboard-activate` loads an owner-selected identity/private key
  locally, signs the existing challenge, and sends only the signed activation
  over loopback.
- Browser JavaScript receives neither the private key nor the direct API Bearer
  token. It receives an opaque host-only, HttpOnly, SameSite=Strict cookie.
- `/app/api/` enforces the authenticated principal, exact project scope,
  operator/producer role boundary, exact same-origin checks, and per-session
  anti-CSRF values for mutations.
- The direct `/v1/` API remains Bearer-authenticated and the Dashboard BFF is
  excluded from its committed public OpenAPI document. A separate non-served
  Dashboard BFF OpenAPI contract is generated, committed, and drift-checked.
- The frontend uses strict TypeScript, semantic DOM construction, no raw HTML,
  no persistent browser storage, no service worker, no runtime CDN/font/
  analytics dependency, and restrictive response headers.
- Evidence upload, policy execution, assurance export, plugin execution,
  session administration, trust-store reload, remote deployment, and hardware
  access are unavailable and labeled as planned.

## Automated evidence

| Check | Actual result | Boundary |
|---|---|---|
| Dashboard focus | 39 passed | BFF, activation/session, cursor pagination, assets, roles/scopes, client, CLI, and BFF contract |
| Dashboard package coverage | 98.49% | 557 statements, 106 branches |
| Full repository suite | 819 passed, 3 skipped | Existing Windows symlink creation remains unavailable |
| Full branch-aware coverage | 95.20% | 9,565 statements, 2,634 branches |
| Static quality | PASS | Ruff, formatting, strict mypy across 84 source/tool files |
| Frontend static check | PASS | TypeScript strict mode |
| Frontend production build | PASS | Vite content-hashed production output |
| Repeated frontend build | PASS | Byte-identical output and canonical asset inventory |
| Frontend dependency advisory check | PASS | No known advisory at `moderate` threshold in the locked graph |
| Interaction smoke | 33/33 PASS | Existing CLI/authenticated REST behavior retained |
| Clean release smoke | PASS | sdist/wheel build, README screenshot inclusion, clean install, inventory validation, core chain, uninstall |

The installed-wheel browser check additionally proved that the packaged static
inventory could serve and authenticate Overview, Projects, and Candidates in
Edge. It did not repeat the complete mutation/keyboard matrix.

## Real browser record

The test used generic local fixture data and an ephemeral test identity. No
personal email, key, token, absolute path, AFE/MSP430 data, or hardware result
was retained.

| Scenario | Expected | Actual | Result |
|---|---|---|---|
| Initial page | Clear unauthenticated state | Activation explanation and action rendered | PASS |
| CLI companion approval | Browser-bound authenticated session | One-time code approved; Overview loaded | PASS |
| Keyboard navigation | Core path without a mouse | Microsoft Edge completed activation, Projects, Candidates, create/review/confirm/detail/audit | PASS |
| Focus entry/containment/return | Logical focus, modal containment, Escape close, and opener return | Edge cycled first-to-last and last-to-first with Shift+Tab/Tab; Escape removed the dialog and returned visible focus to Create candidate | PASS |
| Candidate creation | One DRAFT plus one audit event | DRAFT, candidate revision 0, profile version 1, `NOT_EVALUATED`, hardware `NOT_PERFORMED`, and `candidate.created` shown | PASS |
| Refresh/back/forward | No duplicate mutation | Prior run retained three rows; the follow-up valid sample retained exactly four rows after reload with one matching audit event | PASS |
| Invalid samples | Clear client/server rejection and no unexpected write | Blank required fields and uppercase SHA stayed client-side; unknown track rendered `STORE_RELEASE_TRACK_NOT_FOUND` and left the list at three | PASS |
| Producer boundary | Read-only candidate access | Create action absent; candidate fields visible; operator-only audit limitation explicit | PASS |
| Logout/expiry/restart | Clear protected state and actionable recovery | Explicit logout, natural 60-second expiry, and service-restart 401 all returned to activation with distinct guidance | PASS |
| Responsive narrow view | No page-level horizontal overflow | 390 × 844 viewport had 375 px body/document scroll width; table/nav used intentional inner scrolling | PASS |
| Large candidate set | Every bounded page remains reachable without omission or duplication | 129 records occupied six pages: five 25-row pages and a four-row final page; the traversal found 129 unique versions and zero cross-page duplicates | PASS |
| Browser 422 recovery | Invalid server-bound input remains safe and actionable | Track `INVALID!` rendered `API_REQUEST_VALIDATION_FAILED`, a safe next step, and a request ID; no candidate was created | PASS |
| Follow-up valid sample | One write and exact readback | `ui-acceptance-20260904` created `cand-9c77d4d795e4d4ec5f12c004` as DRAFT revision 0 with one audit event, `NOT_EVALUATED`, and hardware `NOT_PERFORMED` | PASS |
| Browser console | No application warning/error | No warning or error recorded | PASS |
| Installed-wheel browser | Packaged assets and BFF load | Edge authenticated and read Overview, Projects, and Candidates from a dedicated wheel-only environment | PASS |
| Chrome | Same core flow | Chrome and its enabled integration are installed, but Chrome was not running and no launch was authorized during this run | NOT_RUN |
| Exact zoom matrix | Reachable actions/limitations at 100–200% | Browser zoom could not be set reliably by the available controller | NOT_RUN |
| Screen reader/high contrast/Remote Desktop | Explicit manual evidence | Not executed | NOT_RUN |
| Portfolio screenshot | Generic and claim-accurate retained capture | Retained `docs/assets/forgegate-dashboard-alpha.png` after visible-claim review; README explicitly limits the image to the local Alpha interaction surface | PASS |

## Defects found and corrected during acceptance

1. Commit-SHA custom validity remained latched after a corrected input. The
   input event now clears the stale custom validity before revalidation.
2. A missing hashed asset incorrectly inherited immutable caching. Immutable
   caching now applies only to a successful validated asset response, with a
   regression test.
3. Candidate creation left a stale empty-state panel before detail inspection.
   The post-create flow now awaits list refresh before adding the detail view.
4. Producer detail attempted an operator-only audit request. Producer sessions
   now render an explicit audit-permission boundary while preserving read-only
   candidate detail.
5. Natural expiry left cached project data visible, and the following 401
   activation render could be overwritten by the route's stale partial page.
   A server-expiry timer now clears protected state proactively, and handled
   401 paths return before any outer render.
6. The activation command example hard-coded `operator`, which was misleading
   for producer sessions. It now uses a documented `ROLE` placeholder.
7. The candidate view requested 100 rows but ignored the service cursor, making
   later records unreachable. It now renders bounded 25-row Previous/Next
   pages, resets cursors on project/session changes, and announces each page.
8. Reverse Tab from the first dialog field could escape to the page body under
   Edge automation. The dialog now explicitly traps both Tab directions,
   retains an accessible name, handles Escape, and restores opener focus.
9. The first screenshot packaging run exposed that `MANIFEST.in` included SVG
   but not PNG documentation assets. PNG inclusion and an explicit release
   smoke requirement now prevent a packaged README with a broken image.

## Remaining acceptance work

The complete Phase 24 exit gate requires:

1. Chrome core-flow execution on the supported Windows host;
2. Edge and Chrome checks at 100%, 125%, 150%, 175%, and 200% zoom;
3. browser-driven 409/413/429/500 recovery (401, 404, 422, logout, natural
   expiry, restart, and producer authority paths now pass);
4. high-contrast, screen-reader, and Remote Desktop checks.

Two-tab stale-revision recovery is not applicable to this slice because it has
no revision-mutating command. It becomes mandatory when transition, binding,
evaluation, or other revision writes enter the Dashboard.

## Claim boundary

This checkpoint establishes a local Alpha interaction surface. It does not
establish production readiness, remote/LAN safety, hostile-local-user defense,
evidence-producer authenticity, trusted time, hardware validation, public
release, or GitHub/LinkedIn publication approval.
