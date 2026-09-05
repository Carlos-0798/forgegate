# Optional upstream compatibility contract

This document records accepted compatibility boundaries. It is not itself
ForgeGate evidence.

## Analog Validation Studio — primary software peer

Public result contract: `result-export.v1`, frozen by Analog Validation Studio
Phase 3 commit `9ac23494b86212928185de9b0eef1c1a82a8c0ea` on 2026-08-30. The
read-only compatibility audit was refreshed against Studio planning head
`ef1f3c50834f55566a2022648e271b913aa9399f` on 2026-08-31; the result-export
contract files still resolve to the Phase 3 freeze commit.

ForgeGate now consumes the versioned JSON result export through the optional
`collect-analog-validation` path. It does not call Studio measurement
algorithms, import its Python package, control serial devices, or reinterpret
replay/synthetic results as physical validation. Studio Phase 5 human-readable
reports remain planned and are not assumed by this collector.

Initial mapping proposal:

| Studio label | ForgeGate verification level | Required retained metadata |
|---|---|---|
| `HOST_TEST` | `host_tested` | source commit, environment, report hash |
| `SYNTHETIC` | `simulated` | simulator/config version, seed if applicable |
| `CSV_REPLAY` | `replayed` | source CSV hash and replay configuration |
| `THEORY` | `declared` | model/configuration identity and limitations |
| `SPICE_IDEAL` / `SPICE_MODEL` | `simulated` | model/configuration version and limitations |
| `BENCH_*` in current v1 | `system_observed` plus warning | report hash and retained source metadata |
| future bench schema with mandatory provenance | eligible for later review | instrument/context/calibration references |

The accepted collector retains the exact artifact SHA-256, caller-claimed
producer commit/environment, source software version, evidence source,
limitations, source schemas, TestRun outcome, metrics, and criteria. It emits
no `physically_verified` record because v1 does not require instrument or
calibration provenance.

## MSP430 Equipment Health & Safety Controller — optional artifact peer

Planning reference snapshot: commit `151fdcfa60661bce1ba04af13c1d3509706f7d4a`,
reported 2026-08-30. The implemented optional collector now consumes the frozen
`forgegate.msp430-validation-report.v1` artifact. The retained Phase 6
migration fixture resolves its tested source commit to
`0850241c1b2aa34704228146600501346ee81745`; the planning and evidence snapshots
remain deliberately distinct.

ForgeGate does not open COM ports through this collector, flash firmware,
mutate FRAM, send commands, control the fan, or inherit live Dashboard
observations as stronger evidence. The contract and boundary are documented in
`architecture/MSP430_VALIDATION_COLLECTOR.md`.

Initial mapping proposal:

| MSP430 report evidence level | ForgeGate verification level |
|---|---|
| `HOST_TEST` | `host_tested` |
| `TARGET_BUILD` | `target_built` |
| `LAUNCHPAD_HIL` | `system_observed` plus a retained scope warning |
| `BENCH_MEASURED` with incomplete calibration provenance | `system_observed` plus a retained cap warning |
| `BENCH_MEASURED` with explicit physical context and complete instrument calibration provenance | `physically_verified` |

Every report must carry its own full source commit and source-artifact hashes.
Future progress updates must create a new report rather than rewrite this
snapshot; prior evidence remains associated with its original identities.
