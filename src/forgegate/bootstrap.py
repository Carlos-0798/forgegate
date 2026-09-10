from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator

from forgegate.canonical import sha256_fingerprint
from forgegate.domain.enums import CollectorType, Decision, Operator
from forgegate.domain.models import (
    ArtifactReference,
    CollectorConfig,
    OutputConfig,
    PolicyConfig,
    PolicyRule,
    ProjectConfig,
    ProjectIdentity,
    ReleaseTrack,
    StrictModel,
)


class InitializationError(ValueError):
    pass


class InitializationReport(StrictModel):
    """Deterministic path-free receipt for a newly created project template."""

    schema_version: Literal["forgegate.initialization-report.v1"] = (
        "forgegate.initialization-report.v1"
    )
    initialization_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: Literal["INITIALIZED"] = "INITIALIZED"
    project_id: str
    created_files: tuple[ArtifactReference, ...] = Field(min_length=2, max_length=2)
    ensured_directories: tuple[str, ...] = Field(min_length=4, max_length=4)
    configuration_validation: Literal["STRICT_MODELS_VALIDATED"] = "STRICT_MODELS_VALIDATED"
    hardware_access: Literal["NOT_REQUESTED"] = "NOT_REQUESTED"

    @model_validator(mode="after")
    def report_identity_holds(self) -> InitializationReport:
        paths = [item.path_or_uri for item in self.created_files]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise ValueError("initialized files must be unique and ordered")
        directories = self.ensured_directories
        if tuple(sorted(directories)) != directories or len(directories) != len(set(directories)):
            raise ValueError("initialized directories must be unique and ordered")
        if self.initialization_id != sha256_fingerprint(_report_identity(self)):
            raise ValueError("initialization_id does not match report content")
        return self


def initialize_project(
    target: Path,
    *,
    project_id: str = "sample-project",
    project_name: str = "Sample Project",
    repository: str | None = None,
    default_branch: str = "main",
) -> InitializationReport:
    """Create a strict generic ForgeGate template without overwriting existing files."""

    root, created_root = _prepare_root(target)
    relative_files = ("forgegate.yaml", "policies/pull-request.yaml")
    relative_directories = (".forgegate", "artifacts", "build/forgegate", "policies")
    for relative in relative_files:
        destination = root / Path(relative)
        if destination.exists() or destination.is_symlink():
            if created_root:
                root.rmdir()
            raise InitializationError(f"refusing to overwrite existing path: {relative}")
    for relative in relative_directories:
        destination = root / Path(relative)
        if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
            if created_root and not any(root.iterdir()):
                root.rmdir()
            raise InitializationError(f"initialization directory is unsafe: {relative}")

    try:
        project, policy = _template_models(
            project_id=project_id,
            project_name=project_name,
            repository=repository,
            default_branch=default_branch,
        )
    except ValidationError as exc:
        if created_root and not any(root.iterdir()):
            root.rmdir()
        raise InitializationError(f"invalid project template request: {exc}") from exc
    content = {
        "forgegate.yaml": _yaml_bytes(project),
        "policies/pull-request.yaml": _yaml_bytes(policy),
    }
    staging = Path(tempfile.mkdtemp(prefix=".forgegate-init-", dir=root.parent))
    created_files: list[Path] = []
    created_directories: list[Path] = []
    try:
        for relative, payload in content.items():
            staged = staging / Path(relative)
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(payload)
        for relative in relative_directories:
            directory = root / Path(relative)
            if not directory.exists():
                directory.mkdir(parents=True)
                created_directories.append(directory)
        for relative in relative_files:
            destination = root / Path(relative)
            os.replace(staging / Path(relative), destination)
            created_files.append(destination)
    except OSError as exc:
        for path in reversed(created_files):
            path.unlink(missing_ok=True)
        for directory in sorted(
            created_directories, key=lambda item: len(item.parts), reverse=True
        ):
            with suppress(OSError):
                directory.rmdir()
        if created_root:
            with suppress(OSError):
                root.rmdir()
        raise InitializationError("cannot create ForgeGate project template") from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    references = tuple(
        ArtifactReference(
            path_or_uri=relative,
            media_type="application/yaml",
            sha256=hashlib.sha256(content[relative]).hexdigest(),
            size_bytes=len(content[relative]),
        )
        for relative in sorted(relative_files)
    )
    candidate_report = InitializationReport.model_construct(
        initialization_id="sha256:" + "0" * 64,
        project_id=project.project.id,
        created_files=references,
        ensured_directories=tuple(sorted(relative_directories)),
    )
    return InitializationReport.model_validate(
        {
            **candidate_report.model_dump(mode="json"),
            "initialization_id": sha256_fingerprint(_report_identity(candidate_report)),
        }
    )


def _prepare_root(target: Path) -> tuple[Path, bool]:
    if target.is_symlink():
        raise InitializationError("project target cannot be a symbolic link")
    if target.exists():
        if not target.is_dir():
            raise InitializationError("project target must be a directory")
        return target.resolve(strict=True), False
    parent = target.parent.resolve(strict=True)
    if not parent.is_dir():
        raise InitializationError("project target parent must be a directory")
    try:
        target.mkdir()
    except OSError as exc:
        raise InitializationError("cannot create project target") from exc
    return target.resolve(strict=True), True


def _template_models(
    *,
    project_id: str,
    project_name: str,
    repository: str | None,
    default_branch: str,
) -> tuple[ProjectConfig, PolicyConfig]:
    project = ProjectConfig(
        schema_version="forgegate.project.v1",
        project=ProjectIdentity(
            id=project_id,
            name=project_name,
            repository=repository,
            default_branch=default_branch,
        ),
        release_tracks={
            "pull_request": ReleaseTrack(policy="policies/pull-request.yaml"),
        },
        collectors=[
            CollectorConfig(type=CollectorType.JUNIT, path="artifacts/junit.xml"),
            CollectorConfig(type=CollectorType.COVERAGE_XML, path="artifacts/coverage.xml"),
            CollectorConfig(type=CollectorType.SARIF, path="artifacts/security.sarif"),
            CollectorConfig(type=CollectorType.BENCHMARK_JSON, path="artifacts/benchmark.json"),
        ],
        outputs=OutputConfig(
            **{
                "json": "build/forgegate/attestation.json",
                "markdown": "build/forgegate/summary.md",
            }
        ),
    )
    policy = PolicyConfig(
        schema_version="forgegate.policy.v1",
        name="pull-request",
        rules=[
            PolicyRule(
                id="tests-pass",
                claim="tests.required-pass",
                evidence_kind="test.summary",
                operator=Operator.EQUALS,
                expected=0,
                where={"field": "failures"},
                mandatory=True,
                require_presence=True,
                on_missing=Decision.REVIEW,
            ),
            PolicyRule(
                id="tests-no-errors",
                claim="tests.no-errors",
                evidence_kind="test.summary",
                operator=Operator.EQUALS,
                expected=0,
                where={"field": "errors"},
                mandatory=True,
                require_presence=True,
                on_missing=Decision.REVIEW,
            ),
            PolicyRule(
                id="tests-executed",
                claim="tests.at-least-one-passed",
                evidence_kind="test.summary",
                operator=Operator.GREATER_THAN,
                expected=0,
                where={"field": "passed"},
                mandatory=True,
                require_presence=True,
                on_missing=Decision.REVIEW,
            ),
        ],
    )
    return project, policy


def _yaml_bytes(document: StrictModel) -> bytes:
    rendered = yaml.safe_dump(
        document.model_dump(mode="json", by_alias=True, exclude_none=True),
        sort_keys=False,
        allow_unicode=False,
    )
    return rendered.encode("utf-8")


def _report_identity(report: InitializationReport) -> dict[str, object]:
    return report.model_dump(mode="json", exclude={"schema_version", "initialization_id"})


__all__ = ["InitializationError", "InitializationReport", "initialize_project"]
