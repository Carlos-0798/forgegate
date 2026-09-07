# Phase 42 — offline archive dependency and recovery readiness

Date: 2026-09-07. Evidence: local Windows host tests with synthetic data.

## Implemented

- `workspace recovery-check` validates an exact root ZIP and explicit hash/path
  mappings; strict versioned output distinguishes READY from INCOMPLETE.
- External ZIP hash/structure, manifest and exact original job/event/result
  associations must all pass. Shared and multi-generation dependencies are handled.
- No supplied file mapping, unavailable file, wrong hash and invalid association
  remain distinguishable; global timeout and bad root fail without a READY report.
- Path-free reports contain no result payload, signing key or local directory.
  Duplicate/unrelated mappings fail; no search, fetch or live-store write occurs.

## Validation

The 26 new readiness cases and 94 existing archive/backup cases pass together
(120 tests). Coverage includes unchanged source bytes, exact restored tables,
v3/v4 roots with no archives, absent/mismatched/corrupt dependencies, sidecars,
directory rejection, manifest/row/assembly/size association faults, map bounds,
CLI exit 0/2/3, model coherence, shared backups and multi-generation missing files.

Independent-process synthetic CLI smoke passed. The recovered JUnit summary
remains 4 total, 3 passed, 1 failure, 0 errors/skips and 0.5 seconds. The successful
readiness report verified one archived payload. Omitted mappings returned
INCOMPLETE/NOT_SUPPLIED; the wrong ZIP returned INCOMPLETE/WORKSPACE_HASH_MISMATCH.
Exact table readback after a separate restore and original source preservation
also passed. Retained sample values are in the
[machine-readable report](PHASE_42_RECOVERY_READINESS_ACCEPTANCE.json).

Full `tools/verify.py` passed: 1,233 tests passed, 3 symlink tests skipped because
this Windows environment lacks symlink-creation capability, and 95.72%
branch-aware coverage across 12,286 statements and 3,212 branches. The new
readiness module and workspace CLI each have 100% branch-aware coverage. Ruff,
formatting, mypy (108 files), 52 document plus 3 artifact schemas, both OpenAPI
contracts, asset inventory and all 33 interaction-smoke cases passed.

Clean-wheel release smoke passed with exit code 0 and the final
`ForgeGate release smoke: PASS` marker, including the installed recovery-check
chain. The tested wheel SHA-256 is
`54f67ff8f5f2cf1976b9dea0eca620a6009581b3a03db62e3bdf2cb86648804f`;
the sdist SHA-256 is
`6299ab46af932b8cf274f9dc6d20dedb539e17204c9de33d5864daf425b654b3`.
These identify local smoke builds before final evidence/documentation edits,
not published release artifacts. The plugin capability probe reported runtime
unavailable, correctly prohibiting execution; live sandbox enforcement was not
retested. Optional MSP430 package import checks opened no serial device.

## Evidence boundaries

Readiness covers the exact root snapshot and its original archived-job payloads
at check time. It is not live availability, an actual restore, producer identity,
external key/raw-artifact availability, disk capacity, encryption or physical
hardware validation. Existing restore remains new-directory-only and requires
the root hash; original result readback independently rechecks the original ZIP.
Dashboard capacity retains its explicit NOT_CHECKED label. This phase changes
no browser page, so no new browser screenshot is claimed. CLI evidence is retained
as machine-readable output. GitHub synchronization remains paused.
