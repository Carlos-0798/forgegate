# MSP430 connection and Dashboard observation — 2026-09-04

- Product surface: ForgeGate Windows Local Alpha and an externally connected TI/MSP board
- Authorization: user-authorized local connection and Dashboard interaction testing
- Connection result: **PASS DURING BOUNDED OBSERVATION / DEVICE ABSENT ON LATER FOLLOW-UP**
- ForgeGate hardware integration: **NOT PERFORMED**
- Firmware, protocol, and physical measurement result: **NOT EVALUATED**

## Outcome

Windows continuously enumerated the board as `MSP Application UART1 (COM4)`
and `MSP Debug Interface (COM5)`, with status `OK` and problem code `0`. The TI
USB composite device (`VID 2047`, `PID 0013`) also remained `OK`.

The application UART completed 10 of 10 open/close cycles and remained open
for a separate 10-second observation without an exception. Its receive queue
changed from 208 to 1,144 bytes during the observation. This establishes that
the local USB/UART connection remained present and that bytes arrived at the
Windows serial queue. It does not establish the baud rate, framing, payload
meaning, source authenticity, telemetry correctness, or firmware behavior.

No serial data was read or parsed, no command was sent, DTR and RTS remained
disabled, and the debug interface was not opened. No firmware, FRAM, GPIO, or
external load was changed.

### Follow-up connection state

At `2026-09-05T03:21:27Z`, after the bounded test and repository merge,
Windows no longer enumerated COM4 or COM5. The retained device entries reported
problem code 45 and `Present=false`, and three .NET port enumerations spaced two
seconds apart returned no ports. An attempted device rescan was rejected by
Windows because the current process was not elevated. The Dashboard remained
healthy throughout.

Consequently, this run does **not** establish long-duration connection
stability. The board was stable for the measured 10-cycle/10-second window and
then became absent. A physical USB/power/cable check and a longer repeated
observation are required before calling the connection stable.

## Dashboard interaction result

The authenticated Chrome session passed the following non-mutating checks:

| Check | Expected | Actual | Result |
|---|---|---|---|
| Overview | Service and authority visible together | Healthy, `0.1.0a1`, API `v1`, DB schema `v8`, operator, `sample-api` | PASS |
| Evidence boundary | Hardware result not inferred from an external port check | `Hardware NOT_PERFORMED` and “No hardware access or physical measurement is performed.” remained visible | PASS |
| Projects | Exact authorized project only | `Sample Python API`, profile v1, `sample-api`, default branch `main` | PASS |
| Candidates | Exact stored state | Three DRAFT records; selected detail showed revision 0, `NOT_EVALUATED`, profile v1, and hardware `NOT_PERFORMED` | PASS |
| Required fields | Empty inputs must not advance | Native required-field validation retained focus on Version | PASS |
| Commit format | Invalid SHA must not advance | `abc` was rejected with the exact 40/64 lowercase hexadecimal rule | PASS |
| Review boundary | Valid draft is reviewed before writing | Exact project/version/SHA/branch/track and the one-write warning rendered | PASS |
| Return to edit | Draft values must survive review round-trip | A defect was found, corrected, rebuilt, and retested; Version and Commit SHA were restored exactly | PASS AFTER FIX |
| Cancel | No durable write and focus restored | Dialog closed, Create candidate regained focus, and the row count remained three | PASS |
| Late device follow-up | Board should still enumerate if the connection remained continuous | COM4/COM5 absent; retained PnP entries showed problem 45 and `Present=false`; Dashboard remained healthy | CONNECTION LOST / USER CHECK REQUIRED |

The updated Dashboard static-resource allowlist required one controlled service
restart after rebuilding. The service returned healthy on the same loopback
origin and a new short-lived CLI-approved session completed successfully. The
Dashboard was left running at `http://127.0.0.1:8131/app/`.

## Evidence interpretation

The board check ran outside ForgeGate. ForgeGate currently has no MSP430 live
collector and did not read, authenticate, import, or evaluate the observed
bytes. Therefore the Dashboard's `Hardware NOT_PERFORMED` value is accurate;
changing it to PASS would be an unsupported claim.

The correct future integration boundary is a versioned MSP project report,
not direct source coupling. That report should identify the device and firmware
under test, protocol version, timestamps, transport stability, measurement or
test outcomes, provenance, and explicit confidence/evidence class. ForgeGate
can then add a strict collector and bind the validated report to a candidate.

## Retained evidence

The machine-readable companion record is
[`MSP430_CONNECTION_OBSERVATION_2026-09-04.json`](MSP430_CONNECTION_OBSERVATION_2026-09-04.json).
It deliberately omits the board's unique serial number and contains explicit
false values for firmware writes, serial writes/reads, protocol validation,
physical measurements, and release-evidence import. It also records the later
device absence so the bounded PASS cannot be mistaken for long-duration
stability.
