# Phase 24 manual interaction acceptance — 2026-09-04

- Product: ForgeGate Windows Local Alpha
- Surface: authenticated loopback Web Dashboard
- Browsers: Microsoft Edge and Codex in-app browser on Windows
- Fixture: generic `sample-api` project and local ephemeral acceptance identity
- Hardware access: **NOT_PERFORMED**
- Remote/GitHub action: **NOT_PERFORMED**
- Decision: **EXECUTED LOCAL FLOWS PASS / FULL CROSS-BROWSER EXIT GATE PARTIAL**

## Acceptance outcome

The executed operator and producer workflows pass after correcting one
session-expiry rendering defect discovered by this run. The browser accepted a
valid candidate sample exactly once, rejected invalid samples without an
unexpected durable write, preserved the distinction between candidate state,
engineering decision, project profile, and hardware evidence, and cleared
protected state after logout, expiry, and service restart.

This is local software acceptance evidence. It is not physical-hardware,
production, public-release, evidence-authenticity, or remote-deployment proof.

## Input/output record

| Case | Input or action | Expected output | Actual output | Result |
|---|---|---|---|---|
| Initial state | Open `/app/` without a session | Clear activation boundary | Loopback, CLI-held key, hardware not accessed, Windows Local Alpha, and non-proof statement visible | PASS |
| Operator activation | One-time code + local Ed25519 identity; role `operator`; project `sample-api` | Bounded authenticated session | Overview showed role, project scope, version `0.1.0a1`, API `v1`, DB schema `v8`, and `Hardware NOT_PERFORMED` | PASS |
| Required inputs | Blank Version and Commit SHA | No request and focus first invalid field | Dialog remained open, Version retained focus, and the server received no create request | PASS |
| Commit format | Version `1.0.3`; uppercase 40-character hexadecimal SHA | Client rejection | Dialog remained open, Commit SHA received focus, and no create request was sent | PASS |
| Corrected commit | SHA `1111111111111111111111111111111111111111` | Stale validation clears and review opens | Review page opened with exact project, version, commit, branch, track, and timestamp | PASS |
| Unknown track | Track `not-configured` | Authoritative rejection and no durable candidate | `STORE_RELEASE_TRACK_NOT_FOUND`, safe recovery, and a request ID rendered; CLI list remained at 3 candidates | PASS |
| Valid create | Version `1.0.3`; SHA above; branch `manual-acceptance`; track `pull-request` | One DRAFT and one audit event | Created `cand-cdf03998b941c444d86944a8`; one `candidate.created` event at sequence 5 | PASS |
| Candidate semantics | Inspect the created candidate | Exact authoritative fields and evidence boundary | `DRAFT`; candidate revision `0`; `NOT_EVALUATED`; profile version `1`; hardware `NOT_PERFORMED` | PASS |
| Reload | Reload `#/candidates` after success | No duplicate write | Exactly 4 candidates remained; no second `1.0.3` candidate or audit event appeared | PASS |
| Explicit cancel | Open draft dialog, then Cancel | Dialog closes and focus returns | Dialog removed and Create candidate regained focus | PASS |
| Producer activation | Role `producer`; project `sample-api` | Read-only candidate access | Create action absent; explicit read-only message shown; candidate detail remained readable | PASS |
| Producer audit boundary | Inspect `1.0.3` as producer | No operator audit request | Detail showed that audit history requires an operator session | PASS |
| Logout | Select End session | Protected state clears | Activation page returned with session-ended guidance | PASS |
| Natural expiry | 60-second session | Automatic clear and comprehensible recovery | At expiry, identity/project/candidate state disappeared and the activation page announced expiry | PASS |
| Service restart | Restart server while browser session remains | Next protected request returns to activation | A 401 cleared stale protected state and rendered the activation page without being overwritten | PASS |
| Role guidance | Start activation | Example must not imply operator-only use | Command uses `--role ROLE`; supporting copy says producer or operator | PASS |
| Modal containment | Shift+Tab from first field; Tab from last action | Focus remains inside the modal | Edge moved Version → Review request → Version without escaping after the correction | PASS |
| Escape and return | Press Escape from the first field | Dialog closes and visible focus returns to its opener | Dialog count became zero; Create candidate regained focus with a solid focus outline | PASS |
| Large candidate set | Traverse all pages for 129 candidates | Every row reachable once; controls terminate safely | Six pages contained 25/25/25/25/25/4 rows, 129 unique versions, zero cross-page duplicates, and disabled Next on the last page | PASS |
| Server validation | Track `INVALID!` with otherwise valid fields | 422 is distinct, actionable, and non-mutating | `API_REQUEST_VALIDATION_FAILED`, safe next step, and request ID rendered; total remained unchanged | PASS |
| Follow-up valid create | Version `ui-acceptance-20260904`; SHA `3333333333333333333333333333333333333333`; branch `acceptance/browser-chain`; track `pull-request` | One exact DRAFT and audit event | Created `cand-9c77d4d795e4d4ec5f12c004`; revision `0`, `NOT_EVALUATED`, profile `1`, hardware `NOT_PERFORMED`, one `candidate.created` | PASS |
| Narrow large-data view | 390 × 844 viewport with 25-row page | No page-level horizontal overflow; paging remains reachable | Document scroll width 375 px at 390 px viewport; both paging controls remained visible | PASS |
| Browser console | Complete follow-up workflows | No application warning/error | Edge and in-app browser warning/error logs were empty | PASS |

## Persisted-output cross-check

The CLI independently read the browser-created record from the copied test
database and returned:

- schema `forgegate.release-candidate.v2`;
- version `1.0.3` and the exact 40-character commit SHA;
- branch `manual-acceptance` and track `pull-request`;
- state `DRAFT`, candidate revision `0`, and `evaluation_id: null`;
- frozen project profile version `1`; and
- exactly one matching `candidate.created` audit event.

The rejected unknown-track request produced no fourth row. The later valid
request produced the only fourth row. The original fixture database was not
modified; the run used a copied ignored work database.

The separate large-data fixture began with 128 candidates. The rejected 422
sample did not change that count. The follow-up valid sample produced the sole
129th candidate and exactly one matching audit event.

## Defect discovered and corrected

The first natural-expiry run exposed two linked frontend faults:

1. cached Projects content could remain visible until a network-backed route
   was requested; and
2. a Candidates 401 invoked the activation renderer, but the outer route then
   overwrote it with a partial stale page.

The correction adds a timer derived from the server-issued expiry timestamp,
centralizes protected-state clearing, preserves the activation page after a
handled 401, and provides distinct expired/session-ended guidance. A repeated
60-second expiry and a separate service-restart/401 run both passed.

The run also replaced the activation example's hard-coded `operator` role with
an explicit `ROLE` placeholder so the producer path is not misleading.

The remaining acceptance run found two additional frontend defects. The
candidate page discarded the service cursor after its first 100 rows, so later
records were unreachable. It now exposes bounded 25-row Previous/Next pages,
resets cursor history at session/project boundaries, and announces the page.
Edge also showed that reverse Tab could escape from the first modal field to
the page body. An explicit two-direction focus trap, accessible dialog name,
Escape handler, and opener-focus restoration now pass the repeated keyboard
run.

## Remaining manual boundary

The following items remain `NOT_RUN` or partial and are not inferred from this
run:

- Chrome core flow and the Edge/Chrome 100–200% exact zoom matrix;
- browser-driven 409, 413, 429, and 500 rendering (401, 404, and 422 now have
  browser records; producer authority prevents the normal UI from issuing a
  forbidden write);
- high contrast, screen reader, and Remote Desktop.

A generic-data Windows local-browser capture is now retained at
`docs/assets/forgegate-dashboard-alpha.png`. Its README caption limits the
claim to the implemented Alpha interaction surface and explicitly excludes
hardware, production, and release-approval evidence. The source-distribution
smoke test explicitly requires the PNG so packaged README rendering cannot
silently lose the capture.

Two-tab stale-revision recovery remains not applicable until the Dashboard
exposes a revision-mutating transition, binding, or evaluation command.
