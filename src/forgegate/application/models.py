from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from forgegate.candidates import CandidateEvidenceBinding, CandidateHistory
from forgegate.candidates.models import CandidateTransition, ReleaseCandidate
from forgegate.domain.models import COMMIT_PATTERN, SLUG_PATTERN, StrictModel


class CandidateCreateCommand(StrictModel):
    project_id: str = Field(pattern=SLUG_PATTERN)
    version: str = Field(min_length=1, max_length=120)
    commit_sha: str = Field(pattern=COMMIT_PATTERN)
    source_branch: str = Field(default="main", min_length=1, max_length=255)
    release_track: str = Field(default="pull-request", pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a UTC offset")
        return value


class CandidateHistoryView(StrictModel):
    candidate: ReleaseCandidate
    transitions: tuple[CandidateTransition, ...]
    evidence_binding_required: bool
    evidence_binding: CandidateEvidenceBinding | None

    @classmethod
    def from_history(cls, history: CandidateHistory) -> CandidateHistoryView:
        return cls(
            candidate=history.candidate,
            transitions=history.transitions,
            evidence_binding_required=history.evidence_binding_required,
            evidence_binding=history.evidence_binding,
        )


__all__ = ["CandidateCreateCommand", "CandidateHistoryView"]
