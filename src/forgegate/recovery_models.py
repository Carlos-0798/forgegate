"""Strict path-free reports for offline recovery checks and review handoffs."""

import hashlib
import json
import re
from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from forgegate.bounded_parsing import enforce_json_structure_limits
from forgegate.candidates.models import FINGERPRINT_PATTERN
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.models import SHA256_PATTERN, StrictModel
from forgegate.job_archive_models import MAX_ARCHIVED_JOBS

MAX_RECOVERY_REPORT_BYTES = 256 * 1024


class ArchiveDependencyCheck(StrictModel):
    backup_sha256: str = Field(pattern=SHA256_PATTERN)
    job_ids: list[str] = Field(min_length=1, max_length=MAX_ARCHIVED_JOBS)
    status: Literal["VERIFIED", "NOT_SUPPLIED", "FAILED"]
    error_code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{0,79}$")
    result_payloads_verified: int = Field(ge=0, le=MAX_ARCHIVED_JOBS)
    jobs_without_result: int = Field(ge=0, le=MAX_ARCHIVED_JOBS)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.job_ids != sorted(set(self.job_ids)) or any(
            re.fullmatch(r"job-[0-9a-f]{32}", job) is None for job in self.job_ids
        ):
            raise ValueError("dependency job identities must be canonical and unique")
        if (self.status == "FAILED") != (self.error_code is not None):
            raise ValueError("only failed checks carry error codes")
        count = self.result_payloads_verified + self.jobs_without_result
        if count != (len(self.job_ids) if self.status == "VERIFIED" else 0):
            raise ValueError("dependency verification counts disagree")
        return self


class WorkspaceRecoveryReadiness(StrictModel):
    schema_version: Literal["forgegate.workspace-recovery-readiness.v1"] = (
        "forgegate.workspace-recovery-readiness.v1"
    )
    backup_sha256: str = Field(pattern=SHA256_PATTERN)
    manifest_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    checked_at: datetime
    status: Literal["READY", "INCOMPLETE"]
    archived_job_count: int = Field(ge=0, le=MAX_ARCHIVED_JOBS)
    dependencies: list[ArchiveDependencyCheck] = Field(max_length=MAX_ARCHIVED_JOBS)
    scope: Literal["snapshot_and_exact_archived_job_payloads"] = (
        "snapshot_and_exact_archived_job_payloads"
    )
    availability: Literal["observed_during_check_only"] = "observed_during_check_only"
    restore: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    producer_authenticity: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"
    external_identity_and_artifact_files: Literal["NOT_CHECKED"] = "NOT_CHECKED"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.checked_at.utcoffset() is None:
            raise ValueError("check timestamp requires offset")
        hashes = [item.backup_sha256 for item in self.dependencies]
        jobs = [job for item in self.dependencies for job in item.job_ids]
        if hashes != sorted(set(hashes)) or len(jobs) != len(set(jobs)):
            raise ValueError("dependency identities must be unique and sorted")
        if len(jobs) != self.archived_job_count:
            raise ValueError("archived job count mismatch")
        expected = (
            "READY" if all(d.status == "VERIFIED" for d in self.dependencies) else "INCOMPLETE"
        )
        if self.status != expected:
            raise ValueError("readiness disagrees with dependency checks")
        return self


class RecoveryReadinessHandoff(StrictModel):
    schema_version: Literal["forgegate.recovery-readiness-handoff.v1"] = (
        "forgegate.recovery-readiness-handoff.v1"
    )
    handoff_id: str = Field(pattern=FINGERPRINT_PATTERN)
    source_report_sha256: str = Field(pattern=SHA256_PATTERN)
    report_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    disposition: Literal["READY_FOR_REHEARSAL", "BLOCKED"]
    readiness: WorkspaceRecoveryReadiness
    dependency_count: int = Field(ge=0, le=MAX_ARCHIVED_JOBS)
    verified_dependency_count: int = Field(ge=0, le=MAX_ARCHIVED_JOBS)
    result_payloads_verified: int = Field(ge=0, le=MAX_ARCHIVED_JOBS)
    jobs_without_result: int = Field(ge=0, le=MAX_ARCHIVED_JOBS)
    payload_transfer: Literal["NOT_INCLUDED"] = "NOT_INCLUDED"
    live_availability: Literal["NOT_CHECKED"] = "NOT_CHECKED"
    restore: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"

    def identity_fields(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"handoff_id"})

    @model_validator(mode="after")
    def coherent(self) -> Self:
        expected_disposition = (
            "READY_FOR_REHEARSAL" if self.readiness.status == "READY" else "BLOCKED"
        )
        verified = [item for item in self.readiness.dependencies if item.status == "VERIFIED"]
        if (
            self.disposition != expected_disposition
            or self.report_fingerprint != sha256_fingerprint(self.readiness.model_dump(mode="json"))
            or self.dependency_count != len(self.readiness.dependencies)
            or self.verified_dependency_count != len(verified)
            or self.result_payloads_verified
            != sum(item.result_payloads_verified for item in verified)
            or self.jobs_without_result != sum(item.jobs_without_result for item in verified)
        ):
            raise ValueError("recovery handoff summary mismatch")
        if self.handoff_id != sha256_fingerprint(self.identity_fields()):
            raise ValueError("recovery handoff identity mismatch")
        return self


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def build_recovery_handoff(document: str, expected_sha256: str) -> RecoveryReadinessHandoff:
    """Validate exact imported UTF-8 JSON and derive a path-free review artifact."""
    raw = document.encode("utf-8")
    if (
        not raw
        or len(raw) > MAX_RECOVERY_REPORT_BYTES
        or re.fullmatch(SHA256_PATTERN, expected_sha256) is None
        or hashlib.sha256(raw).hexdigest() != expected_sha256
    ):
        raise ValueError("recovery report bytes or hash invalid")
    enforce_json_structure_limits(raw, max_nodes=20_000, max_depth=20)
    payload = json.loads(
        document,
        object_pairs_hook=_unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")),
    )
    report = WorkspaceRecoveryReadiness.model_validate(payload)
    verified = [item for item in report.dependencies if item.status == "VERIFIED"]
    values: dict[str, object] = {
        "schema_version": "forgegate.recovery-readiness-handoff.v1",
        "source_report_sha256": expected_sha256,
        "report_fingerprint": sha256_fingerprint(report.model_dump(mode="json")),
        "disposition": "READY_FOR_REHEARSAL" if report.status == "READY" else "BLOCKED",
        "readiness": report.model_dump(mode="json"),
        "dependency_count": len(report.dependencies),
        "verified_dependency_count": len(verified),
        "result_payloads_verified": sum(item.result_payloads_verified for item in verified),
        "jobs_without_result": sum(item.jobs_without_result for item in verified),
        "payload_transfer": "NOT_INCLUDED",
        "live_availability": "NOT_CHECKED",
        "restore": "NOT_PERFORMED",
    }
    return RecoveryReadinessHandoff.model_validate(
        {"handoff_id": sha256_fingerprint(values), **values}
    )
