# Offline recovery readiness

Phase 42 checks one exact workspace snapshot and the original backups required
by its archived jobs. Use this owner-operated CLI check before a recovery rehearsal.
It opens only explicitly supplied local files, verifies disposable copies, and
emits a path-free `forgegate.workspace-recovery-readiness.v1` report.

## Review and check

Retain backup SHA-256 values separately when creating backups. First check the
selected workspace ZIP with its retained hash:

```powershell
python -m forgegate workspace recovery-check work/backups/latest.zip --sha256 LATEST_SHA256
```

With archived tasks, missing mappings produce `INCOMPLETE` and list the exact
original backup hashes needed. Supply each explicitly, quoting the entire
`SHA256=PATH` argument if the path contains spaces:

```powershell
python -m forgegate workspace recovery-check work/backups/latest.zip --sha256 LATEST_SHA256 --dependency "ORIGINAL_SHA256=work/backups/original.zip"
```

Repeat `--dependency` for each required hash. No directory search, network fetch,
receipt path dereference or recursive archive extraction occurs. Duplicate,
malformed and unrelated mappings are rejected. At most 1,000 dependencies may
be supplied. Existing ZIP/member/SQLite bounds apply to every file; one shared
deadline covers the whole operation (`--timeout-seconds`, 0.1–300, default 30).
Large sets may need a longer explicit timeout; deadline exhaustion is an error.

## Interpret the output

| Result | Meaning | Exit |
|---|---|---|
| `READY` | Root snapshot validates and all archived-job dependencies verify | 0 |
| `INCOMPLETE` + `NOT_SUPPLIED` | A required hash has no explicit file mapping | 2 |
| `INCOMPLETE` + `FAILED` | A supplied dependency failed; inspect its fixed error code | 2 |
| Operational error | Invalid root, invalid mappings or exhausted deadline; no readiness report | 3 |

Each original ZIP must match its SHA-256, pass the existing full workspace
verifier, and match the receipt's manifest identity. Every referenced job must
match the original row, retained row, event history, record fingerprint, result
fingerprint, assembly identity and normalized result size. A valid unrelated ZIP
cannot satisfy a receipt. One backup is checked once per distinct hash, including
when several jobs share it. Failure of any job prevents that entire dependency
from being marked verified or counted as partially recovered.

`result_payloads_verified` counts exact original result payloads.
`jobs_without_result` counts valid archived terminal jobs such as cancellations
which never had a result. Such jobs do not acquire invented result bytes.
The check covers every direct receipt in the selected root, including receipts
carried across generations. Dependencies inside older ZIPs are not followed as
additional restore roots: each root job's own original payload is checked directly.

`READY` applies only to the exact root hash and file bytes observed during this
check. Files may subsequently move, disappear or change. It does not restore or
rehydrate data, start services, verify disk space or ACLs, provide encryption,
authenticate producers, or verify external keys/trust stores/raw artifacts.
The standard new-directory-only restore and separately hash-checked
`archived-result` commands remain independent operations.

Dashboard capacity continues to say `dependency_availability=NOT_CHECKED`:
this offline report is not a live browser observation and is not uploaded or
cached as current device/workspace health. No browser file path API is added.

## Reproduce

```powershell
python -m pytest tests/test_recovery_readiness.py tests/test_job_archival.py tests/test_workspace_backups.py
python tools/workspace_backups_smoke.py
python tools/verify.py
python tools/release_smoke.py
```

The smoke creates synthetic data, exercises separate CLI processes, checks
READY/missing/wrong-hash outputs, restores into a new directory and compares
retained tables and normalized test results. See the
[Phase 42 acceptance report](../reports/PHASE_42_RECOVERY_READINESS_ACCEPTANCE.md).
