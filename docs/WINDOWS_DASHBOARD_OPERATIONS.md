# Windows Dashboard operations

Phase 31 adds a diagnostic command and an explicit foreground launcher. This
is local Alpha operation support, not a Windows service, startup task, watchdog,
database repair tool, or uptime guarantee. Existing authentication is unchanged.

## Build a reviewed local delivery

The clean-source delivery baseline is [Phase 59](../reports/PHASE_59_CODE_CLOSEOUT_ACCEPTANCE.md),
with isolated installation/HTTP verification and exact runtime-byte equality to
the browser-accepted wheel. The latest retained installed-browser regression is
[Phase 58](../reports/PHASE_58_WINDOWS_DELIVERY_ACCEPTANCE.md): Quick Assessment,
Evidence Replay, portable assurance and Evaluation Comparison passed in actual
Edge from an isolated install and copied synthetic store. That historical package
was a dirty-tree artifact; Phase 59 binds its unchanged runtime to a clean commit.
Both are local Alpha acceptance artifacts, not public releases.

For a retained Windows test build, use the no-overwrite delivery builder from a
Python 3.12 development environment:

```powershell
python tools\build_windows_delivery.py C:\private\forgegate-delivery
```

The destination must not exist. The tool creates a source distribution, extracts
it into a fresh temporary tree, builds the wheel from that tree, checks that the
packaged Dashboard files exactly match their inventory, and writes the wheel,
source distribution and `build-receipt.json` into the destination. This prevents
obsolete hashed frontend assets in a long-lived ignored `build/` directory from
leaking into the wheel. Direct `python -m build --wheel` from a reused source
directory is not an accepted delivery procedure.

The receipt records exact artifact hashes and whether Git reported a clean commit
or a working tree with changes. A `WORKING_TREE_WITH_CHANGES` build is suitable
for isolated local acceptance but cannot be reconstructed from `source_commit`
alone and is not a public release candidate. Build again from the accepted clean
commit before publication. The tool does not sign, upload or publish artifacts.

Install and check the retained wheel in a new environment (paths are examples):

```powershell
py -3.12 -m venv C:\private\forgegate-runtime
C:\private\forgegate-runtime\Scripts\python.exe -m pip install `
  C:\private\forgegate-delivery\forgegate-0.1.0a1-py3-none-any.whl
C:\private\forgegate-runtime\Scripts\python.exe -m pip check
```

Continue with `dashboard-check`, fresh browser activation and the project/candidate
review below. Never place private keys, databases, original evidence or downloaded
source-replay archives in a delivery directory intended for review.

### Build workspace constraints

Use a short local checkout path when building an sdist on Windows. Phase 59
observed failure when a nested checkout produced a 262-character staging file
path; the same frozen commit built successfully from a shorter checkout.
Changing only the output directory does not shorten setuptools' source-side
staging paths. This is a known build-environment limitation, not a failed
installed-runtime check.

Run delivery builds and release smoke sequentially in each checkout. Both
construct an sdist and share setuptools staging state; concurrent builds in
the same checkout are unsupported. Independent test and build checkouts are
appropriate when parallel verification is needed.

When rebuilding frontend assets, complete both build and inventory generation
before checking the tree or running acceptance:

```powershell
pnpm run build:dashboard
python tools/dashboard_assets.py --write
python tools/dashboard_assets.py --check
git diff --exit-code -- src/forgegate/dashboard/static
```

Vite clears its output directory during a build; the separate inventory step
restores the exact asset manifest used by ForgeGate verification.

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

### Phase 48: explicit existing-pair startup

For an owner-selected, already initialized candidate v9 and job v3/v4 pair,
use the new opt-in mode (paths are placeholders):

```powershell
python -m forgegate dashboard --existing-pair `
  --database 'work/my workspace/forgegate.db' `
  --job-store 'work/my workspace/jobs.db' `
  --trust-store 'work/my workspace/trust-store.json' --port 8131

# Equivalent source-distribution launcher:
powershell.exe -NoProfile -File tools/start_dashboard.ps1 `
  -Database 'work/my workspace/forgegate.db' `
  -JobStore 'work/my workspace/jobs.db' `
  -TrustStore 'work/my workspace/trust-store.json' -ExistingPair -Port 8131
```

Both paths are required. This mode refuses hardware options, missing/empty/
foreign/incompatible stores, same-file or SQLite-sidecar namespace overlap,
hard links and detected symlink/junction aliases (including existing sidecars).
It validates both before constructing the service and again in its startup
lifespan, without invoking candidate initialization or a migration. Existing-only
candidate operation opens now also use SQLite `mode=rw`, preventing accidental
file creation if an input disappears between the existence check and open.
The original CLI behavior remains unchanged unless `--existing-pair` is supplied.

Validation observes current application/schema IDs, required schema objects and
columns, metadata, SQLite `quick_check` and foreign keys. A five-second progress
deadline and one-second SQLite lock timeout bound normal checks, not stalled OS
filesystem calls. This is **not** complete record/domain readback, exact trigger
SQL validation, pair lineage proof or a simultaneous consistent backup. Phase 47
snapshot/domain preflight remains a separate prerequisite for future adoption.
Committed WAL is read normally, never ignored via SQLite `immutable=1`. SQLite
may create/manage WAL/SHM sidecars: startup is not a cold-copy-preservation tool.
Do not start a rehearsal directory that must remain cold; use a separately
approved operational copy. No sidecar is manually removed or repaired.

After successful lifespan validation the terminal prints `ForgeGate runtime:`
followed by a path-free JSON record. Its random `runtime_id` and `store_pair_id`
are fresh for each start. The latter is an opaque process-lifetime label for the
private binding to the two selected paths and filesystem file IDs; it is **not**
a database-content hash, persistent workspace/generation ID or credential.

Copy both actual IDs into the diagnostic command in another terminal:

```powershell
python -m forgegate dashboard-check --port 8131 `
  --expected-runtime-id '<32 lowercase hex characters from this startup>' `
  --expected-store-pair-id '<32 lowercase hex characters from this startup>'
```

The same `/healthz` response supplies `X-ForgeGate-Runtime-Id` and
`X-ForgeGate-Store-Pair-Id` headers. The endpoint rechecks file identities and
returns 503 without identity headers on detected removal/replacement/aliasing.
The body contract stays unchanged. Matching IDs plus accepted HTTP/HTML yields
exit 0 with `runtime_correlation=MATCH_NOT_AUTHENTICATED`; wrong, old or absent
IDs yield `RUNTIME_IDENTITY_MISMATCH`, exit 3. Partial/invalid expected IDs yield
exit 2 before connecting. Omitting both retains the original reachability probe.

These public identifiers can be copied by a forged service. They do not
authenticate the responder, authorize stopping a process, or prove continued
database integrity. A startup message precedes socket readiness; run the probe
and then complete fresh browser activation. This mode is **normal authenticated
operation, not read-only probation**: existing reviewed writes remain enabled.
File checks are observations with check/open races, not handle-pinned isolation
or an all-writer fence. No service manager, private ownership channel, stop
command, live switch, rollback, automatic execution or migration was added.
Use only on an owner-controlled local filesystem; network/sync/shared-host
operation and hostile same-user races are not supported.

Reproduce the independent-process check with `python tools/dashboard_pair_smoke.py`.
It starts and stops only its own temporary CLI children, verifies restart and
wrong-pair refusal, and uses no hardware or browser automation. See the
[Phase 48 acceptance report](../reports/PHASE_48_EXISTING_PAIR_ACCEPTANCE.md).

### Owner-controlled recovery procedure

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
   Current v9 stores now have explicit [backup and offline validation commands](STORE_BACKUP_OPERATIONS.md).
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
