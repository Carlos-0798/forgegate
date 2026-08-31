# ForgeGate

ForgeGate is a local-first, evidence-aware release assurance platform under
active development. It is intended to normalize engineering evidence, evaluate
versioned release policies, and generate auditable release decisions.

## Current status

**Phase 1 JUnit evidence slice — still pre-MVP.**

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
- a `collect-junit` CLI preview with deterministic golden-output coverage.

Not implemented yet:

- policy evaluation, persistence, attestations, REST API, plugin execution,
  GitHub integration, or signed provenance;
- coverage, SARIF, benchmark, AFE, or MSP430 collectors;
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

## Product boundary

ForgeGate does not run builds or tests, control devices, perform analog
measurements, or inherit evidence from another repository. Analog Validation
Studio and the MSP430 controller may later export versioned artifacts that an
optional ForgeGate compatibility pack consumes.

## License status

No open-source license has been selected. The current local development copy is
all rights reserved and must not be published or redistributed until the owner
makes an explicit license and release decision.
