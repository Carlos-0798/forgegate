from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from forgegate.domain.models import ArtifactReference, EvidenceRecord, StrictModel


class CollectionStatus(StrEnum):
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"


class IssueSeverity(StrEnum):
    WARNING = "WARNING"
    REJECTION = "REJECTION"


class CollectionIssue(StrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,127}$")
    severity: IssueSeverity
    message: str = Field(min_length=1, max_length=1024)
    location: str | None = Field(default=None, max_length=512)


class CollectionResult(StrictModel):
    collector_name: str = Field(min_length=1, max_length=120)
    collector_version: str = Field(min_length=1, max_length=120)
    status: CollectionStatus
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    warnings: list[CollectionIssue] = Field(default_factory=list)
    rejected_records: list[CollectionIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def result_shape_matches_status(self) -> CollectionResult:
        if self.status is CollectionStatus.COMPLETE:
            if not self.evidence:
                raise ValueError("complete collection must contain evidence")
            if self.rejected_records:
                raise ValueError("complete collection cannot contain rejected records")
        if self.status is CollectionStatus.REJECTED:
            if self.evidence:
                raise ValueError("rejected collection cannot contain evidence")
            if not self.rejected_records:
                raise ValueError("rejected collection must explain its rejection")
        if any(issue.severity is not IssueSeverity.WARNING for issue in self.warnings):
            raise ValueError("warnings must use WARNING severity")
        if any(issue.severity is not IssueSeverity.REJECTION for issue in self.rejected_records):
            raise ValueError("rejected records must use REJECTION severity")
        return self
