import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import forgegate.bootstrap as bootstrap
from forgegate.bootstrap import InitializationError, InitializationReport, initialize_project
from forgegate.cli import app
from forgegate.config import load_config
from forgegate.domain.models import PolicyConfig, ProjectConfig

runner = CliRunner()


def test_init_creates_valid_generic_template_without_path_disclosure(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            str(tmp_path),
            "--project-id",
            "alpha-project",
            "--project-name",
            "Alpha Project",
        ],
    )
    assert result.exit_code == 0
    report = InitializationReport.model_validate_json(result.stdout)
    assert report.project_id == "alpha-project"
    assert str(tmp_path) not in result.stdout
    assert report.hardware_access == "NOT_REQUESTED"
    assert report.ensured_directories == (
        ".forgegate",
        "artifacts",
        "build/forgegate",
        "policies",
    )
    assert isinstance(load_config(tmp_path / "forgegate.yaml"), ProjectConfig)
    assert isinstance(load_config(tmp_path / "policies/pull-request.yaml"), PolicyConfig)
    assert (tmp_path / ".forgegate").is_dir()
    assert (tmp_path / "artifacts").is_dir()
    assert (tmp_path / "build/forgegate").is_dir()


def test_init_refuses_overwrite_and_preserves_existing_bytes(tmp_path: Path) -> None:
    first = initialize_project(tmp_path)
    original = (tmp_path / "forgegate.yaml").read_bytes()
    with pytest.raises(InitializationError, match="refusing to overwrite"):
        initialize_project(tmp_path)
    second = runner.invoke(app, ["init", str(tmp_path)])
    assert second.exit_code == 3
    assert (tmp_path / "forgegate.yaml").read_bytes() == original
    assert first == InitializationReport.model_validate(first.model_dump(mode="json"))


def test_init_can_create_leaf_and_rejects_invalid_project(tmp_path: Path) -> None:
    target = tmp_path / "new-project"
    report = initialize_project(target, repository="https://example.invalid/alpha")
    payload = json.loads(report.model_dump_json())
    assert payload["status"] == "INITIALIZED"
    assert target.is_dir()

    invalid = tmp_path / "invalid-project"
    invalid.mkdir()
    result = runner.invoke(app, ["init", str(invalid), "--project-id", "INVALID"])
    assert result.exit_code == 3
    assert list(invalid.iterdir()) == []

    missing_target = tmp_path / "invalid-new"
    with pytest.raises(InitializationError, match="invalid project template"):
        initialize_project(missing_target, project_id="INVALID")
    assert not missing_target.exists()


def test_initialization_report_rejects_identity_and_order(tmp_path: Path) -> None:
    report = initialize_project(tmp_path)
    payload = report.model_dump(mode="json")
    with pytest.raises(ValidationError, match="initialization_id"):
        InitializationReport.model_validate(payload | {"initialization_id": "sha256:" + "f" * 64})
    with pytest.raises(ValidationError, match="files must be unique and ordered"):
        InitializationReport.model_validate(
            payload | {"created_files": list(reversed(payload["created_files"]))}
        )
    with pytest.raises(ValidationError, match="directories must be unique and ordered"):
        InitializationReport.model_validate(
            payload | {"ensured_directories": list(reversed(payload["ensured_directories"]))}
        )
    with pytest.raises(ValidationError, match="directories must be unique and ordered"):
        InitializationReport.model_validate(payload | {"ensured_directories": [".forgegate"] * 4})


def test_init_rejects_unsafe_targets_and_rolls_back(tmp_path: Path, monkeypatch) -> None:
    target_file = tmp_path / "file-target"
    target_file.write_text("keep", encoding="utf-8")
    with pytest.raises(InitializationError, match="must be a directory"):
        initialize_project(target_file)

    unsafe = tmp_path / "unsafe"
    unsafe.mkdir()
    (unsafe / ".forgegate").write_text("keep", encoding="utf-8")
    with pytest.raises(InitializationError, match="directory is unsafe"):
        initialize_project(unsafe)

    rollback = tmp_path / "rollback"
    rollback.mkdir()
    monkeypatch.setattr(bootstrap.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError()))
    with pytest.raises(InitializationError, match="cannot create"):
        initialize_project(rollback)
    assert not (rollback / "forgegate.yaml").exists()
    assert not (rollback / "policies/pull-request.yaml").exists()

    parent_file = tmp_path / "parent-file"
    parent_file.write_text("keep", encoding="utf-8")
    with pytest.raises(InitializationError, match="parent must be a directory"):
        initialize_project(parent_file / "child")


def test_prepare_root_wraps_creation_failure(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "cannot-create"
    original = Path.mkdir

    def fail_selected(path: Path, *args, **kwargs):
        if path == target:
            raise OSError("injected")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_selected)
    with pytest.raises(InitializationError, match="cannot create project target"):
        initialize_project(target)
