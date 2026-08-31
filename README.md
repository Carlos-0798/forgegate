# ForgeGate

ForgeGate is a local-first, evidence-aware release assurance platform under
active development. It is intended to normalize engineering evidence, evaluate
versioned release policies, and generate auditable release decisions.

## Current status

**Phase 3 Analog Validation Studio compatibility slice implemented; not production-ready.**

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
- a local SQLite v2 candidate store with WAL, FULL synchronous durability,
  foreign keys, exact application/schema identity, and explicit transactions;
- canonical append-only candidate snapshots and transition events with an
  optimistic current-revision pointer and immutable idempotency responses;
- exact retry replay, conflicting-key rejection, stale-write protection,
  restart recovery, bounded writer contention, and audit-chain validation;
- persisted `candidate create`, `advance`, `show`, and `history` CLI paths;
- explicit validated v1-to-v2 migration and legacy evaluation backfill;
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

Not implemented yet:

- REST API, plugin execution, GitHub integration, database authorization,
  backup/repair, or signed provenance/key management;
- MSP430 compatibility collector;
- any AFE/MSP430 runtime integration or hardware operation;
- any production deployment or public release.

## Local development

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

.\.venv\Scripts\python.exe -m forgegate candidate history `
  work/forgegate.db cand-dab25eb0be1a0107b3996080
```

Every persisted write requires a caller-owned idempotency key. Exact retries
return the original response; reuse for different normalized input and stale
revisions fail closed. The database establishes local transaction ordering, not
producer authenticity or operator authorization.

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

For a schema-v1 database created by 0.1.0.dev7, migration is explicit:

```powershell
.\.venv\Scripts\python.exe -m forgegate candidate migrate-store work/forgegate.db
```

If that database already contains a terminal candidate, it references but does
not contain its original policy evaluation. Import the exact original document
with `candidate import-evaluation` before attesting. ForgeGate verifies the
evaluation ID, commit, decision, and timestamp; it does not reconstruct or
invent missing evidence.

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

## Product boundary

ForgeGate does not run builds or tests, control devices, or perform analog
measurements. The Studio integration consumes only its frozen public JSON
artifact; it neither imports Studio code nor converts current `BENCH_*` labels
into physical verification. The MSP430 controller may later expose a separate
versioned artifact for another optional collector.

## License status

No open-source license has been selected. The current local development copy is
all rights reserved and must not be published or redistributed until the owner
makes an explicit license and release decision.
