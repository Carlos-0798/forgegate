# Phase 3 Analog Validation compatibility acceptance report

- Date: 2026-08-31
- ForgeGate version: 0.1.0.dev9
- Scope: first optional software-peer collector
- Outcome: accepted on local host; not production-ready
- Hardware/serial activity: none

## Accepted boundary

ForgeGate now consumes Analog Validation Studio's frozen public JSON
`result-export.v1` contract. The upstream contract files last changed at Studio
commit `9ac23494b86212928185de9b0eef1c1a82a8c0ea`; the read-only audit was
refreshed while the Studio repository was at planning head
`ef1f3c50834f55566a2022648e271b913aa9399f`.

Audit fingerprints:

| Upstream file | SHA-256 |
|---|---|
| `docs/result-exports.md` | `6dbaec5ad007eb1484163684c67a05c93cc7cf0543583ed2dc7f1804c987c04c` |
| `exports/models.py` | `cb955fd494703b5ec6a705aff7526c3a98952f25885d12457ea82b45ddbbafec` |
| `exports/json_v1.py` | `13f661dadad8a70590cf4189f90564c0aa248a8c8b98ffd6c74011fbae89da55` |
| DC result Golden | `a137b527303a7a8938b4bba7f74d28f35e9a9ca013474cd5946f4d6da9591547` |
| Hysteresis result Golden | `e7534508afea6dcf231387de293408d0a1b247ad3ee4a496b970dba4456f58db` |

The collector imports no Studio module, starts no subprocess, opens no COM
port, and performs no analysis or device operation. It does not assume or
consume the Studio Phase 5 human-readable report, which remains planned
upstream.

## Implemented result

- committed consumer-side
  `schemas/analog-validation.result-export.v1.schema.json` mirror with exact
  drift verification;
- bounded duplicate-safe UTF-8 JSON parsing using the upstream 2,000,000-byte
  limit plus ForgeGate node/depth limits;
- exact root/nested field, enum, timestamp, criterion, disposition, and source
  validation;
- repeated TestRun, point, evidence-record, raw-record, criteria, and outcome
  consistency checks;
- deterministic `analog-validation.run`, `analog-validation.metric`, and
  `analog-validation.criterion` records bound to the artifact SHA-256 and the
  caller's execution context;
- fixed source-derived verification mapping with no CLI override;
- `BENCH_DMM`, `BENCH_CONTROLLER`, and `BENCH_SCOPE` capped at
  `system_observed` with `AFE_BENCH_EVIDENCE_CAPPED` because v1 does not require
  instrument/calibration provenance;
- sample artifact, Golden normalization, CLI test, adversarial contract tests,
  architecture/security documentation, and installed-package smoke path.

## Verification

`python tools/verify.py` passed:

- 486 passed, 1 skipped because this Windows host cannot create the symlink
  fixture;
- 100% branch-aware coverage across 3,393 statements and 964 branches;
- the new collector alone: 59 focused tests and 100% across 431 statements and
  106 branches;
- Ruff, Ruff format, strict mypy, `pip check`, configuration examples, and all
  committed document/artifact Schema drift checks passed.

The collector was also run read-only against both exact upstream Phase 3
Goldens in the Studio repository. DC (`a137...91547`) completed with one run,
nine metrics, and five criteria; hysteresis (`e753...58db`) completed with one
run, ten metrics, and five criteria. Both retained `SYNTHETIC` as `simulated`
and their explicit no-hardware limitations.

`python tools/release_smoke.py` also passed:

- isolated sdist and wheel builds completed and the expanded manifest contained
  the collector, contract mirror, example, Golden, tests, documentation, and
  this report;
- a clean repository-external virtual environment installed the wheel and ran
  `collect-analog-validation` successfully against the committed sample;
- all existing policy, candidate-store, attestation, JUnit, coverage,
  Benchmark, and SARIF installed CLI paths still passed.

## Evidence and claim boundary

- A collector `COMPLETE` means valid normalization, not an upstream or release
  PASS.
- Upstream PASS/FAIL and criterion decisions are retained without recomputing
  them; ForgeGate policy evaluation remains separate.
- Artifact SHA-256 proves byte identity, not the caller-claimed producer commit
  or producer authentication.
- No physical AFE validation claim was imported or created.
- The previously reported AFE-side `BENCH_CONTROLLER` observation remains
  limited to MSP430 UART compatibility; this work did not repeat or broaden it.
- No MSP430 board, sensor, fan, external supply, firmware, or serial port was
  accessed.

## Next compatibility gate

Keep this collector frozen unless the upstream public result contract changes.
The next project step may either define a generic evidence-bundle assembly
workflow around collected records or begin the MSP430 report-contract audit
after the user supplies a new hardware-project progress alignment. It must not
infer an MSP430 hardware result from the current Studio or ForgeGate evidence.
