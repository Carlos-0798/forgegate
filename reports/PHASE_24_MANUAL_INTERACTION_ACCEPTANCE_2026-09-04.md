# Phase 24 manual interaction acceptance — 2026-09-04

- Product: ForgeGate Windows Local Alpha
- Surface: authenticated loopback Web Dashboard
- Browser: Codex in-app browser on Windows
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

## Remaining manual boundary

The following items remain `NOT_RUN` or partial and are not inferred from this
run:

- Chrome core flow and the Edge/Chrome 100–200% exact zoom matrix;
- full modal Tab containment and an observable Escape-key run (explicit Cancel
  focus return passed, but the available controller did not produce an
  observable Escape event);
- browser-driven 403, 409, 413, 422, 429, and 500 rendering;
- bounded-large-data visual review, high contrast, screen reader, and Remote
  Desktop;
- a retained portfolio screenshot.

Two-tab stale-revision recovery remains not applicable until the Dashboard
exposes a revision-mutating transition, binding, or evaluation command.
