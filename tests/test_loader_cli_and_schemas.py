import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forgegate.cli import app
from forgegate.config import ConfigLoadError, load_config
from forgegate.schema_registry import ARTIFACT_SCHEMAS, SCHEMAS, schema_filename

runner = CliRunner()


@pytest.mark.parametrize(
    "relative_path",
    [
        "examples/sample-python-api/forgegate.yaml",
        "examples/sample-python-api/policies/pull-request.yaml",
        "examples/sample-python-api/policies/production.yaml",
        "examples/sample-python-api/evidence/pass-bundle.json",
        "examples/sample-python-api/evidence/fail-bundle.json",
        "examples/sample-python-api/candidates/draft.json",
        "examples/sample-python-api/candidates/evaluating.json",
    ],
)
def test_examples_load(repository_root: Path, relative_path: str) -> None:
    config = load_config(repository_root / relative_path)
    assert config.schema_version.startswith("forgegate.")


def test_unsupported_schema_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "unknown.yaml"
    path.write_text("schema_version: forgegate.unknown.v1\n", encoding="utf-8")
    with pytest.raises(ConfigLoadError, match="unsupported schema_version"):
        load_config(path)


def test_missing_file_is_user_facing(tmp_path: Path) -> None:
    with pytest.raises(ConfigLoadError, match="cannot access configuration"):
        load_config(tmp_path / "does-not-exist.yaml")


def test_non_mapping_root_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- unsafe\n", encoding="utf-8")
    with pytest.raises(ConfigLoadError, match="root must be a mapping"):
        load_config(path)


def test_missing_schema_version_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"
    path.write_text("project: {}\n", encoding="utf-8")
    with pytest.raises(ConfigLoadError, match="schema_version is required"):
        load_config(path)


def test_invalid_yaml_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("schema_version: [unterminated\n", encoding="utf-8")
    with pytest.raises(ConfigLoadError, match="cannot parse configuration"):
        load_config(path)


def test_schema_validation_error_is_user_facing(tmp_path: Path) -> None:
    path = tmp_path / "invalid-project.yaml"
    path.write_text("schema_version: forgegate.project.v1\n", encoding="utf-8")
    with pytest.raises(ConfigLoadError, match="project"):
        load_config(path)


def test_loader_rejects_oversized_config(tmp_path: Path) -> None:
    path = tmp_path / "large.yaml"
    path.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(ConfigLoadError, match="exceeds"):
        load_config(path)


def test_doctor_reports_phase() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["phase"] == "phase8-project-authority-discovery"
    assert report["supported_schemas"] == sorted(SCHEMAS)
    assert report["supported_artifact_schemas"] == sorted(ARTIFACT_SCHEMAS)


def test_validate_config_cli(repository_root: Path) -> None:
    path = repository_root / "examples/sample-python-api/forgegate.yaml"
    result = runner.invoke(app, ["validate-config", str(path)])
    assert result.exit_code == 0
    assert "VALID forgegate.project.v1" in result.stdout


def test_invalid_config_cli_uses_error_exit_code(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("schema_version: forgegate.unknown.v1\n", encoding="utf-8")
    result = runner.invoke(app, ["validate-config", str(path)])
    assert result.exit_code == 3
    assert "unsupported schema_version" in result.output


def test_candidate_create_cli_matches_committed_example(repository_root: Path) -> None:
    result = runner.invoke(
        app,
        [
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
            "--branch",
            "main",
            "--track",
            "pull-request",
        ],
    )
    expected = json.loads(
        (repository_root / "examples/sample-python-api/candidates/draft.json").read_text(
            encoding="utf-8"
        )
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout) == expected


def test_candidate_transition_cli_matches_golden(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = runner.invoke(
        app,
        [
            "candidate",
            "transition",
            str(root / "candidates/draft.json"),
            "--to",
            "COLLECTING",
            "--occurred-at",
            "2026-08-30T12:01:00Z",
            "--reason",
            "begin evidence collection",
        ],
    )
    expected = json.loads(
        (repository_root / "tests/golden/candidate_collecting_transition.json").read_text(
            encoding="utf-8"
        )
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout) == expected


def test_candidate_terminal_transition_binds_policy_evaluation(
    repository_root: Path,
) -> None:
    root = repository_root / "examples/sample-python-api"
    result = runner.invoke(
        app,
        [
            "candidate",
            "transition",
            str(root / "candidates/evaluating.json"),
            "--to",
            "PASS",
            "--occurred-at",
            "2026-08-30T21:00:00Z",
            "--evaluation",
            str(repository_root / "tests/golden/policy_pass.json"),
            "--reason",
            "policy evaluation passed",
        ],
    )
    expected = json.loads(
        (repository_root / "tests/golden/candidate_pass_transition.json").read_text(
            encoding="utf-8"
        )
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout) == expected


def test_candidate_cli_error_paths(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    create_error = runner.invoke(
        app,
        [
            "candidate",
            "create",
            "--project",
            "sample-api",
            "--version",
            "1.2.0",
            "--commit",
            "a" * 40,
            "--created-at",
            "not-a-timestamp",
        ],
    )
    base_transition = [
        "candidate",
        "transition",
        str(root / "candidates/draft.json"),
        "--to",
        "READY",
        "--occurred-at",
        "2026-08-30T12:01:00Z",
    ]
    illegal = runner.invoke(app, base_transition)
    invalid_timestamp = runner.invoke(app, [*base_transition[:-1], "not-a-timestamp"])
    blank_command = [*base_transition]
    blank_command[4] = "COLLECTING"
    blank_reason = runner.invoke(app, [*blank_command, "--reason", " "])
    wrong_document = runner.invoke(
        app,
        [
            "candidate",
            "transition",
            str(root / "policies/pull-request.yaml"),
            "--to",
            "COLLECTING",
            "--occurred-at",
            "2026-08-30T12:01:00Z",
        ],
    )
    wrong_evaluation_document = runner.invoke(
        app,
        [
            "candidate",
            "transition",
            str(root / "candidates/evaluating.json"),
            "--to",
            "PASS",
            "--occurred-at",
            "2026-08-30T21:00:00Z",
            "--evaluation",
            str(root / "evidence/pass-bundle.json"),
        ],
    )

    assert create_error.exit_code == 3
    assert "Invalid isoformat string" in create_error.output
    assert illegal.exit_code == 3
    assert "CANDIDATE_TRANSITION_INVALID" in illegal.output
    assert invalid_timestamp.exit_code == 3
    assert "Invalid isoformat string" in invalid_timestamp.output
    assert blank_reason.exit_code == 3
    assert "CANDIDATE_REASON_EMPTY" in blank_reason.output
    assert wrong_document.exit_code == 3
    assert "candidate path must contain" in wrong_document.output
    assert wrong_evaluation_document.exit_code == 3
    assert "evaluation path must contain" in wrong_evaluation_document.output


@pytest.mark.parametrize(
    ("bundle", "expected_exit", "expected_decision"),
    [
        ("pass-bundle.json", 0, "PASS"),
        ("fail-bundle.json", 1, "FAIL"),
    ],
)
def test_evaluate_policy_cli_exit_contract(
    repository_root: Path,
    bundle: str,
    expected_exit: int,
    expected_decision: str,
) -> None:
    root = repository_root / "examples/sample-python-api"
    result = runner.invoke(
        app,
        [
            "evaluate-policy",
            str(root / "policies/pull-request.yaml"),
            str(root / "evidence" / bundle),
            "--evaluated-at",
            "2026-08-30T21:00:00Z",
        ],
    )
    assert result.exit_code == expected_exit
    payload = json.loads(result.stdout)
    expected = json.loads(
        (repository_root / f"tests/golden/policy_{expected_decision.lower()}.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload == expected


def test_evaluate_policy_cli_review_exit(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = runner.invoke(
        app,
        [
            "evaluate-policy",
            str(root / "policies/production.yaml"),
            str(root / "evidence/pass-bundle.json"),
            "--evaluated-at",
            "2026-08-30T21:00:00Z",
        ],
    )
    assert result.exit_code == 2
    assert json.loads(result.stdout)["decision"] == "REVIEW"


def test_evaluate_policy_cli_error_paths(repository_root: Path, tmp_path: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    invalid_policy = tmp_path / "invalid-policy.yaml"
    invalid_policy.write_text(
        """schema_version: forgegate.policy.v1
name: invalid-expression
rules:
  - id: invalid-field
    claim: tests.required-pass
    evidence_kind: test.summary
    operator: equals
    expected: 0
    where:
      field: missing
    minimum_trust: claimed_ci_metadata
    minimum_verification: ci_validated
""",
        encoding="utf-8",
    )
    command = [
        "evaluate-policy",
        str(invalid_policy),
        str(root / "evidence/pass-bundle.json"),
        "--evaluated-at",
        "2026-08-30T21:00:00Z",
    ]
    evaluation_error = runner.invoke(app, command)
    wrong_type = runner.invoke(
        app,
        [
            "evaluate-policy",
            str(root / "evidence/pass-bundle.json"),
            str(root / "evidence/pass-bundle.json"),
            "--evaluated-at",
            "2026-08-30T21:00:00Z",
        ],
    )
    wrong_bundle_type = runner.invoke(
        app,
        [
            "evaluate-policy",
            str(root / "policies/pull-request.yaml"),
            str(root / "policies/pull-request.yaml"),
            "--evaluated-at",
            "2026-08-30T21:00:00Z",
        ],
    )
    invalid_timestamp = runner.invoke(app, [*command[:-1], "not-a-timestamp"])

    assert evaluation_error.exit_code == 3
    assert json.loads(evaluation_error.stdout)["decision"] == "ERROR"
    assert wrong_type.exit_code == 3
    assert "policy path must contain" in wrong_type.output
    assert wrong_bundle_type.exit_code == 3
    assert "evidence path must contain" in wrong_bundle_type.output
    assert invalid_timestamp.exit_code == 3
    assert "Invalid isoformat string" in invalid_timestamp.output


def test_collect_junit_cli_vertical_slice(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = runner.invoke(
        app,
        [
            "collect-junit",
            "artifacts/junit.xml",
            "--root",
            str(root),
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
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "COMPLETE"
    assert payload["evidence"][0]["kind"] == "test.summary"
    assert payload["evidence"][0]["value"]["failures"] == 1


def test_collect_junit_cli_rejects_invalid_timestamp(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = runner.invoke(
        app,
        [
            "collect-junit",
            "artifacts/junit.xml",
            "--root",
            str(root),
            "--commit",
            "a" * 40,
            "--collected-at",
            "not-a-timestamp",
        ],
    )
    assert result.exit_code == 3
    assert "Invalid isoformat string" in result.output


def test_collect_junit_cli_returns_rejected_exit_code(tmp_path: Path) -> None:
    (tmp_path / "junit.xml").write_text("<testsuite>", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "collect-junit",
            "junit.xml",
            "--root",
            str(tmp_path),
            "--commit",
            "a" * 40,
            "--collected-at",
            "2026-08-30T20:30:00Z",
        ],
    )
    assert result.exit_code == 3
    assert json.loads(result.stdout)["status"] == "REJECTED"


@pytest.mark.parametrize(
    ("command", "artifact", "tool"),
    [
        ("collect-coverage-xml", "artifacts/coverage.xml", "coverage.py"),
        ("collect-lcov", "artifacts/coverage.info", "lcov"),
    ],
)
def test_collect_coverage_cli_vertical_slices(
    repository_root: Path,
    command: str,
    artifact: str,
    tool: str,
) -> None:
    root = repository_root / "examples/sample-python-api"
    result = runner.invoke(
        app,
        [
            command,
            artifact,
            "--root",
            str(root),
            "--commit",
            "b" * 40,
            "--collected-at",
            "2026-08-30T22:00:00Z",
            "--source-tool",
            tool,
            "--source-version",
            "7.10.0",
            "--trust",
            "claimed_ci_metadata",
            "--verification-level",
            "ci_validated",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "COMPLETE"
    assert [record["kind"] for record in payload["evidence"][:2]] == [
        "coverage.line",
        "coverage.branch",
    ]


def test_collect_coverage_cli_rejects_invalid_inputs(repository_root: Path, tmp_path: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    invalid_timestamp = runner.invoke(
        app,
        [
            "collect-coverage-xml",
            "artifacts/coverage.xml",
            "--root",
            str(root),
            "--commit",
            "b" * 40,
            "--collected-at",
            "not-a-timestamp",
        ],
    )
    assert invalid_timestamp.exit_code == 3
    assert "Invalid isoformat string" in invalid_timestamp.output

    invalid_lcov = tmp_path / "invalid.info"
    invalid_lcov.write_text("SF:a.py\n", encoding="utf-8")
    rejected = runner.invoke(
        app,
        [
            "collect-lcov",
            "invalid.info",
            "--root",
            str(tmp_path),
            "--commit",
            "b" * 40,
            "--collected-at",
            "2026-08-30T22:00:00Z",
        ],
    )
    assert rejected.exit_code == 3
    assert json.loads(rejected.stdout)["status"] == "REJECTED"


def test_collect_sarif_cli_vertical_slice(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = runner.invoke(
        app,
        [
            "collect-sarif",
            "artifacts/security.sarif",
            "--root",
            str(root),
            "--commit",
            "c" * 40,
            "--collected-at",
            "2026-08-30T23:00:00Z",
            "--trust",
            "claimed_ci_metadata",
            "--verification-level",
            "ci_validated",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "COMPLETE"
    assert [record["kind"] for record in payload["evidence"]] == [
        "static_analysis.summary",
        "static_analysis.finding",
        "static_analysis.finding",
    ]


def test_collect_sarif_cli_rejects_invalid_inputs(repository_root: Path, tmp_path: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    invalid_timestamp = runner.invoke(
        app,
        [
            "collect-sarif",
            "artifacts/security.sarif",
            "--root",
            str(root),
            "--commit",
            "c" * 40,
            "--collected-at",
            "not-a-timestamp",
        ],
    )
    assert invalid_timestamp.exit_code == 3
    assert "Invalid isoformat string" in invalid_timestamp.output

    invalid_sarif = tmp_path / "invalid.sarif"
    invalid_sarif.write_text('{"version":"2.1.0","runs":[]}', encoding="utf-8")
    rejected = runner.invoke(
        app,
        [
            "collect-sarif",
            "invalid.sarif",
            "--root",
            str(tmp_path),
            "--commit",
            "c" * 40,
            "--collected-at",
            "2026-08-30T23:00:00Z",
        ],
    )
    assert rejected.exit_code == 3
    assert json.loads(rejected.stdout)["status"] == "REJECTED"


def test_collect_benchmark_cli_vertical_slice(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = runner.invoke(
        app,
        [
            "collect-benchmark",
            "artifacts/benchmark.json",
            "--root",
            str(root),
            "--commit",
            "d" * 40,
            "--collected-at",
            "2026-08-31T00:00:00Z",
            "--trust",
            "claimed_ci_metadata",
            "--verification-level",
            "ci_validated",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "COMPLETE"
    assert len(payload["evidence"]) == 3
    assert all(record["kind"] == "benchmark.metric" for record in payload["evidence"])


def test_collect_benchmark_cli_rejects_invalid_inputs(
    repository_root: Path, tmp_path: Path
) -> None:
    root = repository_root / "examples/sample-python-api"
    invalid_timestamp = runner.invoke(
        app,
        [
            "collect-benchmark",
            "artifacts/benchmark.json",
            "--root",
            str(root),
            "--commit",
            "d" * 40,
            "--collected-at",
            "not-a-timestamp",
        ],
    )
    assert invalid_timestamp.exit_code == 3
    assert "Invalid isoformat string" in invalid_timestamp.output

    invalid_benchmark = tmp_path / "invalid.json"
    invalid_benchmark.write_text(
        '{"schema_version":"forgegate.benchmark.v1","tool":{},"metrics":[]}',
        encoding="utf-8",
    )
    rejected = runner.invoke(
        app,
        [
            "collect-benchmark",
            "invalid.json",
            "--root",
            str(tmp_path),
            "--commit",
            "d" * 40,
            "--collected-at",
            "2026-08-31T00:00:00Z",
        ],
    )
    assert rejected.exit_code == 3
    assert json.loads(rejected.stdout)["status"] == "REJECTED"


def test_schema_export_cli(tmp_path: Path) -> None:
    output = tmp_path / "schemas"
    result = runner.invoke(app, ["export-schemas", str(output)])
    assert result.exit_code == 0
    for schema_version in SCHEMAS:
        path = output / schema_filename(schema_version)
        assert path.is_file()
        assert b"\r\n" not in path.read_bytes()
        assert json.loads(path.read_text(encoding="utf-8"))["type"] == "object"
    for schema_name in ARTIFACT_SCHEMAS:
        path = output / schema_filename(schema_name)
        assert path.is_file()
        assert b"\r\n" not in path.read_bytes()
        assert json.loads(path.read_text(encoding="utf-8"))["type"] == "object"


def test_committed_schemas_match_models(repository_root: Path) -> None:
    for schema_version, model in SCHEMAS.items():
        expected = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        path = repository_root / "schemas" / schema_filename(schema_version)
        assert path.read_text(encoding="utf-8") == expected


def test_core_schemas_remain_domain_neutral() -> None:
    payload = json.dumps(
        {name: model.model_json_schema() for name, model in SCHEMAS.items()}
    ).lower()
    assert "msp430" not in payload
    assert "analog validation studio" not in payload
