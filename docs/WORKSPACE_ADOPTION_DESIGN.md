# Live-workspace adoption and rollback design

Status: **DESIGN ONLY — runtime adoption and rollback NOT IMPLEMENTED**.
Phase 46, 2026-09-07. This is an engineering proposal for owner review, not an
owner-approved switch or a claim that the failure matrix has passed.

Implementation update (Phase 47): the [offline preflight](WORKSPACE_ADOPTION_PREFLIGHT.md)
now scans supported records and compares explicit snapshots/cold copies. Runtime
adoption remains unimplemented. See that contract for exact validation limits,
including missing original request bodies and unauthenticated lineage.

Implementation update (Phase 48): existing-only paired startup, private selected
file-ID binding and public per-start correlation are now available. These do
not implement the private ownership channel, probation or all-writer fence.
The source table below records the Phase 46 baseline; the launcher now also
forwards a job store and offers the explicit existing-pair mode. All live
adoption fault cases below remain NOT RUN as complete adoption scenarios.

## Decision and scope

Use an explicit, local Windows maintenance operation to adopt a verified pair
of candidate/job stores. Keep the old generation intact. Never overwrite either
live database, mix generations, or infer authority from a port, PID, job owner,
hash, Dashboard login, or an earlier rehearsal receipt.

The first implementation must support only an already managed, cooperative
workspace on an owner-controlled local filesystem. An existing unmanaged
Dashboard must be refused, not discovered and killed. Bootstrap into managed
operation is a separate, explicit maintenance action. No service registration,
watchdog, unattended restart, automatic worker, network share, cloud-sync root,
hardware reconnection, migration, GitHub action or publisher-trust claim is added.

This protects release-assurance history and report-job continuity; it does not
turn ForgeGate into a test runner or a general device-management platform.

## Evidence from the current implementation

| Source | Current behavior | Consequence for adoption |
|---|---|---|
| `tools/start_dashboard.ps1` | Foreground launch; advisory bind probe; no job-store argument | Not a managed launcher; paired recovery must currently use the explicit CLI |
| `src/forgegate/cli.py`, `dashboard` | Accepts `--job-store`; initializes candidate application before serving | Future adoption startup needs existing-only validation, not silent creation |
| `src/forgegate/api/app.py`, lifespan and `/healthz` | Initializes application; health returns service/version data | Neither proves selected generation, exact store pair or write readiness |
| `src/forgegate/dashboard/runtime.py` | Checks HTTP and installed HTML; ownership/integrity explicitly unverified | Reachability cannot authorize stop, promotion or rollback |
| `src/forgegate/workspace_backups.py`, `backup_workspace` | Job then candidate write reservations; SQLite snapshots; running leases refused | Reusable snapshot primitive, not a persistent all-writer maintenance fence |
| `src/forgegate/recovery_rehearsal.py`, `rehearse_recovery` | Exact recheck, new directory, cold readback, final receipt | Historical restored-copy evidence, not present process/store availability |
| `src/forgegate/collection_jobs.py` | Cooperative execution lifecycle and private lease | Job execution ownership is not OS process authority or a workspace lease |

The backup validator checks bounded SQLite structure, job/event/result histories
and referenced candidate history. It does **not** fully validate every candidate,
profile, audit, idempotency record or trigger definition. Adoption needs its own
complete supported-domain readback gate; a rehearsal receipt cannot bypass it.

## Required identities and private state

Use three distinct identities: a stable managed workspace ID, a new generation
ID for each adopted store pair, and a per-start runtime instance ID. These are
correlation identifiers, not credentials. Preserve historical candidate/job IDs
inside their generation; do not rewrite history to make copies appear unrelated.

A proposed local plan binds the source generation and coordinated snapshot,
target rehearsal receipt and exact member hashes, schema versions, external
archive dependencies, runtime build/asset identity, trust-store content identity,
requested loopback endpoint, limits, and recovery-point comparison. Derive its
identity from strict bounded canonical content. Exact input bytes are hashed
separately. Paths belong to an explicit private local mapping, not a browser
report. Replaced files, changed configuration or changed source state require a
new comparison and confirmation; a plan is never an execution credential.

A private operation journal lives outside both database generations. It retains
operation/plan IDs, expected previous state, source/target generations, durable
transition intent and result, and failure class. Do not export keys, bearer or
lease tokens, raw reports, command lines or absolute paths. Public review receipts
are bounded and path-free, content-addressed but unsigned local evidence.

## Recovery-point and data-loss review

Before downtime, compare a fresh coordinated source snapshot with the exact cold
target. Compare complete supported domain inventories, not only task counts or
timestamps: profiles/revisions, candidates/transitions, bindings, policy material,
evaluations, attestations, job events/results, archive dependencies and retained
request identities. Report missing, changed and target-only identities with
bounded pagination/totals. Unknown lineage or incomplete validation is BLOCKED,
not zero data loss. Same counts do not prove equivalence.

After fencing and draining, take and verify a final source recovery snapshot.
Recompute the comparison. Any difference from the reviewed plan invalidates its
confirmation. Present the new comparison while remaining in maintenance, or
resume the verified original generation without switching. Choosing an older or
divergent target explicitly accepts the listed history difference; it is not an
automatic merge or lossless upgrade. Queue replay remains manual.

## Process ownership and quiescence

1. A future manager retains the OS process handle from its own launch and uses
   a private per-start capability for a bounded shutdown/identity handshake.
   Record PID and start time only as diagnostics. Never kill by process name,
   stale PID or listening port. Lost authority means BLOCKED/RECOVERY_REQUIRED.
2. Every supported CLI/API/Dashboard write entry point must participate in the
   same workspace-wide maintenance protocol. A write-admission guard spans the
   whole multi-store operation, not just one transaction. Drain admitted calls;
   reject new calls with an explicit maintenance response and no automatic retry.
3. Use a manager-held exclusive OS lock plus a durable maintenance marker and
   monotonic generation fencing. A marker by itself is not a lock. Manager death
   must not clear the marker or reopen writes; the managed child fails closed
   when its control channel is lost. Stale generations cannot resume writing.
4. Running jobs must finish cooperatively or be separately cancelled and reach
   a verified terminal state. Lease expiry alone is not process termination.
   Deadline expiry aborts adoption; do not force a parser or recover a lease as
   an implicit side effect. Acquire job then candidate reservations for the final
   snapshot, matching existing lock order, while maintenance remains in force.
5. Confirm owned-child exit before using its public port for the new child.
   Unknown writers, direct SQLite writers or legacy launchers are unsupported;
   no same-user malicious-process isolation is claimed. Refuse an unmanaged
   workspace instead of claiming that one idle observation proves exclusivity.

The protocol must be implemented and tested across all supported mutation paths
before any switch command exists. Holding two SQLite locks temporarily is not a
replacement for this protocol across shutdown/startup.

## Generation layout, startup and commit boundary

Keep source and target in distinct directories. A single private active-generation
descriptor selects the **pair**. Do not sequentially replace two configured paths.
Generation descriptors and IDs are immutable; an active generation's databases
become mutable only after its write gate opens. Retain verified recovery snapshots
separately; do not hard-link a live database to its rollback copy.

Stage the target by fresh verification of exact rehearsal bytes, dependencies and
full supported-domain readback. Missing/empty stores, sidecar ambiguity, aliases,
hard-link overlap, reparse points, incompatible schema/build or changed inputs
must refuse. Use existing-only opens. Never treat a possibly live WAL database as
immutable or copy only its main file. No implicit migration or initialization.

After the old child exits, launch the owned target with both stores and hardware
disabled, in **probation maintenance mode**. Keep all business writes closed.
Verify process identity through the private control channel, actual generation
and both opened store identities, exact assets, schema/domain checks and current
external trust configuration. Test authorization with a fresh bounded session;
old sessions do not transfer. Hardware-free readiness cannot imply MSP430 health.
This probation mode and identity handshake do not exist in the current server.

Publication uses an expected-old-generation check under the manager lock and a
single same-volume descriptor replacement, with journal intent written first.
The Windows filesystem primitive, flush ordering and crash reconciliation must
pass the matrix before implementation acceptance. An atomic filename operation
alone does not prove a power-loss-safe multi-resource transaction.

Persist a **WRITE_ENABLE_INTENT** before allowing the target to accept business
writes. This is the conservative rollback boundary, even if no write is known
to have arrived. Once this intent exists, never automatically restart the old
generation: an acknowledgement or journal update could have been lost after a
successful target write. Keep both copies and require explicit reconciliation.
Write admission can open only after descriptor publication, matching durable
intent and a live manager control channel. A completed operation receipt follows
the acknowledged transition; losing it must not trigger a second switch.

## State transitions and failure outcomes

Names below are proposed states, **not implemented API/Schema enums**.

| State | Required exit evidence | Failure behavior |
|---|---|---|
| PLANNED | Strict identities and complete comparison reviewed | Refuse without changing source runtime |
| QUIESCING | All admitted writes drained; manager fence held | Do not switch; resume source only with verified ownership and safe fence release |
| SOURCE_SEALED | Final source snapshot verified; comparison still exact | Changed comparison requires new review; no stale confirmation |
| SOURCE_STOPPED | Owned handle confirms exit | Unknown exit means RECOVERY_REQUIRED; no target write admission |
| TARGET_PROBATION | Owned target identity, both stores, assets/auth/domain readback pass | Stop only the owned target; restore source descriptor/start original under fence |
| TARGET_SELECTED | Descriptor durably selects target; writes still closed | Pre-intent rollback allowed only after target exit and journal reconciliation |
| WRITE_ENABLE_INTENT | Durable intent and exact selected generation | No automatic rollback from here, including an ambiguous acknowledgement |
| ACTIVE | Target acknowledges write admission; completion receipt retained | Failure is RECOVERY_REQUIRED, not silent downgrade to the old copy |
| ROLLED_BACK | Owned target exited; original identity/health reverified | Report recovered availability, not successful adoption |
| RECOVERY_REQUIRED | Operator inspects journal, descriptors, handles and both copies | No auto-clear, overwrite, cleanup, lease recovery or hardware start |

Journal/pointer disagreement, a broken journal chain, lost control channel or
unknown process after restart always fail closed. Pre-intent rollback must be
tested; it is not a promise that the original can always be restarted. If original
startup fails, preserve both copies, show outage and require owner intervention.

## Fault-injection acceptance matrix

**All cases below are NOT RUN for adoption.** Existing backup/rehearsal tests are
prerequisite evidence only. Each future run must record exact fixture hashes,
observed state, process identities, exit codes, store readback and preserved files.
Use isolated synthetic copies; none of these cases requires the owner's board.

| ID | Input or injected failure | Required observable result |
|---|---|---|
| A01 | Valid current pair, no concurrent write | One selected generation; owned target ready; fresh login; exact records |
| A02 | Older target; equal totals but changed history | Exact differences shown; no implicit loss acceptance |
| A03 | Source changes after plan or during drain | Confirmation invalidated; target never writable |
| A04 | Target/receipt/dependency bytes replaced after review | Exact recheck rejects before switch |
| A05 | Missing/empty store, wrong version, partial marker | Refuse; no store creation or migration |
| A06 | Same-file/hard-link alias, junction or sidecar ambiguity | Refuse; source bytes and descriptor preserved |
| A07 | Forged same-version HTTP service occupies port | Ownership check fails; unrelated process untouched |
| A08 | Stale/reused PID, lost handle or capability | No stop-by-PID fallback; explicit recovery requirement |
| A09 | API, CLI and Dashboard race maintenance admission | Admitted writes drain; later writes rejected; no partial cross-store operation |
| A10 | Active parser, expired lease, slow write or lock contention | Bounded refusal/drain; no forced kill or implicit lease recovery |
| A11 | Unmanaged source or declared legacy writer in enrollment/preflight | Manager refuses adoption; does not claim that old binaries honor the fence |
| A12 | Manager dies during drain or target probation | Child admission stays closed; durable marker survives for reconciliation |
| A13 | Wrong target store pair, build, asset or generation handshake | Probation fails; target never write-enabled |
| A14 | Trust revoked/changed, auth failure or old browser token | No stale trust acceptance/session transfer; re-review or refuse |
| A15 | Target startup crash or startup timeout before intent | Owned target exit verified; original rollback independently checked |
| A16 | Descriptor/journal write denied, disk full, sharing violation | No success receipt; preserved copies; unambiguous rollback or recovery-required |
| A17 | Crash before/after each journal and descriptor publication | Deterministic restart reconciliation; never two write-enabled generations |
| A18 | Crash after write-enable intent, before/after first write | No automatic old-generation restart, even if receipt absent |
| A19 | Original cannot restart during pre-intent rollback | Outage reported; both generations retained; no false ROLLED_BACK |
| A20 | Duplicate apply, two managers, stale plan replay | At most one admission transition; exact outcome lookup, no second execution |
| A21 | Full domain/audit/request-key corruption outside job references | Adoption refuses even when existing narrow rehearsal validation passes |
| A22 | Queued work and archived payloads after successful adoption | No automatic execution; manual exact result readback matches dependencies |
| A23 | Timeout/cancel at every stage, interrupted final receipt write | Honest state/exit outcome; no destructive cleanup or false success |
| A24 | Hardware configured in historical source runtime | Adoption defaults hardware off; no serial access or automatic reconnect |

The Windows integration tier must use real independent processes and real file
sharing failures, not mocks alone. Crash injection is not physical power-loss
certification. Keep native assistive acceptance separate from this matrix.

## Implementation gates and owner acceptance

1. **Phase 47: read-only adoption preflight.** Strict plan/report models and CLI
   for exact cold target identity, supported-domain validation and comparison of
   explicit coordinated source snapshots. No process control, fence, descriptor
   mutation or live readiness claim. Reject incomplete comparisons. Export schema
   and test valid/stale/corrupt/divergent inputs and no-mutation properties.
2. **Managed lifecycle prerequisite.** Implement existing-only paired startup,
   all-writer admission/fencing, owned control channel and probation identity;
   prove A05-A14 with isolated Windows processes before adding apply.
3. **Explicit adoption and rollback.** Add reviewed downtime/recovery-point
   confirmation, journal/descriptor protocol and A01-A24 evidence. Owner acceptance
   of exact paths, generation, downtime and data differences precedes any real
   workspace switch. A browser import alone never supplies this authority.

For Phase 46, acceptance is traceable design coverage and a fresh existing-suite
regression run, not runtime adoption acceptance. Screenshots are deferred until
there is a new user-visible implementation; retain earlier screenshots with their
original phase and fixture labels. GitHub synchronization remains paused.

## Primary references

- SQLite documents that WAL commits may reside outside the main database file
  and that separate databases are not one atomic transaction:
  [WAL](https://sqlite.org/wal.html). This motivates pair-level fencing and avoiding
  main-file-only live copies; it does not prove the proposed manager correct.
- Use the consistent-copy primitive described by SQLite's
  [Online Backup API](https://sqlite.org/backup.html), retaining the existing
  cross-store reservations; a single database backup is not a workspace commit.
- Windows distinguishes process handles from identifiers and their lifetimes:
  [Process Handles and Identifiers](https://learn.microsoft.com/en-us/windows/win32/procthread/process-handles-and-identifiers).
  The proposed ownership/control protocol is a ForgeGate design decision, not an
  existing guarantee conferred by a PID or an HTTP response.
