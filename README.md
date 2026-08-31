# ForgeGate

ForgeGate is a local-first, evidence-aware release assurance platform under
active development. It is intended to normalize engineering evidence, evaluate
versioned release policies, and generate auditable release decisions.

[![CI](https://github.com/Carlos-0798/forgegate/actions/workflows/ci.yml/badge.svg)](https://github.com/Carlos-0798/forgegate/actions/workflows/ci.yml)

## Current status

**Phase 7 project registry and audit-query workflow implemented; not production-ready.**

This private-development checkpoint provides a working Python 3.12 CLI and a
loopback-only REST API. Its strongest ForgeGate-owned evidence is local host
testing; it contains no physical-device verification or production-deployment
claim.

## Architecture and workflow

```text
JUnit / coverage / SARIF / benchmark / optional Studio artifact
                              |
                              v
                  bounded evidence collectors
                              |
                              v
             audited, commit-bound evidence assembly
                              |
                              v
 release candidate -> persisted binding -> versioned policy evaluation
                              |
                              v
        immutable transition history + unsigned local attestation
```

The core remains domain-neutral. Analog Validation Studio is consumed only
through a frozen JSON contract, while MSP430 support remains a planned optional
collector rather than a runtime or hardware dependency.

## Verified results

| Gate | Result | Evidence level |
|---|---|---|
| Python tests | 563 passed, 1 skipped because Windows symlink creation was unavailable | Local host test |
| Branch-aware coverage | 100% across 4,385 statements and 1,180 branches | Local host test |
| Static quality gates | Ruff, formatting, and strict mypy passed | Local host test |
| Contracts | JSON Schema and OpenAPI drift checks passed | Local host test |
| Packaging | sdist/wheel build and clean-environment install smoke passed | Local host test |
| GitHub Actions | Windows, Ubuntu, and macOS completed `verify.py` and `release_smoke.py` | PASS — [run 33403322055](https://github.com/Carlos-0798/forgegate/actions/runs/33403322055) |
| Hardware/device behavior | Not exercised by ForgeGate | Out of scope |

## Key design decisions

- Evidence collection, policy evaluation, candidate transitions, and
  attestation are separate operations so a successful collector cannot silently
  become a release decision.
- SHA-256 identities establish byte integrity and association, not producer or
  operator authenticity.
- Candidate writes use caller-owned idempotency keys and optimistic revisions;
  persisted history is append-only.
- The REST API shares its application service with the CLI, accepts no local
  artifact-loader or output-directory path, and is restricted to loopback.
- Upstream AFE or future MSP430 results retain their original evidence level;
  ForgeGate does not relabel software or replay evidence as physical proof.

<details>
<summary>Detailed implemented capabilities</summary>

Implemented and host-verified in this checkpoint:

- strict, versioned project, policy, and evidence-bundle models;
- fail-closed configuration loading with a 1 MiB input limit;
- explicit evidence trust and verification levels;
- guards that prevent a mandatory zero-count rule from passing without evidence;
- CLI commands for environment diagnosis, configuration validation, and schema export;
- generic sample configuration with no AFE or MSP430 dependency;
- documented optional compatibility boundaries for Analog Validation Studio and
  the MSP430 Equipment Health & Safety Controller;
- a root-confined artifact registry that captures exact bytes, size, media type,
  and SHA-256 identity;
- a bounded JUnit collector that emits normalized `test.summary` evidence plus
  explicit warnings or rejections;
- bounded Cobertura/coverage.py XML and LCOV collectors that emit line and
  branch coverage for repository, package, and module scopes;
- a bounded SARIF 2.1.0 collector that emits an explicit summary even when a
  successful scan contains zero results, plus one normalized record per finding;
- a strict ForgeGate-owned `forgegate.benchmark.v1` schema and bounded collector
  for metric value, unit, scope, baseline, and tolerance facts;
- `collect-junit`, `collect-coverage-xml`, `collect-lcov`, `collect-sarif`, and
  `collect-benchmark` CLI previews with deterministic golden-output coverage.
- deterministic evaluation at an explicit timestamp with trust, verification,
  age, presence, filter, aggregation, operator, and conflict semantics;
- a versioned machine-readable policy-evaluation result with stable input
  fingerprints, per-rule explanations, evidence references, and remediation;
- `evaluate-policy` with PASS/FAIL/REVIEW/ERROR exit codes 0/1/2/3 and generic
  committed PASS/FAIL examples;
- immutable release candidates with the exact DRAFT → COLLECTING → READY →
  EVALUATING → PASS/FAIL/REVIEW/ERROR state graph;
- deterministic candidate/transition identities, exact revisions, monotonic
  timestamps, immutable terminal states, and before/after fingerprints;
- mandatory policy-evaluation binding for PASS/FAIL/REVIEW terminal states;
- stateless `candidate create` and `candidate transition` CLI previews with
  committed structural and evaluation-bound Golden outputs;
- a local SQLite v4 candidate/project store with WAL, FULL synchronous durability,
  foreign keys, exact application/schema identity, and explicit transactions;
- canonical append-only candidate snapshots and transition events with an
  optimistic current-revision pointer and immutable idempotency responses;
- exact retry replay, conflicting-key rejection, stale-write protection,
  restart recovery, bounded writer contention, and audit-chain validation;
- persisted `candidate create`, `advance`, `show`, and `history` CLI paths;
- explicit validated v1/v2/v3-to-v4 migration, audit projection, and legacy
  evaluation backfill;
- durable append-only policy evaluations and release attestations;
- self-validating `forgegate.release-attestation.v1` records containing the
  terminal candidate, transition chain, evaluation, and content fingerprints;
- deterministic JSON/Markdown rendering, atomic content-addressed publication,
  exact replay, and conflict rejection;
- persisted `candidate migrate-store`, `import-evaluation`, `attest`, and
  `show-attestation` CLI paths.
- an optional, artifact-only Analog Validation Studio `result-export.v1`
  collector with a committed consumer-side Schema mirror;
- strict TestRun, criteria, metric, point, limitation, and record-lineage
  validation without importing or running the upstream Studio;
- deterministic `analog-validation.run`, `.metric`, and `.criterion` evidence,
  with source-derived verification levels and no collector-owned release
  decision;
- automatic `BENCH_*` capping at `system_observed` because v1 does not require
  instrument identity or calibration provenance;
- `collect-analog-validation` CLI preview, compatibility fixture, Golden
  projection, adversarial tests, Schema drift gate, and installed-wheel smoke.
- strict, bounded collection-result JSON loading with referenced-artifact
  byte revalidation;
- `forgegate.evidence-bundle-assembly.v1` receipts preserving raw result
  hashes, normalized fingerprints, collector versions, artifacts, evidence
  IDs, and warnings;
- `assemble-evidence` with candidate-commit binding, duplicate/conflict gates,
  content-derived identity, and fail-closed warning handling;
- policy evaluation of either a direct evidence bundle or a validated assembly.
- a self-validating `forgegate.candidate-evidence-binding.v1` document covering
  the revision-one `COLLECTING` snapshot and complete audited assembly;
- immutable, idempotent SQLite binding persistence plus `bind-evidence` and
  `show-evidence` CLI paths;
- mandatory binding and chronology gates before a new v3-or-later candidate reaches
  `READY`;
- terminal evaluation enforcement against the bound assembly's nested
  evidence-bundle fingerprint, with non-fabricating v1/v2 migration semantics.
- a shared candidate application-service boundary used by both CLI and HTTP;
- a versioned FastAPI surface for health, idempotent candidate creation, and
  candidate/history/evidence/attestation reads;
- strict request models, structured error envelopes, caller-supplied or
  generated request correlation IDs, and sanitized unexpected failures;
- `serve` with mandatory loopback-only binding plus deterministic
  `export-openapi` and a committed OpenAPI 3.1 drift gate;
- API/CLI candidate-creation parity, durable SQLite readback integration, and
  installed-wheel OpenAPI smoke verification.
- idempotent, expected-revision REST transitions plus immutable audited
  assembly binding;
- REST policy evaluation that reads only the persisted binding, computes the
  decision, and atomically records the matching terminal transition;
- durable REST attestation creation without accepting a filesystem output
  path or publishing files;
- release-track/policy-name matching, loopback Host validation, and a declared
  4 MiB request-length guard;
- complete HTTP create → collect-state → bind → ready → evaluate → attest
  integration with exact replay and conflict tests.
- immutable project-profile registration with exact idempotent replay and
  canonical configuration identity;
- transactional append-only audit events for successful project/candidate
  lifecycle writes, including deterministic v3 history projection on migration;
- stable cursor pages with bounded project/candidate filtering through
  `project register/show`, `audit events`, and loopback REST endpoints.


</details>

## Quick start

```powershell
.\tools\setup_environment.ps1
.\.venv\Scripts\python.exe tools\verify.py
.\.venv\Scripts\python.exe tools\release_smoke.py
```

On Linux/macOS, run `./tools/setup_environment.sh`. The checked direct
dependency constraints keep local and CI quality-gate versions aligned while
the package retains compatible version ranges for downstream users.

See `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, and
`docs/VERIFICATION_MATRIX.md` before making capability claims.

Start the local API against an existing or new local candidate database:

```powershell
.\.venv\Scripts\python.exe -m forgegate serve `
  --database work/forgegate.db `
  --host 127.0.0.1 --port 8000
```

The server accepts only `localhost` or a loopback IP and also rejects a
non-loopback HTTP `Host`. Candidate creation, transition, evidence binding, and
evaluation writes require `Idempotency-Key`; transitions and evaluation also
require `expected_revision`. Attestation creation is content-deterministic and
persists only to SQLite. The API never accepts a path from which to load an
assembly/artifact or an attestation output directory; path metadata already
inside a validated assembly is not dereferenced. OpenAPI is available at
`/openapi.json`, and the
committed copy can be regenerated with:

```powershell
.\.venv\Scripts\python.exe -m forgegate export-openapi `
  schemas/forgegate.openapi.v1.json
```

This API has no authentication or authorization and is not approved for LAN,
internet, shared-host, or production deployment.

Register and read one immutable project profile, then query its local audit
events:

```powershell
.\.venv\Scripts\python.exe -m forgegate project register `
  work/forgegate.db examples/sample-python-api/forgegate.yaml `
  --registered-at 2026-08-31T14:00:00Z `
  --idempotency-key project:sample-api:v1

.\.venv\Scripts\python.exe -m forgegate project show `
  work/forgegate.db sample-api

.\.venv\Scripts\python.exe -m forgegate audit events `
  work/forgegate.db --project sample-api --limit 100
```

Audit sequences are stable cursors within one database lineage. The log covers
successful durable state changes; it is not an authenticated compliance log
and does not automatically ingest rejected requests or collector warnings.

Preview the first collection path without making a release decision:

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-junit artifacts/junit.xml `
  --root examples/sample-python-api `
  --commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa `
  --collected-at 2026-08-30T20:30:00Z `
  --source-tool pytest --source-version 8.4.2 `
  --trust claimed_ci_metadata --verification-level ci_validated
```

The command's `COMPLETE` status means collection completed; the evidence's
`passed` or `failed` status describes the tests. Policy evaluation is a separate
explicit action.

After saving one or more collection command JSON outputs beneath the same
artifact root, assemble them for one candidate:

```powershell
.\.venv\Scripts\python.exe -m forgegate assemble-evidence `
  work/junit.collection.json work/coverage.collection.json `
  --root examples/sample-python-api `
  --commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa `
  --generated-at 2026-08-30T20:31:00Z
```

The original artifacts must still match the references in every collection
result. Any warning rejects by default; `--retain-warnings` explicitly keeps
the warnings in the audited envelope. The resulting JSON can be passed directly
as the evidence argument to `evaluate-policy`.

Evaluate committed PASS and FAIL examples at a caller-supplied timestamp:

```powershell
.\.venv\Scripts\python.exe -m forgegate evaluate-policy `
  examples/sample-python-api/policies/pull-request.yaml `
  examples/sample-python-api/evidence/pass-bundle.json `
  --evaluated-at 2026-08-30T21:00:00Z
```

Exit code `0` means PASS, `1` FAIL, `2` REVIEW, and `3` ERROR. Configuration or
system errors also use `3`. The evaluator does not collect, rebuild, rerun, or
authenticate evidence while deciding.

Create a deterministic local DRAFT candidate and preview one legal structural
transition without persistence:

```powershell
.\.venv\Scripts\python.exe -m forgegate candidate create `
  --project sample-api --version 1.2.0 `
  --commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa `
  --created-at 2026-08-30T12:00:00Z

.\.venv\Scripts\python.exe -m forgegate candidate transition `
  examples/sample-python-api/candidates/draft.json `
  --to COLLECTING --occurred-at 2026-08-30T12:01:00Z
```

PASS/FAIL/REVIEW transitions additionally require `--evaluation` pointing to a
matching `forgegate.policy-evaluation.v1` document.

Initialize a local store, persist the same deterministic candidate, atomically
advance the expected revision, and read its validated audit history:

```powershell
New-Item -ItemType Directory -Force work | Out-Null
.\.venv\Scripts\python.exe -m forgegate candidate init-store work/forgegate.db

.\.venv\Scripts\python.exe -m forgegate candidate create `
  --project sample-api --version 1.2.0 `
  --commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa `
  --created-at 2026-08-30T12:00:00Z `
  --database work/forgegate.db `
  --idempotency-key create:sample-api-1.2.0

.\.venv\Scripts\python.exe -m forgegate candidate advance `
  work/forgegate.db cand-dab25eb0be1a0107b3996080 `
  --to COLLECTING --expected-revision 0 `
  --occurred-at 2026-08-30T12:01:00Z `
  --idempotency-key advance:sample-api-collecting

.\.venv\Scripts\python.exe -m forgegate candidate bind-evidence `
  work/forgegate.db cand-dab25eb0be1a0107b3996080 `
  work/evidence-assembly.json `
  --bound-at 2026-08-30T20:31:00Z `
  --idempotency-key bind-evidence:sample-api-1.2.0

.\.venv\Scripts\python.exe -m forgegate candidate show-evidence `
  work/forgegate.db cand-dab25eb0be1a0107b3996080

.\.venv\Scripts\python.exe -m forgegate candidate history `
  work/forgegate.db cand-dab25eb0be1a0107b3996080
```

Every persisted write requires a caller-owned idempotency key. Exact retries
return the original response; reuse for different normalized input and stale
revisions fail closed. New v3 candidates cannot advance to `READY` before an
immutable binding is present, and the terminal evaluation must be produced from
that assembly's nested bundle. The database establishes local transaction
ordering, not producer authenticity or operator authorization.

After reaching PASS, FAIL, REVIEW, or ERROR, persist and publish a deterministic
attestation bundle:

```powershell
.\.venv\Scripts\python.exe -m forgegate candidate attest `
  work/forgegate.db cand-dab25eb0be1a0107b3996080 `
  --issued-at 2026-08-30T22:00:00Z `
  --output-root work/attestations

.\.venv\Scripts\python.exe -m forgegate candidate show-attestation `
  work/forgegate.db cand-dab25eb0be1a0107b3996080
```

The bundle contains `attestation.json` and `attestation.md` beneath a directory
named from the attestation SHA-256. An exact rerun verifies and reuses those
bytes; ForgeGate does not overwrite a conflicting target. Database persistence
commits before filesystem publication, so an output failure is recovered by
rerunning the same command.

For a schema-v1 or schema-v2 database created by 0.1.0.dev7/dev8, migration is
explicit:

```powershell
.\.venv\Scripts\python.exe -m forgegate candidate migrate-store work/forgegate.db
```

Migration preserves existing candidates with no binding requirement; it does
not fabricate a historical assembly. If a v1 database already contains a
terminal candidate, it references but does not contain its original policy
evaluation. Import the exact original document with `candidate
import-evaluation` before attesting. ForgeGate verifies the evaluation ID,
commit, decision, and timestamp; it does not reconstruct or invent missing
evidence.

Coverage artifacts use the same provenance options:

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-coverage-xml `
  artifacts/coverage.xml --root examples/sample-python-api `
  --commit bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb `
  --collected-at 2026-08-30T22:00:00Z

.\.venv\Scripts\python.exe -m forgegate collect-lcov `
  artifacts/coverage.info --root examples/sample-python-api `
  --commit bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb `
  --collected-at 2026-08-30T22:00:00Z
```

Coverage percentages remain facts until a policy rule explicitly evaluates
them.

SARIF 2.1.0 collection reads scanner identity from the artifact:

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-sarif `
  artifacts/security.sarif --root examples/sample-python-api `
  --commit cccccccccccccccccccccccccccccccccccccccc `
  --collected-at 2026-08-30T23:00:00Z `
  --trust claimed_ci_metadata --verification-level ci_validated
```

A `COMPLETE` result means the artifact was collected successfully. Finding
levels, kinds, suppressions, and a zero-result summary remain evidence; the
collector does not issue a release decision.

Benchmark collection reads tool identity and metrics from the versioned
ForgeGate artifact:

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-benchmark `
  artifacts/benchmark.json --root examples/sample-python-api `
  --commit dddddddddddddddddddddddddddddddddddddddd `
  --collected-at 2026-08-31T00:00:00Z `
  --trust claimed_ci_metadata --verification-level ci_validated
```

Observed values, baselines, and absolute/percent tolerances remain facts. A
`COMPLETE` collection does not assert that performance is acceptable; only an
explicit matching policy rule can make that determination.

Collect an Analog Validation Studio structured result without importing its
runtime or touching a device:

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-analog-validation `
  artifacts/analog-validation-result.json `
  --root examples/sample-python-api `
  --commit 9ac23494b86212928185de9b0eef1c1a82a8c0ea `
  --collected-at 2026-08-31T13:00:00Z
```

`--commit` is the claimed Studio artifact-producing commit. ForgeGate derives
the verification level from `evidence_source`; there is intentionally no
verification-level override. A valid upstream `PASS` remains observed evidence
until a separate ForgeGate policy evaluates it.

## Repository layout

| Path | Purpose |
|---|---|
| `src/forgegate/` | Domain models, collectors, policy engine, persistence, CLI, and REST API |
| `tests/` | Unit, adversarial, integration, Golden, and contract-drift tests |
| `schemas/` | Committed JSON Schema and OpenAPI contracts |
| `examples/` | Generic reproducible project, policies, evidence, and artifacts |
| `docs/` | Architecture, security, compatibility, status, roadmap, and verification records |
| `reports/` | Phase acceptance and environment-audit reports |
| `tools/` | Environment setup, full verification, and clean-install release smoke |

## Known limitations and product boundary

Not implemented yet:

- authenticated or non-loopback API deployment;
- HTTP artifact collection or filesystem publication;
- project profile updates/listing, project-authoritative candidate creation,
  rejected-request audit ingestion, audit export/retention, plugin execution,
  or product-level GitHub integration;
- database authorization, backup/repair, signatures, or trusted producer/CI
  identity;
- MSP430 compatibility collection, AFE/MSP430 runtime integration, or any
  hardware operation;
- production deployment or public release.

ForgeGate does not run builds or tests, control devices, or perform analog
measurements. The Studio integration consumes only its frozen public JSON
artifact; it neither imports Studio code nor converts current `BENCH_*` labels
into physical verification. Assembly only revalidates local artifacts and
joins existing evidence; persisted binding connects that local assembly to the
candidate lifecycle but does not authenticate it. The REST API is a loopback
transport over the same application service and SQLite adapter; it adds no
user, producer, or machine identity. SHA-256 is not producer authentication.
The MSP430 controller may later expose a separate versioned artifact for
another optional collector.

## Roadmap

The next core slice binds new product-surface candidate creation to registered
projects and configured release tracks, then adds bounded project/candidate
discovery. Authenticated identity must still precede any non-loopback
deployment. MSP430 compatibility remains gated on a separately frozen public
result contract. See [docs/ROADMAP.md](docs/ROADMAP.md) for acceptance-level
tasks.

## License status

No open-source license has been selected. The current local development copy is
all rights reserved and must not be published or redistributed until the owner
makes an explicit license and release decision.
