# Phase 47 — read-only adoption preflight acceptance

Date: 2026-09-08. Baseline runtime commit: `81710fb`; Phase 46 local design edits
were preserved. GitHub synchronization remains paused; no commit/push/PR/merge or
owner-workspace adoption is included in this phase.

## Implemented outcome

- Strict `forgegate.workspace-adoption-preflight.v1` document and owner CLI.
- Exact cold target/receipt/archive association, current template/schema checks,
  bounded full supported-table scan, domain/history/audit/replay readback, external
  archive checks and fingerprint-only difference pages.
- Explicit MATCH/DIFFERENT versus no adoption authority; incomplete checks refuse.
- New rehearsal readback uses disposable copies of actual destination bytes,
  avoiding creation of WAL/SHM sidecars in the published cold directory.

See [operations and limits](../docs/WORKSPACE_ADOPTION_PREFLIGHT.md). This implements
the snapshot-preflight part of the Phase 46 design, not a live-source freshness
check, authenticated lineage, original request reconstruction or managed switch.

## Verification evidence

- Final focused preflight/rehearsal run with warnings treated as errors:
  `python -m pytest tests/test_adoption_preflight.py tests/test_recovery_rehearsal.py -q -W error`
  passed 87 cases in 20.54 seconds. Final full `tools/verify.py` exited 0 with
  `ForgeGate development verification: PASS`: 1,344 passed, 3 host symlink skips,
  95.85% branch-aware coverage (12,876 statements, 3,338 branches). All 49 new
  preflight cases are included. Inventory/preflight modules reach 100% and the
  report-model module 94.83%; this is not full security or live adoption coverage.
- Ruff/formatting (313 files), strict mypy (114 source/tool files), dependency
  consistency, 56 document plus 3 artifact schemas, both OpenAPI drift checks,
  packaged assets and 33/33 expected CLI/REST smoke outcomes pass.
- [Independent-process synthetic CLI evidence](PHASE_47_ADOPTION_PREFLIGHT_EVIDENCE.json):
  MATCH exit 0; one additional queued job gives exactly two SOURCE_ONLY records,
  DIFFERENT exit 2; wrong source hash refuses with exit 3. Cold-copy bytes and
  its three-member directory are preserved; task remains QUEUED.
- Clean-wheel packaging and independent CLI smoke: `tools/release_smoke.py`
  exited 0 with `ForgeGate release smoke: PASS`. The required sdist paths include
  the new schema, test module and independent CLI smoke; the latter also runs
  with the clean-installed wheel interpreter. Optional serial dependency import
  is tested without opening any device. Tested package hashes:
  - wheel: `1f8b65ef54480201720bd47f14afd45388a80fa9a3ec970b8222baf8108eb4fa`
  - sdist: `adc8761f595828cd783f965986ba9d67869e9d2fed88a4374bf1536a22cd94ae`
  These identify acceptance-run builds before final documentation result updates,
  not a published release or a later rebuild.
- Retained synthetic evidence JSON SHA-256:
  `36131e3e7aec64bdfdc262e37777e32b401a63f62634d2d64aff9fac2e31a0ea`.
  254 relative documentation links resolved; `git diff --check` passes.
- No new browser page or screenshot is claimed. Earlier Dashboard screenshots
  retain their original phase labels. No native accessibility, Remote Desktop,
  owner-workspace service restart or MSP430 acceptance was performed. Existing
  packaging smoke may start/stop its own disposable local runtime fixtures.

## Failures found and disposition

1. The first real preflight rejected a newly rehearsed copy because earlier
   read-only SQLite inspection left WAL/SHM files. Corrected new-rehearsal readback
   to inspect disposable copies; strict sidecar refusal stays in place. Existing
   owner directories are not deleted, repaired or silently reclassified.
2. Initial model construction used dictionaries where typed table models were
   expected, causing serializer warnings. Typed construction now precedes strict
   final validation; warnings are not suppressed.
3. Initial additional test fixtures supplied a too-short project revision key
   and a successful security event without an actor. Fixture inputs were corrected
   to existing valid contracts; production validators were not weakened.

## Remaining gates

Existing-only paired startup, owned-process identity, all-writer maintenance
fencing, private control channel, target probation, generation publication and
rollback fault injection remain future implementation. The Phase 46 live
adoption matrix is not claimed passed by these offline tests. Owner acceptance
of exact downtime/data differences is still required before a real switch.
