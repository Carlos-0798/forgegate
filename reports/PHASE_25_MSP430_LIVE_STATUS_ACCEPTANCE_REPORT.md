# Phase 25 MSP430 live-status acceptance

Date: 2026-09-05

Product: ForgeGate `0.1.0a1`
Scope: optional, authenticated, input-only Windows MSP430 UART status

## Outcome

ForgeGate now has an optional Devices page that refreshes once per second and
shows three independent signals:

- serial connection: `CONNECTING`, `CONNECTED`, `DISCONNECTED`, or `ERROR`;
- heartbeat: `NOT_OBSERVED`, `NORMAL`, `STALE`, or `INVALID`; and
- device-reported health: `UNKNOWN`, `NORMAL`, `WARNING`, or `FAULT`.

The production Dashboard path was observed against the owner-authorized MSP430
application UART on COM4. It displayed `CONNECTED`, heartbeat `NORMAL`, device
`FAULT`, and fault flags `0015`. Over one ten-second browser interval, sequence
advanced from 58007 to 58017 and the valid-frame counter advanced from 151 to
161. The sequence-gap counter remained zero. One protocol error had already
been rejected before the interval and did not increase during it; its exact
cause was not retained and is not asserted.

## Boundary and independence

The implementation consumes the public `msp430.uart.v1` description at
upstream commit `151fdcfa60661bce1ba04af13c1d3509706f7d4a`. It does not import
the MSP430 project, copy its runtime, or turn live telemetry into evidence.
The application UART is explicitly selected at startup. ForgeGate sets DTR and
RTS inactive before opening it, performs bounded input reads, and exposes no
serial write call, firmware/debug action, FRAM/GPIO change, or external-load
control.

`FAULT 0015` is the firmware's reported state. The page deliberately keeps it
separate from `CONNECTED` and heartbeat `NORMAL`; it is not a ForgeGate software
failure or a release decision.

## Verification performed

- strict ASCII/newline/128-byte TEL framing;
- CRC-16/CCITT-FALSE known vector and frame verification;
- integer, state, fault-field, and PWM range rejection;
- legacy non-TEL line ignore behavior;
- monotonic normal-to-stale transition;
- invalid-frame indication and next-valid-frame recovery;
- forward gaps, discontinuities, frame/error/gap/reconnect counters;
- absent endpoint without attempting to open serial;
- dependency and I/O failure sanitization;
- monitor start/stop lifecycle with a fake that exposes no write method;
- authenticated BFF authorization and explicit live-status evidence boundary;
- strict TypeScript build, hashed static assets, asset inventory, and committed
  twelve-operation Dashboard OpenAPI contract;
- real authenticated browser rendering and one-second counter/sequence refresh;
- real COM4 input-only observation described above.

The repository-wide gate completed with 840 passed and 3 skipped tests, 95.32%
branch-aware coverage across 9,906 statements and 2,708 branches, Ruff and
format checks, strict mypy across 90 source/tool files, dependency consistency,
asset-inventory verification, 33/33 interaction checks, all JSON Schemas, and
both OpenAPI drift checks. The packaging smoke also passed for the standard
wheel without pyserial and the separate `msp430` extra with pyserial 3.5.

The final browser pass navigated from Devices to Overview and back. Polling
resumed and the sequence advanced from 58525 to 58535; the Overview showed
`READ_ONLY_TELEMETRY`, the 1280 px viewport had no horizontal overflow, and no
browser error or warning was recorded. The retained 1264 x 1358 PNG has SHA-256
`7baf6de9d5269f6856e9f6a1c47a454c085abbefa39b2b42667efacb39c81e89`.

## Not established

The physical unplug/replug page transition remains `NOT_RUN` because it
requires a person to disconnect and reconnect the board while the monitor is
running. Deterministic disconnected, stale, invalid, and recovery behavior is
covered, but it is not a substitute for that physical interaction.

This phase does not validate temperatures, voltage, current, power, PWM,
sensors, firmware correctness, producer authenticity, uninterrupted
long-duration stability, release evidence, remote deployment, or production
readiness. The planned MSP430 report collector remains a separate future gate.

The machine-readable observation and non-claims are retained in
[`PHASE_25_MSP430_LIVE_STATUS_EVIDENCE_2026-09-05.json`](PHASE_25_MSP430_LIVE_STATUS_EVIDENCE_2026-09-05.json).
