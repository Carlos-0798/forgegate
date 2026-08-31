from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from forgegate.collectors.benchmark import BENCHMARK_JSON_SCHEMA
from forgegate.schema_registry import SCHEMAS, schema_filename

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
    benchmark_path = REPOSITORY_ROOT / "schemas/forgegate.benchmark.v1.schema.json"
    benchmark_expected = json.dumps(BENCHMARK_JSON_SCHEMA, indent=2, sort_keys=True) + "\n"
    if not benchmark_path.is_file():
        raise SystemExit(f"missing committed schema: {benchmark_path}")
    if benchmark_path.read_text(encoding="utf-8") != benchmark_expected:
        raise SystemExit(f"schema drift: {benchmark_path}")
    print("\nCommitted JSON Schemas: PASS", flush=True)


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
    ]
    for command in commands:
        run(command)
    verify_committed_schemas()
    print("\nForgeGate development verification: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
