from __future__ import annotations

import hashlib
import os
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
    "requirements/dev-constraints.txt",
    "schemas/forgegate.project.v1.schema.json",
    "schemas/forgegate.policy-evaluation.v1.schema.json",
    "schemas/forgegate.release-candidate.v1.schema.json",
    "schemas/forgegate.candidate-transition.v1.schema.json",
    "schemas/forgegate.candidate-transition-result.v1.schema.json",
    "schemas/forgegate.release-attestation.v1.schema.json",
    "schemas/forgegate.benchmark.v1.schema.json",
    "schemas/analog-validation.result-export.v1.schema.json",
    "tests/test_models.py",
    "tests/golden/junit_summary.json",
    "tests/golden/benchmark_metrics.json",
    "tests/golden/analog_validation_result.json",
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
        candidate_id = "cand-dab25eb0be1a0107b3996080"
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
            "--database",
            str(candidate_store),
            "--idempotency-key",
            "create:release-smoke-001",
        ]
        run(persisted_create, cwd=root)
        run(persisted_create, cwd=root)
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
        for revision, status, timestamp in (
            (1, "READY", "2026-08-30T12:02:00Z"),
            (2, "EVALUATING", "2026-08-30T12:03:00Z"),
            (3, "PASS", "2026-08-30T21:00:00Z"),
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
            if status == "PASS":
                advance_command.extend(
                    [
                        "--evaluation",
                        str(REPOSITORY_ROOT / "tests/golden/policy_pass.json"),
                    ]
                )
            run(advance_command, cwd=root)
        run(
            [
                str(python),
                "-m",
                "forgegate",
                "candidate",
                "import-evaluation",
                str(candidate_store),
                candidate_id,
                str(REPOSITORY_ROOT / "tests/golden/policy_pass.json"),
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
