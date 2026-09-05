# Local Dashboard UX requirements

## Status and evidence boundary

- Status: narrow Phase 24 slice, Phase 25 optional live status, and Phase 26
  read-only assurance review implemented; the exact zoom and
  assistive-technology exit gates remain incomplete
- Target: a local, browser-based control plane for the Windows Alpha
- Product evidence: local host automation plus partial real-browser acceptance
- Hardware evidence: optional input-only UART status observation; no device
  control, measurement validation, or release evidence

These requirements adapt owner-supplied interaction lessons from a separate
engineering application. They do not import that application's UI, workflow,
runtime, measurements, or evidence. ForgeGate retains its own release-assurance
domain and artifact-only compatibility boundaries.

## Product objective

The Dashboard should let an individual developer understand and operate the
existing ForgeGate project, candidate, evidence, decision, assurance, plugin,
and audit workflows without weakening the CLI/API security model. It is a
presentation and orchestration surface over the existing application/domain
services. It must not contain a second policy engine, lifecycle implementation,
or evidence-normalization path.

The implemented slices cover authenticated local access, service status,
optional device status, project discovery, candidate discovery, candidate
creation, candidate detail, audit history, bound-evidence inspection,
explainable policy results, retained attestations, and portable-assurance
identity. Evidence import, decision execution, assurance export, plugin
execution, trust-store administration, and file publication remain separate
later gates.

## Non-goals

- remote, LAN, internet, SaaS, or multi-user deployment;
- browser access to private signing keys;
- hardware, serial, AFE, or MSP430 control; optional serial input is observation only;
- changing an evidence level or engineering decision in presentation code;
- replacing the CLI or public versioned REST contracts;
- accepting arbitrary server filesystem paths from the browser;
- claiming WCAG conformance, production security, or third-party certification.

## Primary users and roles

| User | Need | Authority shown by the UI |
|---|---|---|
| Operator | Create and advance authorized release work | Exact project scopes and write authority |
| Producer | Inspect authorized project evidence and results | Read-only project scopes |
| Reviewer | Understand why a candidate reached a decision | Read-only retained documents and limitations |

The browser must never infer authority from a visible or disabled control. The
server remains authoritative and every protected response is scoped to the
authenticated principal.

## Information architecture

The navigation model is:

1. **Overview** — health, version, database schema, authenticated identity,
   role, project scope, session expiry, and current limitations.
2. **Devices** — optional serial connection, heartbeat freshness, and
   device-reported state, with read-only and non-evidence boundaries.
3. **Projects** — bounded project list, immutable profile identity, current
   profile, and revision history.
4. **Candidates** — project-scoped list, create action, current lifecycle,
   exact revision, commit, track, and governing profile.
5. **Evidence** — collection receipts, warnings, artifact identities,
   verification levels, and candidate binding.
6. **Decision** — frozen policy material, per-rule outcome, remediation, and
   overall PASS/FAIL/REVIEW/ERROR.
7. **Assurance** — attestation, signature status, portable bundle identity,
   offline verification, and export state.
8. **Plugins** — discovery, compatibility, requested/approved permissions,
   run plan, isolation evidence, receipts, and low-trust output.
9. **Audit & security** — project/candidate audit events, security-event
   journal, session state, and trust-store status.

Items 1–7 are implemented for their stated read-only or bounded-create slices.
Candidate audit history is embedded in item 4; dedicated Plugins and Audit &
security workspaces remain planned.

Navigation labels describe objects and outcomes. Mutating actions use explicit
verbs such as **Create candidate**, **Review transition**, **Run policy
evaluation**, **Download assurance bundle**, and **Revoke session**.

## Interaction state model

Each mutating workflow distinguishes:

| State | Meaning | Permitted action |
|---|---|---|
| Draft | Editable browser fields only | Validate or discard |
| Validated draft | Client checks passed; no authority granted | Request server validation |
| Reviewed command | Immutable request, current revision, and side effects displayed | Confirm once |
| Submitting | One request owns the idempotency key | Wait or safely cancel only when supported |
| Final response | Server response and request ID retained | Inspect, navigate, or start a new command |
| Stale | Server revision or authority changed | Reload and review again |

Editing a reviewed command invalidates it immediately. Browser refresh,
back/forward navigation, a double click, or a request retry must not issue a
second mutation. A successful idempotent replay is visibly distinct from a new
write. An idempotency conflict or stale revision never retries automatically.

## Status and evidence presentation

Every result view separates these fields:

| Field | Required meaning |
|---|---|
| Request status | Whether the HTTP/application command completed |
| Candidate status | DRAFT, COLLECTING, READY, EVALUATING, or terminal state |
| Engineering decision | PASS, FAIL, REVIEW, ERROR, or not evaluated |
| Evidence source | Tool, artifact, producer declaration, and collection time |
| Verification level | Declared, simulated, replayed, CI-validated, system-observed, or other exact retained label |
| Authority | Identity, role, project scope, and frozen project profile |
| Integrity | Commit, content ID, size, and SHA-256 where available |
| Limitations | What the result does not establish |
| Hardware claim | Always explicit; live serial status is READ_ONLY_TELEMETRY while control remains NOT_PERFORMED |

Green styling alone must never imply that evidence is authentic, hardware was
tested, a release was published, or the product is production-ready. Missing or
unknown evidence is never rendered as zero or PASS.

## Authentication and session UX

- The page begins unauthenticated and explains why project data is unavailable.
- Activation must use the approved local companion flow; the browser never
  reads a private key or receives a raw API Bearer token.
- The active identity, role, project scopes, and session expiry remain visible.
- Session expiry, logout, revocation, or trust-store change clears protected
  page state and requires a fresh activation.
- HTTP 401, 403, 409, 413, 422, and 429 responses have distinct recovery text.
- Authentication errors show the stable error code and request ID without
  exposing a token, signature, key path, raw header, or traceback.

## Input, errors, and recovery

Inputs show required status, format, limits, examples, and cross-field
constraints before submission. Validation follows required, type, field range,
cross-field, authority, and server-contract order. Client validation is for
guidance only; the server repeats every security and domain check.

An error panel remains reachable from the affected page and provides:

```text
ERROR [STABLE_CODE]
What happened: concise description.
Possible cause: bounded, non-sensitive explanation.
Safe next step: one concrete recovery action.
Request ID: correlation value.
```

New failures replace incompatible success notices. The first invalid field is
identified programmatically and receives focus only when doing so preserves a
logical reading order.

## Files, downloads, and retained state

- The first vertical slice accepts no browser-selected artifact path or upload.
- Future imports require an explicit bounded upload/staging API; a browser path
  is never interpreted as a server path.
- Downloads display the exact content identity, decision, assurance level, and
  limitations before starting.
- Browser download completion is not presented as remote publication, backup,
  archival retention, or GitHub upload.
- Draft convenience state contains no credential, token, key, signature,
  sensitive evidence body, or absolute local path.
- The product registers no service worker in the Alpha and retains no protected
  API response in persistent browser storage.

## Layout and accessibility baseline

- Semantic HTML and DOM order match the intended reading and focus order.
- All actions are keyboard reachable with a visible focus indicator.
- Status, decision, warning, and error meanings use text and structure in
  addition to color and icons.
- Dynamic status messages use an appropriate live region without moving focus
  for routine updates.
- Modals trap focus while open, Escape behavior is documented, and focus
  returns to the invoking control.
- The main action remains visible without hiding evidence limitations.
- Tables provide accessible names and use bounded pagination rather than an
  unbounded client-side dataset.
- Windows Edge and Chrome are checked at 100%, 125%, 150%, 175%, and 200% zoom.
- High contrast, screen reader, Remote Desktop, and other unexecuted checks are
  recorded as NOT_RUN rather than PASS.

## Page Definition of Done

A Dashboard capability is complete only when:

- its user goal, authority, preconditions, success, failure, replay, conflict,
  cancellation, and exit paths are defined;
- it calls existing application/domain logic rather than reproducing it;
- its mutation binds an exact idempotency key and, where applicable, expected
  revision;
- protected state is cleared on session loss;
- untrusted text cannot become executable HTML, script, URL, or CSS;
- keyboard, focus, zoom, empty, loading, error, and bounded-large-data states
  pass automated and manual checks;
- a clean wheel serves the same static assets and API contract;
- documentation, screenshots, and labels match the implemented behavior; and
- every untested environment and assurance limitation remains explicit.
