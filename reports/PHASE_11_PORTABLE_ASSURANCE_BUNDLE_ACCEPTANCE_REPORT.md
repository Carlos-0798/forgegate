# Phase 11 portable assurance bundle acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev18
- Scope: portable retained-decision export, content-addressed publication, and
  database-independent offline verification
- Hardware/device work: none
- Remote/publication work: private repository synchronization only

## Accepted capability

ForgeGate can now project one completed profile-bound release decision into a
self-validating `forgegate.assurance-bundle.v1`. The document combines the
candidate's exact immutable project profile, audited evidence binding, complete
policy material with exact bytes, and release attestation. Cross-document
validation binds project, candidate, commit, release track, profile ID/version,
evidence fingerprint, material ID/hash, evaluation, transition chain, and final
decision before deriving the bundle ID.

`candidate export-assurance` publishes canonical JSON, deterministic Markdown,
and a self-identifying size/SHA-256 manifest beneath a directory named from the
bundle identity. Publication stages and flushes files before an atomic rename;
an exact rerun verifies and reuses existing bytes, while a conflict fails
closed.

`verify-assurance` needs only that three-file directory. It does not open the
originating database, source repository, project configuration, or any path
embedded in evidence metadata. Tests delete the source database before
successful verification.

## Verified controls

- strict profile/evidence/material/evaluation/lifecycle/attestation association;
- exact member allowlist and content-addressed directory-name validation;
- 16 MiB machine-document and 64 KiB auxiliary-document byte limits;
- regular-file and symlink boundaries plus UTF-8, duplicate-key, non-finite
  number, and strict-model checks;
- canonical JSON/Markdown/manifest regeneration with exact size and SHA-256;
- exact publication replay, concurrent exact replay, conflicting bytes,
  missing/extra members, unsafe targets, rename faults, and I/O error handling;
- CLI export, validation, and offline verification through the installed wheel;
- explicit `unsigned_local`, retained-document scope, and
  `source_artifact_bytes=not_embedded` limits.

## Local verification result

- `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict across 51 source files: PASS
- pytest: 602 passed, 1 skipped because this Windows host could not create the
  symlink test fixture
- branch-aware coverage: 98.30% across 5,376 statements and 1,450 branches
- Phase 11 assurance model coverage: 100%
- Phase 11 portable publication/verifier coverage: 95%
- 22 canonical versioned document Schemas plus two artifact Schemas: PASS
- committed OpenAPI drift check: PASS
- source distribution, wheel, clean installation, and installed CLI smoke:
  PASS, including exact assurance export replay and offline verification

These are software/local-host results. No source collector was re-run during
offline verification, and no physical device, AFE runtime, MSP430 board,
authenticated producer, trusted timestamp, signature, TLS, authorization,
public deployment, or production workload was tested.

## Residual and human-intervention boundary

The portable bundle retains evidence documents and their recorded source
artifact references/hashes, but does not copy the underlying JUnit, coverage,
SARIF, benchmark, AFE, or future MSP430 artifact bytes. Verification therefore
proves retained document consistency, exact embedded policy bytes, and local
content association—not source-artifact availability, fresh collector replay,
producer identity, or hardware evidence.

No user action, credential change, serial port, AFE runtime, or hardware access
was required. Authenticated identity must precede any non-loopback operation.
No License, GitHub Release, visibility change, public publication, or LinkedIn
action is authorized by this acceptance.
