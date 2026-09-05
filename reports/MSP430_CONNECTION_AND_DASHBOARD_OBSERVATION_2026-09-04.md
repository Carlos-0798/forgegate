# MSP430 connection and Dashboard observation — 2026-09-04

- Product surface: ForgeGate Windows Local Alpha and an externally connected TI/MSP board
- Authorization: user-authorized local connection and Dashboard interaction testing
- Connection result: **PASS DURING INITIAL BOUNDED OBSERVATION / DEVICE ABSENT ON FOLLOW-UP / PASS AFTER USER RECONNECTION**
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

The absence remains retained counterevidence and prevents treating the initial
bounded PASS as proof of continuous connection stability.

### User reconnection and extended observation

After the user reconnected the board, Windows again reported COM4, COM5, and
the TI USB composite device as `Present=true`, status `OK`, and problem code
`0`. A second no-write/no-read observation ran from
`2026-09-05T03:55:10Z` through `2026-09-05T03:58:46Z` (216.1 seconds):

- COM4 completed 25 of 25 open/close cycles without an exception;
- 90 samples at two-second intervals found zero COM4 or COM5 absences;
- COM4 remained open for 30 of 30 one-second samples while both interfaces
  remained enumerated; and
- the receive-queue count ranged from 19 to 181 bytes, without reading or
  parsing any byte.

COM4 was configured as 9600 8N1 only to exercise the Windows port handle. No
claim is made that this configuration matches the firmware protocol. DTR and
RTS remained disabled, zero commands and zero payload bytes were sent, no
payload bytes were read, COM5 was not opened, and no firmware action occurred.

This establishes stability only for the measured 216.1-second reconnection
window. It does not erase the earlier disappearance or establish long-duration
USB stability, payload correctness, firmware behavior, or physical measurement.

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
| Reconnection enumeration | User-reconnected board should enumerate cleanly | COM4, COM5, and the TI USB composite device returned `Present=true`, problem code 0, and `OK` | PASS — RECONNECTED |
| Extended connection window | Repeated handle and presence checks should remain error-free | 25/25 COM4 open/close cycles, 90/90 two-second presence samples, and 30/30 sustained-open seconds passed in 216.1 seconds | PASS — BOUNDED HOST CONNECTION |
| Reauthenticated Dashboard | Service and evidence boundary should remain accurate after the device test | Overview showed `Healthy`, `0.1.0a1`, API `v1`, DB schema `v8`, and `Hardware NOT_PERFORMED` | PASS |

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
physical measurements, and release-evidence import. It also records both the
later device absence and the subsequent bounded reconnection pass so neither
observation can be mistaken for uninterrupted long-duration stability.
