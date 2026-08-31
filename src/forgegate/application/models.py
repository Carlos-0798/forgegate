from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from forgegate.assembly import EvidenceBundleAssembly
from forgegate.candidates import CandidateEvidenceBinding, CandidateHistory
from forgegate.candidates.models import (
    CANDIDATE_ID_PATTERN,
    CandidateDocument,
    CandidateTransition,
    CandidateTransitionResult,
)
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import (
    COMMIT_PATTERN,
    SLUG_PATTERN,
    PolicyConfig,
    ProjectConfig,
    StrictModel,
)
from forgegate.policy import PolicyMaterial
from forgegate.policy.models import PolicyEvaluationDocument


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


class ProjectRegisterCommand(StrictModel):
    config: ProjectConfig
    registered_at: datetime

    @field_validator("registered_at")
    @classmethod
    def registered_at_must_include_timezone(cls, value: datetime) -> datetime:
        return _timezone_aware(value, "registered_at")


class ProjectReviseCommand(StrictModel):
    config: ProjectConfig
    expected_profile_version: int = Field(ge=1)
    effective_at: datetime

    @field_validator("effective_at")
    @classmethod
    def effective_at_must_include_timezone(cls, value: datetime) -> datetime:
        return _timezone_aware(value, "effective_at")


class ProjectProfileQuery(StrictModel):
    project_id: str = Field(pattern=SLUG_PATTERN)
    after_profile_version: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=200)


class ProjectQuery(StrictModel):
    after_project_id: str | None = Field(default=None, pattern=SLUG_PATTERN)
    limit: int = Field(default=100, ge=1, le=200)


class CandidateQuery(StrictModel):
    project_id: str = Field(pattern=SLUG_PATTERN)
    after_candidate_id: str | None = Field(default=None, pattern=CANDIDATE_ID_PATTERN)
    limit: int = Field(default=100, ge=1, le=200)


class AuditEventQuery(StrictModel):
    after_sequence: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=200)
    project_id: str | None = Field(default=None, pattern=SLUG_PATTERN)
    candidate_id: str | None = Field(default=None, pattern=r"^cand-[0-9a-f]{24}$")


class CandidateHistoryView(StrictModel):
    candidate: CandidateDocument
    transitions: tuple[CandidateTransition, ...]
    evidence_binding_required: bool
    evidence_binding: CandidateEvidenceBinding | None
    policy_material_required: bool
    policy_material: PolicyMaterial | None

    @classmethod
    def from_history(cls, history: CandidateHistory) -> CandidateHistoryView:
        return cls(
            candidate=history.candidate,
            transitions=history.transitions,
            evidence_binding_required=history.evidence_binding_required,
            evidence_binding=history.evidence_binding,
            policy_material_required=history.policy_material_required,
            policy_material=history.policy_material,
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
    policy_material: PolicyMaterial | None = None
    policy: PolicyConfig | None = None
    expected_revision: int = Field(ge=0)
    evaluated_at: datetime
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("evaluated_at")
    @classmethod
    def evaluated_at_must_include_timezone(cls, value: datetime) -> datetime:
        return _timezone_aware(value, "evaluated_at")

    @model_validator(mode="after")
    def exactly_one_policy_input(self) -> CandidateEvaluateCommand:
        if (self.policy_material is None) == (self.policy is None):
            raise ValueError("provide exactly one of policy_material or legacy policy")
        return self


class CandidateAttestCommand(StrictModel):
    issued_at: datetime

    @field_validator("issued_at")
    @classmethod
    def issued_at_must_include_timezone(cls, value: datetime) -> datetime:
        return _timezone_aware(value, "issued_at")


class CandidateEvaluationResult(StrictModel):
    evaluation: PolicyEvaluationDocument
    transition: CandidateTransitionResult
    policy_material: PolicyMaterial | None = None


def _timezone_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value


__all__ = [
    "AuditEventQuery",
    "CandidateAdvanceCommand",
    "CandidateAttestCommand",
    "CandidateBindEvidenceCommand",
    "CandidateCreateCommand",
    "CandidateEvaluateCommand",
    "CandidateEvaluationResult",
    "CandidateHistoryView",
    "CandidateQuery",
    "ProjectProfileQuery",
    "ProjectQuery",
    "ProjectRegisterCommand",
    "ProjectReviseCommand",
]
