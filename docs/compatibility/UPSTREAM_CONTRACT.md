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

## MSP430 Equipment Health & Safety Controller — later hardware peer

Reference snapshot: commit `151fdcfa60661bce1ba04af13c1d3509706f7d4a`,
reported 2026-08-30. ForgeGate may later consume target-build reports, host test
results, UART soak summaries, HIL checklists, and external bench reports. It
must not open COM ports, flash firmware, mutate FRAM, send commands, control the
fan, or inherit Dashboard observations as stronger evidence.

Initial mapping proposal:

| MSP430 evidence | ForgeGate verification level |
|---|---|
| pytest/host protocol tests | `host_tested` |
| TI compiler/linker report | `target_built` |
| GitHub Actions result with claimed metadata | `ci_validated` |
| LaunchPad UART/soak observation | `system_observed` |
| future sensor/fan bench acceptance | `physically_verified` |

Future progress updates must change this snapshot deliberately; prior evidence
must remain associated with its original commit and artifact hashes.
