# Phase 63 — final user-path closeout

Date: 2026-09-09. Result: **LOCAL ENGINEERING ACCEPTANCE PASS**.

This checkpoint closes the scoped Windows Local Alpha after a recipient-style
installation and browser walkthrough. It is an engineering simulation of first
use, not an independent novice study, production qualification or measured
productivity experiment.

## Delivery and cold-start evidence

- Clean source commit: `f2c7abb6c2890b8a81eb1760ac7588528601aa0b`.
- The approved Windows builder generated an sdist in a temporary tree, built the
  wheel from that clean extraction, checked the packaged Dashboard inventory and
  wrote a no-overwrite `build-receipt.json` beside the artifacts.
- Retained wheel: `forgegate-0.1.0a1-py3-none-any.whl`, 363,177 bytes, 116
  members and five inventoried Dashboard files. Its authoritative SHA-256 is in
  the retained build receipt.
- The wheel was installed into a new Python 3.12 environment outside the source
  checkout. `pip check`, demo workspace initialization, existing-pair Dashboard
  startup and loopback health all passed.
- Observed machine elapsed times on this host were 0.50 s to extract the reviewer
  package, 11.02 s to install, 1.26 s to initialize the workspace, 1.28 s to
  start the Dashboard and 0.85 s to activate it. These are diagnostic timings,
  not human active time or evidence of an efficiency improvement.

A direct wheel build from the long-lived source directory was rejected because
its ignored `build/` tree contained obsolete hashed frontend assets. The rejected
artifact remains under the private acceptance work area. The documented isolated
builder then produced a clean-commit package containing only the current CSS and
JavaScript assets. This confirms why direct reused-tree builds are not accepted.

## Browser workflow and output checks

The installed Dashboard was exercised through a visible local browser and CLI-
approved operator session. The retained demo FAIL candidate showed the failing
`tests-pass` rule and the other two passing rules. A new synthetic candidate then
completed report detection, saved-policy selection, immutable binding, READY and
EVALUATING transitions, a three-rule PASS decision, local attestation and
assurance handoff. Its downloaded package independently verified `VALID / PASS`.

The same acceptance also verified a downloaded synthetic FAIL assurance package
as `VALID / FAIL`. `VALID` means the package is internally verifiable; it does not
turn a failed engineering decision into a pass.

The walkthrough exposed one clarity issue: a combined count of one report and one
collection receipt was labelled as two reports. The UI now calls them `original
source files (reports plus exact collection receipts)`. A dedicated regression
covers the one-report/one-receipt case, and the replay dialog checks the same
wording. The clean wheel with the new hashed JavaScript asset was installed and
loaded in a fresh browser session; CLI activation and durable candidate creation
passed. Current browser tooling could not inject a local file into that second
session, so the complete upload-to-PASS observation comes from the earlier full
walkthrough, while the final wording is established by the focused tests, built
asset inventory and installed-wheel load. No stronger claim is made.

## Final verification

- Full `tools/verify.py`: **1,466 passed, 3 environment symlink skips, 95.82%
  branch-aware coverage**; Ruff, formatting, mypy, schemas, OpenAPI, asset
  inventory and 33 interaction smoke cases passed.
- Frontend: TypeScript passed; **265/265 tests passed**.
- `tools/release_smoke.py`: passed its isolated sdist-to-wheel installation and
  runtime checks. Unavailable Podman caused the production plugin sandbox to
  remain fail-closed, as designed; no external plugin execution was claimed.
- Existing retained AVS compatibility remains **VALID / FAIL**, four
  collections, 130 evidence records and 12 unchanged rule outcomes.
- No MSP430 serial access or new hardware evidence was performed in this phase.

## Closeout decision

The Windows Local Alpha is suitable for a controlled reviewer demonstration and
for continued local engineering use. No reproduced blocker remains in its core
path: create candidate, import supported reports, review normalized evidence,
evaluate an authorized policy, explain PASS/FAIL/REVIEW, and export a verifiable
handoff.

Open evidence boundaries remain explicit: independent novice usability, formal
human time/accuracy comparison, native screen-reader speech, high-contrast and
remote-desktop observation, production uptime/security operations, online
publication and current physical hardware validation are not established here.
These are future validation tracks, not reasons to continue adding Alpha features.

Use the [local workspace quickstart](../docs/LOCAL_WORKSPACE_QUICKSTART.md) for a
new installation and [Windows Dashboard operations](../docs/WINDOWS_DASHBOARD_OPERATIONS.md)
for the accepted delivery procedure.
