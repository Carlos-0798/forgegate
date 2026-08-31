from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from forgegate.canonical import sha256_fingerprint
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import COMMIT_PATTERN, SLUG_PATTERN, StrictModel

CANDIDATE_ID_PATTERN = r"^cand-[0-9a-f]{24}$"
FINGERPRINT_PATTERN = r"^sha256:[0-9a-f]{64}$"
TERMINAL_CANDIDATE_STATUSES = frozenset(
    {
        CandidateStatus.PASS,
        CandidateStatus.FAIL,
        CandidateStatus.REVIEW,
        CandidateStatus.ERROR,
    }
)
EVALUATION_REQUIRED_STATUSES = frozenset(
    {CandidateStatus.PASS, CandidateStatus.FAIL, CandidateStatus.REVIEW}
)
ALLOWED_CANDIDATE_TRANSITIONS = {
    CandidateStatus.DRAFT: frozenset({CandidateStatus.COLLECTING}),
    CandidateStatus.COLLECTING: frozenset({CandidateStatus.READY}),
    CandidateStatus.READY: frozenset({CandidateStatus.EVALUATING}),
    CandidateStatus.EVALUATING: TERMINAL_CANDIDATE_STATUSES,
    CandidateStatus.PASS: frozenset(),
    CandidateStatus.FAIL: frozenset(),
    CandidateStatus.REVIEW: frozenset(),
    CandidateStatus.ERROR: frozenset(),
}
EXPECTED_CANDIDATE_REVISION = {
    CandidateStatus.DRAFT: 0,
    CandidateStatus.COLLECTING: 1,
    CandidateStatus.READY: 2,
    CandidateStatus.EVALUATING: 3,
    CandidateStatus.PASS: 4,
    CandidateStatus.FAIL: 4,
    CandidateStatus.REVIEW: 4,
    CandidateStatus.ERROR: 4,
}


class ReleaseCandidate(StrictModel):
    schema_version: Literal["forgegate.release-candidate.v1"] = "forgegate.release-candidate.v1"
    candidate_id: str = Field(pattern=CANDIDATE_ID_PATTERN)
    project_id: str = Field(pattern=SLUG_PATTERN)
    version: str = Field(min_length=1, max_length=120)
    commit_sha: str = Field(pattern=COMMIT_PATTERN)
    source_branch: str = Field(min_length=1, max_length=255)
    release_track: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    status: CandidateStatus = CandidateStatus.DRAFT
    revision: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    evaluated_at: datetime | None = None
    evaluation_id: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)

    @field_validator("created_at", "updated_at", "evaluated_at")
    @classmethod
    def timestamps_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("candidate timestamps must include a UTC offset")
        return value

    @model_validator(mode="after")
    def lifecycle_fields_are_consistent(self) -> ReleaseCandidate:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if self.revision != EXPECTED_CANDIDATE_REVISION[self.status]:
            raise ValueError("candidate revision does not match lifecycle status")
        if self.status in TERMINAL_CANDIDATE_STATUSES:
            if self.evaluated_at is None:
                raise ValueError("terminal candidate requires evaluated_at")
            if not self.created_at <= self.evaluated_at <= self.updated_at:
                raise ValueError("evaluated_at must be within the candidate lifetime")
        elif self.evaluated_at is not None:
            raise ValueError("non-terminal candidate cannot have evaluated_at")
        if self.status in EVALUATION_REQUIRED_STATUSES and self.evaluation_id is None:
            raise ValueError("release decision candidate requires evaluation_id")
        if self.status not in TERMINAL_CANDIDATE_STATUSES and self.evaluation_id is not None:
            raise ValueError("non-terminal candidate cannot have evaluation_id")
        return self


class CandidateTransition(StrictModel):
    schema_version: Literal["forgegate.candidate-transition.v1"] = (
        "forgegate.candidate-transition.v1"
    )
    transition_id: str = Field(pattern=FINGERPRINT_PATTERN)
    candidate_id: str = Field(pattern=CANDIDATE_ID_PATTERN)
    from_status: CandidateStatus
    to_status: CandidateStatus
    from_revision: int = Field(ge=0)
    to_revision: int = Field(ge=1)
    prior_candidate_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    result_candidate_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    occurred_at: datetime
    evaluation_id: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def transition_must_be_legal(self) -> CandidateTransition:
        if self.to_revision != self.from_revision + 1:
            raise ValueError("candidate transition must increment revision by one")
        if self.to_status not in ALLOWED_CANDIDATE_TRANSITIONS[self.from_status]:
            raise ValueError(
                f"illegal candidate transition: {self.from_status} -> {self.to_status}"
            )
        if (
            self.from_revision != EXPECTED_CANDIDATE_REVISION[self.from_status]
            or self.to_revision != EXPECTED_CANDIDATE_REVISION[self.to_status]
        ):
            raise ValueError("transition revisions do not match lifecycle statuses")
        if self.prior_candidate_fingerprint == self.result_candidate_fingerprint:
            raise ValueError("candidate transition fingerprints must differ")
        if self.to_status in EVALUATION_REQUIRED_STATUSES and self.evaluation_id is None:
            raise ValueError("release decision transition requires evaluation_id")
        if self.to_status not in TERMINAL_CANDIDATE_STATUSES and self.evaluation_id is not None:
            raise ValueError("non-terminal transition cannot have evaluation_id")
        identity = self.model_dump(mode="json", exclude={"schema_version", "transition_id"})
        if self.transition_id != sha256_fingerprint(identity):
            raise ValueError("transition_id does not match transition content")
        return self


class CandidateTransitionResult(StrictModel):
    schema_version: Literal["forgegate.candidate-transition-result.v1"] = (
        "forgegate.candidate-transition-result.v1"
    )
    candidate: ReleaseCandidate
    transition: CandidateTransition

    @model_validator(mode="after")
    def candidate_and_transition_must_match(self) -> CandidateTransitionResult:
        event = self.transition
        candidate = self.candidate
        if event.candidate_id != candidate.candidate_id:
            raise ValueError("transition candidate_id does not match candidate")
        if event.to_status is not candidate.status:
            raise ValueError("transition result state does not match candidate")
        if event.occurred_at != candidate.updated_at:
            raise ValueError("transition time does not match candidate updated_at")
        if event.evaluation_id != candidate.evaluation_id:
            raise ValueError("transition evaluation_id does not match candidate")
        fingerprint = sha256_fingerprint(candidate.model_dump(mode="json"))
        if event.result_candidate_fingerprint != fingerprint:
            raise ValueError("transition result fingerprint does not match candidate")
        return self
