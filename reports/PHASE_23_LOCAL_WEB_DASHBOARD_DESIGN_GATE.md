# Phase 23 local Web Dashboard design gate

- Date: 2026-09-04
- Product: ForgeGate `0.1.0a1`
- Scope: Dashboard architecture, UX, threat model, and acceptance design
- Implementation evidence: none
- Hardware access: `NOT_PERFORMED`

## Outcome

**PASS for the design gate only.** The proposed Dashboard preserves the
existing domain-neutral core, loopback-only deployment, Ed25519 authority,
path-free REST boundary, evidence semantics, and CLI/API application services.
No graphical page, browser authentication flow, static asset bundle, Dashboard
route, frontend test, or screenshot is implemented by this phase.

## Accepted decisions

- one same-origin local web process rather than a hosted SPA or Electron-first
  product;
- an `/app/api/` browser-for-frontend boundary separate from the existing
  Bearer-authenticated `/v1/` API;
- companion CLI activation so private keys and raw API Bearer tokens do not
  enter browser JavaScript;
- no upload, evaluation, assurance export, plugin execution, or trust-store
  administration in the first vertical slice;
- strict separation of request completion, candidate status, engineering
  decision, verification level, limitations, and hardware claim;
- a mandatory clean-wheel, real-browser, adversarial, keyboard, zoom, and
  expected-versus-actual acceptance gate.

## Inputs reviewed

- the existing authenticated loopback REST architecture and OpenAPI contract;
- candidate revision, idempotency, project-scope, audit, and security-event
  behavior;
- current Windows Alpha packaging and interaction gates; and
- owner-supplied interaction lessons from a separate engineering application,
  adapted without importing its runtime, UI, or evidence.

## Deliverables

- `docs/product/DASHBOARD_UX_REQUIREMENTS.md`
- `docs/architecture/LOCAL_WEB_DASHBOARD.md`
- `docs/security/DASHBOARD_THREAT_MODEL.md`
- `docs/DASHBOARD_ACCEPTANCE_MATRIX.md`

## Remaining implementation gate

Phase 24 must implement the narrow authenticated Overview/Projects/Candidates
slice and satisfy the acceptance matrix. Until then, the CLI and authenticated
loopback REST API remain the only implemented user-facing surfaces. The design
gate is not a production, public-release, accessibility, hardware, or
non-loopback claim.
