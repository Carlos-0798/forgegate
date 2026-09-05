# Phase 24 manual interaction acceptance — 2026-09-04

- Product: ForgeGate Windows Local Alpha
- Surface: authenticated loopback Web Dashboard
- Browsers: Microsoft Edge, Google Chrome, and Codex in-app browser on Windows
- Fixture: generic `sample-api` project and local ephemeral acceptance identity
- ForgeGate hardware access/integration: **NOT_PERFORMED**
- External board connectivity observation: **PASS — connection only; no serial read/write, firmware action, protocol validation, or measurement**
- Remote/GitHub action: **NOT_PERFORMED**
- Decision: **EXECUTED LOCAL FLOWS PASS / FULL CROSS-BROWSER EXIT GATE PARTIAL**

## Acceptance outcome

The executed operator and producer workflows pass after correcting the
interaction defects discovered by these runs. The browsers accepted a
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
| Browser console | Complete follow-up workflows | No application warning/error | Edge, Chrome, and in-app browser warning/error logs were empty | PASS |
| Chrome core flow | Activate, inspect Overview/Projects/Candidates, create, and inspect | Same authoritative state and boundaries as Edge | Chrome completed the flow with generic local data and no console warning/error | PASS |
| Chrome pagination | Traverse the 129-record fixture | Six bounded pages, no omission or duplication | 25/25/25/25/25/4 rows, 129 unique versions, zero duplicates; Previous and reload returned to expected pages | PASS |
| Chrome focus | Initial focus, bidirectional Tab trap, Escape and result transition | Focus never escapes the active modal | Entry focused Version; Shift+Tab/Tab wrapped; Escape returned to Create candidate; successful creation renamed the dialog and focused Inspect candidate | PASS |
| Chrome 422 | Track `INVALID!` | Actionable rejection without write | `API_REQUEST_VALIDATION_FAILED` with safe next step and request ID; no invalid candidate row | PASS |
| Chrome final create | Version `chrome-a11y-20260904`; SHA `6666666666666666666666666666666666666666`; branch `acceptance/chrome-a11y` | One DRAFT and one audit event | Created `cand-be1fa73cb1f976c82423dfbc`; revision `0`, `NOT_EVALUATED`, profile `1`, hardware `NOT_PERFORMED`, one `candidate.created` | PASS |
| Chrome restart/reflow | Restart service; then set 390 × 844 viewport | Clear stale session and preserve actions without page overflow | Restart returned to activation; narrow document width was 375 px and Previous/Next/Create remained visible | PASS |
| MSP430 Windows connection | Enumerate TI/MSP interfaces; non-writing COM4 open/close and sustained-open observation | Stable connection without changing the board | COM4 and COM5 remained Windows `OK`; COM4 passed 10/10 open/close cycles and a 10-second sustained open; zero reads/writes, DTR/RTS disabled | PASS — CONNECTION ONLY |
| Post-connection Dashboard | Recheck health and hardware claim | Service healthy; external observation must not become ForgeGate hardware evidence | Health remained `ok`; Overview continued to show `Hardware NOT_PERFORMED` and the no-hardware/no-measurement limitation | PASS |
| Late MSP430 follow-up | Re-enumerate after the bounded passing window | Report any later absence without extending the PASS claim | COM4/COM5 were absent; retained PnP entries showed problem 45 and `Present=false`; three two-second port samples were empty while Dashboard health remained `ok` | CONNECTION LOST / USER CHECK REQUIRED |
| MSP430 reconnection | Repeat a longer no-write/no-read host observation after user reconnection | Record bounded recovery without erasing the earlier absence | COM4/COM5 and the TI USB composite device returned `OK`, problem code 0, and `Present=true`; 25/25 COM4 opens, 90/90 two-second presence samples, and 30 sustained-open seconds passed over 216.1 seconds | PASS — BOUNDED CONNECTION |
| Post-reconnection Dashboard | Reauthenticate and inspect the authoritative Overview | Service stays healthy and the external port result is not promoted to hardware evidence | Chrome showed `Healthy`, `0.1.0a1`, API `v1`, DB schema `v8`, operator scope `sample-api`, and `Hardware NOT_PERFORMED` | PASS |
| Review round-trip | Enter a valid draft, review it, then return to edit | All draft fields retained without writing | Initial run cleared Version and Commit SHA; implementation was corrected and repeated Chrome run restored both exact values with a no-submit notice | PASS AFTER FIX |
| Injected 409 | Version `ui-error-409` in isolated fault harness | No automatic retry; reload and re-review guidance | `STORE_IDEMPOTENCY_CONFLICT`, status 409, request ID, focused alert, disabled Confirm, restored draft, zero write | PASS — PRESENTATION |
| Injected 413 | Version `ui-error-413` in isolated fault harness | State the 4 MiB limit and require a smaller reviewed request | `API_BODY_TOO_LARGE`, status 413, request ID, focused alert, disabled Confirm, restored draft, zero write | PASS — PRESENTATION |
| Injected 429 | Version `ui-error-429`; `Retry-After: 3` | Hold the action for the stated interval | `API_AUTH_RATE_LIMITED`, status 429, request ID, focused alert, countdown observed at `Retry in 2s`, action re-enabled after the hold, zero write | PASS — PRESENTATION |
| Injected 500 | Version `ui-error-500` in isolated fault harness | Do not infer whether the write happened; require logs and authoritative-state inspection | `API_INTERNAL_ERROR`, status 500, request ID, focused alert, disabled Confirm, restored draft, zero write | PASS — PRESENTATION |

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

The Chrome run began from those 129 candidates. Its invalid sample created no
row. Two generic valid samples—one revealing the result-focus defect and one
verifying the correction—produced the only two additional candidates, for 131
total. `chrome-a11y-20260904` has exactly one `candidate.created` event.

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

Chrome then exposed that a successful write left the dialog named as a pending
confirmation and moved focus to the page body when its controls were replaced.
The result state now changes the accessible heading to `Request completed`,
labels the saved draft, and focuses Inspect candidate. The repeated Chrome
write/detail/audit run passed after rebuilding and restarting the local service.

The user-authorized MSP430 connection check then exposed no board or Dashboard
availability fault, but the adjacent draft-review run found that Back to edit
discarded Version and Commit SHA. The dialog now restores all reviewed fields,
announces that no request has been submitted, and retains opener-focus behavior
on Cancel. The repeated Chrome run restored the exact sample values and the
candidate count remained unchanged. The external COM4 observation is recorded
separately and does not change ForgeGate's `Hardware NOT_PERFORMED` claim.
The later follow-up found that Windows no longer enumerated COM4/COM5. The
bounded connection observation therefore remains valid only for its measured
window and does not establish long-duration stability. After the user
reconnected the board, a second 216.1-second observation passed 25/25 COM4
open/close cycles, 90/90 two-second COM4/COM5 presence samples, and 30 seconds
of sustained COM4 opening. The earlier absence remains retained, and the new
result still does not establish uninterrupted long-duration stability,
protocol correctness, firmware behavior, physical measurement, or ForgeGate
collector execution. A fresh Chrome activation then confirmed `Service
Healthy` and `Hardware NOT_PERFORMED` remained visible together.

An isolated Chrome fault-presentation run then exercised 409, 413, 429, and
500 responses through the real Dashboard UI. Every case rendered its exact
HTTP status, stable code, request ID, focused alert, and status-specific safe
next step. Conflict, oversized-body, and internal-error samples left Confirm
disabled. The rate-limit sample honored `Retry-After: 3`, showed a decrementing
retry label, and re-enabled the action after the hold. Back to edit restored the
exact draft each time, and the copied fixture remained at three candidates.
These injected responses prove presentation behavior only, not the occurrence
or authenticity of an operational failure.

## Remaining manual boundary

The following items remain `NOT_RUN` or partial and are not inferred from this
run:

- Edge/Chrome 100–200% exact zoom matrix;
- high contrast, screen reader, and Remote Desktop.

Five generic-data Windows Chrome captures are retained under `docs/assets/`
and indexed by `docs/PORTFOLIO_EVIDENCE.md`: authority/limitations, candidate
list, candidate detail/audit, validation recovery, and the earlier large-data
pagination fixture. Captions and the machine-readable capture record limit the
claim to the implemented Alpha interaction surface and explicitly exclude
hardware, evidence-authenticity, production, and release-approval evidence.
The source-distribution smoke test explicitly requires every JPEG so packaged
README rendering cannot silently lose the captures.

The retention audit also found that the browser emits JPEG bytes by default;
the earlier `.png` extension did not match its content. All retained browser
captures now use `.jpg`, and an automated test binds each file's JPEG marker,
byte length, and SHA-256 digest to the capture record.

Two-tab stale-revision recovery remains not applicable until the Dashboard
exposes a revision-mutating transition, binding, or evaluation command.
