# Phase 46 — workspace adoption design review

Date: 2026-09-07. Baseline: `81710fb` (`feat: add rehearsal receipt review`).
Scope: local design and documentation only. GitHub synchronization remains paused.

## Outcome

The [adoption/rollback proposal](../docs/WORKSPACE_ADOPTION_DESIGN.md) is recorded
for owner review. It defines identities, recovery-point differences, all-writer
quiescence, owned-process control, existing-only paired startup, probation checks,
journal/descriptor transitions and a conservative no-automatic-rollback boundary.
Its 24 fault-injection cases are requirements, **not executed adoption tests**.

No production code, dependencies, generated schemas or assets changed. No live
Dashboard was stopped/restarted, no database was adopted/migrated, no hardware
was accessed, and no remote operation was performed for this phase.

## Findings and disposition

| Finding from baseline source | Disposition |
|---|---|
| Windows launcher does not forward a job-store argument although paired recovery prose implied it did | Corrected recovery instructions to use explicit CLI with both existing stores and another port |
| Ordinary Dashboard startup initializes the candidate application | Existing-only managed startup specified; runtime behavior unchanged |
| HTTP health and matching HTML do not attest process/store identity | Private owned-process identity handshake plus store-pair readback required |
| Snapshot locks expire after copying and do not fence every later writer | Persistent maintenance/admission protocol required before stop/start |
| Existing rehearsal validates a bounded subset of domain history | Complete supported-domain validation required before adoption eligibility |
| Rehearsal copies may be older/divergent with matching aggregate counts | Exact identity/history comparison and renewed final-source review required |
| Silent rollback after write admission could discard committed target data | Durable WRITE_ENABLE_INTENT closes automatic rollback eligibility |
| Verification matrix retained earlier OpenAPI and coverage totals | Corrected to Phase 45 contract: 29 paths / 31 operations and 95.77% |

Primary SQLite and Microsoft references are linked in the design. They support
the underlying storage/process constraints; they do not validate a future
ForgeGate manager or establish a compliance certification.

## Verification

- Source review: current launcher, Dashboard CLI/API startup/health, runtime
  diagnostics, paired backup and rehearsal implementation inspected.
- Full existing development gate: `.venv/Scripts/python.exe tools/verify.py`
  exited 0 with `ForgeGate development verification: PASS` on Windows/Python
  3.12.10. Pytest: 1,295 passed, 3 host symlink skips, 115.02 seconds; branch-aware
  coverage 95.77% (12,536 statements, 3,246 branches). These are existing-suite
  regressions, not new adoption tests.
- Dependency consistency, Ruff, formatting (308 files), strict mypy (110 files),
  packaged assets (5 files), example validation, committed JSON Schemas and both
  OpenAPI drift checks pass. CLI/REST interaction smoke: 33/33 expected outputs.
- Direct committed Dashboard contract inspection confirms 29 paths/31 operations.
  Relative Markdown links: 237 resolved at the initial documentation check;
  acceptance matrix: 24 unique case IDs. `git diff --check` passes.
- New adoption fault-injection cases: NOT RUN; implementation absent.
- Browser, native accessibility, remote desktop and MSP430: NOT RUN this phase.
  Phase 45 screenshots remain historical, not relabeled as new acceptance.
- Release smoke: not rerun; no packaging/dependency/runtime changes. Phase 45
  package results remain historical package evidence.

## Next acceptance gate

Phase 47 is a bounded read-only preflight model/CLI over explicit coordinated
source snapshots and cold target copies. Its reports must reject incomplete
domain comparison and must not claim live readiness or grant process control.
Managed lifecycle and all 24 fault cases remain gates before any real switch.
