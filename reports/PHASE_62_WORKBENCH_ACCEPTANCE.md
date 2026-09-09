# Phase 62 — independent first use and release workbench

Date: 2026-09-09. Result: **LOCAL INTEGRATION PASS**.

The owner reopened feature scope for a runtime, interaction and product review.
This checkpoint closes a coherent user task: install independently, prepare a
private workspace, assess original reports, understand the decision and verify
the downloaded handoff. It does not add another platform subsystem.

## What changed and why

| Dimension | Observed gap | Delivered change |
|---|---|---|
| Runtime correctness | Global testcase selection discarded failing summary-only sibling suites; nested count mismatches were invisible | Recursive per-suite accounting, no parent double counting, bounded suite locations and nested mismatch warnings |
| Policy correctness | Generated default policy could PASS error-only, zero-test or all-skipped reports | Three checks: passed > 0, failures = 0, errors = 0; historical frozen policies unchanged |
| First use | Phase 61 reviewer package could run CLI fixtures, but its Dashboard instructions depended on the owner's ignored development workspace | Installed `workspace-init`, fresh random scoped identity, initialized stores, strict configuration, optional synthetic examples, original XML and standalone Windows instructions |
| Interaction | Overview primarily displayed authority/limits instead of a next action | Project-scoped workbench, Quick assessment, outcome-directed review links, grouped navigation, bounded search/state filters and explicit refresh |
| UI reliability | Late Overview/Candidates requests could restore stale content after navigation/session changes | Request-generation, route and session checks; invalidated project-cache writes |
| Verification reliability | A negative smoke expecting exit 3 could falsely succeed on exit 0; outside-directory coverage workers missed the existing configuration | Nonzero mismatch guard and regression; explicit absolute coverage configuration and cwd-independent patterns for the same three existing excluded files |

## Exact artifact and verification

- Runtime source: `64b817b53e35c42d58ea1c545a0bf1eab5900fc1`.
- Verification-only follow-up: `deb6845` changes coverage configuration and the
  verification command, not installed runtime or dependency requirements.
- Fresh-sdist wheel: `forgegate-0.1.0a1-py3-none-any.whl`, 363,050 bytes,
  SHA-256 `85954723e44979c439618c0c48dee8f65ff96616bea36b3842575c72fc29aada`.
- Wheel inventory: 116 members; five inventoried Dashboard assets. All 111
  installed `forgegate/` runtime members match this exact wheel byte-for-byte.
- Full `tools/verify.py`: **1,466 passed, 3 environment symlink skips, 95.82%
  branch-aware coverage**, Ruff/format/mypy, 33 interaction smoke cases, asset
  inventory, JSON Schemas and both OpenAPI contracts PASS.
- Frontend: TypeScript PASS; **264/264 tests PASS**, including 16 new workbench
  cases. Production assets built before package construction.
- `tools/release_smoke.py`: PASS from the clean short-path source checkout,
  including independent workspace setup, random key identity, exact project
  authorization, duplicate refusal/unchanged bytes and no-demo initialization.
- Actual Windows PowerShell 5 execution of generated first-policy instructions
  produces UTF-8 without BOM and a loadable profile-authorized policy material.

The exact wheel was additionally installed into a new Python 3.12 environment
outside the repository. Package imports resolved inside its `site-packages`;
`pip check` passed. `workspace-init --demo` created its own stores and keys, and
the installed Dashboard started with the existing-pair option on loopback. No
original workspace or historical delivery wheel was overwritten.

## Actual browser input/output checks

Browser: Codex in-app browser on Windows. Local operator activation, not an
authentication bypass. Both candidates below were created and assessed through
the visible UI, using newly generated original XML and an explicitly selected
saved policy. They are **SYNTHETIC / declared / unsigned_local**.

| Case | Expected parsed result | Actual decision | Download verification |
|---|---|---|---|
| synthetic-browser-pass | total 2, passed 2, failures 0, errors 0, skipped 0 | PASS; all 3 rules pass | VALID / PASS, verifier exit 0 |
| synthetic-browser-fail | total 2, passed 1, failures 1, errors 0, skipped 0 | FAIL; tests-pass actual 1 vs required 0 | VALID / FAIL, verifier exit 0 |

Both retained candidates reach revision 4 with one immutable evidence record,
their real rule results and unsigned-local attestation. The downloaded ZIPs,
not substitutes exported through another client, were checked for the exact
three allowed members and independently verified by the installed CLI. A VALID
package may correctly contain a FAIL engineering decision.

Additional checks: FAIL filter shows 1/3 loaded candidates, unmatched search
shows 0/3, clear restores 3/3; after both UI assessments, refreshed Overview shows
4 loaded, 2 needing investigation and 2 policy-passed. Outcome links open the
correct retained candidate. Default, 390px and 768px widths have no document-level
horizontal overflow; the narrow navigation has its own horizontal scrolling.
Browser warning/error console entries: 0. Refresh retains stored outcomes.

Six real screenshots and their hashes are indexed in the
[machine-readable acceptance record](PHASE_62_WORKBENCH_EVIDENCE.json).
The narrow capture is a single viewport; no stitched full-page narrow capture is
used as layout evidence.

## Retained real-project compatibility

The new installed package verifies the original AVS replay ZIP unchanged:
**VALID / FAIL**, four collections, 130 evidence records and eight source files.
All 12 rule results exactly match the retained baseline: 10 PASS, 2 FAIL.
The archive SHA-256 remains
`961e6f953b7a7497d1f0a289c9d1ba884cfc54bb299553a130f47099b223ce8e`.
This is a new consumer compatibility check, not a new AVS execution. No MSP430
serial access, firmware, physical measurement or upstream edit occurred.

## Retained unsuccessful attempts and boundaries

- An early regression run was interrupted after review found a deep-suite
  diagnostic exceeding its location bound. A compact ordinal path and a 48-level
  regression were added before the final runtime source commit.
- The first complete regression run passed all 1,466 tests but failed coverage
  at 94.32% because outside-directory subprocesses omitted the existing coverage
  configuration. Configuration propagation was corrected, then the full gate
  passed at 95.82%. The threshold remains 95%; no new exclusions were added.
- The browser adapter's download-event wait timed out although the file was
  downloaded successfully. The actual Downloads file and installed verification,
  not that event timeout, establish the handoff result.
- A private acceptance helper initially used a relative verifier path from a
  different cwd; after absolute resolution both downloaded files passed. No
  product code change or replacement download was needed.

Native assistive-technology/RDP acceptance and independent human time/accuracy
measurement remain open. The result is an agent-driven local Windows test, not
unassisted recipient acceptance, production readiness or producer authenticity.
No GitHub synchronization, public Release, License or LinkedIn publication.

Use [Local workspace quickstart](../docs/LOCAL_WORKSPACE_QUICKSTART.md) for the
current recipient workflow. Prior Phase 59-61 files remain historical evidence.
