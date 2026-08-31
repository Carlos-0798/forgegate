from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from forgegate.application import CandidateApplication, CandidateCreateCommand
from forgegate.candidates import CandidateStoreError


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


def test_candidate_application_create_replay_and_read_contract(tmp_path: Path) -> None:
    application = CandidateApplication.for_database(tmp_path / "forgegate.db")
    application.initialize()

    preview = application.preview_candidate(command())
    created = application.create_candidate(command(), idempotency_key="api:create:001")
    replay = application.create_candidate(command(), idempotency_key="api:create:001")
    history = application.get_history(created.candidate_id)

    assert preview == created == replay == application.get_candidate(created.candidate_id)
    assert history.candidate == created
    assert history.transitions == ()
    assert history.evidence_binding_required is True
    assert history.evidence_binding is None

    with pytest.raises(CandidateStoreError, match="STORE_EVIDENCE_BINDING_NOT_FOUND"):
        application.get_evidence(created.candidate_id)
    with pytest.raises(CandidateStoreError, match="STORE_ATTESTATION_NOT_FOUND"):
        application.get_attestation(created.candidate_id)
