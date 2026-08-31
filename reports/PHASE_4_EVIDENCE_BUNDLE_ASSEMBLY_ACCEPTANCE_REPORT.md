# Phase 4 evidence-bundle assembly acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev10
- Scope: local collection-result loading, artifact revalidation, audited
  evidence-bundle assembly, and policy-input compatibility
- Hardware/device work: none
- Remote/publication work: none

## Accepted capability

ForgeGate can load one or more local collector `CollectionResult` JSON files,
revalidate each referenced artifact against current exact bytes, and create a
strict `forgegate.evidence-bundle-assembly.v1` envelope for one candidate
commit. The envelope retains both the normal evidence bundle and auditable
receipts for every source result.

Warnings reject assembly by default and remain visible when explicitly
retained. The existing policy engine accepts the validated nested evidence
bundle without changing collector evidence or deriving a new trust level.

## Verified controls

- root-confined, stable byte registration of collection-result files;
- strict UTF-8 JSON, duplicate-key, non-finite-number, node, and depth gates;
- exact `CollectionResult` validation;
- original artifact availability and path/media-type/size/SHA-256 equality;
- `COMPLETE` status, evidence-to-artifact ownership, and candidate-commit
  equality;
- duplicate source/result/evidence rejection and conflicting-path rejection;
- explicit warning retention, monotonic timestamps, and content-derived
  assembly identity;
- deterministic Schema and Golden drift checks;
- direct-bundle and assembly-fed policy CLI compatibility;
- clean wheel installation and collection-to-assembly-to-policy smoke.

## Local verification result

- `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict across package and verification tools: PASS
- assembly focus: 20 passed; 100% across 218 statements and 70 branches
- full pytest: 506 passed, 1 skipped because this Windows host could not create
  the symlink test fixture
- full branch-aware coverage: 100% across 3,628 statements and 1,036 branches
- nine document Schemas plus two artifact Schemas: exported, parsed, and
  drift-checked
- source-distribution required-path manifest: PASS
- repository-external wheel installation: PASS
- installed JUnit + Benchmark collection, assembly validation, and policy PASS:
  PASS
- all prior installed CLI smoke paths: PASS

These results are local-host evidence. They are not evidence of CI, remote,
hardware, or producer-authenticated verification.

## Evidence boundary

The assembly proves internal consistency and local byte identity at assembly
time. It does not prove who produced an artifact, authenticate a claimed
commit or CI run, sign evidence, execute tests, import Analog Validation Studio,
or access the MSP430 board. Persisted candidate-to-assembly binding remains a
later phase.
