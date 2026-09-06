# Windows Dashboard operations

Phase 31 adds a diagnostic command and an explicit foreground launcher. This
is local Alpha operation support, not a Windows service, startup task, watchdog,
database repair tool, or uptime guarantee. Existing authentication is unchanged.

## Check before starting or restarting

From the repository's activated Python 3.12 environment:

```powershell
python -m forgegate dashboard-check --port 8131
```

The command makes at most two unauthenticated GETs: `/healthz` and `/app/`.
It does not create a session, open a database, access serial ports, follow
redirects, use environment HTTP proxies, or send keys/cookies/tokens. Each
body is capped at 64 KiB plus one rejection byte. The default socket-operation
timeout is three seconds (`--timeout-seconds 0.1..10`); it is **not** a total
wall-clock deadline against a peer that continuously trickles bytes. Ctrl+C
can cancel a probe. Only loopback hosts are accepted.

| Result | Meaning and next step |
|---|---|
| `DASHBOARD_REACHABLE` | Health matches the installed schema and HTML bytes match this installation. Open the page and activate through the CLI. |
| `CONNECTION_REFUSED` | The endpoint refused a connection at that instant. Start the intended service and check again. |
| `CONNECTION_TIMEOUT` | An operation timed out; this does not prove the process stopped. Inspect responsiveness/networking. |
| `HEALTH_HTTP_ERROR` | An HTTP listener responded with a non-200 status, including redirects. Inspect its identity and logs. |
| `HEALTH_INVALID` | Invalid, oversized, wrong-type or incompatible health response. Check port and server version. |
| `DASHBOARD_HTTP_ERROR` | Health passed but the HTML endpoint did not. An API-only server is one possible cause. |
| `DASHBOARD_HTML_MISMATCH` | Wrong media type or different HTML. Compare installed/server versions and assets. |
| `PROBE_FAILED` | Transport/protocol/local asset read failure; raw response and exception details are not exported. |

Exit codes: **0** = reachable HTTP/HTML, **3** = diagnostic not ready,
**2** = invalid arguments. JSON explicitly says that instance ownership,
database integrity, browser interaction and hardware were **not verified**.
Even an identical health/HTML response cannot prove which process, database or
trust store is behind the port. JS/CSS execution and authenticated actions
need separate browser acceptance. `ready` must not be used as release evidence.

## Start an existing workspace

Use your own existing database and public trust-store file; paths below are
placeholders. The launcher does not create credentials or an empty replacement
database; missing and empty database files are rejected. Relative input paths
resolve against the caller's current directory.

```powershell
powershell.exe -NoProfile -File tools/start_dashboard.ps1 `
  -Database 'work/my workspace/forgegate.db' `
  -TrustStore 'work/my workspace/trust-store.json' `
  -Port 8131
```

The default interpreter is the repository `.venv/Scripts/python.exe`, resolved
relative to the script. Override with `-Python` and a trusted interpreter's
file path when needed. The script is included in the source distribution;
the diagnostic CLI is also installed by the wheel. No execution-policy setting
is modified; if scripts are blocked, use the equivalent CLI in your trusted
environment instead of weakening machine policy automatically:

```powershell
python -m forgegate dashboard --database 'work/my workspace/forgegate.db' `
  --trust-store 'work/my workspace/trust-store.json' --host 127.0.0.1 --port 8131
```

Unlike the script, the underlying CLI can initialize a missing database. Check
the exact existing file before using that fallback. The script's existence
and exclusive-port probes are advisory and subject to local races; they are
not protection against a hostile local user deleting/changing files or taking
the port between checks. Actual server startup remains authoritative.

Keep the launch terminal open. **Ctrl+C stops that foreground service**;
closing the terminal, logging out or rebooting can stop it. A startup message
is not readiness confirmation: run `dashboard-check` from a second terminal.
The launcher does not silently reuse another listener, change ports, kill
processes, retry, register auto-start, or bypass the server's schema checks.
The child process's exit code is retained; interrupt exit codes may be nonzero.

MSP430 remains off by default. Only after explicit owner approval, add
`-Msp430Port COM4` (replace with the verified port). This retains the existing
input-only monitor. Do not start a second monitor against the same board.
`-SessionTtlSeconds` accepts 60..3600; the default is 900 seconds. Neither flag
is inferred from another running instance.

## Controlled recovery

1. Check the exact URL/port and diagnostic output. If a listener exists,
   inspect it locally (`Get-NetTCPConnection -State Listen -LocalPort 8131`).
   A PID or successful probe alone is not authority to stop it.
2. For an instance you own, retain relevant logs locally and stop its launch
   terminal with Ctrl+C. Verify shutdown before starting a replacement.
3. Before a version/schema change, create and verify a consistent SQLite
   backup using its backup API, or use an approved offline procedure. Do not
   copy only the main file from a live WAL database. Never delete/reinitialize
   an old store to make startup succeed. Follow the explicit migration contract
   in [SQLite candidate store](architecture/SQLITE_CANDIDATE_STORE.md).
4. Start the same approved database/trust store, check HTTP/HTML, then open the
   actual browser. Restart clears in-memory sessions; use a fresh activation
   code and existing CLI-held key. Do not paste private keys into the browser.
5. Verify the expected project, candidate history, and (if enabled) Devices
   state. A visible page alone does not establish data preservation or hardware
   health. Keep raw logs local; they may include paths, IDs and access details.

Reproduce the isolated HTTP smoke without hardware or user data:

```powershell
python tools/dashboard_runtime_smoke.py
```

It starts/stops only its own temporary servers and exercises the installed CLI
against Dashboard, API-only and stopped cases. Use `--output` with a **new**
filename to retain a JSON receipt; existing receipts are never overwritten.
