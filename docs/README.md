# ForgeGate documentation

This index separates current product claims from design detail, security
analysis, compatibility contracts, and historical acceptance evidence.

## Start here

1. [Project status](PROJECT_STATUS.md) — current maturity and accepted baseline
2. [Verification matrix](VERIFICATION_MATRIX.md) — evidence level for each capability
3. [Roadmap](ROADMAP.md) — completed and remaining acceptance gates
4. [Reproducible interaction walkthrough](DEMO.md) — generic CLI/API examples with expected output
5. [Portfolio evidence gallery](PORTFOLIO_EVIDENCE.md) — retained screenshots, exact fixture data, hashes, and claim boundaries
6. [Security policy](../SECURITY.md) — supported scope and responsible reporting

Latest local engineering slice: [coordinated workspace backup and recovery](WORKSPACE_RECOVERY.md),
with paired snapshots, independent verification, restored copies and retention plans.
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
