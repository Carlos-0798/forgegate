# ForgeGate

**Evidence in. Auditable release decision out.**

ForgeGate is a local-first Python release-assurance platform that normalizes
engineering evidence, evaluates versioned policies, and produces deterministic,
reviewable release decisions.

The intended benefit is less manual work reconciling reports and handing off a
version for review. **Human efficiency and accuracy improvement are not yet
measured.** Formal [Phase 53B](docs/product/EFFICIENCY_ACCEPTANCE.md) comparison is
deferred by the owner. [Quick assessment](docs/QUICK_ASSESSMENT.md) automates batch
identification and the reviewed evidence-to-decision sequence.
[Evaluation comparison](docs/DECISION_COMPARISON.md) highlights rule changes and
missing evidence across explicitly selected candidates, and blocks like-for-like
conclusions when their policy/profile authority differs.

[![CI](https://github.com/Carlos-0798/forgegate/actions/workflows/ci.yml/badge.svg)](https://github.com/Carlos-0798/forgegate/actions/workflows/ci.yml)

## Current status

**Independent first use and task workbench.** The owner reopened the Alpha
scope after Phase 61 to improve runtime correctness, interactions and delivery.
Start with the [local workspace quickstart](docs/LOCAL_WORKSPACE_QUICKSTART.md):
the installed package prepares its own private identity, stores and optional
synthetic PASS/FAIL examples, without a development checkout.

```powershell
python -m forgegate workspace-init ./my-workspace --demo
```

Overview now prioritizes starting an assessment and reviewing candidate outcomes.
Candidate search and state filters apply to the explicitly loaded page, not an
unstated global total. The default test policy requires successful executed tests;
JUnit aggregation retains failures from mixed detailed and summary-only suites.
The [current acceptance record](reports/PHASE_62_WORKBENCH_ACCEPTANCE.md) includes
1,466 Python passes, 264 frontend passes, fresh-install browser PASS/FAIL handoff
and unchanged retained AVS results.

![ForgeGate release workbench with synthetic PASS and FAIL examples](docs/assets/phase62/workbench.jpg)

**Windows Alpha completion accepted 2026-09-09.** Code closeout,
frozen-package real-project acceptance and the reproducible final demonstration
are complete.
See the historical [finite completion gates](docs/ALPHA_COMPLETION_PLAN.md).
The [Phase 59 closeout record](reports/PHASE_59_CODE_CLOSEOUT_ACCEPTANCE.md)
binds the local delivery to its exact clean source commit and records limitations.
The [Phase 60 acceptance](reports/PHASE_60_REAL_PROJECT_ACCEPTANCE.md) uses that
exact installed wheel to reproduce the retained AVS `VALID / FAIL` decision and
the MSP430 artifact-only `COMPLETE` result without new upstream or hardware work.
The [Phase 61 final demo](reports/PHASE_61_FINAL_DEMO_ACCEPTANCE.md) adds a
fresh-recipient PASS/FAIL run, actual authenticated browser walkthrough and a
manifest-verified non-secret reviewer package.

> **Testable Windows Alpha `0.1.0a1`** — the end-to-end local CLI assurance
> workflow, reviewed local Dashboard actions, optional read-only MSP430 live
> status, artifact-only MSP430 report collection, candidate-bound assurance
> download, and brokered Windows plugin path are implemented. The product is
> not production-ready.

The current checkpoint demonstrates:

- [final Windows demonstration](reports/PHASE_61_FINAL_DEMO_ACCEPTANCE.md):
  exact frozen wheel installation, generic positive/negative exits, actual
  authenticated Dashboard review, reusable screenshots and explicit limits;
- [refreshed Windows installed-wheel acceptance](reports/PHASE_58_WINDOWS_DELIVERY_ACCEPTANCE.md):
  isolated Python 3.12 install, synthetic four-report quick assessment, private
  replay and assurance verification, and comparable/incompatible evaluation
  controls all pass in actual Edge; the dirty working-tree build is not a public
  release candidate;
- [real AVS quick assessment](reports/PHASE_56_AVS_QUICK_ACCEPTANCE.md):
  distinct report metadata, reviewed warning retention and bounded larger XML;
  actual Edge handoff independently reproduces all 12 historical rule results
  and VALID / FAIL with 130 records, without rerunning upstream tests;
- [repeat-use quick handoff](reports/PHASE_55_QUICK_HANDOFF_ACCEPTANCE.md):
  explicitly choose a compatible saved policy and save the original report/receipt
  replay ZIP from the completed assessment, without selecting the files again;
  actual Edge download independently replays four collections to VALID / PASS;
- [quick assessment](reports/PHASE_54_QUICK_ASSESSMENT_ACCEPTANCE.md):
  content-detected report batches and one reviewed evidence-to-attestation
  sequence; real Edge PASS/FAIL/REVIEW, directory import, invalid-report safe
  stop and independently verified PASS download. Human gains remain unmeasured;
- [reviewed Windows installed-wheel delivery](reports/PHASE_52_WINDOWS_DELIVERY_ACCEPTANCE.md):
  a fresh-sdist build prevents stale Dashboard assets, installs in an isolated
  Python 3.12 environment, starts the real loopback UI, preserves the AVS
  candidate and independently verifies its downloaded VALID/FAIL assurance ZIP;
- [private original-report export and offline replay](docs/EVIDENCE_REPLAY.md):
  exact collection inputs, parser results and retained policy are checked in a
  bounded, database-independent ZIP; actual Edge download reproduces the AVS
  FAIL decision without rerunning upstream tests or authenticating their origin;
- [real AVS host-report integration](reports/PHASE_50_AVS_HOST_ACCEPTANCE.md):
  four collector receipts and 130 records through reviewed Dashboard binding,
  policy evaluation and independently verified assurance download; the frozen
  producer baseline correctly remains FAIL (one test failure, 15 untriaged
  static review candidates), not a hardware or producer-authentication claim;
- fail-closed collection of JUnit, coverage, SARIF, benchmark, and optional
  Analog Validation Studio artifacts;
- bounded operator-only JUnit and standard CI browser collection (JUnit +
  Cobertura/LCOV, optional SARIF and benchmark JSON), with exact-byte hashing,
  reviewed durable tasks, explicit warning retention and separately
  confirmed immutable binding; [collection boundaries](docs/DASHBOARD_COLLECTION_CONTRACT.md);
- loopback HTTP/HTML diagnostics and an explicit Windows foreground launcher
  with [startup and recovery guidance](docs/WINDOWS_DASHBOARD_OPERATIONS.md);
- opt-in existing-only candidate/job paired startup, with no silent initialization
  or migration and fresh public runtime correlation; not a managed owner channel,
  probation mode, writer fence or live workspace switch;
- consistent candidate-store snapshots and offline backup validation with
  [no-overwrite and private-data boundaries](docs/STORE_BACKUP_OPERATIONS.md);
- [coordinated candidate/job backup and recovery](docs/WORKSPACE_RECOVERY.md),
  including exact historical association checks, restore to a new directory,
  and non-destructive retention plans;
- [reviewed terminal-job archival](docs/JOB_ARCHIVAL.md) backed by exact verified
  snapshots, preserving history and duplicate-request protection while freeing
  logical job/result quota; Dashboard details disclose external-backup dependencies;
- [read-only job capacity and archive visibility](docs/JOB_CAPACITY.md), with
  store-wide owner CLI quotas and project-scoped Dashboard filters/usage that do
  not disclose other-project counts or claim external-backup availability;
- [offline recovery readiness](docs/RECOVERY_READINESS.md) checks explicitly
  supplied original backups against snapshot receipts and exact archived-job
  payloads, reporting missing or failed dependencies before recovery rehearsal;
  an operator-only [recovery handoff](docs/DASHBOARD_RECOVERY_HANDOFF.md) page
  validates an exact path-free report, separates READY from BLOCKED, and exports
  a content-addressed review artifact without uploading backup payloads;
- [reviewed recovery rehearsal](docs/RECOVERY_REHEARSAL.md) rechecks that handoff
  against exact original backups, restores only into a new directory, verifies
  copied database bytes/history and retains a final receipt without switching
  live stores or rehydrating archived result payloads;
- the operator-only [rehearsal receipt review](docs/DASHBOARD_RECOVERY_REHEARSAL_REVIEW.md)
  validates and displays that exact completion receipt without accepting a path,
  running recovery, rehydrating results or switching the live workspace;
- [read-only adoption preflight](docs/WORKSPACE_ADOPTION_PREFLIGHT.md) compares
  exact source snapshots and cold rehearsal copies across all supported tables,
  with current domain readback, archive dependencies and bounded difference pages;
  MATCH does not prove live freshness or authorize a workspace switch;
- [durable local report jobs](docs/COLLECTION_JOBS.md) with idempotent submission,
  explicit execution/cancellation, expired-lease recovery and bounded pending
  input retention; v2 records expose non-credential execution ownership and
  bounded lease-renewal history, while cancellation is checked between parser
  stages; CLI and explicitly reviewed browser submission/execution;
- [opt-in Dashboard job management](docs/DASHBOARD_JOBS.md): project-scoped
  list/detail/results, reviewed submission/parsing, cancellation and expired-lease
  recovery with retained operator attribution, plus exact assembly download and
  separately confirmed immutable evidence binding; no automatic binding, candidate
  transition or policy PASS;
- deterministic policy decisions over commit-bound evidence;
- immutable project profiles, release candidates, and append-only audit history;
- content-addressed attestations and portable assurance bundles;
- an Ed25519-authenticated, project-authorized, loopback-only REST API;
- a same-origin local Dashboard for activation, status, project discovery,
  candidate creation, reviewed lifecycle/evidence/evaluation/attestation
  actions, audit and assurance inspection, operator-reviewed portable bundle
  download, and optional live device status without browser-held signing keys;
- offline GitHub Actions gating without GitHub API write permissions; and
- rootless Podman/WSL2 isolation for the exact Windows plugin runs that passed
  the retained hostile-fixture checks.

ForgeGate has read public UART v1 telemetry from a connected MSP430 board in an
explicitly enabled, input-only Windows session. It has not sent a device command,
flashed firmware, validated a physical measurement, converted telemetry into
release evidence, or been approved for LAN, internet, shared-host, or production
deployment.

## Architecture and workflow

```mermaid
flowchart LR
    A["JUnit · Coverage · SARIF · Benchmark<br/>Optional AFE and MSP430 reports"]
    B["Bounded collectors<br/>Exact bytes + SHA-256"]
    C["Audited evidence assembly<br/>Candidate commit binding"]
    D["Immutable project profile<br/>Authorized policy material"]
    E["Deterministic evaluation<br/>PASS · FAIL · REVIEW · ERROR"]
    F["Attestation + portable bundle<br/>Offline verification"]
    G["GitHub Actions gate<br/>Exact CI commit"]
    H["External trust store<br/>Ed25519 signer authority"]
    I["Installed plugin manifest"]
    J["Windows Podman/WSL2 broker<br/>Validated low-trust output"]
    M["Optional MSP430 UART v1 monitor<br/>Read-only live status"]
    W["Dashboard Devices page<br/>Connection · heartbeat · device health"]
    X["Reviewed Dashboard workflow<br/>Evidence · decision · attestation"]

    A --> B --> C --> D --> E --> F --> G
    H --> F
    I --> J --> B
    M --> W
    C --> X
    D --> X
    E --> X
    F --> X
```

The core stays domain-neutral. Analog Validation Studio integration consumes a
frozen public JSON contract without importing the upstream runtime. The optional
MSP430 live monitor consumes the frozen public UART v1 protocol without importing
the upstream runtime, sending serial bytes, or changing generic operation.
A separate strict collector consumes `forgegate.msp430-validation-report.v1`
artifacts without importing upstream code or opening a device. Live UART state is
never converted into candidate evidence.

## Verified results

Aggregate regression figures below use the Phase 58 recorded checkpoint.
Named earlier-phase rows describe their historical scope, not additional totals.

| Gate | Current result | Evidence boundary |
|---|---|---|
| Full Python suite | 1,433 passed, 3 skipped; 95.80% branch-aware coverage | Local host test; skips require unavailable Windows symlink creation |
| Branch-aware coverage | 95.80% at the Phase 58 checkpoint | Local host test; historical statement/branch totals are not mixed into this checkpoint |
| Static quality | Ruff, formatting, and strict mypy passed | Phase 58 local host test |
| Standard CI Dashboard workflow | Four report families; 35 focused Python and 10 new frontend cases; actual Edge preview, binding, six-rule PASS and malformed-SARIF rejection | Synthetic acceptance only, not measured production performance; [Phase 49 evidence](reports/PHASE_49_STANDARD_CI_ACCEPTANCE.md) |
| Existing-only paired startup | 36 new cases, 98 focused regressions and independent CLI startup/restart/refusal checks | Selected file identities and public runtime correlation, not authenticated process ownership or live adoption; [Phase 48 evidence](reports/PHASE_48_EXISTING_PAIR_ACCEPTANCE.md) |
| Adoption preflight | 49 new tests and independent-process MATCH/DIFFERENT/refusal checks | Offline local snapshot comparison and cold-copy preservation; not runtime adoption, live freshness or authenticated lineage; [Phase 47 evidence](reports/PHASE_47_ADOPTION_PREFLIGHT_ACCEPTANCE.md) |
| Rehearsal receipt review | 93 focused Python cases, 148 production-TypeScript cases and actual isolated Edge import/reselection passed | Local synthetic test; 27 tasks/43 events plus exact restored-copy identities displayed; no restore execution, live switch, continuing-availability or hardware claim; [Phase 45 evidence](reports/PHASE_45_RECOVERY_REHEARSAL_REVIEW_ACCEPTANCE.md) |
| Recovery rehearsal | 38 new tests; 160 combined recovery/archive cases; actual CLI with the earlier Edge handoff and independent readback | Local synthetic test; 27 tasks/43 events restored, 4-test/1-failure archived result preserved; no live replacement or payload rehydration |
| Recovery handoff | 40 focused Python cases, 9 production-TypeScript cases and native Edge READY/BLOCKED imports plus independently hashed downloads passed | Local synthetic test; exact-byte trailing-newline and sequential-reselection regressions fixed; no restore, payload upload, live availability, producer authentication, hardware or publication |
| Offline recovery readiness | 26 new cases; 120 combined archive/backup/readiness cases; exact CLI READY/missing/wrong-hash outcomes | Local synthetic test; observed snapshot/payload readiness only; [Phase 42 evidence](reports/PHASE_42_RECOVERY_READINESS_ACCEPTANCE.md) |
| Reviewed job archival | 46 new regressions; 94 combined archive/backup cases, 100% focused branch coverage; actual Edge detail and clean-wheel CLI recovery | Local synthetic test; history/idempotency retained; logical quota only; original external backups required |
| Coordinated workspace recovery | 48 focused cases; backup/CLI modules 100% branch-aware coverage; paired snapshots, restored-copy execution and retention planning | Local synthetic test; no live replacement, automatic purge, encryption or power-loss certification |
| Durable local report jobs | 99 focused Python cases plus actual synthetic browser execution; CLI lifecycle, v1/v2-to-v3 store migration, cooperative cancellation/renewal, exact browser export and reviewed binding | Local synthetic test; no automatic worker, mid-parser preemption, candidate transition, policy decision or hardware |
| Candidate-store backup | 27 focused cases; backup module 100% branch-aware coverage; installed CLI round trip passes | Local host test; no automatic restore, encryption or blanket domain validation |
| Contracts | 58 document and 3 artifact JSON Schemas plus direct-API and Dashboard-BFF OpenAPI (30 paths, 32 operations) | Current local contract inventory; drift checks are part of development verification |
| Packaging | sdist/wheel build and clean-environment install smoke passed | Local host test |
| User interaction smoke | 33/33 expected CLI and authenticated REST outcomes matched | Local host test; ephemeral key/database, no hardware |
| Dashboard automation | 248 TypeScript host interaction tests passed at Phase 58, including quick assessment, source replay and evaluation comparison | Local host test; [Phase 58 actual Edge checks](reports/PHASE_58_WINDOWS_DELIVERY_ACCEPTANCE.md) verify the installed workflow; not exhaustive browser/OS certification |
| Dashboard browser interaction | Full reviewed Edge workflow, Edge/Chrome keyboard/focus, 129-record pagination, 390 px responsive, 409/413/422/429/500 recovery, exact Edge 100–200% zoom, and clean-console paths passed | Windows local browser test; uncommon errors use a zero-write presentation harness; Narrator is bounded PASS, while spoken output, high contrast, and real Remote Desktop remain open |
| MSP430 report collector | 34 focused tests plus clean-wheel CLI collection passed; one LaunchPad HIL migration fixture produced 17 normalized records with retained warnings | Local artifact test; the fixture is a historical upstream result, not a new run or physical-measurement claim |
| MSP430 live status | COM4 opened input-only at 115200 8-N-1; authenticated Devices page showed `CONNECTED`, heartbeat `NORMAL`, device `FAULT`, flags `0015`; sequence advanced 58007→58017 over 10 seconds with 10 accepted frames and no sequence gap | Owner-authorized Windows physical-device observation; one earlier invalid frame was rejected, no command or firmware/debug action, measurement validation, release evidence, or long-duration stability claim |
| Windows plugin controls | 18/18 clean-wheel controls passed with the fixed pure-Python fixture | Live local WSL2/Podman test; no general publisher or plugin trust claim |
| Cross-platform CI | `verify.py`, `release_smoke.py`, and the generic Action smoke passed | [GitHub Actions run 33999452478](https://github.com/Carlos-0798/forgegate/actions/runs/33999452478); hosted CI did not run live Podman fixtures |
| Hardware/device behavior | Connection and UART heartbeat status observed only | Device control and measurement validation remain out of scope |

See the [verification matrix](docs/VERIFICATION_MATRIX.md) for capability-level
status, the [Phase 27 acceptance report](reports/PHASE_27_DASHBOARD_WRITE_AND_MSP430_COLLECTOR_ACCEPTANCE_REPORT.md)
for the reviewed browser/collector checkpoint, the
[interaction acceptance report](reports/INTERACTION_ACCEPTANCE_REPORT_2026-09-04.md)
for core expected-versus-actual samples, and the
[software integrity and interaction audit](reports/SOFTWARE_INTEGRITY_INTERACTION_AUDIT_2026-09-03.md)
for the accepted security/package checkpoint. Historical phase reports are
retained under [`reports/`](reports/README.md) instead of being presented as
current results.

## Key design decisions

- **Collection is not a decision.** A successful collector only contributes
  evidence; policy evaluation remains a separate explicit action.
- **Integrity is not authenticity.** SHA-256 binds exact bytes and associations.
  Signer authentication requires a separately managed Ed25519 trust record.
- **History is append-only.** Candidate changes use idempotency keys and
  optimistic revisions; exact replay is distinct from conflicting reuse.
- **Policy authority is frozen.** A candidate retains the immutable project
  profile and exact policy bytes that authorized its decision.
- **Portable verification is explicit.** A bundle can be checked without its
  source database, but source-artifact bytes and trusted time are not implied.
- **Plugins are untrusted inputs.** Discovery does not import plugin code. The
  Windows broker owns I/O, enforces the retained run plan, and does not promote
  plugin output above `unsigned_local` / `declared` evidence.
- **Peer projects keep their evidence labels.** ForgeGate never converts AFE
  software results, replay data, or MSP430 reports into physical proof.

## Quick start

Requirements: Python 3.12. Live plugin execution additionally requires the
documented Windows 11, WSL2, and rootless Podman environment.

```powershell
.\tools\setup_environment.ps1
.\.venv\Scripts\python.exe tools\verify.py
.\.venv\Scripts\python.exe tools\interaction_smoke.py
.\.venv\Scripts\python.exe tools\release_smoke.py
.\.venv\Scripts\python.exe -m forgegate init work\sample-project
```

Validate the committed generic project and evaluate its reproducible PASS
fixture:

```powershell
.\.venv\Scripts\python.exe -m forgegate validate-config `
  examples\sample-python-api\forgegate.yaml

.\.venv\Scripts\python.exe -m forgegate evaluate-policy `
  examples\sample-python-api\policies\pull-request.yaml `
  examples\sample-python-api\evidence\pass-bundle.json `
  --evaluated-at 2026-08-30T21:00:00Z
```

![ForgeGate CLI transcript showing a validated configuration and deterministic PASS decision](docs/assets/forgegate-cli-demo.svg)

The image is a formatted excerpt of commands rerun against this checkpoint, not
a hardware or production screenshot. The exact commands, complete output, and
evidence label are retained in the [reproducible CLI walkthrough](docs/DEMO.md).

Decision exits are stable: `0` PASS, `1` FAIL, `2` REVIEW, and `3` ERROR.
ForgeGate does not run the build or authenticate evidence while evaluating it.

The current Alpha includes a narrow same-origin local Dashboard. Start it with
an owner-managed trust store and an initialized project database:

```powershell
.\.venv\Scripts\forgegate.exe dashboard `
  --database work\forgegate.db `
  --trust-store work\trust-store.json

# In another terminal, approve the code displayed by the page:
.\.venv\Scripts\forgegate.exe dashboard-activate FG-ABCDE-FGHJK `
  --server http://127.0.0.1:8000 `
  --identity work\operator-identity.json `
  --private-key work\operator-private-key.pem `
  --role operator `
  --project sample-api
```

Use the fresh code and exact `--server` origin shown by your page. If you start
the service with `--port 8131`, activation must also target port 8131. Replace
the identity/key paths, role, and project with your owner-managed values; the
page never accepts a private key. An expired code requires a new activation.
Connection/rate failures provide a manual retry action without auto-resubmission.

The browser receives an opaque HttpOnly cookie, never the raw API Bearer token
or private signing key. The implemented pages cover activation, Overview,
Devices, Projects, candidate list/create/detail/audit, Evidence, Decision, and
Assurance for one selected candidate, plus an operator-only project Audit
workspace. Audit supports candidate filtering, 25-event cursor pages, full
event/subject fingerprints, recorded actor identity, and refresh/back links;
missing actors remain explicitly unrecorded. An operator can explicitly review and
confirm each legal lifecycle transition, bind a complete local evidence-
assembly JSON document, evaluate exact policy-material JSON, and generate the
terminal attestation. An operator can then review the current revision, bundle
identity, exact member set, and limitations before downloading the deterministic
portable ZIP; the server accepts no output path and writes no export file.
Automatic collection, server-side file browsing, plugin execution, and
administration remain CLI/API work or visibly planned. Swagger UI and ReDoc stay disabled; the committed,
drift-checked OpenAPI document remains the direct API reference.

For an unbound COLLECTING candidate, **Collect JUnit report** accepts one raw
XML report up to 1 MiB and previews it using the existing collector. Supply the
original collection time and reported source metadata; evidence stays
`unsigned_local` / `declared`. Review counts and warnings before the separate
immutable binding confirmation. This is not automatic test execution, a durable
job queue, or multi-report collection. Original bytes are not retained.
See the [collection contract](docs/DASHBOARD_COLLECTION_CONTRACT.md) and
[synthetic acceptance samples](examples/dashboard-junit/README.md).
Real Edge acceptance now covers file selection, PASS/FAIL policy workflows,
warning consent and forbidden-XML rejection using explicitly synthetic samples.
It found and corrected a shared-policy binding defect; SQLite schema v9 permits
multiple candidates to reuse exact policy content while preserving one immutable
binding per candidate. Existing databases require a backup and explicit migration.
See the [Phase 30 report](reports/PHASE_30_JUNIT_COLLECTION_ACCEPTANCE.md).

A completed retained task now exposes two deliberately separate actions: export
the exact canonical assembly, or bind that same assembly through the existing
candidate-evidence workflow after a fresh candidate check and confirmation.

![ForgeGate retained job result with separately reviewed download and evidence-binding actions](docs/assets/phase37-job-result-actions.jpg)

The [Phase 37 acceptance report](reports/PHASE_37_JOB_RESULT_HANDOFF_ACCEPTANCE.md)
records the actual Edge download, byte-for-byte SHA-256 validation, immutable
binding and independent CLI/store readback. Its synthetic test summary deliberately
contains one failure; the candidate stays `COLLECTING` revision 1 and no policy
decision is made. This is local host evidence, not producer authentication,
hardware validation or production approval.

For startup diagnosis, use `python -m forgegate dashboard-check --port 8131`.
The [Windows operation guide](docs/WINDOWS_DASHBOARD_OPERATIONS.md) and
[Phase 31 report](reports/PHASE_31_WINDOWS_RUNTIME_ACCEPTANCE.md) cover the
foreground launcher, failures and safe restart; this is not a background service.

MSP430 monitoring is an optional dependency and must be enabled explicitly. The
monitor enumerates and opens only the selected application UART, sets DTR/RTS
inactive before opening, reads bounded newline-delimited frames, and never calls
the serial write path:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[msp430]"
.\.venv\Scripts\forgegate.exe dashboard `
  --database work\forgegate.db `
  --trust-store work\trust-store.json `
  --msp430-port COM4
```

The Devices page refreshes every second and separates serial connection,
heartbeat freshness, and the firmware-reported device state. `FAULT 0015` can
therefore coexist with a healthy connection and heartbeat; it is not presented
as a ForgeGate release failure. The versioned UART adapter decodes `0015` as
DS18B20 missing, NTC unavailable/out of range, and INA219 communication
unavailable while labeling those values as firmware reports rather than
ForgeGate diagnoses.

![ForgeGate Devices page showing a connected MSP430, normal UART heartbeat, and decoded firmware-reported fault flags](docs/assets/forgegate-dashboard-msp430-decoded-faults.jpg)

This real Windows browser capture records the owner-authorized, input-only COM4
observation described in the
[Phase 25 acceptance report](reports/PHASE_25_MSP430_LIVE_STATUS_ACCEPTANCE_REPORT.md).
It demonstrates live transport and presentation only—not sensor accuracy,
firmware correctness, release evidence, hardware control, or production
readiness.

![ForgeGate Dashboard showing a completed reviewed candidate workflow at PASS revision 4](docs/assets/forgegate-dashboard-reviewed-workflow-pass.jpg)

![ForgeGate Dashboard tracing the same workflow to its retained policy decision](docs/assets/forgegate-dashboard-reviewed-workflow-decision.jpg)

These Edge captures show one generic, isolated workflow from DRAFT through PASS
and an `unsigned_local` attestation. Every mutation was separately reviewed;
the table and detail were reloaded from authoritative state. Exact identities,
negative input results, 100–200% zoom measurements, image hashes, and boundaries
are retained in the
[Phase 27 browser evidence](reports/DASHBOARD_PHASE27_INTERACTION_EVIDENCE_2026-09-05.json).
The [portfolio evidence gallery](docs/PORTFOLIO_EVIDENCE.md) retains the broader
Overview, candidate, validation-error, pagination, assurance, and zoom captures.
None proves producer authenticity, hardware correctness, deployment approval,
or production readiness.

![ForgeGate reviewed portable assurance download showing the exact candidate revision, bundle ID, canonical members, and evidence boundary](docs/assets/forgegate-dashboard-assurance-export-confirm.jpg)

The Phase 28 Edge run downloaded the candidate-bound ZIP, extracted exactly the
three canonical members, and passed the existing database-independent verifier.
The [machine record](reports/DASHBOARD_PHASE28_ASSURANCE_EXPORT_EVIDENCE_2026-09-05.json)
retains the archive hash, response contract, negative authorization/stale-state
results, screenshot hashes, and explicit non-claims.

For plugin inspection, API authentication, candidate persistence, bundle
signing, and GitHub gate commands, use the [CLI and workflow guide](docs/DEMO.md)
and architecture index rather than copying unreviewed commands from screenshots.

## Repository layout

| Path | Purpose |
|---|---|
| [`src/forgegate/`](src/forgegate/) | Domain models, collectors, policy engine, persistence, CLI, REST API, and plugin boundaries |
| [`tests/`](tests/) | Unit, adversarial, integration, Golden, migration, and contract-drift tests |
| [`schemas/`](schemas/) | Committed JSON Schema and OpenAPI contracts |
| [`examples/`](examples/) | Generic reproducible project, policies, evidence, and artifacts |
| [`docs/`](docs/README.md) | Architecture, security, compatibility, status, roadmap, and walkthroughs |
| [`reports/`](reports/README.md) | Current acceptance evidence plus immutable historical phase reports |
| [`tools/`](tools/) | Environment setup, full verification, and clean-install release smoke |

Start with [project status](docs/PROJECT_STATUS.md), the
[documentation index](docs/README.md), and the
[verification matrix](docs/VERIFICATION_MATRIX.md). Security-sensitive behavior
and reporting instructions are documented in [SECURITY.md](SECURITY.md).

## Known limitations

- The authenticated API is loopback-only and has no TLS, reverse-proxy trust,
  hostile-local-user defense, or remote-deployment approval.
- The local Web Dashboard is a narrow Alpha surface. Evidence, decision, and
  assurance review plus explicit candidate transitions, evidence binding,
  policy evaluation, attestation generation, and candidate-bound portable ZIP
  download and bounded private source-report replay export are implemented.
  Automatic collection, server-side browsing, arbitrary-source export, plugin, and administration
  workflows are not. Foreground report parsing now records execution ownership,
  renews at bounded checkpoints, and observes explicit cancellation between
  stages; there is still no scheduler, background service, or arbitrary parser
  preemption. Exact 100–200% Edge zoom passes; spoken Narrator output,
  Windows high contrast, and a real Remote Desktop run remain unexecuted.
  The Dashboard BFF has a separate generated and drift-checked
  OpenAPI contract without exposing interactive docs.
- Sessions, authentication rate state, and trust-store distribution are not
  durable or distributed; time is caller/server supplied rather than trusted.
- General third-party plugin trust is not established. Native extensions,
  dependency-rich plugins, remote acquisition, and Linux/macOS execution
  backends are unsupported.
- The GitHub bridge performs offline bundle/commit gating only. It does not add
  custom Checks, PR annotations, artifact upload, OIDC identity, or API writes.
- Automatic restore/repair, database authorization, managed key custody, online revocation,
  and administrator-resistant audit logging are not implemented.
  Current-schema backup and structural verification are local CLI operations;
  they do not authenticate data or replay all domain-history invariants.
- MSP430 live status is input-only and process-local. It retains no telemetry
  history, controls no hardware, does not validate sensor values, and does not
  create release evidence. The separate artifact collector can normalize a
  strict upstream report, but it never promotes HIL to physical verification
  or accesses the live device.
- No production deployment or public release has been authorized.

These constraints are product boundaries, not implied future results. See the
[threat model](docs/security/THREAT_MODEL.md) for the complete trust analysis.

## Roadmap

The real AVS artifact handoff and private source-report replay are accepted.
The current product priority is [Phase 54 quick assessment](docs/QUICK_ASSESSMENT.md):
batch selection, report identification and reviewed execution of the existing
assurance workflow. Phase 53B human comparison is deferred by the owner;
productivity gains remain NOT MEASURED. A new immutable upstream candidate follows only when an
owner-approved producer revision/disposition is available.
Do not rerun the unchanged failing baseline, replace real artifacts
with the synthetic tutorial, or expand process-management infrastructure unless
a measured delivery blocker requires it.

Separate maturity gates (not prerequisites for that core workflow) are:

1. complete Windows high-contrast, spoken Narrator-output, and real Remote
   Desktop evidence without claiming full accessibility certification;
2. build a private owned-process channel on existing-only paired startup, then prove
   all-writer fencing and rollback against the
   [adoption design](docs/WORKSPACE_ADOPTION_DESIGN.md) before any live switch;
   snapshot preflight and public runtime correlation are implemented; owned-process
   authentication, managed lifecycle and runtime adoption are not;
3. align future MSP430 report revisions through the frozen artifact contract
   while keeping live UART status separate from evidence;
4. establish publisher provenance and broader hostile-plugin compatibility;
5. design TLS/proxy identity, durable security state, retention/export, and
   managed key lifecycle before considering non-loopback deployment; and
6. consider GitHub Checks, signed CI provenance, OIDC, and artifact publication
   only as separately authorized integrations.

Completed acceptance-level work and remaining tasks are tracked in
[docs/ROADMAP.md](docs/ROADMAP.md). Roadmap items are not claims of delivery.

## License status

No open-source license has been selected. The current private-development copy
is all rights reserved and must not be published or redistributed until the
owner makes an explicit license and release decision.
