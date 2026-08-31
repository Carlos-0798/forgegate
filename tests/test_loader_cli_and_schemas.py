import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forgegate.cli import app
from forgegate.config import ConfigLoadError, load_config
from forgegate.schema_registry import SCHEMAS, schema_filename

runner = CliRunner()


@pytest.mark.parametrize(
    "relative_path",
    [
        "examples/sample-python-api/forgegate.yaml",
        "examples/sample-python-api/policies/pull-request.yaml",
        "examples/sample-python-api/policies/production.yaml",
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
    assert report["phase"] == "phase0-contract-baseline"
    assert report["supported_schemas"] == sorted(SCHEMAS)


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


def test_schema_export_cli(tmp_path: Path) -> None:
    output = tmp_path / "schemas"
    result = runner.invoke(app, ["export-schemas", str(output)])
    assert result.exit_code == 0
    for schema_version in SCHEMAS:
        path = output / schema_filename(schema_version)
        assert path.is_file()
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
