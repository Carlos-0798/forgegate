# ForgeGate acceptance evidence

Reports in this directory are retained engineering records. Use the current
checkpoint first; older phase documents remain historical evidence and should
not be quoted as the latest project status.

## Current checkpoint

- [Phase 24 authenticated local Dashboard checkpoint](PHASE_24_AUTHENTICATED_LOCAL_DASHBOARD_ACCEPTANCE_REPORT.md) — implementation and automation pass; full manual cross-browser exit gate partial
- [Phase 24 manual interaction acceptance](PHASE_24_MANUAL_INTERACTION_ACCEPTANCE_2026-09-04.md) — operator/producer inputs, durable output cross-check, expiry/restart recovery, Edge/Chrome focus, 129-record pagination, 422 recovery, and remaining manual boundary
- [MSP430 connection and Dashboard observation](MSP430_CONNECTION_AND_DASHBOARD_OBSERVATION_2026-09-04.md) — user-authorized Windows USB/UART stability and non-mutating Dashboard checks; not firmware, protocol, measurement, or ForgeGate hardware-integration proof
- [MSP430 connection observation record](MSP430_CONNECTION_OBSERVATION_2026-09-04.json) — exact local counters and explicit non-claims without a device serial number
- [Dashboard fault-presentation record](DASHBOARD_FAULT_PRESENTATION_EVIDENCE_2026-09-04.json) — isolated Chrome 409/413/429/500 rendering, focus, recovery, countdown, and zero-write evidence; test injection, not authentic operational failure evidence
- [Dashboard portfolio capture record](DASHBOARD_PORTFOLIO_CAPTURE_EVIDENCE_2026-09-04.json) — generic Chrome fixture, 422 non-mutation cross-check, screenshot dimensions, hashes, and claim boundaries
- [Phase 23 local Web Dashboard design gate](PHASE_23_LOCAL_WEB_DASHBOARD_DESIGN_GATE.md) — historical design evidence
- [Interaction acceptance report](INTERACTION_ACCEPTANCE_REPORT_2026-09-04.md)
- [Software integrity and interaction audit](SOFTWARE_INTEGRITY_INTERACTION_AUDIT_2026-09-03.md)
- [Latest clean-wheel Windows interaction evidence](SOFTWARE_INTEGRITY_INTERACTION_LIVE_EVIDENCE.json)
- [Phase 22 Windows Alpha acceptance](PHASE_22_WINDOWS_ALPHA_ACCEPTANCE_REPORT.md)
- [Phase 22 Windows Alpha live evidence](PHASE_22_WINDOWS_ALPHA_LIVE_EVIDENCE.json)

The authoritative capability summary is
[`docs/VERIFICATION_MATRIX.md`](../docs/VERIFICATION_MATRIX.md). Raw JSON records
are machine evidence for exact local runs; they are not hardware, production,
publisher-provenance, or general third-party compatibility claims.

## Windows plugin evidence chain

| Phase | Scope | Evidence |
|---|---|---|
| 17 | Import-free plugin discovery | [Acceptance report](PHASE_17_PLUGIN_SDK_DISCOVERY_ACCEPTANCE_REPORT.md) |
| 18 | Execution contract and fail-closed readiness | [Contract report](PHASE_18_ENVIRONMENT_REFERENCE_AND_EXECUTION_CONTRACT_REPORT.md), [model acceptance](PHASE_18_PLUGIN_EXECUTION_CONTRACT_MODELS_ACCEPTANCE_REPORT.md), [Windows readiness](PHASE_18_WINDOWS_SANDBOX_READINESS_REPORT.md) |
| 19 | Low-level Podman/WSL2 hostile fixtures | [Verification report](PHASE_19_WINDOWS_SANDBOX_LIVE_VERIFICATION_REPORT.md), [raw evidence](PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json) |
| 20 | Brokered generic-plugin run and durable replay | [Acceptance report](PHASE_20_PRODUCTION_PLUGIN_BROKER_ACCEPTANCE_REPORT.md), [raw evidence](PHASE_20_WINDOWS_PLUGIN_BROKER_LIVE_EVIDENCE.json) |
| 21 | Operator run/query/collect workflow | [Acceptance report](PHASE_21_PLUGIN_OPERATOR_WORKFLOW_ACCEPTANCE_REPORT.md) |
| 22 | Clean-install Windows Alpha delivery chain | [Acceptance report](PHASE_22_WINDOWS_ALPHA_ACCEPTANCE_REPORT.md), [raw evidence](PHASE_22_WINDOWS_ALPHA_LIVE_EVIDENCE.json) |
| 23 | Local Web Dashboard design gate | [Design report](PHASE_23_LOCAL_WEB_DASHBOARD_DESIGN_GATE.md); no UI implementation |
| 24 | Authenticated local Dashboard vertical slice | [Acceptance report](PHASE_24_AUTHENTICATED_LOCAL_DASHBOARD_ACCEPTANCE_REPORT.md) and [manual interaction record](PHASE_24_MANUAL_INTERACTION_ACCEPTANCE_2026-09-04.md); implementation/local flow pass, manual cross-browser gate partial |

`SANDBOXED` applies only to an exact accepted run. The generic fixture does not
establish publisher trust, native-extension safety, arbitrary dependency
compatibility, remote acquisition safety, or hardware behavior.

## Core release-assurance milestones

- Phase 0: [environment audit](PHASE_0_ENVIRONMENT_AUDIT.md) and [acceptance](PHASE_0_ACCEPTANCE_REPORT.md)
- Phase 1 collectors: [JUnit](PHASE_1_JUNIT_SLICE_ACCEPTANCE_REPORT.md), [coverage](PHASE_1_COVERAGE_SLICE_ACCEPTANCE_REPORT.md), [SARIF](PHASE_1_SARIF_SLICE_ACCEPTANCE_REPORT.md), and [benchmark](PHASE_1_BENCHMARK_SLICE_ACCEPTANCE_REPORT.md)
- Phase 2: [policy engine](PHASE_2_POLICY_ENGINE_ACCEPTANCE_REPORT.md), [candidate lifecycle](PHASE_2_CANDIDATE_LIFECYCLE_ACCEPTANCE_REPORT.md), [SQLite store](PHASE_2_SQLITE_CANDIDATE_STORE_ACCEPTANCE_REPORT.md), and [attestations](PHASE_2_ATTESTATION_ACCEPTANCE_REPORT.md)
- Phase 3: [Analog Validation compatibility](PHASE_3_ANALOG_VALIDATION_COMPATIBILITY_ACCEPTANCE_REPORT.md)
- Phase 4: [evidence assembly](PHASE_4_EVIDENCE_BUNDLE_ASSEMBLY_ACCEPTANCE_REPORT.md) and [candidate binding](PHASE_4_CANDIDATE_EVIDENCE_BINDING_ACCEPTANCE_REPORT.md)
- Phase 5: [local REST API](PHASE_5_LOCAL_REST_API_BASELINE_ACCEPTANCE_REPORT.md)
- Phase 6: [REST command workflow](PHASE_6_LOCAL_REST_COMMAND_WORKFLOW_ACCEPTANCE_REPORT.md)
- Phase 7: [project registry and audit](PHASE_7_PROJECT_REGISTRY_AUDIT_QUERY_ACCEPTANCE_REPORT.md)
- Phase 8: [project authority and discovery](PHASE_8_PROJECT_AUTHORITY_DISCOVERY_ACCEPTANCE_REPORT.md)
- Phase 9: [project profile revisions](PHASE_9_PROJECT_PROFILE_REVISIONS_ACCEPTANCE_REPORT.md)
- Phase 10: [policy materialization](PHASE_10_POLICY_MATERIALIZATION_ACCEPTANCE_REPORT.md)
- Phase 11: [portable assurance bundle](PHASE_11_PORTABLE_ASSURANCE_BUNDLE_ACCEPTANCE_REPORT.md)
- Phase 12: [authenticated assurance identity](PHASE_12_AUTHENTICATED_IDENTITY_FOUNDATION_ACCEPTANCE_REPORT.md)
- Phase 13: [authenticated local API](PHASE_13_AUTHENTICATED_LOCAL_API_ACCEPTANCE_REPORT.md)
- Phase 14: [session lifecycle](PHASE_14_LOCAL_SESSION_LIFECYCLE_ACCEPTANCE_REPORT.md)
- Phase 15: [local API security boundaries](PHASE_15_LOCAL_API_SECURITY_BOUNDARIES_ACCEPTANCE_REPORT.md)
- Phase 16: [offline GitHub Actions gate](PHASE_16_GITHUB_ACTIONS_GATE_ACCEPTANCE_REPORT.md)

## Interpretation rules

- `PASS` means only the named gate passed under the stated environment.
- `LOCAL_HOST_TEST` is not CI, physical-device, or production evidence.
- Hosted CI does not prove the local Podman/WSL2 hostile-fixture results.
- AFE simulation or bench-labeled upstream data is not ForgeGate hardware proof.
- Planned MSP430 compatibility remains unimplemented until its public artifact
  contract is frozen and aligned in this project context.
- Historical failures and corrections remain part of the record.
