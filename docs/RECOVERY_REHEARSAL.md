# Reviewed recovery rehearsal

Phase 44 connects a reviewed Recovery-page handoff to an owner-operated CLI
restore and post-copy verification. Only a **new directory** may be created.
It never replaces live databases, changes launch settings or starts a worker.

## Run and inspect

1. Run `workspace recovery-check` with the root ZIP's retained SHA-256 and each
   explicit original-backup mapping. Export a new readiness report.
2. Import that report on the operator-only Dashboard Recovery page, review the
   exact root/dependency identities and download the READY handoff. BLOCKED
   handoffs cannot authorize a rehearsal.
3. Hash the downloaded file, then invoke the CLI with the original ZIPs and a
   destination that does not exist:

```powershell
Get-FileHash work/recovery-handoff.json -Algorithm SHA256
python -m forgegate workspace rehearse-recovery work/backups/latest.zip work/rehearsal-copy work/recovery-handoff.json --handoff-sha256 LOWERCASE_HANDOFF_SHA256 --dependency "ORIGINAL_SHA256=work/backups/original.zip"
```

Repeat `--dependency` for each required original. No mappings are needed when
the reviewed snapshot contains no archived tasks. Paths remain local CLI inputs,
never browser/server file-browsing inputs. Keep hashes independently; a hash
calculated from a substituted file alone does not authenticate its origin.

The CLI checks bounded UTF-8, exact file hash, duplicate/non-finite JSON,
handoff identity and READY status. It then rechecks the root and all explicit
dependencies. The fresh report must match every reviewed field except the old
observation timestamp. Root and original hashes, manifest identity, archived
job identities and result counts cannot change silently. Old timestamps neither
expire nor authorize a restore; the fresh byte checks are mandatory.

Both copied databases are inspected using the existing SQLite, job-history and
referenced-candidate-history verifier. Post-copy details must equal the verified
snapshot; both final database files must retain the exact manifest byte hashes.
Only then is `REHEARSAL.json` published with an exclusive final link. It contains
the reviewed handoff, a fresh readiness observation, source manifest, exact member
hashes, job/event totals, inspection fingerprint and content-addressed receipt ID.
CLI stdout has the same JSON value, though whitespace differs from the marker.
`validate-config` is not the loader for operational recovery documents. The
rehearsal command validates the receipt during creation; a standalone read-only
Dashboard receipt-review surface is the next slice, not delivered here.

Exit 0 means `RESTORED_COPY_VERIFIED`. Exit 3 means rejected/failed: inspect the
fixed error code and **do not use a partial destination**. Before directory
reservation, failures create no destination. After reservation, partial files
remain for manual inspection without a completed marker; retries must use a
different new directory. ForgeGate never recursively deletes or adopts a partial
directory. A leftover `.REHEARSAL.pending` link is harmless if the final marker
exists and validates. File flushes are performed, but power-loss durability and
hostile-local-user filesystem races are not certified.

One 0.1–300 second deadline (default 30) spans input checks, both verified root
reads, dependency checks, copy, readback and pre-publication checks. No time budget
is reset between stages. Existing ZIP/store limits apply; handoff bytes are
bounded to 256 KiB + 4 KiB. The directory's parent must already exist and the
filesystem must support the exclusive hard-link publication primitive.

## Evidence limits and manual acceptance

- Archived results are verified in their explicit external backups, **not copied
  into or rehydrated inside the recovered job store**. Keep those originals.
- Keys, trust stores, raw artifacts and the separate plugin-run store are not
  included or checked. Full candidate-domain replay is not implied.
- A receipt records an observation, not continuing file availability, producer
  authenticity, a signature, backup encryption or production recovery approval.
- No candidate transition, policy evaluation, automatic queued-job execution,
  hardware operation, service switch or new browser restore button occurs.
- For manual acceptance, compare marker member hashes with `Get-FileHash` on
  `candidates.db`/`jobs.db`, inspect the retained task via `jobs show`, and read an
  archived result only through `workspace archived-result` plus its original hash.
  Confirm the marker says `live_workspace_changed=false` and that a second run to
  the same directory is rejected. Do not switch the live Dashboard as part of this
  check. These instructions are an owner workflow, not a claim they all ran.

Reproduce automated/local-process acceptance with:

```powershell
python -m pytest tests/test_recovery_rehearsal.py
python tools/workspace_backups_smoke.py
python tools/verify.py
python tools/release_smoke.py
```

See [Phase 44 acceptance](../reports/PHASE_44_RECOVERY_REHEARSAL_ACCEPTANCE.md).
