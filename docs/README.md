# ForgeGate documentation

This index separates current product claims from design detail, security
analysis, compatibility contracts, and historical acceptance evidence.

## Start here — review or try ForgeGate

1. [Product brief](product/PRODUCT_BRIEF.md) — the report-review problem, intended user and engineering tradeoffs
2. [Portfolio evidence gallery](PORTFOLIO_EVIDENCE.md#recommended-review-path) — a short route through the workbench, real software-report case and verifiable handoff; no installation required
3. [Independent local workspace](LOCAL_WORKSPACE_QUICKSTART.md) — install, initialize your own workspace and repeat the synthetic PASS/FAIL task; for a source checkout without a supplied wheel, start with the [README build instructions](../README.md#quick-start)
4. [Project status](PROJECT_STATUS.md) and [verification matrix](VERIFICATION_MATRIX.md) — accepted capabilities and their evidence limits
5. [Domain model](architecture/DOMAIN_MODEL.md), [policy engine](architecture/POLICY_ENGINE.md) and [trust model](architecture/TRUST_AND_EVIDENCE.md) — implementation and design review
6. [Roadmap](ROADMAP.md) and [security policy](../SECURITY.md) — remaining work, supported scope and responsible reporting

## Maintainer resumption and historical acceptance

The [2026-09-09 pause/resumption checkpoint](PROJECT_RESUME_CHECKPOINT_2026-09-09.md)
and [Private GitHub synchronization](../reports/GITHUB_SYNC_2026-09-09.md)
preserve the engineering handoff. They are maintenance records, not prerequisites
for reviewing or trying the product. The accepted baseline includes
[monitor presets](MONITOR_PRESETS.md) and
[Phase 64 evidence](../reports/PHASE_64_MONITOR_PRESETS_ACCEPTANCE.md).

The [frozen Phase 61 Windows demonstration](FINAL_WINDOWS_DEMO.md) retains its
original package and expected outcomes. Its GUI commands require the owner's
historical private workspace; new users should follow the independent workspace
guide above. The [generic CLI/API walkthrough](DEMO.md) remains available for
deeper interaction examples. Older delivery slices below retain their original
scope and do not supersede the current first-use guide.

Previously completed milestone: [feature freeze and Alpha completion](ALPHA_COMPLETION_PLAN.md).
Phases 59-61 close the local source/build baseline, frozen-package real-project
acceptance and final demonstration. The scoped Windows Alpha milestone is complete.
See the [Phase 59 closeout](../reports/PHASE_59_CODE_CLOSEOUT_ACCEPTANCE.md) and
[Phase 60 acceptance](../reports/PHASE_60_REAL_PROJECT_ACCEPTANCE.md) for the
accepted identities, outcomes and verification boundaries, followed by the
[Phase 61 final demo](../reports/PHASE_61_FINAL_DEMO_ACCEPTANCE.md).

Previous engineering slice: [Phase 58 Windows installed-wheel acceptance](../reports/PHASE_58_WINDOWS_DELIVERY_ACCEPTANCE.md),
covering installed Quick Assessment, Evidence Replay, assurance and comparison.
It builds on [Evaluation comparison](DECISION_COMPARISON.md) and
[Phase 57 acceptance](../reports/PHASE_57_DECISION_COMPARISON_ACCEPTANCE.md), building
on [Quick assessment](QUICK_ASSESSMENT.md) and its
[real AVS quick-handoff acceptance](../reports/PHASE_56_AVS_QUICK_ACCEPTANCE.md).
The [Phase 53 efficiency and accuracy protocol](product/EFFICIENCY_ACCEPTANCE.md)
and [blank observation record](product/EFFICIENCY_RUN_TEMPLATE.md) are retained,
but human comparison is deferred by owner. The [product brief](product/PRODUCT_BRIEF.md)
continues to prioritize report-review and handoff benefits without unmeasured claims.

Historical delivery slice: [reviewed Windows installed-wheel delivery](../reports/PHASE_52_WINDOWS_DELIVERY_ACCEPTANCE.md)
using the [Windows operating guide](WINDOWS_DASHBOARD_OPERATIONS.md), plus
[private original-report export and offline replay](EVIDENCE_REPLAY.md),
with [Phase 51 acceptance](../reports/PHASE_51_SOURCE_REPLAY_ACCEPTANCE.md).
It extends [real AVS host acceptance](../reports/PHASE_50_AVS_HOST_ACCEPTANCE.md)
and its [file-only consumer pack](../examples/analog-validation-studio-host/README.md),
using the [standard CI collection contracts](DASHBOARD_COLLECTION_CONTRACT.md).
The integration is accepted; its frozen producer baseline correctly remains FAIL.
Real artifact delivery takes priority over further process management.

Deferred engineering design: [workspace adoption and rollback](WORKSPACE_ADOPTION_DESIGN.md),
with source-traced gaps, recovery-point review and 24 NOT RUN fault-injection
cases. No live switch or managed lifecycle is implemented by this design.

Earlier Phase 48 local slice: [existing-only paired startup and runtime correlation](WINDOWS_DASHBOARD_OPERATIONS.md),
with explicit no-initialization/no-migration startup and public per-start IDs,
not authenticated process ownership or a writer fence. Previous slice:
[read-only adoption preflight](WORKSPACE_ADOPTION_PREFLIGHT.md),
which compares exact snapshots and a cold rehearsal directory without process
control or switch authority. Latest browser slice:
[Dashboard rehearsal receipt review](DASHBOARD_RECOVERY_REHEARSAL_REVIEW.md),
which presents the exact content-addressed restored-copy receipt without adding
browser restore or workspace-switch authority. It follows the
[reviewed recovery rehearsal](RECOVERY_REHEARSAL.md),
[Recovery-page handoff review](DASHBOARD_RECOVERY_HANDOFF.md) and
[offline readiness checks](RECOVERY_READINESS.md).
Previous slice: [durable report-job lifecycle](COLLECTION_JOBS.md)
with visible execution ownership, bounded lease renewal and cooperative stop
checkpoints, with [Phase 38 browser and host evidence](../reports/PHASE_38_JOB_EXECUTION_LIFECYCLE_ACCEPTANCE.md).
Phase 37 exact export/binding browser evidence remains separately retained in the
[handoff report](../reports/PHASE_37_JOB_RESULT_HANDOFF_ACCEPTANCE.md).

## Product and trust model

- [Product brief](product/PRODUCT_BRIEF.md)
- [Domain model](architecture/DOMAIN_MODEL.md)
- [Independent core decision](architecture/ADR-0001-independent-core.md)
- [Trust and evidence](architecture/TRUST_AND_EVIDENCE.md)
- [Threat model](security/THREAT_MODEL.md)

## Evidence and release decisions

- [Artifact and JUnit collection](architecture/ARTIFACT_AND_JUNIT_SLICE.md)
- [Coverage collectors](architecture/COVERAGE_COLLECTORS.md)
- [SARIF collector](architecture/SARIF_COLLECTOR.md)
- [Benchmark collector](architecture/BENCHMARK_JSON_COLLECTOR.md)
- [Evidence bundle assembly](architecture/EVIDENCE_BUNDLE_ASSEMBLY.md)
- [Candidate evidence binding](architecture/CANDIDATE_EVIDENCE_BINDING.md)
- [Durable local collection jobs](COLLECTION_JOBS.md) — CLI lifecycle, restart/cancel semantics and private data boundaries
- [Dashboard job management](DASHBOARD_JOBS.md) — explicit store upgrade/configuration, operator-only inspection, parsing, exact export and immutable evidence handoff
- [Policy engine](architecture/POLICY_ENGINE.md)
- [Candidate lifecycle](architecture/CANDIDATE_LIFECYCLE.md)
- [Attestations](architecture/ATTESTATIONS.md)
- [Portable assurance bundles](architecture/PORTABLE_ASSURANCE_BUNDLES.md)
- [Authenticated assurance identity](architecture/AUTHENTICATED_ASSURANCE_IDENTITY.md)

## Persistence, API, and audit

- [Reviewed recovery rehearsal](RECOVERY_REHEARSAL.md)
- [Coordinated workspace backup, recovery and retention planning](WORKSPACE_RECOVERY.md)
- [Candidate store backup and validation](STORE_BACKUP_OPERATIONS.md)
- [SQLite candidate store](architecture/SQLITE_CANDIDATE_STORE.md)
- [Project registry and audit query](architecture/PROJECT_REGISTRY_AND_AUDIT_QUERY.md)
- [Project authority and discovery](architecture/PROJECT_AUTHORITY_AND_DISCOVERY.md)
- [Project profile revisions](architecture/PROJECT_PROFILE_REVISIONS.md)
- [Policy materialization](architecture/POLICY_MATERIALIZATION.md)
- [Local REST API](architecture/LOCAL_REST_API.md)
- [Local REST command workflow](architecture/LOCAL_REST_COMMAND_WORKFLOW.md)
- [Authenticated local API](architecture/AUTHENTICATED_LOCAL_API.md)
- [Local session lifecycle](architecture/LOCAL_SESSION_LIFECYCLE.md)
- [Local API security boundaries](architecture/LOCAL_API_SECURITY_BOUNDARIES.md)

## Local Dashboard

- [Windows startup, diagnostics and recovery](WINDOWS_DASHBOARD_OPERATIONS.md)
- [Dashboard UX requirements](product/DASHBOARD_UX_REQUIREMENTS.md)
- [Local Web Dashboard architecture](architecture/LOCAL_WEB_DASHBOARD.md)
- [Dashboard assurance export](architecture/DASHBOARD_ASSURANCE_EXPORT.md)
- [Dashboard threat model](security/DASHBOARD_THREAT_MODEL.md)
- [Dashboard acceptance matrix](DASHBOARD_ACCEPTANCE_MATRIX.md)

These documents govern the implemented Phase 24 activation, Phase 25 optional
live status, Phase 26 assurance review, Phase 27 reviewed candidate writes, and
Phase 28 operator-reviewed portable ZIP download.
The packaged frontend and browser-for-frontend session boundary are present.
Edge and Chrome keyboard/focus, pagination, responsive,
409/413/422/429/500 recovery, clean-console paths, and exact Edge 100–200% zoom
pass; uncommon statuses use an isolated zero-write presentation harness.
Narrator has a bounded keyboard/semantic result without spoken-output capture;
high contrast and Remote Desktop retain their explicit unexecuted state.

## CI and plugins

- [GitHub Actions gate](architecture/GITHUB_ACTIONS_GATE.md)
- [Plugin SDK discovery](architecture/PLUGIN_SDK_DISCOVERY.md)
- [Plugin execution security contract](architecture/PLUGIN_EXECUTION_SECURITY_CONTRACT.md)
- [Windows plugin sandbox](architecture/WINDOWS_PLUGIN_SANDBOX.md)
- [Brokered plugin execution](architecture/PRODUCTION_PLUGIN_BROKER.md)
- [Plugin operator workflow](architecture/PLUGIN_OPERATOR_WORKFLOW.md)
- [Windows Alpha delivery](architecture/WINDOWS_ALPHA_DELIVERY.md)

## Compatibility and research

- [Analog Validation collector](architecture/ANALOG_VALIDATION_COLLECTOR.md)
- [MSP430 validation-report collector](architecture/MSP430_VALIDATION_COLLECTOR.md)
- [Upstream compatibility contract](compatibility/UPSTREAM_CONTRACT.md)
- [Open-source reference review](research/OPEN_SOURCE_REFERENCE_REVIEW.md)

Analog Validation Studio and the MSP430 project remain independent producers.
ForgeGate consumes only explicitly versioned artifacts and preserves their
original evidence level. Their source code, runtime, and hardware are not part
of the ForgeGate core.

## Acceptance evidence

Current and historical acceptance reports are indexed separately in
[`reports/README.md`](../reports/README.md). A report documents what was tested
at a particular checkpoint; it does not silently update later capability claims.
