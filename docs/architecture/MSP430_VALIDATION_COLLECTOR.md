# MSP430 validation-report collector

## Purpose and ownership boundary

ForgeGate consumes a completed, versioned MSP430 validation report as an
optional compatibility artifact. The upstream MSP430 project owns firmware,
UART production, hardware operation, validation procedures, and the truth of
the reported observations. ForgeGate owns only fail-closed parsing,
normalization, provenance retention, and later policy evaluation.

The collector never opens a serial port, imports the MSP430 runtime, flashes
firmware, changes FRAM or GPIO, sends a command, or controls an external load.
Live Dashboard telemetry and a validation report are deliberately separate:
live status cannot be bound as release evidence unless an upstream project
first emits the formal artifact.

```text
forgegate.msp430-validation-report.v1 JSON
        |
        v
ArtifactRegistry -- project root + exact bytes + size + SHA-256
        |
        v
Msp430ValidationReportCollector -- strict schema + semantic invariants
        |
        +--> msp430-validation.run
        +--> msp430-validation.check
        +--> msp430-validation.metric
        |
        v
CollectionResult -> reviewed EvidenceBundleAssembly -> candidate binding
```

## Contract

The committed schema is
`schemas/forgegate.msp430-validation-report.v1.schema.json`. A valid report
contains:

- exact producer and subject identities, including a full lowercase 40- or
  64-character commit SHA;
- a bounded run with UTC-aware timestamps, duration, evidence level, and
  outcome;
- unique checks and metrics with finite scalar values;
- explicit board connection, access mode, connection scope, external
  components, instruments, and physical-measurement status;
- exact source-artifact names, media types, SHA-256 digests, and sizes;
- retained corrections that preserve the original outcome and source digest;
- at least one limitation.

The parser rejects invalid UTF-8, NUL bytes, duplicate JSON keys, non-finite
numbers, unknown fields or versions, excess size, node/depth limits, relative
path escape, commit mismatch, duplicate identities, outcome/check
contradictions, and impossible evidence-level/hardware combinations. A rejected
document produces no normalized evidence.

## Evidence-level mapping

| Upstream level | ForgeGate verification level | Required boundary |
|---|---|---|
| `HOST_TEST` | `host_tested` | hardware access is `NOT_PERFORMED` |
| `TARGET_BUILD` | `target_built` | hardware access is `NOT_PERFORMED` |
| `LAUNCHPAD_HIL` | `system_observed` | connected LaunchPad and explicit read-only/observed scope; warning retained |
| `BENCH_MEASURED` | `physically_verified` only with complete instrument provenance | physical measurement, external-bench scope, and every instrument calibration status are explicit |

`BENCH_MEASURED` is capped at `system_observed` with a warning when calibration
provenance is incomplete. No display label or caller option can promote the
level.

## Current migration fixture

`examples/msp430-validation/artifacts/phase6-soak-report.json` is a
privacy-safe migration fixture transcribed from retained Phase 6 evidence for
commit `0850241c1b2aa34704228146600501346ee81745`. It records 7,206 rows over
7,200 seconds, seven PASS checks, nine metrics, three source digests, and one
reviewed correction. It is classified as `LAUNCHPAD_HIL` and therefore maps to
`system_observed`, not `physically_verified`.

The fixture explicitly excludes external sensors, INA219, MOSFET, fan, 5 V
load, calibrated instruments, and physical electrical measurement. It is a
contract and regression fixture, not a new run performed by ForgeGate.

## Read-only CLI preview

```powershell
.\.venv\Scripts\forgegate.exe collect-msp430-validation `
  artifacts\phase6-soak-report.json `
  --root examples\msp430-validation `
  --commit 0850241c1b2aa34704228146600501346ee81745 `
  --collected-at 2026-09-05T18:30:00Z
```

The command returns a `CollectionResult`. It does not create a candidate,
evaluate a policy, publish an artifact, or communicate with hardware.

