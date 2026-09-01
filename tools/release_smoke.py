from __future__ import annotations

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

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SDIST_PATHS = (
    "AGENTS.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "docs/PROJECT_STATUS.md",
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
    "docs/architecture/EVIDENCE_BUNDLE_ASSEMBLY.md",
    "docs/architecture/CANDIDATE_EVIDENCE_BINDING.md",
    "docs/architecture/LOCAL_REST_API.md",
    "docs/architecture/LOCAL_REST_COMMAND_WORKFLOW.md",
    "docs/architecture/PROJECT_REGISTRY_AND_AUDIT_QUERY.md",
    "docs/architecture/PROJECT_AUTHORITY_AND_DISCOVERY.md",
    "docs/architecture/PROJECT_PROFILE_REVISIONS.md",
    "docs/architecture/POLICY_MATERIALIZATION.md",
    "docs/architecture/PORTABLE_ASSURANCE_BUNDLES.md",
    "examples/sample-python-api/artifacts/junit.xml",
    "examples/sample-python-api/artifacts/junit-pass.xml",
    "examples/sample-python-api/artifacts/benchmark.json",
    "examples/sample-python-api/artifacts/security.sarif",
    "examples/sample-python-api/artifacts/coverage.info",
    "examples/sample-python-api/artifacts/coverage.xml",
    "examples/sample-python-api/artifacts/analog-validation-result.json",
    "examples/sample-python-api/forgegate.yaml",
    "examples/sample-python-api/evidence/pass-bundle.json",
    "examples/sample-python-api/evidence/fail-bundle.json",
    "examples/sample-python-api/candidates/draft.json",
    "examples/sample-python-api/candidates/evaluating.json",
    "reports/PHASE_1_JUNIT_SLICE_ACCEPTANCE_REPORT.md",
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
    "requirements/dev-constraints.txt",
    "schemas/forgegate.project.v1.schema.json",
    "schemas/forgegate.policy-evaluation.v1.schema.json",
    "schemas/forgegate.policy-evaluation.v2.schema.json",
    "schemas/forgegate.policy-material.v1.schema.json",
    "schemas/forgegate.assurance-bundle.v1.schema.json",
    "schemas/forgegate.assurance-bundle-manifest.v1.schema.json",
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
    "schemas/forgegate.openapi.v1.json",
    "schemas/forgegate.benchmark.v1.schema.json",
    "schemas/analog-validation.result-export.v1.schema.json",
    "tests/test_models.py",
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
    "tools/verify.py",
    "tests/test_candidate_lifecycle.py",
    "tests/test_candidate_store.py",
    "tests/test_candidate_store_cli.py",
    "tests/test_attestations.py",
    "tests/test_analog_validation_collector.py",
    "tests/test_evidence_assembly.py",
    "tests/test_candidate_evidence_binding.py",
    "tests/test_application.py",
    "tests/test_api.py",
    "tests/test_project_registry_audit.py",
    "tests/test_project_authority_discovery.py",
    "tests/test_project_profile_revisions.py",
    "tests/test_policy_materialization.py",
    "tests/test_assurance_bundle.py",
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
        raise SystemExit(completed.returncode)


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
    print("\nSource distribution manifest: PASS", flush=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="forgegate-release-") as temporary:
        root = Path(temporary)
        dist = root / "dist"
        run([sys.executable, "-m", "build", "--outdir", str(dist)])

        wheels = list(dist.glob("*.whl"))
        sdists = list(dist.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise SystemExit("release build must produce exactly one wheel and one sdist")
        wheel = wheels[0]
        sdist = sdists[0]
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
                str(wheel),
            ],
            cwd=root,
        )
        run(
            [
                str(python),
                "-c",
                "from importlib.metadata import version; import forgegate; "
                "assert version('forgegate') == forgegate.__version__",
            ],
            cwd=root,
        )
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
            ("/v1/projects", "post"): "registerProject",
            ("/v1/projects", "get"): "listProjects",
            ("/v1/projects/{project_id}", "get"): "getProject",
            ("/v1/projects/{project_id}/profile", "get"): "getCurrentProjectProfile",
            ("/v1/projects/{project_id}/revisions", "get"): "listProjectProfileRevisions",
            ("/v1/projects/{project_id}/revisions", "post"): "reviseProjectProfile",
            ("/v1/projects/{project_id}/candidates", "get"): "listProjectCandidates",
            ("/v1/audit-events", "get"): "queryAuditEvents",
            ("/v1/candidates/{candidate_id}/transitions", "post"): "advanceCandidate",
            ("/v1/candidates/{candidate_id}/evidence", "post"): "bindCandidateEvidence",
            ("/v1/candidates/{candidate_id}/evaluate", "post"): "evaluateCandidate",
            ("/v1/candidates/{candidate_id}/policy", "get"): "getCandidatePolicyMaterial",
            ("/v1/candidates/{candidate_id}/attestation", "post"): "attestCandidate",
        }
        for (path, method), operation_id in expected_operations.items():
            if openapi["paths"][path][method]["operationId"] != operation_id:
                raise SystemExit(f"installed wheel is missing API operation: {operation_id}")
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "serve",
                "--database",
                str(root / "api-rejected.db"),
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
        for document in ("assurance-bundle.json", "manifest.json"):
            run(
                [
                    str(python),
                    "-m",
                    "forgegate",
                    "validate-config",
                    str(assurance_directory / document),
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

        print(f"\nwheel sha256={sha256(wheel)}", flush=True)
        print(f"sdist sha256={sha256(sdist)}", flush=True)
        print("ForgeGate release smoke: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
