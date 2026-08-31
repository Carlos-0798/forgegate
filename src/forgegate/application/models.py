from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from forgegate.assembly import EvidenceBundleAssembly
from forgegate.candidates import CandidateEvidenceBinding, CandidateHistory
from forgegate.candidates.models import (
    CandidateTransition,
    CandidateTransitionResult,
    ReleaseCandidate,
)
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import COMMIT_PATTERN, SLUG_PATTERN, PolicyConfig, StrictModel
from forgegate.policy.models import PolicyEvaluation


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


class CandidateAdvanceCommand(StrictModel):
    to_status: CandidateStatus
    expected_revision: int = Field(ge=0)
    occurred_at: datetime
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_include_timezone(cls, value: datetime) -> datetime:
        return _timezone_aware(value, "occurred_at")


class CandidateBindEvidenceCommand(StrictModel):
    assembly: EvidenceBundleAssembly
    bound_at: datetime

    @field_validator("bound_at")
    @classmethod
    def bound_at_must_include_timezone(cls, value: datetime) -> datetime:
        return _timezone_aware(value, "bound_at")


class CandidateEvaluateCommand(StrictModel):
    policy: PolicyConfig
    expected_revision: int = Field(ge=0)
    evaluated_at: datetime
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("evaluated_at")
    @classmethod
    def evaluated_at_must_include_timezone(cls, value: datetime) -> datetime:
        return _timezone_aware(value, "evaluated_at")


class CandidateAttestCommand(StrictModel):
    issued_at: datetime

    @field_validator("issued_at")
    @classmethod
    def issued_at_must_include_timezone(cls, value: datetime) -> datetime:
        return _timezone_aware(value, "issued_at")


class CandidateEvaluationResult(StrictModel):
    evaluation: PolicyEvaluation
    transition: CandidateTransitionResult


def _timezone_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value


__all__ = [
    "CandidateAdvanceCommand",
    "CandidateAttestCommand",
    "CandidateBindEvidenceCommand",
    "CandidateCreateCommand",
    "CandidateEvaluateCommand",
    "CandidateEvaluationResult",
    "CandidateHistoryView",
]
