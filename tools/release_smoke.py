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
    "examples/sample-python-api/artifacts/junit.xml",
    "examples/sample-python-api/artifacts/junit-pass.xml",
    "examples/sample-python-api/artifacts/benchmark.json",
    "examples/sample-python-api/artifacts/security.sarif",
    "examples/sample-python-api/artifacts/coverage.info",
    "examples/sample-python-api/artifacts/coverage.xml",
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
    "requirements/dev-constraints.txt",
    "schemas/forgegate.project.v1.schema.json",
    "schemas/forgegate.policy-evaluation.v1.schema.json",
    "schemas/forgegate.release-candidate.v1.schema.json",
    "schemas/forgegate.candidate-transition.v1.schema.json",
    "schemas/forgegate.candidate-transition-result.v1.schema.json",
    "schemas/forgegate.benchmark.v1.schema.json",
    "tests/test_models.py",
    "tests/golden/junit_summary.json",
    "tests/golden/benchmark_metrics.json",
    "tests/golden/coverage_xml.json",
    "tests/golden/lcov_summary.json",
    "tests/golden/policy_pass.json",
    "tests/golden/policy_fail.json",
    "tests/golden/candidate_collecting_transition.json",
    "tests/golden/candidate_pass_transition.json",
    "tests/golden/sarif_summary.json",
    "tools/verify.py",
    "tests/test_candidate_lifecycle.py",
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
