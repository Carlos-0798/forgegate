from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
from pathlib import Path

from build_windows_delivery import build_windows_delivery
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SDIST_PATHS = (
    "tools/build_windows_delivery.py",
    "tests/test_windows_delivery_build.py",
    "tests/test_release_smoke.py",
    "tests/test_workspace_init.py",
    "schemas/forgegate.workspace-initialization.v1.schema.json",
    "schemas/forgegate.workspace-adoption-preflight.v1.schema.json",
    "tests/test_adoption_preflight.py",
    "tools/adoption_preflight_smoke.py",
    "docs/DASHBOARD_RECOVERY_REHEARSAL_REVIEW.md",
    "reports/PHASE_45_RECOVERY_REHEARSAL_REVIEW_ACCEPTANCE.md",
    "reports/PHASE_45_RECOVERY_REHEARSAL_REVIEW_EVIDENCE.json",
    "schemas/forgegate.recovery-rehearsal-review.v1.schema.json",
    "docs/DASHBOARD_RECOVERY_HANDOFF.md",
    "reports/PHASE_43_RECOVERY_HANDOFF_ACCEPTANCE.md",
    "reports/PHASE_43_RECOVERY_HANDOFF_ACCEPTANCE.json",
    "schemas/forgegate.recovery-rehearsal.v1.schema.json",
    "tests/test_recovery_rehearsal.py",
    "docs/RECOVERY_REHEARSAL.md",
    "schemas/forgegate.recovery-readiness-handoff.v1.schema.json",
    "tests/test_dashboard_recovery.py",
    "frontend/tests/recovery.test.mjs",
    "tests/test_job_capacity.py",
    "docs/JOB_CAPACITY.md",
    "schemas/forgegate.workspace-recovery-readiness.v1.schema.json",
    "tests/test_recovery_readiness.py",
    "docs/RECOVERY_READINESS.md",
    "reports/PHASE_42_RECOVERY_READINESS_ACCEPTANCE.md",
    "schemas/forgegate.job-capacity.v1.schema.json",
    "schemas/forgegate.job-project-usage.v1.schema.json",
    "reports/PHASE_41_JOB_CAPACITY_ACCEPTANCE.md",
    "reports/PHASE_41_JOB_CAPACITY_ACCEPTANCE.json",
    "tools/workspace_backups_smoke.py",
    "tests/test_workspace_backups.py",
    "tests/test_job_archival.py",
    "docs/JOB_ARCHIVAL.md",
    "schemas/forgegate.job-archive-plan.v1.schema.json",
    "schemas/forgegate.job-archive-receipt.v1.schema.json",
    "schemas/forgegate.workspace-backup.v2.schema.json",
    "docs/WORKSPACE_RECOVERY.md",
    "schemas/forgegate.workspace-backup.v1.schema.json",
    "reports/PHASE_37_JOB_RESULT_HANDOFF_ACCEPTANCE.md",
    "reports/PHASE_37_JOB_RESULT_HANDOFF_EVIDENCE.json",
    "tests/test_dashboard_job_result_handoff.py",
    "frontend/tests/job-result-handoff.test.mjs",
    "docs/assets/phase37-job-result-actions.jpg",
    "docs/assets/phase37-assembly-download-review.jpg",
    "docs/assets/phase37-evidence-binding-result.jpg",
    "docs/assets/phase37-bound-evidence.jpg",
    "reports/PHASE_36_DASHBOARD_JOB_SUBMISSION_ACCEPTANCE.md",
    "reports/PHASE_36_DASHBOARD_JOB_SUBMISSION_EVIDENCE.json",
    "tests/test_dashboard_job_submission.py",
    "frontend/tests/job-submission.test.mjs",
    "docs/assets/phase36-submit-review.png",
    "docs/assets/phase36-task-result.png",
    "docs/assets/phase36-combined-result.png",
    "docs/assets/phase36-retained-warnings.png",
    "reports/PHASE_35_DASHBOARD_JOBS_ACCEPTANCE.md",
    "reports/PHASE_35_DASHBOARD_JOBS_EVIDENCE.json",
    "docs/DASHBOARD_JOBS.md",
    "docs/assets/phase35-job-result.png",
    "docs/assets/phase35-job-cancelled.png",
    "docs/assets/phase35-job-recovered.png",
    "docs/assets/phase35-job-conflict.png",
    "tools/manual_dashboard_jobs.py",
    "tests/test_dashboard_jobs.py",
    "frontend/tests/jobs.test.mjs",
    "reports/PHASE_34_COLLECTION_JOBS_ACCEPTANCE.md",
    "reports/PHASE_34_COLLECTION_JOB_SMOKE.json",
    "docs/COLLECTION_JOBS.md",
    "tools/collection_jobs_smoke.py",
    "tests/test_collection_jobs.py",
    "schemas/forgegate.collection-job-request.v1.schema.json",
    "schemas/forgegate.collection-job.v1.schema.json",
    "schemas/forgegate.collection-job.v2.schema.json",
    "schemas/forgegate.collection-job-result.v1.schema.json",
    "reports/PHASE_38_JOB_EXECUTION_LIFECYCLE_ACCEPTANCE.md",
    "reports/PHASE_38_JOB_EXECUTION_LIFECYCLE_EVIDENCE.json",
    "reports/PHASE_33_MULTI_REPORT_ACCEPTANCE.md",
    "docs/assets/forgegate-dashboard-multi-report-bound.jpg",
    "docs/assets/forgegate-dashboard-multi-report-decision.jpg",
    "docs/assets/forgegate-dashboard-multi-report-rules.jpg",
    "frontend/tests/multi-collection.test.mjs",
    "tests/test_dashboard_multi_collection.py",
    "examples/dashboard-multi-report/forgegate.yaml",
    "examples/dashboard-multi-report/policies/pull-request.yaml",
    "examples/dashboard-multi-report/tests.xml",
    "examples/dashboard-multi-report/coverage.xml",
    "examples/dashboard-multi-report/coverage-low.xml",
    "examples/dashboard-multi-report/coverage.info",
    "docs/STORE_BACKUP_OPERATIONS.md",
    "tests/test_store_backups.py",
    "tools/start_dashboard.ps1",
    "tools/dashboard_runtime_smoke.py",
    "tools/dashboard_pair_smoke.py",
    "tests/test_dashboard_startup.py",
    "tests/test_dashboard_runtime.py",
    "docs/WINDOWS_DASHBOARD_OPERATIONS.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "package.json",
    "pnpm-lock.yaml",
    "frontend/index.html",
    "frontend/src/main.ts",
    "frontend/src/styles.css",
    "frontend/src/vite-env.d.ts",
    "frontend/tsconfig.json",
    "frontend/vite.config.ts",
    "docs/README.md",
    "docs/DEMO.md",
    "docs/PROJECT_STATUS.md",
    "docs/ROADMAP.md",
    "docs/VERIFICATION_MATRIX.md",
    "docs/DASHBOARD_ACCEPTANCE_MATRIX.md",
    "docs/PORTFOLIO_EVIDENCE.md",
    "docs/DASHBOARD_COLLECTION_CONTRACT.md",
    "docs/assets/forgegate-dashboard-junit-import-form.jpg",
    "examples/dashboard-junit/forgegate.yaml",
    "examples/dashboard-junit/policies/pull-request.yaml",
    "examples/dashboard-junit/pass.xml",
    "examples/dashboard-junit/fail.xml",
    "examples/dashboard-junit/warning.xml",
    "examples/dashboard-junit/rejected.xml",
    "frontend/tests/collection.test.mjs",
    "tools/manual_dashboard_collection.py",
    "docs/assets/forgegate-cli-demo.svg",
    "docs/assets/forgegate-dashboard-alpha.jpg",
    "docs/assets/forgegate-dashboard-candidate-detail.jpg",
    "docs/assets/forgegate-dashboard-candidates.jpg",
    "docs/assets/forgegate-dashboard-overview.jpg",
    "docs/assets/forgegate-dashboard-validation-error.jpg",
    "docs/assets/forgegate-dashboard-msp430-live-status.png",
    "docs/assets/forgegate-dashboard-msp430-decoded-faults.jpg",
    "docs/assets/forgegate-dashboard-evidence-review.jpg",
    "docs/assets/forgegate-dashboard-decision-review.jpg",
    "docs/assets/forgegate-dashboard-assurance-review.jpg",
    "docs/assets/forgegate-dashboard-reviewed-workflow-pass.jpg",
    "docs/assets/forgegate-dashboard-reviewed-workflow-decision.jpg",
    "docs/assets/forgegate-dashboard-reviewed-workflow-assurance.jpg",
    "docs/assets/forgegate-dashboard-zoom-100.jpg",
    "docs/assets/forgegate-dashboard-zoom-125.jpg",
    "docs/assets/forgegate-dashboard-zoom-150.jpg",
    "docs/assets/forgegate-dashboard-zoom-175.jpg",
    "docs/assets/forgegate-dashboard-zoom-200.jpg",
    "docs/assets/forgegate-dashboard-zoom-200-dialog.jpg",
    "docs/architecture/ARTIFACT_AND_JUNIT_SLICE.md",
    "docs/architecture/BENCHMARK_JSON_COLLECTOR.md",
    "docs/architecture/COVERAGE_COLLECTORS.md",
    "docs/architecture/DOMAIN_MODEL.md",
    "docs/architecture/SARIF_COLLECTOR.md",
    "docs/architecture/POLICY_ENGINE.md",
    "docs/architecture/CANDIDATE_LIFECYCLE.md",
    "docs/architecture/SQLITE_CANDIDATE_STORE.md",
    "docs/architecture/ATTESTATIONS.md",
    "docs/architecture/ANALOG_VALIDATION_COLLECTOR.md",
    "docs/architecture/MSP430_VALIDATION_COLLECTOR.md",
    "docs/architecture/EVIDENCE_BUNDLE_ASSEMBLY.md",
    "docs/architecture/CANDIDATE_EVIDENCE_BINDING.md",
    "docs/architecture/LOCAL_REST_API.md",
    "docs/architecture/LOCAL_REST_COMMAND_WORKFLOW.md",
    "docs/architecture/LOCAL_WEB_DASHBOARD.md",
    "docs/architecture/PROJECT_REGISTRY_AND_AUDIT_QUERY.md",
    "docs/architecture/PROJECT_AUTHORITY_AND_DISCOVERY.md",
    "docs/architecture/PROJECT_PROFILE_REVISIONS.md",
    "docs/architecture/POLICY_MATERIALIZATION.md",
    "tests/test_policy_material_reuse_migration.py",
    "docs/assets/forgegate-dashboard-junit-fail-decision.jpg",
    "docs/assets/forgegate-dashboard-junit-pass-decision.jpg",
    "docs/assets/forgegate-dashboard-junit-warning-consent.jpg",
    "docs/assets/forgegate-dashboard-junit-rejected.jpg",
    "docs/assets/forgegate-dashboard-shared-policy-error.jpg",
    "docs/architecture/PORTABLE_ASSURANCE_BUNDLES.md",
    "docs/architecture/AUTHENTICATED_ASSURANCE_IDENTITY.md",
    "docs/architecture/AUTHENTICATED_LOCAL_API.md",
    "docs/architecture/LOCAL_SESSION_LIFECYCLE.md",
    "docs/architecture/GITHUB_ACTIONS_GATE.md",
    "docs/architecture/PLUGIN_SDK_DISCOVERY.md",
    "docs/architecture/PLUGIN_EXECUTION_SECURITY_CONTRACT.md",
    "docs/architecture/WINDOWS_PLUGIN_SANDBOX.md",
    "docs/architecture/PRODUCTION_PLUGIN_BROKER.md",
    "docs/architecture/PLUGIN_OPERATOR_WORKFLOW.md",
    "docs/architecture/WINDOWS_ALPHA_DELIVERY.md",
    "docs/product/DASHBOARD_UX_REQUIREMENTS.md",
    "docs/security/DASHBOARD_THREAT_MODEL.md",
    "src/forgegate/dashboard/static/asset-inventory.json",
    "src/forgegate/dashboard/static/index.html",
    "src/forgegate/dashboard/static/third-party-licenses.json",
    "examples/sample-python-api/artifacts/junit.xml",
    "examples/sample-python-api/artifacts/junit-pass.xml",
    "examples/sample-python-api/artifacts/benchmark.json",
    "examples/sample-python-api/artifacts/security.sarif",
    "examples/sample-python-api/artifacts/coverage.info",
    "examples/sample-python-api/artifacts/coverage.xml",
    "examples/sample-python-api/artifacts/analog-validation-result.json",
    "examples/msp430-validation/artifacts/phase6-soak-report.json",
    "examples/sample-python-api/forgegate.yaml",
    "examples/plugin-sdk/sample-collector-plugin/pyproject.toml",
    "examples/plugin-sdk/sample-collector-plugin/README.md",
    "examples/plugin-sdk/sample-collector-plugin/src/forgegate_sample_collector/__init__.py",
    "examples/plugin-sdk/sample-collector-plugin/src/forgegate_sample_collector/runtime.py",
    "examples/plugin-sdk/sample-collector-plugin/src/forgegate_sample_collector/forgegate-plugin.json",
    "examples/sample-python-api/evidence/pass-bundle.json",
    "examples/sample-python-api/evidence/fail-bundle.json",
    "examples/sample-python-api/candidates/draft.json",
    "examples/sample-python-api/candidates/evaluating.json",
    "examples/sample-python-api/github-action-fixture/assurance-dbb54d911ff973918e1e89e52c4d58785ee6b8cb3f43e6f76c946c0a6ae605c9/assurance-bundle.json",
    "examples/sample-python-api/github-action-fixture/assurance-dbb54d911ff973918e1e89e52c4d58785ee6b8cb3f43e6f76c946c0a6ae605c9/manifest.json",
    "examples/sample-python-api/github-action-fixture/assurance-dbb54d911ff973918e1e89e52c4d58785ee6b8cb3f43e6f76c946c0a6ae605c9/README.md",
    "reports/PHASE_1_JUNIT_SLICE_ACCEPTANCE_REPORT.md",
    "reports/README.md",
    "reports/PHASE_1_COVERAGE_SLICE_ACCEPTANCE_REPORT.md",
    "reports/PHASE_1_BENCHMARK_SLICE_ACCEPTANCE_REPORT.md",
    "reports/PHASE_1_SARIF_SLICE_ACCEPTANCE_REPORT.md",
    "reports/PHASE_2_POLICY_ENGINE_ACCEPTANCE_REPORT.md",
    "reports/PHASE_2_CANDIDATE_LIFECYCLE_ACCEPTANCE_REPORT.md",
    "reports/PHASE_2_SQLITE_CANDIDATE_STORE_ACCEPTANCE_REPORT.md",
    "reports/PHASE_2_ATTESTATION_ACCEPTANCE_REPORT.md",
    "reports/PHASE_3_ANALOG_VALIDATION_COMPATIBILITY_ACCEPTANCE_REPORT.md",
    "reports/PHASE_4_EVIDENCE_BUNDLE_ASSEMBLY_ACCEPTANCE_REPORT.md",
    "reports/PHASE_4_CANDIDATE_EVIDENCE_BINDING_ACCEPTANCE_REPORT.md",
    "reports/PHASE_5_LOCAL_REST_API_BASELINE_ACCEPTANCE_REPORT.md",
    "reports/PHASE_6_LOCAL_REST_COMMAND_WORKFLOW_ACCEPTANCE_REPORT.md",
    "reports/PHASE_7_PROJECT_REGISTRY_AUDIT_QUERY_ACCEPTANCE_REPORT.md",
    "reports/PHASE_8_PROJECT_AUTHORITY_DISCOVERY_ACCEPTANCE_REPORT.md",
    "reports/PHASE_9_PROJECT_PROFILE_REVISIONS_ACCEPTANCE_REPORT.md",
    "reports/PHASE_10_POLICY_MATERIALIZATION_ACCEPTANCE_REPORT.md",
    "reports/PHASE_11_PORTABLE_ASSURANCE_BUNDLE_ACCEPTANCE_REPORT.md",
    "reports/PHASE_12_AUTHENTICATED_IDENTITY_FOUNDATION_ACCEPTANCE_REPORT.md",
    "reports/PHASE_13_AUTHENTICATED_LOCAL_API_ACCEPTANCE_REPORT.md",
    "reports/PHASE_14_LOCAL_SESSION_LIFECYCLE_ACCEPTANCE_REPORT.md",
    "reports/PHASE_15_LOCAL_API_SECURITY_BOUNDARIES_ACCEPTANCE_REPORT.md",
    "reports/PHASE_16_GITHUB_ACTIONS_GATE_ACCEPTANCE_REPORT.md",
    "reports/PHASE_17_PLUGIN_SDK_DISCOVERY_ACCEPTANCE_REPORT.md",
    "reports/PHASE_18_WINDOWS_SANDBOX_READINESS_REPORT.md",
    "reports/PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json",
    "reports/PHASE_19_WINDOWS_SANDBOX_LIVE_VERIFICATION_REPORT.md",
    "reports/PHASE_20_PRODUCTION_PLUGIN_BROKER_ACCEPTANCE_REPORT.md",
    "reports/PHASE_20_WINDOWS_PLUGIN_BROKER_LIVE_EVIDENCE.json",
    "reports/PHASE_21_PLUGIN_OPERATOR_WORKFLOW_ACCEPTANCE_REPORT.md",
    "reports/PHASE_22_WINDOWS_ALPHA_ACCEPTANCE_REPORT.md",
    "reports/PHASE_22_WINDOWS_ALPHA_LIVE_EVIDENCE.json",
    "reports/PHASE_23_LOCAL_WEB_DASHBOARD_DESIGN_GATE.md",
    "reports/PHASE_24_AUTHENTICATED_LOCAL_DASHBOARD_ACCEPTANCE_REPORT.md",
    "reports/PHASE_24_MANUAL_INTERACTION_ACCEPTANCE_2026-09-04.md",
    "reports/PHASE_25_MSP430_LIVE_STATUS_ACCEPTANCE_REPORT.md",
    "reports/PHASE_25_MSP430_LIVE_STATUS_EVIDENCE_2026-09-05.json",
    "reports/MSP430_MANUAL_UNPLUG_REPLUG_EVIDENCE_2026-09-05.json",
    "reports/PHASE_26_DASHBOARD_ASSURANCE_REVIEW_ACCEPTANCE_REPORT.md",
    "reports/DASHBOARD_ASSURANCE_REVIEW_EVIDENCE_2026-09-05.json",
    "reports/DASHBOARD_PHASE27_INTERACTION_EVIDENCE_2026-09-05.json",
    "reports/PHASE_27_DASHBOARD_WRITE_AND_MSP430_COLLECTOR_ACCEPTANCE_REPORT.md",
    "reports/DASHBOARD_PORTFOLIO_CAPTURE_EVIDENCE_2026-09-04.json",
    "reports/SOFTWARE_INTEGRITY_INTERACTION_AUDIT_2026-09-03.md",
    "reports/SOFTWARE_INTEGRITY_INTERACTION_LIVE_EVIDENCE.json",
    "requirements/dev-constraints.txt",
    "schemas/forgegate.project.v1.schema.json",
    "schemas/forgegate.policy-evaluation.v1.schema.json",
    "schemas/forgegate.policy-evaluation.v2.schema.json",
    "schemas/forgegate.policy-material.v1.schema.json",
    "schemas/forgegate.assurance-bundle.v1.schema.json",
    "schemas/forgegate.assurance-bundle-manifest.v1.schema.json",
    "schemas/forgegate.assurance-signature.v1.schema.json",
    "schemas/forgegate.signing-identity.v1.schema.json",
    "schemas/forgegate.trust-store.v1.schema.json",
    "schemas/forgegate.release-candidate.v1.schema.json",
    "schemas/forgegate.release-candidate.v2.schema.json",
    "schemas/forgegate.candidate-transition.v1.schema.json",
    "schemas/forgegate.candidate-transition-result.v1.schema.json",
    "schemas/forgegate.release-attestation.v1.schema.json",
    "schemas/forgegate.evidence-bundle-assembly.v1.schema.json",
    "schemas/forgegate.candidate-evidence-binding.v1.schema.json",
    "schemas/forgegate.registered-project.v1.schema.json",
    "schemas/forgegate.registered-project-page.v1.schema.json",
    "schemas/forgegate.project-profile-revision.v1.schema.json",
    "schemas/forgegate.project-profile-page.v1.schema.json",
    "schemas/forgegate.release-candidate-page.v1.schema.json",
    "schemas/forgegate.audit-event.v1.schema.json",
    "schemas/forgegate.audit-event-page.v1.schema.json",
    "schemas/forgegate.audit-actor.v1.schema.json",
    "schemas/forgegate.api-security-event.v1.schema.json",
    "schemas/forgegate.api-security-event-page.v1.schema.json",
    "schemas/forgegate.github-action-report.v1.schema.json",
    "schemas/forgegate.plugin-manifest.v1.schema.json",
    "schemas/forgegate.plugin-discovery.v1.schema.json",
    "schemas/forgegate.plugin-run-plan.v1.schema.json",
    "schemas/forgegate.plugin-protocol-message.v1.schema.json",
    "schemas/forgegate.plugin-run-transition.v1.schema.json",
    "schemas/forgegate.plugin-run-result.v1.schema.json",
    "schemas/forgegate.plugin-output.v1.schema.json",
    "schemas/forgegate.plugin-run-receipt.v1.schema.json",
    "schemas/forgegate.plugin-run-record.v1.schema.json",
    "schemas/forgegate.plugin-run-page.v1.schema.json",
    "schemas/forgegate.initialization-report.v1.schema.json",
    "schemas/forgegate.windows-plugin-sandbox-capability.v1.schema.json",
    "schemas/forgegate.openapi.v1.json",
    "schemas/forgegate.dashboard-openapi.v1.json",
    "schemas/forgegate.benchmark.v1.schema.json",
    "schemas/analog-validation.result-export.v1.schema.json",
    "schemas/forgegate.msp430-validation-report.v1.schema.json",
    "tests/test_models.py",
    "tests/test_bootstrap.py",
    "tests/test_plugin_workflow.py",
    "tests/golden/junit_summary.json",
    "tests/golden/benchmark_metrics.json",
    "tests/golden/analog_validation_result.json",
    "tests/golden/evidence_bundle_assembly.json",
    "tests/golden/candidate_evidence_binding.json",
    "tests/golden/coverage_xml.json",
    "tests/golden/lcov_summary.json",
    "tests/golden/policy_pass.json",
    "tests/golden/policy_fail.json",
    "tests/golden/candidate_collecting_transition.json",
    "tests/golden/candidate_pass_transition.json",
    "tests/golden/release_attestation_pass.json",
    "tests/golden/release_attestation_pass.md",
    "tests/golden/sarif_summary.json",
    "tools/interaction_smoke.py",
    "tools/verify.py",
    "tools/verify_windows_alpha.ps1",
    "tests/test_candidate_lifecycle.py",
    "tests/test_candidate_store.py",
    "tests/test_candidate_store_cli.py",
    "tests/test_attestations.py",
    "tests/test_analog_validation_collector.py",
    "tests/test_msp430_validation_collector.py",
    "tests/test_evidence_assembly.py",
    "tests/test_candidate_evidence_binding.py",
    "tests/test_application.py",
    "tests/test_api.py",
    "tests/test_project_registry_audit.py",
    "tests/test_project_authority_discovery.py",
    "tests/test_project_profile_revisions.py",
    "tests/test_policy_materialization.py",
    "tests/test_assurance_bundle.py",
    "tests/test_identity_signatures.py",
    "tests/test_plugins.py",
    "tests/test_plugin_execution_models.py",
    "tests/test_plugin_broker.py",
    "tests/test_windows_plugin_sandbox.py",
    "tests/test_windows_sandbox_live_tool.py",
    "tests/test_windows_plugin_broker_live_tool.py",
    "tests/test_dashboard.py",
    "tests/test_dashboard_client.py",
    "tests/test_msp430_live_status.py",
    "tools/dashboard_assets.py",
    "tools/verify_windows_sandbox_live.py",
    "tools/verify_windows_plugin_broker_live.py",
)
FORBIDDEN_SDIST_PREFIXES = (
    "examples/plugin-sdk/sample-collector-plugin/build/",
    "examples/plugin-sdk/sample-collector-plugin/src/forgegate_sample_collector_plugin.egg-info/",
)


def run(
    command: list[str],
    *,
    cwd: Path = REPOSITORY_ROOT,
    expected_returncode: int = 0,
) -> None:
    print(f"\n> {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != expected_returncode:
        raise SystemExit(f"command returned {completed.returncode}; expected {expected_returncode}")


def run_capture(command: list[str], output: Path, *, cwd: Path) -> None:
    print(f"\n> {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if completed.stdout:
        print(completed.stdout, end="", flush=True)
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr, flush=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    output.write_text(completed.stdout, encoding="utf-8")


def clean_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def smoke_workspace_initialization(python: Path, root: Path) -> None:
    """Exercise first use from the installed wheel without repository fixtures."""
    workspace = root / "first-use-workspace"
    receipt_path = root / "workspace-initialization.json"
    command = [
        str(python),
        "-m",
        "forgegate",
        "workspace-init",
        str(workspace),
        "--project-id",
        "release-demo",
        "--demo",
    ]
    run_capture(command, receipt_path, cwd=root)
    receipt_text = receipt_path.read_text(encoding="utf-8")
    receipt = json.loads(receipt_text)
    if (
        receipt["schema_version"] != "forgegate.workspace-initialization.v1"
        or receipt["project_id"] != "release-demo"
        or receipt["status"] != "INITIALIZED"
        or receipt["service"] != "NOT_STARTED"
        or receipt["browser_session"] != "NOT_ACTIVATED"
        or receipt["hardware_access"] != "NOT_PERFORMED"
        or receipt["private_key"] != "operator-key.pem"
        or {case["decision"] for case in receipt["demo_cases"]} != {"PASS", "FAIL"}
        or len(receipt["demo_cases"]) != 2
        or any(
            case["evidence_origin"] != "SYNTHETIC" or case["verification_level"] != "declared"
            for case in receipt["demo_cases"]
        )
    ):
        raise SystemExit("installed workspace initialization returned an unexpected receipt")
    machine_paths = (str(root), root.as_posix(), json.dumps(str(root))[1:-1])
    if "PRIVATE KEY" in receipt_text or any(path in receipt_text for path in machine_paths):
        raise SystemExit("workspace receipt exposed private key bytes or a machine path")
    for relative in (
        "operator-key.pem",
        "identity.json",
        "trust-store.json",
        "forgegate.db",
        "jobs.db",
        "START_HERE.md",
        "artifacts/synthetic-demo-pass.xml",
        "artifacts/synthetic-demo-fail.xml",
        "artifacts/synthetic-demo-pass-collection.json",
        "artifacts/synthetic-demo-fail-collection.json",
    ):
        if not (workspace / relative).is_file() or (workspace / relative).stat().st_size == 0:
            raise SystemExit(f"installed workspace is missing a generated file: {relative}")
    if json.loads((workspace / "workspace.json").read_text(encoding="utf-8")) != receipt:
        raise SystemExit("workspace completion marker differs from the CLI receipt")
    for relative in (
        "workspace.json",
        "forgegate.yaml",
        "policies/pull-request.yaml",
        "identity.json",
        "trust-store.json",
    ):
        run(
            [str(python), "-m", "forgegate", "validate-config", str(workspace / relative)],
            cwd=root,
        )
    run(
        [
            str(python),
            "-c",
            (
                "import sys; from pathlib import Path; "
                "from forgegate.identity import load_identity_document, "
                "load_ed25519_private_key, derive_signing_identity; "
                "root=Path(sys.argv[1]); "
                "key=load_ed25519_private_key(root/'operator-key.pem'); "
                "identity=load_identity_document(root/'identity.json'); "
                "trust=load_identity_document(root/'trust-store.json'); "
                "assert derive_signing_identity(key, display_name=identity.display_name) "
                "== identity; "
                "assert len(trust.identities)==1 and trust.identities[0].identity==identity; "
                "assert [r.value for r in trust.identities[0].roles]==['operator']; "
                "assert trust.identities[0].project_ids==('release-demo',)"
            ),
            str(workspace),
        ],
        cwd=root,
    )
    retained_hashes = {
        path.relative_to(workspace).as_posix(): sha256(path)
        for path in workspace.rglob("*")
        if path.is_file()
    }
    run(command, cwd=root, expected_returncode=3)
    if retained_hashes != {
        path.relative_to(workspace).as_posix(): sha256(path)
        for path in workspace.rglob("*")
        if path.is_file()
    }:
        raise SystemExit("duplicate workspace initialization changed retained files")
    second_workspace = root / "second-first-use-workspace"
    second_receipt = root / "second-workspace-initialization.json"
    run_capture(
        [str(python), "-m", "forgegate", "workspace-init", str(second_workspace)],
        second_receipt,
        cwd=root,
    )
    second = json.loads(second_receipt.read_text(encoding="utf-8"))
    if (
        second["demo_cases"]
        or second["operator_identity_id"] == receipt["operator_identity_id"]
        or sha256(second_workspace / "operator-key.pem") == sha256(workspace / "operator-key.pem")
    ):
        raise SystemExit("fresh workspace reused signing identity or seeded unsolicited evidence")
    print("\nInstalled first-use workspace: PASS", flush=True)


def verify_sdist(sdist: Path) -> None:
    with tarfile.open(sdist, "r:gz") as archive:
        members = {member.name for member in archive.getmembers() if member.isfile()}
    missing = [
        required
        for required in REQUIRED_SDIST_PATHS
        if not any(member.endswith(f"/{required}") for member in members)
    ]
    if missing:
        raise SystemExit("sdist is missing required paths: " + ", ".join(missing))
    payload_paths = {member.split("/", maxsplit=1)[1] for member in members if "/" in member}
    forbidden = sorted(
        path
        for path in payload_paths
        if any(path.startswith(prefix) for prefix in FORBIDDEN_SDIST_PREFIXES)
    )
    if forbidden:
        raise SystemExit("sdist contains build residue: " + ", ".join(forbidden))
    print("\nSource distribution manifest: PASS", flush=True)


def main(
    *,
    windows_live_broker: bool = False,
    live_output: Path | None = None,
    sandbox_evidence: Path | None = None,
    podman: Path | None = None,
) -> int:
    if windows_live_broker and (live_output is None or sandbox_evidence is None):
        raise SystemExit("live broker smoke requires output and sandbox evidence paths")
    with tempfile.TemporaryDirectory(prefix="forgegate-release-") as temporary:
        root = Path(temporary)
        dist = root / "dist"
        build_windows_delivery(dist)

        plugin_dist = root / "plugin-dist"
        plugin_source = root / "sample-collector-plugin"
        shutil.copytree(
            REPOSITORY_ROOT / "examples/plugin-sdk/sample-collector-plugin",
            plugin_source,
            ignore=shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__"),
        )
        run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(plugin_dist)],
            cwd=plugin_source,
        )

        wheels = list(dist.glob("*.whl"))
        sdists = list(dist.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise SystemExit("release build must produce exactly one wheel and one sdist")
        wheel = wheels[0]
        sdist = sdists[0]
        plugin_wheels = list(plugin_dist.glob("*.whl"))
        if len(plugin_wheels) != 1:
            raise SystemExit("sample plugin build must produce exactly one wheel")
        plugin_wheel = plugin_wheels[0]
        verify_sdist(sdist)

        environment = root / "clean-environment"
        venv.EnvBuilder(with_pip=True, clear=False).create(environment)
        python = clean_python(environment)
        run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--upgrade",
                "-c",
                str(REPOSITORY_ROOT / "requirements/dev-constraints.txt"),
                "pip",
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                str(wheel),
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-c",
                (
                    "from pathlib import Path; "
                    "import forgegate.dashboard.assets as assets; "
                    "root = Path(assets.__file__).resolve().parent / 'static'; "
                    "inventory = assets.validate_dashboard_assets(root); "
                    "assert len(inventory.assets) >= 5"
                ),
            ],
            cwd=root,
        )
        empty_plugin_report = root / "plugins-empty.json"
        run_capture(
            [str(python), "-m", "forgegate", "plugins", "list"],
            empty_plugin_report,
            cwd=root,
        )
        if json.loads(empty_plugin_report.read_text(encoding="utf-8"))["total"] != 0:
            raise SystemExit("clean ForgeGate wheel unexpectedly discovered a plugin")
        run(
            [
                str(python),
                "-c",
                (
                    "import importlib.util; "
                    "assert importlib.util.find_spec('serial') is None; "
                    "from forgegate.compatibility.msp430_live import crc16_ccitt_false; "
                    "assert crc16_ccitt_false(b'123456789') == 0x29B1"
                ),
            ],
            cwd=root,
        )
        sandbox_report = root / "windows-sandbox-capability.json"
        run_capture(
            [str(python), "-m", "forgegate", "plugins", "sandbox-status"],
            sandbox_report,
            cwd=root,
        )
        sandbox_payload = json.loads(sandbox_report.read_text(encoding="utf-8"))
        if (
            sandbox_payload["external_plugin_execution"] != "PROHIBITED"
            or sandbox_payload["advertised_isolation_tier"] != "NONE"
        ):
            raise SystemExit("installed sandbox probe advertised unverified execution")
        run(
            [str(python), "-m", "forgegate", "validate-config", str(sandbox_report)],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                str(plugin_wheel),
            ],
            cwd=root,
        )
        plugin_report = root / "plugins-installed.json"
        run_capture(
            [str(python), "-m", "forgegate", "plugins", "list"],
            plugin_report,
            cwd=root,
        )
        installed_plugin = json.loads(plugin_report.read_text(encoding="utf-8"))
        if (
            installed_plugin["total"] != 1
            or installed_plugin["compatible"] != 1
            or installed_plugin["plugins"][0]["plugin_id"] != "example.forgegate-sample-collector"
            or installed_plugin["plugins"][0]["execution"] != "NOT_LOADED"
        ):
            raise SystemExit("installed sample plugin was not discovered safely")
        run(
            [str(python), "-m", "forgegate", "validate-config", str(plugin_report)],
            cwd=root,
        )
        if windows_live_broker:
            assert live_output is not None and sandbox_evidence is not None
            live_command = [
                str(python),
                str(REPOSITORY_ROOT / "tools/verify_windows_plugin_broker_live.py"),
                "--sandbox-evidence",
                str(sandbox_evidence.resolve(strict=True)),
                "--output",
                str(live_output.resolve(strict=False)),
            ]
            if podman is not None:
                live_command.extend(("--podman", str(podman.resolve(strict=True))))
            run(live_command, cwd=root)
            live_report = json.loads(live_output.read_text(encoding="utf-8"))
            live_report["forgegate_installation"] = "CLEAN_WHEEL"
            live_report.pop("verification_id", None)
            live_report["verification_id"] = (
                "sha256:"
                + hashlib.sha256(
                    json.dumps(
                        live_report,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest()
            )
            live_output.write_text(
                json.dumps(live_report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        run(
            [
                str(python),
                "-m",
                "pip",
                "uninstall",
                "--yes",
                "forgegate-sample-collector-plugin",
            ],
            cwd=root,
        )
        removed_plugin_report = root / "plugins-removed.json"
        run_capture(
            [str(python), "-m", "forgegate", "plugins", "list"],
            removed_plugin_report,
            cwd=root,
        )
        if json.loads(removed_plugin_report.read_text(encoding="utf-8"))["total"] != 0:
            raise SystemExit("sample plugin remained discoverable after uninstall")
        run(
            [
                str(python),
                "-c",
                "from importlib.metadata import version; import forgegate; "
                "assert version('forgegate') == forgegate.__version__",
            ],
            cwd=root,
        )
        initialized_project = root / "initialized-project"
        initialization_report = root / "initialization-report.json"
        run_capture(
            [
                str(python),
                "-m",
                "forgegate",
                "init",
                str(initialized_project),
                "--project-id",
                "release-smoke",
                "--project-name",
                "Release Smoke",
            ],
            initialization_report,
            cwd=root,
        )
        for initialized_document in (
            initialization_report,
            initialized_project / "forgegate.yaml",
            initialized_project / "policies/pull-request.yaml",
        ):
            run(
                [str(python), "-m", "forgegate", "validate-config", str(initialized_document)],
                cwd=root,
            )
        run(
            [str(python), "-m", "forgegate", "init", str(initialized_project)],
            cwd=root,
            expected_returncode=3,
        )
        smoke_workspace_initialization(python, root)
        assembly_root = root / "assembly-inputs"
        artifact_directory = assembly_root / "artifacts"
        artifact_directory.mkdir(parents=True)
        shutil.copyfile(
            REPOSITORY_ROOT / "examples/sample-python-api/artifacts/junit-pass.xml",
            artifact_directory / "junit-pass.xml",
        )
        shutil.copyfile(
            REPOSITORY_ROOT / "examples/sample-python-api/artifacts/benchmark.json",
            artifact_directory / "benchmark.json",
        )
        junit_collection = assembly_root / "junit.collection.json"
        benchmark_collection = assembly_root / "benchmark.collection.json"
        run_capture(
            [
                str(python),
                "-m",
                "forgegate",
                "collect-junit",
                "artifacts/junit-pass.xml",
                "--root",
                str(assembly_root),
                "--commit",
                "a" * 40,
                "--collected-at",
                "2026-08-30T20:30:00Z",
                "--source-tool",
                "pytest",
                "--source-version",
                "8.4.2",
                "--trust",
                "claimed_ci_metadata",
                "--verification-level",
                "ci_validated",
            ],
            junit_collection,
            cwd=root,
        )
        run_capture(
            [
                str(python),
                "-m",
                "forgegate",
                "collect-benchmark",
                "artifacts/benchmark.json",
                "--root",
                str(assembly_root),
                "--commit",
                "a" * 40,
                "--collected-at",
                "2026-08-30T20:30:00Z",
                "--trust",
                "claimed_ci_metadata",
                "--verification-level",
                "ci_validated",
            ],
            benchmark_collection,
            cwd=root,
        )
        assembly_path = assembly_root / "assembly.json"
        run_capture(
            [
                str(python),
                "-m",
                "forgegate",
                "assemble-evidence",
                junit_collection.name,
                benchmark_collection.name,
                "--root",
                str(assembly_root),
                "--commit",
                "a" * 40,
                "--generated-at",
                "2026-08-30T20:31:00Z",
            ],
            assembly_path,
            cwd=root,
        )
        exported_openapi = root / "forgegate.openapi.v1.json"
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "export-openapi",
                str(exported_openapi),
            ],
            cwd=root,
        )
        if (
            exported_openapi.read_bytes()
            != (REPOSITORY_ROOT / "schemas/forgegate.openapi.v1.json").read_bytes()
        ):
            raise SystemExit("installed wheel OpenAPI contract differs from committed contract")
        openapi = json.loads(exported_openapi.read_text(encoding="utf-8"))
        expected_operations = {
            ("/v1/auth/challenges", "post"): "createApiAuthChallenge",
            ("/v1/auth/session", "delete"): "logoutApiSession",
            ("/v1/auth/sessions", "post"): "createApiSession",
            ("/v1/auth/sessions/{session_id}", "delete"): "revokeApiSession",
            ("/v1/auth/trust-store/reload", "post"): "reloadApiTrustStore",
            ("/v1/projects", "post"): "registerProject",
            ("/v1/projects", "get"): "listProjects",
            ("/v1/projects/{project_id}", "get"): "getProject",
            ("/v1/projects/{project_id}/profile", "get"): "getCurrentProjectProfile",
            ("/v1/projects/{project_id}/revisions", "get"): "listProjectProfileRevisions",
            ("/v1/projects/{project_id}/revisions", "post"): "reviseProjectProfile",
            ("/v1/projects/{project_id}/candidates", "get"): "listProjectCandidates",
            ("/v1/audit-events", "get"): "queryAuditEvents",
            ("/v1/security-events", "get"): "queryApiSecurityEvents",
            ("/v1/candidates/{candidate_id}/transitions", "post"): "advanceCandidate",
            ("/v1/candidates/{candidate_id}/evidence", "post"): "bindCandidateEvidence",
            ("/v1/candidates/{candidate_id}/evaluate", "post"): "evaluateCandidate",
            ("/v1/candidates/{candidate_id}/policy", "get"): "getCandidatePolicyMaterial",
            ("/v1/candidates/{candidate_id}/attestation", "post"): "attestCandidate",
        }
        for (path, method), operation_id in expected_operations.items():
            if openapi["paths"][path][method]["operationId"] != operation_id:
                raise SystemExit(f"installed wheel is missing API operation: {operation_id}")
        exported_dashboard_openapi = root / "forgegate.dashboard-openapi.v1.json"
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "export-dashboard-openapi",
                str(exported_dashboard_openapi),
            ],
            cwd=root,
        )
        if (
            exported_dashboard_openapi.read_bytes()
            != (REPOSITORY_ROOT / "schemas/forgegate.dashboard-openapi.v1.json").read_bytes()
        ):
            raise SystemExit(
                "installed wheel Dashboard OpenAPI contract differs from committed contract"
            )
        dashboard_openapi = json.loads(exported_dashboard_openapi.read_text(encoding="utf-8"))
        dashboard_operations = {
            (
                "/app/api/recovery-rehearsal-review",
                "post",
            ): "reviewDashboardRecoveryRehearsal",
            (
                "/app/api/recovery-review",
                "post",
            ): "reviewDashboardRecoveryReadiness",
            (
                "/app/api/candidates/{candidate_id}/junit-preview",
                "post",
            ): "previewDashboardCandidateJUnit",
            (
                "/app/api/candidates/{candidate_id}/collection-preview",
                "post",
            ): "previewDashboardCandidateCollection",
            ("/app/api/candidates", "post"): "createDashboardCandidate",
            (
                "/app/api/candidates/{candidate_id}/transitions",
                "post",
            ): "advanceDashboardCandidate",
            (
                "/app/api/candidates/{candidate_id}/evidence",
                "post",
            ): "bindDashboardCandidateEvidence",
            (
                "/app/api/candidates/{candidate_id}/evaluate",
                "post",
            ): "evaluateDashboardCandidate",
            (
                "/app/api/candidates/{candidate_id}/attestation",
                "post",
            ): "attestDashboardCandidate",
        }
        for (path, method), operation_id in dashboard_operations.items():
            if dashboard_openapi["paths"][path][method]["operationId"] != operation_id:
                raise SystemExit(
                    f"installed wheel is missing Dashboard BFF operation: {operation_id}"
                )
        run(
            [
                str(python),
                "-c",
                "import base64; from datetime import datetime, timezone; "
                "from forgegate.dashboard.collection import "
                "DashboardJUnitPreviewRequest, preview_junit; "
                "r=preview_junit('fixture', DashboardJUnitPreviewRequest("
                "expected_revision=1, reported_commit='a'*40, "
                "content_base64=base64.b64encode(b'<testsuite tests=\"2\"/>').decode(), "
                "source_tool='installed-fixture', source_version='1', "
                "collected_at=datetime(2026,1,1,tzinfo=timezone.utc))); "
                "assert r.assembly is not None; "
                "assert r.collection.evidence[0].value['passed']==2; "
                "assert r.collection.evidence[0].verification_level=='declared'; "
                "assert r.persistence=='NOT_RETAINED'; print('installed JUnit preview: PASS')",
            ],
            cwd=root,
        )
        if (
            dashboard_openapi["paths"]["/app/api/live-status"]["get"]["operationId"]
            != "getDashboardLiveStatus"
        ):
            raise SystemExit("installed wheel is missing live-status BFF operation")
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "serve",
                "--database",
                str(root / "api-rejected.db"),
                "--trust-store",
                str(REPOSITORY_ROOT / "pyproject.toml"),
                "--host",
                "0.0.0.0",
            ],
            cwd=root,
            expected_returncode=3,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "validate-config",
                str(assembly_path),
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "collect-msp430-validation",
                "artifacts/phase6-soak-report.json",
                "--root",
                str(REPOSITORY_ROOT / "examples/msp430-validation"),
                "--commit",
                "0850241c1b2aa34704228146600501346ee81745",
                "--collected-at",
                "2026-09-05T18:30:00Z",
            ],
            cwd=root,
        )
        assembly_evaluation = assembly_root / "assembly.evaluation.json"
        run_capture(
            [
                str(python),
                "-m",
                "forgegate",
                "evaluate-policy",
                str(REPOSITORY_ROOT / "examples/sample-python-api/policies/pull-request.yaml"),
                str(assembly_path),
                "--evaluated-at",
                "2026-08-30T21:00:00Z",
            ],
            assembly_evaluation,
            cwd=root,
        )
        for bundle, expected_returncode in (("pass-bundle.json", 0), ("fail-bundle.json", 1)):
            run(
                [
                    str(python),
                    "-m",
                    "forgegate",
                    "evaluate-policy",
                    str(REPOSITORY_ROOT / "examples/sample-python-api/policies/pull-request.yaml"),
                    str(REPOSITORY_ROOT / "examples/sample-python-api/evidence" / bundle),
                    "--evaluated-at",
                    "2026-08-30T21:00:00Z",
                ],
                cwd=root,
                expected_returncode=expected_returncode,
            )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "create",
                "--project",
                "sample-api",
                "--version",
                "1.2.0",
                "--commit",
                "a" * 40,
                "--created-at",
                "2026-08-30T12:00:00Z",
            ],
            cwd=root,
        )
        candidate_store = root / "candidate-store.db"
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "init-store",
                str(candidate_store),
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "migrate-store",
                str(candidate_store),
            ],
            cwd=root,
        )
        unauthorized_create = [
            str(python),
            "-m",
            "forgegate",
            "candidate",
            "create",
            "--project",
            "sample-api",
            "--version",
            "1.2.0",
            "--commit",
            "a" * 40,
            "--created-at",
            "2026-08-30T12:00:00Z",
            "--database",
            str(candidate_store),
            "--idempotency-key",
            "create:release-smoke-unregistered",
        ]
        run(unauthorized_create, cwd=root, expected_returncode=3)
        project_register = [
            str(python),
            "-m",
            "forgegate",
            "project",
            "register",
            str(candidate_store),
            str(REPOSITORY_ROOT / "examples/sample-python-api/forgegate.yaml"),
            "--registered-at",
            "2026-08-30T11:59:00Z",
            "--idempotency-key",
            "project:release-smoke-001",
        ]
        run(project_register, cwd=root)
        run(project_register, cwd=root)
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "project",
                "list",
                str(candidate_store),
                "--limit",
                "1",
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "project",
                "show",
                str(candidate_store),
                "sample-api",
            ],
            cwd=root,
        )
        for project_command in ("current", "history"):
            run(
                [
                    str(python),
                    "-m",
                    "forgegate",
                    "project",
                    project_command,
                    str(candidate_store),
                    "sample-api",
                ],
                cwd=root,
            )
        persisted_create = [
            str(python),
            "-m",
            "forgegate",
            "candidate",
            "create",
            "--project",
            "sample-api",
            "--version",
            "1.2.0",
            "--commit",
            "a" * 40,
            "--created-at",
            "2026-08-30T12:00:00Z",
            "--track",
            "pull-request",
            "--database",
            str(candidate_store),
            "--idempotency-key",
            "create:release-smoke-001",
        ]
        persisted_candidate_path = root / "persisted-candidate.json"
        run_capture(persisted_create, persisted_candidate_path, cwd=root)
        persisted_candidate = json.loads(persisted_candidate_path.read_text(encoding="utf-8"))
        candidate_id = str(persisted_candidate["candidate_id"])
        if persisted_candidate["schema_version"] != "forgegate.release-candidate.v2":
            raise SystemExit("persisted candidate is not bound to a project profile")
        run(persisted_create, cwd=root)
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "list",
                str(candidate_store),
                "--project",
                "sample-api",
                "--limit",
                "1",
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "show",
                str(candidate_store),
                candidate_id,
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "audit",
                "events",
                str(candidate_store),
                "--project",
                "sample-api",
                "--candidate",
                candidate_id,
                "--limit",
                "8",
            ],
            cwd=root,
        )
        persisted_advance = [
            str(python),
            "-m",
            "forgegate",
            "candidate",
            "advance",
            str(candidate_store),
            candidate_id,
            "--to",
            "COLLECTING",
            "--expected-revision",
            "0",
            "--occurred-at",
            "2026-08-30T12:01:00Z",
            "--idempotency-key",
            "advance:release-smoke-001",
        ]
        run(persisted_advance, cwd=root)
        run(persisted_advance, cwd=root)
        bind_evidence = [
            str(python),
            "-m",
            "forgegate",
            "candidate",
            "bind-evidence",
            str(candidate_store),
            candidate_id,
            str(assembly_path),
            "--bound-at",
            "2026-08-30T20:31:00Z",
            "--idempotency-key",
            "bind-evidence:release-smoke-001",
        ]
        run(bind_evidence, cwd=root)
        run(bind_evidence, cwd=root)
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "show-evidence",
                str(candidate_store),
                candidate_id,
            ],
            cwd=root,
        )
        for revision, status, timestamp in (
            (1, "READY", "2026-08-30T20:32:00Z"),
            (2, "EVALUATING", "2026-08-30T20:33:00Z"),
        ):
            advance_command = [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "advance",
                str(candidate_store),
                candidate_id,
                "--to",
                status,
                "--expected-revision",
                str(revision),
                "--occurred-at",
                timestamp,
                "--idempotency-key",
                f"advance:release-smoke-{status.lower()}",
            ]
            run(advance_command, cwd=root)
        policy_material = root / "policy-material.json"
        run_capture(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "materialize-policy",
                str(candidate_store),
                candidate_id,
                "--project-root",
                str(REPOSITORY_ROOT / "examples/sample-python-api"),
            ],
            policy_material,
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "validate-config",
                str(policy_material),
            ],
            cwd=root,
        )
        evaluate_candidate = [
            str(python),
            "-m",
            "forgegate",
            "candidate",
            "evaluate",
            str(candidate_store),
            candidate_id,
            str(policy_material),
            "--expected-revision",
            "3",
            "--evaluated-at",
            "2026-08-30T21:00:00Z",
            "--idempotency-key",
            "evaluate:release-smoke-pass",
        ]
        run(evaluate_candidate, cwd=root)
        run(evaluate_candidate, cwd=root)
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "show-policy",
                str(candidate_store),
                candidate_id,
            ],
            cwd=root,
        )
        attestation_output = root / "attestations"
        attest = [
            str(python),
            "-m",
            "forgegate",
            "candidate",
            "attest",
            str(candidate_store),
            candidate_id,
            "--issued-at",
            "2026-08-30T22:00:00Z",
            "--output-root",
            str(attestation_output),
        ]
        run(attest, cwd=root)
        run(attest, cwd=root)
        assurance_output = root / "assurance"
        export_assurance = [
            str(python),
            "-m",
            "forgegate",
            "candidate",
            "export-assurance",
            str(candidate_store),
            candidate_id,
            "--output-root",
            str(assurance_output),
        ]
        run(export_assurance, cwd=root)
        run(export_assurance, cwd=root)
        assurance_directories = [path for path in assurance_output.iterdir() if path.is_dir()]
        if len(assurance_directories) != 1:
            raise SystemExit("installed wheel did not publish exactly one assurance directory")
        assurance_directory = assurance_directories[0]
        run(
            [str(python), "-m", "forgegate", "verify-assurance", str(assurance_directory)],
            cwd=root,
        )
        github_output = root / "github-output.txt"
        replay_destination = root / "source-replay"
        replay_export = [
            str(python),
            "-m",
            "forgegate",
            "evidence-replay",
            "export",
            str(candidate_store),
            candidate_id,
            "--source-root",
            str(assembly_root),
            "--destination",
            str(replay_destination),
        ]
        run(replay_export, cwd=root)
        run(replay_export, cwd=root, expected_returncode=3)
        replay_archives = list(replay_destination.glob("replay-*.zip"))
        if len(replay_archives) != 1:
            raise SystemExit("installed wheel did not publish exactly one source replay ZIP")
        replay_verify = [
            str(python),
            "-m",
            "forgegate",
            "evidence-replay",
            "verify",
            str(replay_archives[0]),
        ]
        run([*replay_verify, "--expected-commit", "a" * 40], cwd=root)
        run([*replay_verify, "--expected-commit", "b" * 40], cwd=root, expected_returncode=3)
        github_summary = root / "github-summary.md"
        github_report = root / "github-action-report.json"
        github_gate = [
            str(python),
            "-m",
            "forgegate",
            "github-gate",
            str(assurance_directory),
            "--expected-commit",
            "a" * 40,
        ]
        run_capture(
            [
                *github_gate,
                "--github-output",
                str(github_output),
                "--step-summary",
                str(github_summary),
            ],
            github_report,
            cwd=root,
        )
        if "gate_status=VALID\n" not in github_output.read_text(encoding="utf-8"):
            raise SystemExit("installed GitHub gate did not write VALID action output")
        if "**Decision: PASS**" not in github_summary.read_text(encoding="utf-8"):
            raise SystemExit("installed GitHub gate did not write the PASS job summary")
        run(
            [str(python), "-m", "forgegate", "validate-config", str(github_report)],
            cwd=root,
        )
        if os.environ.get("GITHUB_OUTPUT") and os.environ.get("GITHUB_STEP_SUMMARY"):
            run(github_gate, cwd=root)
        for assurance_member in ("assurance-bundle.json", "manifest.json"):
            run(
                [
                    str(python),
                    "-m",
                    "forgegate",
                    "validate-config",
                    str(assurance_directory / assurance_member),
                ],
                cwd=root,
            )
        private_key_path = root / "ephemeral-producer-key.pem"
        private_key_path.write_bytes(
            Ed25519PrivateKey.generate().private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        identity_path = root / "signing-identity.json"
        run_capture(
            [
                str(python),
                "-m",
                "forgegate",
                "identity",
                "derive",
                str(private_key_path),
                "--display-name",
                "release-smoke-producer",
            ],
            identity_path,
            cwd=root,
        )
        trust_store_path = root / "trust-store.json"
        run_capture(
            [
                str(python),
                "-m",
                "forgegate",
                "identity",
                "trust",
                str(identity_path),
                "--role",
                "producer",
                "--role",
                "operator",
                "--project",
                "sample-api",
            ],
            trust_store_path,
            cwd=root,
        )
        challenge_path = root / "api-challenge.json"
        run_capture(
            [
                str(python),
                "-c",
                (
                    "import sys; from pathlib import Path; "
                    "from forgegate.api import ApiAuthenticator, ApiChallengeRequest; "
                    "from forgegate.identity import IdentityRole, TrustStore, "
                    "load_identity_document; "
                    "trust=load_identity_document(Path(sys.argv[1])); "
                    "assert isinstance(trust, TrustStore); "
                    "identity=trust.identities[0].identity; "
                    "challenge=ApiAuthenticator(trust).issue_challenge(ApiChallengeRequest("
                    "identity_id=identity.identity_id, role=IdentityRole.OPERATOR, "
                    "project_ids=('sample-api',))); print(challenge.model_dump_json(indent=2))"
                ),
                str(trust_store_path),
            ],
            challenge_path,
            cwd=root,
        )
        session_request_path = root / "api-session-request.json"
        run_capture(
            [
                str(python),
                "-m",
                "forgegate",
                "identity",
                "sign-api-challenge",
                str(challenge_path),
                str(identity_path),
                str(private_key_path),
            ],
            session_request_path,
            cwd=root,
        )
        session_request = json.loads(session_request_path.read_text(encoding="utf-8"))
        if set(session_request) != {"challenge_id", "signature_base64"}:
            raise SystemExit("installed wheel API challenge signer returned an invalid request")
        run(
            [
                str(python),
                "-c",
                (
                    "import sys; from pathlib import Path; "
                    "from forgegate.api import ApiAuthenticator, ApiChallengeRequest, "
                    "sign_api_challenge; from forgegate.identity import IdentityRole, "
                    "SigningIdentity, TrustStore, load_ed25519_private_key, "
                    "load_identity_document; trust=load_identity_document(Path(sys.argv[1])); "
                    "identity=load_identity_document(Path(sys.argv[2])); "
                    "assert isinstance(trust, TrustStore) and "
                    "isinstance(identity, SigningIdentity); "
                    "auth=ApiAuthenticator(trust, trust_store_loader=lambda: trust); "
                    "challenge=auth.issue_challenge("
                    "ApiChallengeRequest(identity_id=identity.identity_id, "
                    "role=IdentityRole.OPERATOR, project_ids=('sample-api',))); "
                    "session=auth.create_session(sign_api_challenge(challenge, identity=identity, "
                    "private_key=load_ed25519_private_key(Path(sys.argv[3])))); "
                    "principal=auth.authenticate('Bearer '+session.access_token); "
                    "assert principal.identity == identity and "
                    "principal.role is IdentityRole.OPERATOR; "
                    "reload_result=auth.reload_trust_store(principal); "
                    "assert reload_result.retained_sessions == 1; "
                    "revoked=auth.logout(principal); "
                    "assert revoked.session_id == session.session_id"
                ),
                str(trust_store_path),
                str(identity_path),
                str(private_key_path),
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-c",
                (
                    "import sys; from datetime import UTC, datetime; from pathlib import Path; "
                    "from forgegate.candidates import SQLiteCandidateRepository; "
                    "from forgegate.security_events import ApiSecurityEventType; "
                    "repository=SQLiteCandidateRepository(Path(sys.argv[1]), "
                    "security_event_capacity=1); repository.initialize(); "
                    "event=repository.append_api_security_event("
                    "event_type=ApiSecurityEventType.AUTHENTICATION_REJECTED, "
                    "occurred_at=datetime(2026,8,31,22,0,tzinfo=UTC), "
                    "request_id='release-smoke-request-01', "
                    "outcome_code='API_SESSION_INVALID'); "
                    "page=repository.api_security_events(); "
                    "assert page.events == (event,) and page.saturated"
                ),
                str(root / "security-events.db"),
            ],
            cwd=root,
        )
        signature_output = root / "signatures"
        sign_assurance = [
            str(python),
            "-m",
            "forgegate",
            "sign-assurance",
            str(assurance_directory),
            str(identity_path),
            str(private_key_path),
            "--role",
            "producer",
            "--signed-at",
            "2026-08-31T23:00:00Z",
            "--output-root",
            str(signature_output),
        ]
        first_signature_result = root / "first-signature-result.json"
        second_signature_result = root / "second-signature-result.json"
        run_capture(sign_assurance, first_signature_result, cwd=root)
        run_capture(sign_assurance, second_signature_result, cwd=root)
        first_signature = json.loads(first_signature_result.read_text(encoding="utf-8"))
        second_signature = json.loads(second_signature_result.read_text(encoding="utf-8"))
        if first_signature["output_replayed"] or not second_signature["output_replayed"]:
            raise SystemExit("installed wheel did not preserve exact signature replay semantics")
        signature_path = Path(str(second_signature["signature_path"]))
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "verify-assurance-signature",
                str(assurance_directory),
                str(signature_path),
                str(trust_store_path),
            ],
            cwd=root,
        )
        for identity_document_path in (identity_path, trust_store_path, signature_path):
            run(
                [
                    str(python),
                    "-m",
                    "forgegate",
                    "validate-config",
                    str(identity_document_path),
                ],
                cwd=root,
            )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "show-attestation",
                str(candidate_store),
                candidate_id,
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "history",
                str(candidate_store),
                candidate_id,
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "transition",
                str(REPOSITORY_ROOT / "examples/sample-python-api/candidates/draft.json"),
                "--to",
                "COLLECTING",
                "--occurred-at",
                "2026-08-30T12:01:00Z",
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "transition",
                str(REPOSITORY_ROOT / "examples/sample-python-api/candidates/evaluating.json"),
                "--to",
                "PASS",
                "--occurred-at",
                "2026-08-30T21:00:00Z",
                "--evaluation",
                str(REPOSITORY_ROOT / "tests/golden/policy_pass.json"),
            ],
            cwd=root,
        )
        run([str(python), str(REPOSITORY_ROOT / "tools/dashboard_runtime_smoke.py")], cwd=root)
        run([str(python), str(REPOSITORY_ROOT / "tools/dashboard_pair_smoke.py")], cwd=root)
        run([str(python), str(REPOSITORY_ROOT / "tools/collection_jobs_smoke.py")], cwd=root)
        run([str(python), str(REPOSITORY_ROOT / "tools/workspace_backups_smoke.py")], cwd=root)
        run([str(python), str(REPOSITORY_ROOT / "tools/adoption_preflight_smoke.py")], cwd=root)
        run([str(python), "-m", "forgegate", "doctor"], cwd=root)
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "validate-config",
                str(REPOSITORY_ROOT / "examples/sample-python-api/forgegate.yaml"),
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "collect-analog-validation",
                "artifacts/analog-validation-result.json",
                "--root",
                str(REPOSITORY_ROOT / "examples/sample-python-api"),
                "--commit",
                "9ac23494b86212928185de9b0eef1c1a82a8c0ea",
                "--collected-at",
                "2026-08-31T13:00:00Z",
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "collect-benchmark",
                "artifacts/benchmark.json",
                "--root",
                str(REPOSITORY_ROOT / "examples/sample-python-api"),
                "--commit",
                "d" * 40,
                "--collected-at",
                "2026-08-31T00:00:00Z",
                "--trust",
                "claimed_ci_metadata",
                "--verification-level",
                "ci_validated",
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "collect-junit",
                "artifacts/junit.xml",
                "--root",
                str(REPOSITORY_ROOT / "examples/sample-python-api"),
                "--commit",
                "a" * 40,
                "--collected-at",
                "2026-08-30T20:30:00Z",
                "--source-tool",
                "pytest",
                "--source-version",
                "8.4.2",
                "--trust",
                "claimed_ci_metadata",
                "--verification-level",
                "ci_validated",
            ],
            cwd=root,
        )
        for command, artifact, source_tool in (
            ("collect-coverage-xml", "artifacts/coverage.xml", "coverage.py"),
            ("collect-lcov", "artifacts/coverage.info", "lcov"),
        ):
            run(
                [
                    str(python),
                    "-m",
                    "forgegate",
                    command,
                    artifact,
                    "--root",
                    str(REPOSITORY_ROOT / "examples/sample-python-api"),
                    "--commit",
                    "b" * 40,
                    "--collected-at",
                    "2026-08-30T22:00:00Z",
                    "--source-tool",
                    source_tool,
                    "--source-version",
                    "7.10.0",
                    "--trust",
                    "claimed_ci_metadata",
                    "--verification-level",
                    "ci_validated",
                ],
                cwd=root,
            )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "collect-sarif",
                "artifacts/security.sarif",
                "--root",
                str(REPOSITORY_ROOT / "examples/sample-python-api"),
                "--commit",
                "c" * 40,
                "--collected-at",
                "2026-08-30T23:00:00Z",
                "--trust",
                "claimed_ci_metadata",
                "--verification-level",
                "ci_validated",
            ],
            cwd=root,
        )

        snapshot = root / "candidate-backup.db"
        backup_receipt = root / "candidate-backup-receipt.json"
        run_capture(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "backup-store",
                str(candidate_store),
                str(snapshot),
            ],
            backup_receipt,
            cwd=root,
        )
        backup_document = json.loads(backup_receipt.read_text(encoding="utf-8"))
        if backup_document["status"] != "BACKUP_CREATED" or backup_document["size_bytes"] <= 0:
            raise SystemExit("installed backup did not produce a verified snapshot")
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "verify-backup",
                str(snapshot),
                "--sha256",
                backup_document["sha256"],
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "backup-store",
                str(candidate_store),
                str(snapshot),
            ],
            cwd=root,
            expected_returncode=3,
        )
        run(
            [str(python), "-m", "pip", "uninstall", "--yes", "forgegate"],
            cwd=root,
        )
        run(
            [
                str(python),
                "-c",
                "import importlib.util; assert importlib.util.find_spec('forgegate') is None",
            ],
            cwd=root,
        )
        msp430_environment = root / "msp430-environment"
        venv.EnvBuilder(with_pip=True, clear=False).create(msp430_environment)
        msp430_python = clean_python(msp430_environment)
        run(
            [
                str(msp430_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-c",
                str(REPOSITORY_ROOT / "requirements/dev-constraints.txt"),
                f"forgegate[msp430] @ {wheel.resolve().as_uri()}",
            ],
            cwd=root,
        )
        run(
            [
                str(msp430_python),
                "-c",
                (
                    "import serial; "
                    "from forgegate.compatibility.msp430_live import "
                    "MSP430_UART_BAUD_RATE; "
                    "assert serial.VERSION == '3.5'; "
                    "assert MSP430_UART_BAUD_RATE == 115200"
                ),
            ],
            cwd=root,
        )
        print(f"\nwheel sha256={sha256(wheel)}", flush=True)
        print(f"sdist sha256={sha256(sdist)}", flush=True)
        print("ForgeGate release smoke: PASS", flush=True)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify ForgeGate source and clean-wheel release")
    parser.add_argument("--windows-live-broker", action="store_true")
    parser.add_argument("--live-output", type=Path)
    parser.add_argument("--sandbox-evidence", type=Path)
    parser.add_argument("--podman", type=Path)
    arguments = parser.parse_args()
    raise SystemExit(
        main(
            windows_live_broker=arguments.windows_live_broker,
            live_output=arguments.live_output,
            sandbox_evidence=arguments.sandbox_evidence,
            podman=arguments.podman,
        )
    )
