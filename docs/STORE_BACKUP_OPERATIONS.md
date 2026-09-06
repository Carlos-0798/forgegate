# Candidate store backup and validation

Phase 32 adds two local owner-operated CLI commands, independent of the browser,
AFE and MSP430. No HTTP endpoint, background job, migration or restore is added.
Only current schema **v9** stores are supported. Older stores still require the
previously documented SQLite backup procedure before explicit migration.

## Create a consistent snapshot

```powershell
python -m forgegate candidate backup-store `
  'work/my workspace/forgegate.db' 'work/backups/before-upgrade.db'
```

Create and restrict the destination parent directory beforehand. The destination
must be a **new file**, with no pre-existing `-wal`, `-shm` or `-journal` files.
Missing sources, source directories/symlinks/junctions, wrong schemas and
existing destinations are rejected. No target is overwritten and no source is
initialized, migrated or deleted.

The source is opened with SQLite `mode=ro`. A pinned read transaction and the
SQLite backup API copy a consistent committed snapshot, including required WAL
content, into a private staging directory beside the target. Pending transactions
are not included. The copy is checked before publication, closed and flushed,
then published using an atomic create-if-absent hard link. Filesystems without
hard-link support fail closed; there is no overwrite-prone fallback. This has
been exercised on local Windows, not network shares or cloud-synced folders.

The final file is independent of the source and temporary staging link. SQLite
may create/update source WAL coordination sidecars during read-only access;
"read-only" means no source logical records or schema are written by this command,
not a guarantee that the source directory sees no filesystem activity.

## Validate an offline backup

Keep the creation receipt's `sha256` separately, then run:

```powershell
python -m forgegate candidate verify-backup 'work/backups/before-upgrade.db' `
  --sha256 EXACT_64_CHARACTER_LOWERCASE_SHA256_FROM_RECEIPT
```

Do not point this command at an active database. It rejects SQLite sidecars,
copies the file with bounded streaming and change detection, and checks that
disposable copy. It never opens the input through SQLite or intentionally changes
the input file. Without `--sha256`, structural validation still runs but
`expected_hash_matched` is **false**: no comparison with an earlier receipt occurred.

Successful JSON receipts include the snapshot SHA-256, size, schema and counts
for the 17 current store tables. No database path, record content, identity,
credential or arbitrary SQLite error text is printed by these commands.
Receipts are operational observations, not signed assurance documents.

Checks cover SQLite integrity, foreign keys, current ForgeGate schema metadata
and required object names. They do **not** replay every domain-history invariant,
prove the trigger SQL has not been replaced by an administrator, authenticate
the data producer, or establish that the source was correct. The receipt states
`domain_history_validation=NOT_PERFORMED` and `restore_performed=false`.
Separate round-trip tests exercise retained candidate, evidence and attestation
reads through the existing application; this is not a blanket correctness claim
about every backup's records.

## Limits, failure and recovery

- Maximum snapshot/file size: **1 GiB**. Default cooperative work deadline:
  **30 seconds**, configurable with `--timeout-seconds 0.1..300`. SQLite VM,
  backup progress and streaming checks cooperate; an OS filesystem call can
  outlast the deadline. This is not a hard real-time guarantee.
- Success exits `0`; operational failures exit `3` with fixed `BACKUP_*` codes;
  invalid CLI syntax/ranges exit `2`. Refusal leaves any pre-existing target
  untouched. A competing target creation is never replaced.
- Pre-publication failures remove this invocation's staging directory. If cleanup
  fails after publication, the command can return an error while a complete
  destination already exists. Inspect and verify it; never retry by overwriting.
  Abrupt process/power loss can leave staging files, and directory-entry power-loss
  durability is not claimed. There is no automatic cleanup of unknown directories.
- Source/destination paths must be in owner-controlled local directories.
  Path/stat checks do not defend against an administrator or hostile local user
  racing path replacement. Do not verify a file another process is writing.
- Backups contain private project data, audit metadata and possibly sensitive
  values embedded in records. They are **not encrypted or redacted**. Do not
  commit, upload or place them in the screenshot/evidence gallery. Protect them
  and the receipts with the owner's folder ACL and retention policy.
- This snapshots only the candidate store. It does not include raw artifacts,
  the separate plugin-run store, trust-store files, signing keys, in-memory
  sessions or UART telemetry. Keep those operational requirements separate.
- A recovery rehearsal should use a separate copied database and verify expected
  project/candidate/evidence/decision history before changing the live launch
  configuration. No automatic restore or replacement command is provided.

## Primary implementation references

The implementation uses [Python 3.12's SQLite backup API](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup)
and follows the [SQLite Online Backup API](https://www.sqlite.org/backup.html)
snapshot model. These references justify the copy mechanism, not ForgeGate's
application-level correctness or hardware claims.
