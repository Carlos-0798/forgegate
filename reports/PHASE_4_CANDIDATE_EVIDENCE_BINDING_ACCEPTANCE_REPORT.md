# Phase 4 candidate-evidence binding acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev11
- Scope: self-validating assembly binding, SQLite-v3 persistence and migration,
  candidate lifecycle gating, and bound terminal policy evaluation
- Hardware/device work: none
- Remote/publication work: none

## Accepted capability

ForgeGate can persist exactly one audited evidence assembly against a new
revision-one `COLLECTING` candidate. The strict
`forgegate.candidate-evidence-binding.v1` companion document embeds both inputs,
their canonical fingerprints, an explicit binding time, and a content-derived
binding ID.

New SQLite-v3 candidates cannot advance to `READY` without that durable record.
The later terminal policy evaluation must reference the canonical fingerprint
of the binding's nested `EvidenceBundle`, so the stored release decision cannot
silently use a different evidence set.

## Verified controls

- exact candidate/assembly commit equality and revision-one `COLLECTING` state;
- timezone-aware, non-regressing candidate, assembly, binding, and transition
  chronology;
- recomputed candidate, assembly, nested-bundle, and binding fingerprints;
- one immutable binding per candidate with foreign-key and append-only trigger
  protection;
- canonical idempotency request identity, exact replay, new-key replay
  recording, conflicting-key rejection, and rollback fault injection;
- `COLLECTING -> READY` missing-binding and pre-binding-time rejection;
- terminal evaluation mismatch rejection;
- read/restart validation against the revision-one snapshot and complete audit
  chain;
- explicit validated v1/v2-to-v3 migration with immutable legacy no-binding
  semantics;
- CLI bind/show/error paths, canonical Schema, committed Golden, and installed
  package workflow.

## Local verification result

- `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict across package and verification tools: PASS
- candidate evidence-binding/store focus: 71 passed; 100% across 526 statements
  and 138 branches
- full pytest: 523 passed, 1 skipped because this Windows host could not create
  the symlink test fixture
- full branch-aware coverage: 100% across 3,799 statements and 1,088 branches
- ten document Schemas plus two artifact Schemas: exported, parsed, and
  drift-checked
- source-distribution required-path manifest: PASS
- repository-external wheel installation: PASS
- installed JUnit + Benchmark collection, assembly validation, candidate
  binding, READY/EVALUATING/PASS transitions, evaluation replay, attestation,
  and readback: PASS
- all prior installed CLI smoke paths: PASS

These results are local-host evidence. They are not evidence of remote CI,
hardware, producer authentication, or public release.

## Migration and compatibility boundary

Existing v1/v2 candidates migrate with `evidence_binding_required = 0` and no
binding row. ForgeGate deliberately does not reconstruct or imply a historical
assembly. Candidates created after migration use the v3 gate. Existing v1
terminal candidates still require the exact original evaluation backfill
before attestation.

No Analog Validation Studio runtime or MSP430 interface is imported or opened.
The binding accepts only ForgeGate public documents, so future AFE/MSP430
collectors can remain optional artifact producers behind the same generic
assembly boundary.

## Assurance boundary

The binding and SQLite audit chain prove deterministic local content
association and transaction ordering. SHA-256 does not authenticate a producer,
operator, CI run, commit authority, clock, or physical measurement. Release
attestation v1 contains the terminal evaluation fingerprint but not the full
assembly receipts; `candidate show-evidence` is the authoritative companion
readback until a future attestation schema explicitly carries that relationship.
