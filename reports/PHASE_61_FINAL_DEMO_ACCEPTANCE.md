# Phase 61 final Windows demonstration acceptance

Date: 2026-09-09

Result: **LOCAL FINAL DEMO PASS — SCOPED WINDOWS ALPHA MILESTONE COMPLETE**

## Delivered reviewer path

The final [Windows demonstration guide](../docs/FINAL_WINDOWS_DEMO.md) provides
one bounded reviewer sequence: fresh wheel installation, project validation,
generic PASS/FAIL policy controls, authenticated Dashboard navigation, real-project
evidence references, expected outcomes, recovery guidance and limitations.

A local non-secret reviewer ZIP was built and independently verified:

| Field | Accepted value |
|---|---|
| File | `forgegate-windows-alpha-demo-0.1.0a1.zip` |
| SHA-256 | `f199c0047725b3d0a56474431aeb1b48de2e00bcb928900e1173863189a69ee4` |
| Size | 1,038,035 bytes |
| Members | 15, including exact wheel, guide, fixtures, path-free evidence and six retained screenshots |
| Secret/data check | No private key and no database |

The ZIP remains ignored local delivery material. It is not a GitHub Release,
signed artifact, License grant or offline dependency mirror.

## Fresh-recipient execution

The exact final ZIP was extracted into a new directory. A fresh Python 3.12
virtual environment installed the enclosed wheel and its dependencies. Package
origin resolved inside the new environment's `site-packages`, not the source tree.

| Control | Expected | Actual |
|---|---|---|
| Validate generic project | exit 0, `VALID` | PASS |
| Positive policy input | decision PASS, exit 0 | PASS / 0 |
| Negative policy input | decision FAIL, exit 1 | FAIL / 1; `tests-pass` failed |

The intended nonzero negative exit proves fail-closed gate behavior and is not a
demo crash. Dependency installation used the configured package cache/index;
fully offline dependency installation was not tested or packaged.

## Actual authenticated browser walkthrough

The frozen Phase 59 installation started a new loopback Dashboard on port 8161.
A fresh one-time code produced an operator session scoped only to `sample-api`.
The following actual states were inspected:

- Overview: Healthy, version `0.1.0a1`, API v1, candidate-store schema v9 and
  all four evidence-boundary statements visible.
- Candidates: seven retained synthetic candidates. The positive
  `phase58-installed-quick` is PASS at revision 4; the negative
  `junit-fail-fixture` is FAIL at revision 4.
- Evidence: the positive case shows four collections, nine records and exact
  binding/assembly identities.
- Decision: all six positive rules pass. The negative case explains
  `security-clean` as actual `1` against expected `0` with
  `RULE_NOT_SATISFIED`.
- Assurance: `UNSIGNED_LOCAL`, exact attestation/bundle identities, immutable
  four-transition chain and `not_embedded` source bytes.
- Devices: `No live monitor configured`; the final demo did not open a serial
  port or use the MSP430 board.

Browser console warnings/errors were zero. Root horizontal overflow was zero.
The page retained one main landmark, one H1, English document language and an
ARIA live region. The seven candidate rows, 32 snapshots, 25 transitions, six
bindings, six evaluations, five attestations and 50 audit events were unchanged
after the reviewed browser reads.

## Screenshot and real-project evidence

Phase 59 established byte equality for all 109 runtime package members between
the accepted wheel and the Phase 58 browser-tested wheel. The final ZIP therefore
reuses the six installed-wheel Phase 58 screenshots. No duplicate image is
presented as newly captured evidence.

Phase 60 remains the authoritative real-project checkpoint: retained AVS replay
is `VALID / FAIL` with 130 records and 12 exact rules; retained MSP430 artifact
collection is `COMPLETE` with 17 `system_observed` records and both scope warnings.
Neither producer was rerun during this final demonstration.

## Final repository gate

- Python development verification: 1,433 passed, three Windows
  symlink-capability skips, 95.80% branch-aware coverage.
- CLI/REST interaction smoke: 33/33 PASS.
- Frontend TypeScript check and 248 production interaction cases: PASS.
- Dependency, lint, formatting, strict typing, Dashboard asset inventory,
  committed Schema and both OpenAPI checks: PASS.

## Remaining boundaries

- No current upstream execution, hardware access, producer authentication,
  GitHub synchronization, public release or deployment occurred.
- No quantified human speed or accuracy improvement is claimed.
- Agent-driven interaction is not independent first-use operator acceptance.
- Spoken screen-reader output, native high contrast and real Remote Desktop
  remain open quality commitments, not claims of this default Edge demonstration.
- The result closes the defined local Windows Alpha milestone; it does not make
  ForgeGate production-ready or generally compatible with arbitrary producers.

Machine-readable evidence:
[PHASE_61_FINAL_DEMO_EVIDENCE.json](PHASE_61_FINAL_DEMO_EVIDENCE.json).
