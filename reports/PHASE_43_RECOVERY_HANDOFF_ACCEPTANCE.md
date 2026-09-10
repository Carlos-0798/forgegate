# Phase 43 — reviewed recovery handoff

Date: 2026-09-07. Evidence: local Windows host tests with synthetic private data.
Status: automated and native Edge synthetic acceptance passed.

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

Forty focused Python cases pass across Dashboard recovery and offline
readiness. Nine production-TypeScript cases cover READY/BLOCKED presentation,
local invalid/oversize refusal, 409/429/500 display without automatic retry,
producer isolation, late-response suppression and sequential report reselection.
The complete frontend suite passes 139 cases.

`tools/verify.py` passed with 1,247 tests and 3 environment-dependent symlink
skips. Branch-aware coverage is 95.72% across 12,372 statements and 3,226
branches; both recovery modules are 100%. Ruff, formatting, strict mypy across
109 source/tool files, 53 document plus 3 artifact Schemas, 28-path/30-operation
Dashboard OpenAPI, packaged asset inventory and 33 interaction-smoke outcomes
all pass.

`tools/release_smoke.py` also passed from clean Windows environments. The built
wheel SHA-256 was
`a5aeda6053a880ed0c7862e901b456c8dbccf008f189ec80f8944ff5201d42a4`; the
sdist SHA-256 was
`57063aa20800c1fae8fc3bb017cd95480f3f48e0af937b91cb6474d017567d87`.
The smoke workflow installed the wheel, exercised packaged CLI/storage flows,
verified the candidate-store backup, and installed the MSP430 optional extra in
an isolated environment. It did not connect to physical hardware.

## Native Edge acceptance and findings

An isolated Edge session activated successfully with the synthetic operator.
Native file selection then exposed a real exact-byte bug: the request model's
inherited whitespace normalization removed the CLI report's final newline after
the browser had hashed it. The service correctly rejected the mismatch. The
request model now preserves imported text byte-for-byte, and a regression case
covers the CLI-style final newline.

The next manual pass exposed that a successful review left the review button
disabled after selecting another file. File changes now clear the prior result
and enable a fresh explicit review; a production-TypeScript regression case
covers READY followed by INCOMPLETE in one page session.

The repaired build passed the following native Edge workflow:

- READY source SHA-256
  `257e526e7fb054dda638b4353b5b5a3352c7d885b7e3e8ff912ac76f82b7f39b`
  rendered `READY_FOR_REHEARSAL` with handoff
  `sha256:23ae5fd541481602ceee688df03e4a9a1b5910bfb9b607bc5622b143a58bef15`.
- Its downloaded JSON independently hashed to
  `c74b57d88f6af6d19adb78c273ed5ad608cea94d8037e6548bbc4e22df308c2d`.
- INCOMPLETE source SHA-256
  `a70cd6eefa7e0af7adecb7be971e27adb8aee12077c0deb62da9ed3644ff5a9b`
  rendered `BLOCKED` and dependency `NOT_SUPPLIED`, with handoff
  `sha256:e9703e4b35be98147d6d8331886e8284b5bdf48ac37fbd8076caacc1791b6da7`.
- Its downloaded JSON independently hashed to
  `8fa3b1a0ed290786eed1f4564d51c7b3267838aad965ca190daf4decf1bade45`.
- Both downloaded documents passed strict `RecoveryReadinessHandoff` model
  validation.

Screenshots of the successful READY and BLOCKED states were captured in the
interactive browser session. Browser policy blocked writing those captured bytes
back through a `file://` bridge, so no repository screenshot is claimed or
committed. The structured hashes above remain the durable local evidence.

## Evidence boundaries

All data is synthetic. READY is a historical exact-snapshot observation, not
current availability. No restore, failover, backup transfer, producer
authentication, production-store access, GitHub action or MSP430 access occurred.
The Edge checks used synthetic local data and do not expand those claims.
