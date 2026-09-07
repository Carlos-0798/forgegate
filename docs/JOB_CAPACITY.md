# Job capacity and archive visibility

Phase 41 adds read-only operational visibility for the bounded collection-job
store. It does not create a scheduler, retention daemon, backup probe, archive
write in the browser, or physical database measurement.

## Owner-only store capacity

Use the local CLI on an owner-restricted store:

```powershell
python -m forgegate jobs capacity work/jobs.db
python -m forgegate jobs list work/jobs.db --archive-filter archived
```

`jobs capacity` reports the actual store-wide logical quotas: current and
archived record counts, immediately available slots, pending normalized input
bytes, live normalized result bytes, and the distinct SHA-256 identities of
external backup dependencies. A v3 store reports archiving disabled and zero
immediately available archive slots; the 1,000-receipt quota becomes available
only after the explicit reviewed v4 migration.

The output deliberately reports `dependency_availability=NOT_CHECKED` and
`physical_database_size=NOT_REPORTED`. A dependency hash identifies required
bytes; it does not prove that the corresponding private ZIP still exists, is
readable, or can be recovered. Logical quota release is not secure erasure or
SQLite file compaction.

## Project-scoped Dashboard view

The Jobs page can filter **All**, **Current**, or **Archived** tasks and retains
that filter through pagination and detail navigation. It shows only the selected
authorized project's current/archive counts, pending-input bytes, live-result
bytes, and dependency hashes. The API scans the complete bounded set of at most
100 current and 1,000 archived identities before applying the page limit, so an
archived record that sorts after the first 100 identities is still discoverable.

The browser intentionally does not disclose store-wide remaining slots. Such a
total could reveal activity in projects the operator cannot read. Project usage
and its task page are refreshed reads, not one transaction-wide snapshot; use
explicit refresh when coordinating maintenance.

## Operational interpretation

- Counts are logical row classifications, not a filesystem or WAL size.
- Byte counts cover normalized retained UTF-8 payloads, not original reports.
- Dependency hashes are deduplicated; their presence is a recovery warning, not
  a failed health check because availability is not probed.
- Filtering and counting perform no candidate, policy, archive, backup, device,
  repository, or GitHub write.

## Reproduce

```powershell
python -m pytest tests/test_job_capacity.py
pnpm check:dashboard
pnpm test:dashboard
python tools/verify.py
python tools/release_smoke.py
```

See the [Phase 41 acceptance report](../reports/PHASE_41_JOB_CAPACITY_ACCEPTANCE.md)
for exact local results and explicit boundaries.
