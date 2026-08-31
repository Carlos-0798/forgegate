# Optional upstream compatibility contract

This document is an integration plan, not accepted ForgeGate evidence.

## Analog Validation Studio — primary software peer

Reference snapshot: Phase 4 Step 2, commit
`95c1432febdce70007daba013cae4cce47cf8556`, reported 2026-08-30.

ForgeGate may later consume a versioned validation report exported by the
Studio. It must not call Studio measurement algorithms, import its Python
package, control serial devices, or reinterpret replay/synthetic results as
physical validation.

Initial mapping proposal:

| Studio label | ForgeGate verification level | Required retained metadata |
|---|---|---|
| `HOST_TEST` | `host_tested` | source commit, environment, report hash |
| `SYNTHETIC` | `simulated` | simulator/config version, seed if applicable |
| `CSV_REPLAY` | `replayed` | source CSV hash and replay configuration |
| future physical bench result | `physically_verified` | instrument/context/calibration references |

The exact Studio export schema must be frozen in the Studio repository first.
ForgeGate's generic local CLI MVP is now accepted; freezing that public Studio
artifact and implementing an optional collector is the next compatibility
stage.

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
