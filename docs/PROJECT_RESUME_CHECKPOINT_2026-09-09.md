# Project pause and resumption checkpoint — 2026-09-09

Purpose: preserve the engineering stopping point while the owner prepares job
applications and synchronizes the existing private GitHub repository. This is
a development bookmark, not abandonment, a public release, or permission to
perform future hardware actions. Earlier dated acceptance records stay unchanged.

## Accepted stopping point

- Product: ForgeGate `0.1.0a1`, completed Windows Local Alpha plus the accepted
  Phase 64 reusable-monitor-preset extension.
- Starting checkout: `codex/reviewed-job-archival`, HEAD
  `9b9230ebc4db9e3c4c3bdf7a0acf34634f0d1d0d`, with Phase 64 runtime, tests,
  contracts, assets and documentation present as uncommitted changes.
- Last accepted local gates: 1,568 Python passes, three host symlink skips,
  95.90% branch-aware coverage; 296 frontend passes; 33 interaction checks;
  schema/OpenAPI/assets, strict typing, lint and clean-install smoke PASS.
- Retained real AVS integration: four collections, 130 normalized records and
  all 12 rule outcomes reproduced (10 PASS / 2 FAIL). `VALID / FAIL` is the
  expected successful verification of a retained engineering failure.
- Phase 64 installed-wheel browser acceptance: activation, explicit start/stop,
  reload without duplicate reader, restart with new authorization and default
  STOPPED, plus the clearly labeled six-state simulation. No serial port was
  opened in that acceptance. Historical actual MSP430 observations remain
  separately labeled; they are not refreshed hardware measurements.

The accepted runtime and Phase 64 evidence are now preserved at commit
`5f4eb15b79e5ea5f12fd964ead31e8d1b33c7c5b`
(`feat: add reusable read-only monitor presets`). Later synchronization commits
contain portfolio and resumption documentation, not another feature expansion.
The [synchronization record](../reports/GITHUB_SYNC_2026-09-09.md)
identifies the resulting source checkpoint, fresh checks and remote outcome;
do not mistake the older working-tree wheel for a byte-identical new build.

## What is already delivered — do not rebuild it

1. Standard JUnit, coverage XML/LCOV, SARIF and benchmark report collectors;
   bounded validation, normalization, version/candidate binding and policies.
2. Authenticated local Dashboard and CLI: workspace initialization, quick
   assessment, saved-policy reuse, candidate/evidence/decision review, comparison,
   assurance export and original-report offline replay.
3. SQLite history, scoped/idempotent writes, cooperative foreground report jobs,
   snapshots, archival and new-directory recovery checks.
4. Optional artifact-only AVS/MSP430 collectors, input-only MSP430 UART v1
   status, project-scoped monitor presets and hardware-free demonstration.
5. Installed Windows delivery, deterministic packaged assets and retained
   positive/negative integration and browser evidence.

Core purpose remains engineering-evidence review and release assurance. Device
status is optional, not the core product and not candidate evidence. ForgeGate
does not replace upstream testing, scanning, firmware or acquisition software.

## Resume engineering here after job preparation

The next proposed engineering slice is **adapter conformance and extension
example**, not another platform rewrite. Confirm the owner still wants this
slice before implementing it; a next-step proposal is not a completed feature.

| Priority | Bounded next task | Acceptance / stop condition |
|---|---|---|
| 1 | A protocol-specific adapter contract/example using the existing live-status and preset boundaries | A fixture-driven adapter conforms to connection/freshness/invalid/fault/recovery semantics; host tests cover malformed input, partial frames, duplicate start and late stop; core works without adapters or serial dependencies; no simulation-to-hardware claim |
| 2 | Reusable preset setup guidance and compatibility declaration | Document required protocol/version/baud and fixed safe parameters; allowlisted configuration rejects unsupported combinations; no automatic COM guessing or arbitrary driver loading; add UI editing only if a concrete repeated-setup problem warrants it |
| 3 | Real acceptance of a supported physical protocol when a device and explicit owner authorization are available | Record exact board/firmware/protocol and observed states; compare displayed output with known input; retain failures and evidence labels; a second board is NOT supported until this gate is completed |
| 4 | Durable measurement capture, only if selected as a separate user task | Define raw bytes/timestamps/source identity, bounds, stop/export and evidence levels before coding; live status must not silently become release evidence |

Do not buy hardware, open a serial port, change firmware, send commands, or
assume that hardware permission transfers to a new session. No new AVS/MSP430
upstream revision is required for the current portfolio milestone. When one is
approved later, create a new immutable candidate; do not overwrite old evidence
or rerun the unchanged failing baseline to make the presentation look green.

## Retained quality work and deferred expansion

- Native Windows high contrast, captured spoken Narrator output and actual
  Remote Desktop acceptance remain uncompleted; earlier keyboard/zoom checks
  must not be described as full accessibility certification.
- Independent novice acceptance and the Phase 53B human comparison remain
  unrun/deferred. Keep the existing fair-baseline protocol; no speedup or accuracy
  percentages until measured.
- No automatic monitoring at startup, background watchdog, multi-process device
  broker, generalized driver marketplace or broad board compatibility.
- Managed live-workspace switching, publisher provenance, cloud/team service,
  TLS/SSO and production identity operations remain separate, need-driven work.

Do not treat this list as a demand to implement every item. Choose one valuable
vertical slice, with inputs, expected outputs and an exit criterion. Reuse
accepted infrastructure and repeat only checks affected by changes, followed by
the full repository gate before accepting a new code checkpoint.

## Resumption checklist

1. Read `AGENTS.md`, this checkpoint, current status, roadmap and verification
   matrix; inspect `git status`, branch/HEAD and current upstream changes.
2. Use the repository Python 3.12 environment and verify the actual import path.
   Preserve all uncommitted user work; never reset/clean to match this note.
3. The last demonstration used an independently installed, hardware-free
   environment. Its URL/process/authorization may have expired; inspect runtime
   reachability before reuse. Do not overwrite its stores or restart a service
   merely to synchronize GitHub. Use a new isolated workspace for new tests.
4. Confirm the intended next slice and available protocol/device/input evidence.
   Recommend the appropriate GPT model before starting the next engineering step.
5. Run focused checks and then `python tools/verify.py`; run
   `python tools/release_smoke.py` for package/dependency/delivery changes.
   Keep frontend host tests distinct from browser and physical evidence.
6. Retain meaningful new screenshots/results with explicit synthetic/replay/
   host/physical labels. Update the current overview, not every historical report.
7. Preserve the owner's manual-only cloud CI policy: pushes and PRs do not
   trigger hosted tests. Run the retained workflow only on explicit request;
   cloud billing resolution is not required to resume local engineering or
   Private synchronization. Do not label an unrun cloud check PASS. See the
   [manual run instructions](../README.md#optional-cloud-validation).

## Key references

- [Current product brief](product/PRODUCT_BRIEF.md)
- [Monitor presets and extension criteria](MONITOR_PRESETS.md)
- [Phase 64 acceptance and wheel identity](../reports/PHASE_64_MONITOR_PRESETS_ACCEPTANCE.md)
- [Phase 64 machine evidence](../reports/PHASE_64_MONITOR_PRESETS_EVIDENCE.json)
- [Windows first use](LOCAL_WORKSPACE_QUICKSTART.md)
- [Real AVS quick assessment](../reports/PHASE_56_AVS_QUICK_ACCEPTANCE.md)
- [Verification matrix](VERIFICATION_MATRIX.md)
- [Deferred human comparison](product/EFFICIENCY_ACCEPTANCE.md)

GitHub authorization for this interruption covers synchronization into the
existing Private repository. Public visibility, License, GitHub Release,
LinkedIn publication and account spending remain separate owner decisions.
