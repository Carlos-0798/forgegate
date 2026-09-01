from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from forgegate.api import create_api_app
from forgegate.schema_registry import ARTIFACT_SCHEMAS, SCHEMAS, schema_filename

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print(f"\n> {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def verify_committed_schemas() -> None:
    for schema_version, model in sorted(SCHEMAS.items()):
        expected = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        path = REPOSITORY_ROOT / "schemas" / schema_filename(schema_version)
        if not path.is_file():
            raise SystemExit(f"missing committed schema: {path}")
        if path.read_text(encoding="utf-8") != expected:
            raise SystemExit(
                f"schema drift: {path}; run `python -m forgegate export-schemas schemas`"
            )
    for schema_name, schema in sorted(ARTIFACT_SCHEMAS.items()):
        path = REPOSITORY_ROOT / "schemas" / schema_filename(schema_name)
        expected = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        if not path.is_file():
            raise SystemExit(f"missing committed schema: {path}")
        if path.read_text(encoding="utf-8") != expected:
            raise SystemExit(f"schema drift: {path}")
    print("\nCommitted JSON Schemas: PASS", flush=True)


def verify_committed_openapi() -> None:
    expected = (
        json.dumps(
            create_api_app(Path("forgegate-openapi-contract.db"), contract_only=True).openapi(),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    path = REPOSITORY_ROOT / "schemas/forgegate.openapi.v1.json"
    if not path.is_file():
        raise SystemExit(f"missing committed OpenAPI contract: {path}")
    if path.read_text(encoding="utf-8") != expected:
        raise SystemExit(f"OpenAPI drift: {path}; run `python -m forgegate export-openapi {path}`")
    print("\nCommitted OpenAPI contract: PASS", flush=True)


def main() -> int:
    python = sys.executable
    commands = [
        [python, "-m", "pip", "check"],
        [python, "-m", "ruff", "check", "."],
        [python, "-m", "ruff", "format", "--check", "."],
        [python, "-m", "mypy", "src", "tools"],
        [python, "-m", "pytest", "--cov=forgegate", "--cov-branch"],
        [
            python,
            "-m",
            "forgegate",
            "validate-config",
            "examples/sample-python-api/forgegate.yaml",
        ],
        [
            python,
            "-m",
            "forgegate",
            "validate-config",
            "examples/sample-python-api/policies/pull-request.yaml",
        ],
        [
            python,
            "-m",
            "forgegate",
            "validate-config",
            "examples/sample-python-api/policies/production.yaml",
        ],
        [
            python,
            "-m",
            "forgegate",
            "validate-config",
            "examples/sample-python-api/candidates/draft.json",
        ],
        [
            python,
            "-m",
            "forgegate",
            "validate-config",
            "examples/sample-python-api/candidates/evaluating.json",
        ],
        [
            python,
            "-m",
            "forgegate",
            "validate-config",
            "tests/golden/candidate_collecting_transition.json",
        ],
        [
            python,
            "-m",
            "forgegate",
            "validate-config",
            "tests/golden/candidate_pass_transition.json",
        ],
        [
            python,
            "-m",
            "forgegate",
            "validate-config",
            "tests/golden/release_attestation_pass.json",
        ],
        [
            python,
            "-m",
            "forgegate",
            "validate-config",
            "tests/golden/evidence_bundle_assembly.json",
        ],
        [
            python,
            "-m",
            "forgegate",
            "validate-config",
            "tests/golden/candidate_evidence_binding.json",
        ],
    ]
    for command in commands:
        run(command)
    verify_committed_schemas()
    verify_committed_openapi()
    print("\nForgeGate development verification: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
