"""Explicit offline dependency checks against one exact workspace snapshot."""

import json
import re
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from forgegate.candidates.backups import _check_time, _connect, _deadline
from forgegate.candidates.models import FINGERPRINT_PATTERN
from forgegate.canonical import sha256_fingerprint
from forgegate.collection_jobs import CollectionJobResult
from forgegate.domain.models import SHA256_PATTERN, StrictModel
from forgegate.job_archival import _snapshot
from forgegate.job_archive_models import MAX_ARCHIVED_JOBS, JobArchivePlan, JobArchiveReceipt
from forgegate.workspace_backups import WorkspaceBackupError, _guard, _require, _verified


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


def _check_dependency(
    backup: Path, digest: str, plans: list[JobArchivePlan], deadline: float
) -> int:
    """One disposable verified copy per hash; compare exact original rows/events."""
    with _guard(), _verified(backup, digest, deadline) as (root, manifest, _, _):
        manifest_id = sha256_fingerprint(manifest.model_dump(mode="json"))
        payloads = 0
        with closing(_connect(root / "jobs.db", deadline)) as jobs:
            for plan in plans:
                _check_time(deadline)
                _require(
                    manifest_id == plan.backup_manifest_fingerprint,
                    "RECOVERY_MANIFEST_MISMATCH",
                )
                row, events = _snapshot(jobs, plan.job_id)
                result = (
                    CollectionJobResult.model_validate_json(row["result"])
                    if row["result"] is not None
                    else None
                )
                _require(
                    sha256_fingerprint(row) == plan.source_row_fingerprint
                    and sha256_fingerprint({**row, "result": None}) == plan.retained_row_fingerprint
                    and events == plan.events_fingerprint
                    and sha256_fingerprint(json.loads(row["record"])) == plan.record_fingerprint
                    and len((row["result"] or "").encode()) == plan.result_size_bytes
                    and (sha256_fingerprint(result.model_dump(mode="json")) if result else None)
                    == plan.result_fingerprint
                    and (result.assembly.assembly_id if result and result.assembly else None)
                    == plan.assembly_id,
                    "RECOVERY_JOB_MISMATCH",
                )
                payloads += row["result"] is not None
        _check_time(deadline)
        return payloads


def check_recovery_readiness(
    backup: Path,
    *,
    expected_sha256: str,
    dependencies: dict[str, Path],
    timeout_seconds: float = 30,
) -> WorkspaceRecoveryReadiness:
    """Read only explicit files; root corruption/timeouts fail without a READY report."""
    with _guard():
        _require(expected_sha256 is not None, "WORKSPACE_HASH_INVALID")
        _require(
            len(dependencies) <= MAX_ARCHIVED_JOBS
            and all(re.fullmatch(r"[0-9a-f]{64}", key) for key in dependencies),
            "RECOVERY_DEPENDENCY_MAP_INVALID",
        )
        deadline = _deadline(timeout_seconds)
        with _verified(backup, expected_sha256, deadline) as (root, manifest, digest, details):
            plans: dict[str, list[JobArchivePlan]] = {}
            if manifest.job_store_version == 4:
                with closing(_connect(root / "jobs.db", deadline)) as jobs:
                    for row in jobs.execute("SELECT receipt FROM job_archives ORDER BY job_id"):
                        plan = JobArchiveReceipt.model_validate_json(row[0]).plan
                        plans.setdefault(plan.backup_sha256, []).append(plan)
            _require(set(dependencies) <= set(plans), "RECOVERY_UNUSED_DEPENDENCY")
            checks = []
            for key, group in sorted(plans.items()):
                _check_time(deadline)
                status: Literal["VERIFIED", "NOT_SUPPLIED", "FAILED"] = "NOT_SUPPLIED"
                error = None
                payloads = 0
                if key in dependencies:
                    try:
                        payloads = _check_dependency(dependencies[key], key, group, deadline)
                        status = "VERIFIED"
                    except WorkspaceBackupError as exc:
                        # A global deadline must not be downgraded to a per-file finding.
                        _check_time(deadline)
                        error, status = str(exc), "FAILED"
                checks.append(
                    ArchiveDependencyCheck(
                        backup_sha256=key,
                        job_ids=[p.job_id for p in group],
                        status=status,
                        error_code=error,
                        result_payloads_verified=payloads,
                        jobs_without_result=len(group) - payloads if status == "VERIFIED" else 0,
                    )
                )
            _check_time(deadline)
            return WorkspaceRecoveryReadiness(
                backup_sha256=digest.sha256,
                manifest_fingerprint=sha256_fingerprint(manifest.model_dump(mode="json")),
                checked_at=datetime.now(UTC),
                status="READY" if all(c.status == "VERIFIED" for c in checks) else "INCOMPLETE",
                archived_job_count=details["archived_job_count"],
                dependencies=checks,
            )
