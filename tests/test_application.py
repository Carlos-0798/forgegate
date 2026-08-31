from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    CandidateEvaluateCommand,
    ProjectRegisterCommand,
)
from forgegate.candidates import CandidateStoreError, ProfileBoundReleaseCandidate
from forgegate.config import load_config
from forgegate.domain.models import ProjectConfig


def command(**updates: Any) -> CandidateCreateCommand:
    values: dict[str, Any] = {
        "project_id": "sample-api",
        "version": "1.2.0",
        "commit_sha": "a" * 40,
        "source_branch": "main",
        "release_track": "pull-request",
        "created_at": datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
    }
    values.update(updates)
    return CandidateCreateCommand.model_validate(values)


def test_candidate_create_command_is_strict_and_requires_offset_time() -> None:
    with pytest.raises(ValidationError, match="created_at must include a UTC offset"):
        command(created_at=datetime(2026, 8, 30, 12, 0))
    with pytest.raises(ValidationError, match="extra_forbidden"):
        CandidateCreateCommand.model_validate({**command().model_dump(), "unexpected": True})


def test_candidate_write_commands_require_offset_times(repository_root: Path) -> None:
    assembly = load_config(repository_root / "tests/golden/evidence_bundle_assembly.json")
    policy = load_config(repository_root / "examples/sample-python-api/policies/pull-request.yaml")

    invalid_commands = (
        (
            CandidateAdvanceCommand,
            {
                "to_status": "COLLECTING",
                "expected_revision": 0,
                "occurred_at": datetime(2026, 8, 30, 12, 1),
            },
            "occurred_at must include a UTC offset",
        ),
        (
            CandidateBindEvidenceCommand,
            {"assembly": assembly, "bound_at": datetime(2026, 8, 30, 20, 31)},
            "bound_at must include a UTC offset",
        ),
        (
            CandidateEvaluateCommand,
            {
                "policy": policy,
                "expected_revision": 3,
                "evaluated_at": datetime(2026, 8, 30, 21, 0),
            },
            "evaluated_at must include a UTC offset",
        ),
        (
            CandidateAttestCommand,
            {"issued_at": datetime(2026, 8, 30, 22, 0)},
            "issued_at must include a UTC offset",
        ),
    )

    for model, values, message in invalid_commands:
        with pytest.raises(ValidationError, match=message):
            model.model_validate(values)


def test_candidate_application_create_replay_and_read_contract(
    tmp_path: Path, repository_root: Path
) -> None:
    application = CandidateApplication.for_database(tmp_path / "forgegate.db")
    application.initialize()
    project = load_config(repository_root / "examples/sample-python-api/forgegate.yaml")
    assert isinstance(project, ProjectConfig)
    application.register_project(
        ProjectRegisterCommand(
            config=project,
            registered_at=datetime(2026, 8, 30, 11, 59, tzinfo=UTC),
        ),
        idempotency_key="project:application:001",
    )

    preview = application.preview_candidate(command())
    created = application.create_candidate(command(), idempotency_key="api:create:001")
    replay = application.create_candidate(command(), idempotency_key="api:create:001")
    history = application.get_history(created.candidate_id)

    assert isinstance(created, ProfileBoundReleaseCandidate)
    assert created == replay == application.get_candidate(created.candidate_id)
    assert created.project_profile_version == 1
    assert preview.candidate_id != created.candidate_id
    assert (
        preview.project_id,
        preview.version,
        preview.commit_sha,
        preview.source_branch,
        preview.release_track,
        preview.created_at,
    ) == (
        created.project_id,
        created.version,
        created.commit_sha,
        created.source_branch,
        created.release_track,
        created.created_at,
    )
    assert history.candidate == created
    assert history.transitions == ()
    assert history.evidence_binding_required is True
    assert history.evidence_binding is None

    with pytest.raises(CandidateStoreError, match="STORE_EVIDENCE_BINDING_NOT_FOUND"):
        application.get_evidence(created.candidate_id)
    with pytest.raises(CandidateStoreError, match="STORE_ATTESTATION_NOT_FOUND"):
        application.get_attestation(created.candidate_id)
