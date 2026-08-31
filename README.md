# ForgeGate

ForgeGate is a local-first, evidence-aware release assurance platform under
active development. It is intended to normalize engineering evidence, evaluate
versioned release policies, and generate auditable release decisions.

## Current status

**Phase 1 standard collector baseline accepted; still pre-MVP.**

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

Not implemented yet:

- policy evaluation, persistence, attestations, REST API, plugin execution,
  GitHub integration, or signed provenance;
- AFE or MSP430 compatibility collectors;
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
`passed` or `failed` status describes the tests. Neither is a release decision.

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

Coverage percentages are facts. ForgeGate does not decide whether they meet a
release threshold until the future policy engine evaluates them.

SARIF 2.1.0 collection reads scanner identity from the artifact:

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-sarif `
  artifacts/security.sarif --root examples/sample-python-api `
  --commit cccccccccccccccccccccccccccccccccccccccc `
  --collected-at 2026-08-30T23:00:00Z `
  --trust claimed_ci_metadata --verification-level ci_validated
```

A `COMPLETE` result means the artifact was collected successfully. Finding
levels, kinds, suppressions, and a zero-result summary remain evidence for the
future policy engine; the collector does not issue a release decision.

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
`COMPLETE` collection does not assert that performance is acceptable; Phase 2
policy evaluation will make that determination.

## Product boundary

ForgeGate does not run builds or tests, control devices, perform analog
measurements, or inherit evidence from another repository. Analog Validation
Studio and the MSP430 controller may later export versioned artifacts that an
optional ForgeGate compatibility pack consumes.

## License status

No open-source license has been selected. The current local development copy is
all rights reserved and must not be published or redistributed until the owner
makes an explicit license and release decision.
