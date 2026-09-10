"""Archive metadata preserves terminal job identities without retaining result payloads."""

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from forgegate.candidates.models import CANDIDATE_ID_PATTERN, FINGERPRINT_PATTERN
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.models import SHA256_PATTERN, SLUG_PATTERN, StrictModel

MAX_ARCHIVED_JOBS = 1000


class JobArchivePlan(StrictModel):
    schema_version: Literal["forgegate.job-archive-plan.v1"] = "forgegate.job-archive-plan.v1"
    job_id: str = Field(pattern=r"^job-[0-9a-f]{32}$")
    candidate_id: str = Field(pattern=CANDIDATE_ID_PATTERN)
    project_id: str = Field(pattern=SLUG_PATTERN)
    expected_revision: int = Field(ge=1, le=64)
    record_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    events_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    source_row_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    retained_row_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    result_fingerprint: str | None = Field(pattern=FINGERPRINT_PATTERN)
    assembly_id: str | None = Field(pattern=FINGERPRINT_PATTERN)
    result_size_bytes: int = Field(ge=0, le=4 * 1024 * 1024)
    backup_sha256: str = Field(pattern=SHA256_PATTERN)
    backup_manifest_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    expected_candidate_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    terminal_before: datetime
    planned_at: datetime
    authority: Literal["LOCAL_CLI_NOT_AUTHENTICATED"] = "LOCAL_CLI_NOT_AUTHENTICATED"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if any(t.utcoffset() is None for t in (self.terminal_before, self.planned_at)):
            raise ValueError("archive timestamps require offsets")
        if self.terminal_before > self.planned_at:
            raise ValueError("future archive cutoff")
        if (self.result_fingerprint is None) != (self.result_size_bytes == 0):
            raise ValueError("archive result size mismatch")
        if self.assembly_id is not None and self.result_fingerprint is None:
            raise ValueError("archive assembly requires result")
        return self


class JobArchiveReceipt(StrictModel):
    schema_version: Literal["forgegate.job-archive-receipt.v1"] = "forgegate.job-archive-receipt.v1"
    plan: JobArchivePlan
    plan_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    archived_at: datetime
    logical_job_slots_reclaimed: Literal[1] = 1
    audit_and_idempotency_records: Literal["retained"] = "retained"
    result_storage: Literal["external_workspace_backup"] = "external_workspace_backup"
    physical_file_shrink: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    secure_erasure: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.plan_fingerprint != sha256_fingerprint(self.plan.model_dump(mode="json")):
            raise ValueError("archive plan fingerprint mismatch")
        if self.archived_at.utcoffset() is None or self.archived_at < self.plan.planned_at:
            raise ValueError("archive timestamp mismatch")
        return self
