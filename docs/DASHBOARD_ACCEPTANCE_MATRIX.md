# Local Dashboard acceptance matrix

## Status

This matrix defines the gate for the implemented narrow local Web Dashboard.
The Phase 24 authenticated slice, Phase 25 optional live monitor, and Phase 26
read-only assurance review are present, but the full manual UI exit gate is not
yet accepted. Design completion, unit coverage, clean packaging, Edge/Chrome
execution, and the unexecuted exact-zoom/assistive-technology matrix remain
separate evidence.

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
| FGD-A28 | Candidate assurance review | One authorized query returns the exact candidate, transition history, evidence binding, policy material/evaluation, attestation, and portable identity without mutation |
| FGD-A29 | Firmware fault presentation | Known UART v1 bits receive versioned labels; unknown bits remain visible without invented meaning |

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

## 2026-09-04 execution record

| ID | Result | Actual observation / remaining boundary |
|---|---|---|
| FGD-A01 | PASS | CLI loopback launch and `/app/` plus `/healthz` were exercised locally. |
| FGD-A02 | PASS | Dashboard command reuses the established loopback allowlist; external/wildcard cases reject. |
| FGD-A03 | PASS | Wheel/sdist inventory and clean install pass; Edge loaded the installed-wheel assets and authenticated read pages. |
| FGD-A04 | PASS | Built assets contain no remote URL/runtime loader and the observed browser run made only loopback requests. |
| FGD-A05–A10 | PASS | Header, Origin/Host, CSRF, activation success/replay/expiry/browser-binding tests pass. |
| FGD-A11 | PASS | Structural/response checks and the inspected browser DOM/console exposed no key, Bearer token, signature, or persistent credential store. |
| FGD-A12 | PASS | Automation plus explicit logout, natural 60-second expiry, and service-restart/401 browser runs clear protected state and return to activation. Manual administrator revocation remains a separate unexecuted scenario. |
| FGD-A13–A14 | PASS | Producer write/audit denial and exact project-scope enforcement pass. |
| FGD-A15–A19 | PASS | Bounded service queries, exact detail/create/audit, replay, and changed-payload conflict pass automation; Edge traversed all six pages of a 129-record set with zero duplicate versions and performed another reviewed create/readback. |
| FGD-A20 | NOT_APPLICABLE | This slice exposes no revision-mutating command; stale-revision UI becomes mandatory with the first such command. |
| FGD-A21 | PASS | Edge refresh/back/forward retained three rows and issued no observed duplicate mutation. |
| FGD-A22 | PASS | Dynamic values use text-node APIs only; executable HTML APIs/storage/service-worker/eval patterns are rejected by a committed asset test and CSP. |
| FGD-A23 | PASS | Browser runs cover 401 recovery, unknown-track 404, strict-body 422, and isolated test-harness 409/413/429/500 with stable status/code, safe next step, request ID, focused alert, zero write, and a three-second 429 action hold. Producer authority prevents the normal UI from issuing a forbidden write. The injected statuses are presentation evidence, not authentic operational-failure evidence. |
| FGD-A24–A25 | PASS | UI separates request/candidate/decision/hardware/limitations and uses bounded 25-row cursor pages; six-page forward traversal and one backward page produced no duplicate or unreachable row. |
| FGD-A26 | PASS | A separate generated Dashboard BFF OpenAPI document has explicit operation IDs, committed-byte drift checks, and installed-wheel comparison. |
| FGD-A27 | PASS | Full verification and clean release smoke pass at this checkpoint. |
| FGD-A28 | PASS | The project-scoped assurance-review BFF joins persisted source documents without frontend recalculation; complete and missing-record paths pass automation and the committed OpenAPI drift check. |
| FGD-A29 | PASS | `0x0015` renders the three exact UART v1 reports and an unknown-bit fixture renders `UNKNOWN_FAULT_BITS`; labels explicitly deny diagnostic meaning. |
| FGD-M01 | PASS | Initial loading and unauthenticated activation frame rendered without a blank/unfinished state. |
| FGD-M02 | PASS | Microsoft Edge keyboard-only path covered activation, project/candidate navigation, review, confirmation, detail, and audit. |
| FGD-M03 | PASS | Edge kept Shift+Tab/Tab inside the dialog, Escape closed it, and visible focus returned to Create candidate; the dialog retained a semantic accessible name. |
| FGD-M04 | NOT_RUN | Exact 100/125/150/175/200% browser zoom matrix was not executed. |
| FGD-M05 | PASS | Loading, empty, ordinary DRAFT, 404/422 error recovery, and a 129-record six-page state remained distinguishable and recoverable; the broader A23 uncommon-error matrix remains partial. |
| FGD-M06 | PASS | A 60-second session automatically removed identity/project/candidate state and announced expiry with a clear reactivation action. |
| FGD-M07 | NOT_APPLICABLE | No revision-mutating UI exists in this slice. |
| FGD-M08 | PASS | Detail view visibly distinguished request completion, DRAFT, `NOT_EVALUATED`, and hardware `NOT_PERFORMED`. |
| FGD-M09 | PASS | CLI and page copy require explicit service shutdown; closing a tab makes no shutdown claim. |
| FGD-M10 | PASS | Generic-data Windows Chrome captures are retained as JPEG assets and indexed by `docs/PORTFOLIO_EVIDENCE.md`; captions and the machine-readable capture record explicitly exclude hardware, evidence-authenticity, production, and release-approval claims. |

Additional environments: Microsoft Edge PASS for the recorded core, complete
modal-focus, large-data, 422-recovery, and installed-wheel read paths; Chrome
PASS for activation, Overview/Projects/Candidates, complete modal focus,
129-record pagination, 422 recovery, authoritative writes/readbacks, service-
restart recovery, 390 × 844 layout, and clean console; in-app browser PASS for
the 390 × 844 responsive/large-page check and follow-up operator/producer
input-output, logout, expiry, and restart flows. Exact zoom, high contrast,
screen reader, Remote Desktop, Firefox, macOS, and Linux browser runs are
`NOT_RUN`.

The exact follow-up samples and persisted-output cross-check are recorded in
`reports/PHASE_24_MANUAL_INTERACTION_ACCEPTANCE_2026-09-04.md`.

## 2026-09-05 Phase 25/26 follow-up

| Scope | Result | Actual observation / boundary |
|---|---|---|
| Physical unplug/replug | BOUNDED PASS | The owner performed one physical cycle while the page remained open and observed the live transition. The independent post-reconnect window advanced sequence 138→149 and valid frames 3,028→3,039 while reconnects remained 1. No automated transition timestamp or electrical measurement is claimed. |
| Live decoded reports | PASS | The connected COM4 page displayed `FAULT 0015` as `DS18B20_MISSING`, `NTC_RANGE`, and `INA219_COMM`; ForgeGate sent zero serial bytes and made no diagnosis. |
| Evidence review | PASS | A generic persisted PASS fixture rendered its binding, assembly, evidence value, trust, verification level, and artifact hash. |
| Decision review | PASS | The same fixture rendered expected `0`, actual `0`, evidence ID, reason code, explanation, exact policy material, and PASS aggregation. |
| Assurance review | PASS | The same fixture rendered its unsigned-local attestation, bundle identity, transition chain, source-byte state, verification scope, and limitations. |
| Portfolio retention | PASS | Four new JPEG captures have committed dimensions and SHA-256 values in machine-readable evidence records; no personal data or secret is present. |

The detailed records are
`reports/MSP430_MANUAL_UNPLUG_REPLUG_EVIDENCE_2026-09-05.json`,
`reports/DASHBOARD_ASSURANCE_REVIEW_EVIDENCE_2026-09-05.json`, and
`reports/PHASE_26_DASHBOARD_ASSURANCE_REVIEW_ACCEPTANCE_REPORT.md`.

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
