# Phase 6 local REST command workflow acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev13
- Scope: local candidate transition, binding, evaluation, and attestation REST
  commands plus shared application-service and transport safety controls
- Hardware/device work: none
- Remote/publication work: none

## Accepted capability

ForgeGate can execute the complete persisted candidate workflow through its
loopback REST API. Candidate transitions use caller-owned idempotency keys and
expected revisions. Evidence binding accepts one complete audited assembly.
Evaluation reads that immutable binding, executes the supplied release-track
policy, and records the resulting terminal state atomically. Attestation
creation persists and exactly replays the deterministic database document.

The workflow does not collect artifacts, resolve caller-supplied paths, publish
files, authenticate users/producers, or expose the service beyond loopback.

## Verified controls

- DRAFT → COLLECTING → READY → EVALUATING → terminal state sequencing;
- exact transition/evaluation replay, conflicting-key rejection, and stale
  `expected_revision` HTTP 409 behavior;
- immutable assembly binding with state, chronology, commit, and fingerprint
  checks;
- evaluation exclusively against the persisted binding's nested bundle;
- release-track/policy-name equality before a terminal commit;
- decision-derived terminal state plus atomic evaluation/transition storage;
- deterministic attestation create/replay and different-time conflict;
- rejection of binding/attestation in invalid candidate states and evaluation
  without a binding;
- no assembly/artifact loader path or attestation output path in HTTP commands;
  nested assembly path metadata is retained but never dereferenced;
- loopback socket and HTTP Host allowlists;
- structured invalid/negative/oversized declared `Content-Length` handling;
- deterministic OpenAPI export with all installed command operation IDs.

## Local verification result

- `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict across package and verification tools: PASS
- local API/application/network focus: 34 passed; 100% across 282 statements
  and 28 branches
- full pytest: 557 passed, 1 skipped because this Windows host could not create
  the symlink test fixture
- full branch-aware coverage: 100% across 4,106 statements and 1,120 branches
- committed JSON Schemas and expanded OpenAPI 3.1: exported and drift-checked
- source-distribution required-path manifest: PASS
- repository-external wheel installation: PASS
- installed OpenAPI byte comparison and command-operation checks: PASS
- installed external-bind rejection: PASS
- all prior installed collection, assembly, candidate, binding, evaluation,
  attestation, and readback smoke paths: PASS

These are local-host software results. They are not remote CI, hardware,
authenticated-producer, TLS, authorization, or public-release evidence.

## Compatibility boundary

The command models remain ForgeGate-owned and domain-neutral. AFE evidence can
continue to enter through its frozen optional artifact collector. The MSP430
collector remains unimplemented until that project exposes and freezes a
separate public report contract in this conversation.

No upstream runtime, test count, serial result, or physical measurement is
reclassified as ForgeGate evidence. The HTTP layer changes transport only; all
evidence trust and verification labels retain their existing meanings.

## Human-intervention and residual-risk boundary

No user operation, credential, remote account, board interaction, or port
forward was required. The service must remain on loopback and must not be
proxied or tunneled. The 4 MiB guard is based on declared `Content-Length`; an
exact streaming limit for unknown-length/chunked requests is deferred and
documented as residual local denial-of-service risk.
