# Reusable monitor presets

Monitor presets reuse a reviewed local configuration so an authenticated operator
can select **Start monitoring** or **Stop monitoring** in **Live devices**. They
do not replace the release-assurance workflow, authorize device commands, or turn
live status into release evidence.

## First setup

Use the installed Python environment from the [workspace quickstart](LOCAL_WORKSPACE_QUICKSTART.md).
For a workspace with project ID `sample-project`:

```powershell
.\.venv\Scripts\python.exe -m forgegate monitor-preset-init ./my-workspace/monitor-presets.json --project sample-project
.\.venv\Scripts\python.exe -m forgegate dashboard --database ./my-workspace/forgegate.db --trust-store ./my-workspace/trust-store.json --job-store ./my-workspace/jobs.db --existing-pair --monitor-presets ./my-workspace/monitor-presets.json --port 8000
```

Use the paths printed by `workspace-init` if they differ. Activate the browser
with its short-lived code and the workspace operator identity, as documented in
the quickstart. Open **Live devices**, choose the simulated preset, and start it.
The same saved configuration can be reused on later starts; there is no automatic
Windows startup or unattended authentication. Keep the service terminal running.

The simulation repeats six five-second stages: healthy, stale, invalid,
disconnected, firmware fault, recovered. It is explicitly marked **SIMULATED**,
uses no serial device, and is a UI/adapter demonstration, not a hardware test.

## MSP430 read-only monitoring

Install the optional `msp430` dependency in the same environment. Select the real
board's telemetry COM port in Windows Device Manager; it is not necessarily the
debug interface. Replace `COM4` below with that port:

```powershell
.\.venv\Scripts\python.exe -m forgegate monitor-preset-init ./my-workspace/board-presets.json --project sample-project --msp430-port COM4
.\.venv\Scripts\python.exe -m forgegate dashboard --database ./my-workspace/forgegate.db --trust-store ./my-workspace/trust-store.json --job-store ./my-workspace/jobs.db --monitor-presets ./my-workspace/board-presets.json --port 8000
```

This catalog contains both the simulation and the MSP430 preset. Do **not** add
`--existing-pair`: that mode expressly forbids hardware configuration. The normal
mode uses existing current-schema stores, or initializes absent stores; it does
not automatically migrate an old job database. Check the workspace paths first.

Select **MSP430 UART v1 (read-only)** and start. `RUNNING` means the monitoring
task is active, **not** that a device is connected or healthy. Read the separate
connection, heartbeat and device-health results. Stop monitoring before using
another serial application. Stop does not stop the Dashboard server.

Only firmware that emits the supported `msp430.uart.v1` TEL framing, checksum,
fields and 115200-baud stream is supported; a board name or UART connection alone
does not establish compatibility. This feature never transmits commands or
flashes firmware. Opening a port can still have driver/device-specific effects;
DTR/RTS are kept disabled by the MSP430 adapter.

## Configuration and lifecycle boundaries

- `forgegate.monitor-presets.v1` is a bounded JSON catalog: one project, 1–20
  unique presets, two allowlisted adapters, and no credentials, executable code,
  arbitrary driver imports or browser-selected paths.
- Setup refuses to overwrite an existing file. Configuration is loaded once at
  service startup; editing the file requires restarting the service. Loading,
  viewing or restarting never starts monitoring.
- Start/stop require an operator session, exact local Origin, CSRF token and
  authorization for the catalog's project. Other project scopes cannot read its
  monitored source. Short-lived browser authentication remains unchanged.
- One monitor runs per Dashboard process. Stale start revisions and stale stop
  run IDs are rejected. A stop timeout does not free the worker for reuse.
  Different Dashboard processes are not centrally coordinated; do not configure
  multiple servers to use the same physical port.
- Legacy `--msp430-port` remains supported with its original automatic-start
  behavior, but cannot be combined with `--monitor-presets`.
- Live monitoring has no durable measurement export, release gate, calibration
  claim or automatic hardware compatibility detection. Session state is local
  to this process; it is not a persistent compliance audit trail.

## Extension criteria

Add another adapter only against a specified protocol and sample stream, with
normal/stale/invalid/disconnect/recovery controls and clear data-origin labels.
Reuse the monitor lifecycle and the release-evidence boundary. A simulator can
test parsing and UI integration; a second physical board still needs its own
driver, protocol, reconnection and sustained-operation acceptance.

Repeat use removes port/configuration re-entry from the browser monitoring task.
No percentage time saving or human accuracy improvement has been measured.
