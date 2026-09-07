# Phase 43 — reviewed recovery handoff

Date: 2026-09-07. Evidence: local Windows host tests with synthetic private data.
Status: automated acceptance passed; native Edge file-selection acceptance open.

## Implemented

- `workspace recovery-check --output` creates a new path-free UTF-8 JSON report
  for READY and INCOMPLETE outcomes, never overwriting an existing file.
- The authenticated operator-only Recovery page accepts the document, calculates
  its exact-byte SHA-256 and sends no file path or backup payload.
- The same-origin service revalidates size, UTF-8/JSON bounds, duplicate and
  non-finite values, exact hash, strict readiness coherence, CSRF and role.
- A strict `forgegate.recovery-readiness-handoff.v1` document binds the imported
  bytes, normalized report identity, disposition and dependency summary while
  retaining `live_availability=NOT_CHECKED`, `payload_transfer=NOT_INCLUDED` and
  `restore=NOT_PERFORMED`.
- The browser can download the reviewed handoff without changing candidate/job
  storage, starting recovery, accessing hardware or publishing an artifact.

## Automated validation

Thirty-nine focused Python cases pass across Dashboard recovery and offline
readiness. Eight production-TypeScript cases cover READY/BLOCKED presentation,
local invalid/oversize refusal, 409/429/500 display without automatic retry,
producer isolation and late-response suppression. The complete frontend suite
passes 138 cases.

`tools/verify.py` passed with 1,246 tests and 3 environment-dependent symlink
skips. Branch-aware coverage is 95.72% across 12,371 statements and 3,226
branches; both recovery modules are 100%. Ruff, formatting, strict mypy across
109 source/tool files, 53 document plus 3 artifact Schemas, 28-path/30-operation
Dashboard OpenAPI, packaged asset inventory and 33 interaction-smoke outcomes
all pass.

`tools/release_smoke.py` also passed from clean Windows environments. The built
wheel SHA-256 was
`a3cd44b0b555772f6478d188c31c91e8411d7e13df777d3e3b5add98c495b890`; the
sdist SHA-256 was
`dd660ce2ba6f6d6a1899a0719fb7d8c115b487f1144e07385deb708ba04d251f`.
The smoke workflow installed the wheel, exercised packaged CLI/storage flows,
verified the candidate-store backup, and installed the MSP430 optional extra in
an isolated environment. It did not connect to physical hardware.

## Browser observation and open gate

An isolated Edge session activated successfully with the synthetic operator and
rendered the new Recovery navigation/page with the expected historical-check and
no-payload wording. The browser-control extension did not have file-URL access:
its chooser returned zero selected files. A subsequent malformed selection path
returned the expected sanitized HTTP 400. This does not establish successful
native Edge file import or download, and no success screenshot is retained.

To close the gate, the owner must enable file-URL access for the Edge browser-
control extension. Then select the exact generated READY and INCOMPLETE reports,
confirm their expected dispositions/hashes, download the handoff, and compare its
bytes/identity independently. This browser permission is not changed by ForgeGate.

## Evidence boundaries

All data is synthetic. READY is a historical exact-snapshot observation, not
current availability. No restore, failover, backup transfer, producer
authentication, production-store access, GitHub action or MSP430 access occurred.
The local implementation checkpoint may be committed while the manual browser
gate remains explicitly open.
