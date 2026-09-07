"""Explicit offline dependency checks against one exact workspace snapshot."""

import json
import re
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from forgegate.candidates.backups import _check_time, _connect, _deadline
from forgegate.canonical import sha256_fingerprint
from forgegate.collection_jobs import CollectionJobResult
from forgegate.job_archival import _snapshot
from forgegate.job_archive_models import MAX_ARCHIVED_JOBS, JobArchivePlan, JobArchiveReceipt
from forgegate.recovery_models import (
    ArchiveDependencyCheck,
    WorkspaceRecoveryReadiness,
)
from forgegate.workspace_backups import WorkspaceBackupError, _guard, _require, _verified


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
