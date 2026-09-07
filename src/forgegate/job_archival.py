"""Explicit owner-reviewed logical archival backed by an exact workspace snapshot."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forgegate.bounded_parsing import enforce_json_structure_limits
from forgegate.candidates.backups import _check_time, _connect, _deadline, _source
from forgegate.candidates.store import SQLiteCandidateRepository
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.collection_jobs import ACTIVE, CollectionJobResult, CollectionJobStore
from forgegate.job_archive_models import MAX_ARCHIVED_JOBS, JobArchivePlan, JobArchiveReceipt
from forgegate.workspace_backups import _guard, _job_schema, _require, _reserve, _unique, _verified


def _now() -> datetime:
    return datetime.now(UTC)


def _snapshot(con: sqlite3.Connection, job_id: str) -> tuple[dict[str, Any], str]:
    row = con.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    _require(row is not None, "ARCHIVE_JOB_NOT_FOUND")
    events = [
        dict(e)
        for e in con.execute("SELECT * FROM events WHERE job_id=? ORDER BY revision", (job_id,))
    ]
    return dict(row), sha256_fingerprint(events)


def _candidate(con: sqlite3.Connection, database: Path, plan: JobArchivePlan) -> None:
    repository = SQLiteCandidateRepository(database)
    repository._validate_store(con)
    history = repository._load_history(con, plan.candidate_id)
    _require(history.candidate.project_id == plan.project_id, "ARCHIVE_PROJECT_MISMATCH")
    _require(
        sha256_fingerprint(history.candidate.model_dump(mode="json"))
        == plan.expected_candidate_fingerprint,
        "ARCHIVE_CANDIDATE_CHANGED",
    )
    binding = history.evidence_binding
    _require(
        binding is None or binding.assembly.assembly_id != plan.assembly_id,
        "ARCHIVE_BOUND_EVIDENCE",
    )


def _validate_live(
    jobs: sqlite3.Connection,
    store: CollectionJobStore,
    source_row: dict[str, Any],
    source_events: str,
    plan: JobArchivePlan,
) -> None:
    _job_schema(jobs)
    _require(jobs.execute("PRAGMA user_version").fetchone()[0] == 4, "ARCHIVE_MIGRATION_REQUIRED")
    review = store.review_snapshot(jobs, plan.job_id, project_id=plan.project_id)
    _require(review.archive is None, "ARCHIVE_ALREADY_ARCHIVED")
    _require(review.record.state not in ACTIVE, "ARCHIVE_ACTIVE_JOB")
    _require(review.record.revision == plan.expected_revision, "ARCHIVE_REVISION_CONFLICT")
    _require(
        review.record.updated_at < plan.terminal_before <= plan.planned_at <= _now(),
        "ARCHIVE_TIME_INVALID",
    )
    row, events = _snapshot(jobs, plan.job_id)
    _require(row == source_row and events == source_events, "ARCHIVE_BACKUP_STALE")
    _require(
        sha256_fingerprint(row) == plan.source_row_fingerprint
        and sha256_fingerprint({**row, "result": None}) == plan.retained_row_fingerprint
        and events == plan.events_fingerprint
        and sha256_fingerprint(json.loads(row["record"])) == plan.record_fingerprint
        and review.record.candidate_id == plan.candidate_id
        and review.record.result_fingerprint == plan.result_fingerprint
        and len((row["result"] or "").encode()) == plan.result_size_bytes
        and (
            review.result.assembly.assembly_id
            if review.result is not None and review.result.assembly is not None
            else None
        )
        == plan.assembly_id,
        "ARCHIVE_PLAN_MISMATCH",
    )


def plan_job_archive(
    database: Path,
    job_store: Path,
    backup: Path,
    job_id: str,
    *,
    expected_sha256: str,
    expected_revision: int,
    terminal_before: datetime,
    timeout_seconds: float = 30,
) -> JobArchivePlan:
    with _guard():
        _require(expected_sha256 is not None, "WORKSPACE_HASH_INVALID")
        deadline = _deadline(timeout_seconds)
        database, job_store = _source(database), _source(job_store)
        store = CollectionJobStore(job_store)
        with _verified(backup, expected_sha256, deadline) as (root, manifest, digest, _):
            with closing(_connect(root / "jobs.db", deadline)) as source:
                source_row, source_events = _snapshot(source, job_id)
            with _reserve(job_store, deadline) as jobs, _reserve(database, deadline) as candidates:
                review = store.review_snapshot(
                    jobs, job_id, project_id=json.loads(source_row["record"])["project_id"]
                )
                _require(review.archive is None, "ARCHIVE_ALREADY_ARCHIVED")
                _require(review.record.state not in ACTIVE, "ARCHIVE_ACTIVE_JOB")
                repository = SQLiteCandidateRepository(database)
                repository._validate_store(candidates)
                history = repository._load_history(candidates, review.record.candidate_id)
                plan = JobArchivePlan(
                    job_id=job_id,
                    candidate_id=review.record.candidate_id,
                    project_id=review.record.project_id,
                    expected_revision=expected_revision,
                    record_fingerprint=sha256_fingerprint(review.record.model_dump(mode="json")),
                    events_fingerprint=source_events,
                    source_row_fingerprint=sha256_fingerprint(source_row),
                    retained_row_fingerprint=sha256_fingerprint({**source_row, "result": None}),
                    result_fingerprint=review.record.result_fingerprint,
                    assembly_id=review.result.assembly.assembly_id
                    if review.result is not None and review.result.assembly is not None
                    else None,
                    result_size_bytes=len((source_row["result"] or "").encode()),
                    backup_sha256=digest.sha256,
                    backup_manifest_fingerprint=sha256_fingerprint(
                        manifest.model_dump(mode="json")
                    ),
                    expected_candidate_fingerprint=sha256_fingerprint(
                        history.candidate.model_dump(mode="json")
                    ),
                    terminal_before=terminal_before,
                    planned_at=_now(),
                )
                _validate_live(jobs, store, source_row, source_events, plan)
                _candidate(candidates, database, plan)
                _check_time(deadline)
                return plan


def load_archive_plan(path: Path) -> JobArchivePlan:
    with _guard():
        with _source(path).open("rb") as stream:
            payload = stream.read(16385)
        _require(len(payload) <= 16384, "ARCHIVE_PLAN_TOO_LARGE")
        enforce_json_structure_limits(payload, max_nodes=100, max_depth=5)
        return JobArchivePlan.model_validate(json.loads(payload, object_pairs_hook=_unique))


def archive_job(
    database: Path,
    job_store: Path,
    backup: Path,
    plan: JobArchivePlan,
    *,
    confirm_plan: str,
    timeout_seconds: float = 30,
) -> JobArchiveReceipt:
    with _guard():
        plan = JobArchivePlan.model_validate_json(plan.model_dump_json())
        fingerprint = sha256_fingerprint(plan.model_dump(mode="json"))
        _require(confirm_plan == fingerprint, "ARCHIVE_CONFIRMATION_MISMATCH")
        deadline = _deadline(timeout_seconds)
        database, job_store = _source(database), _source(job_store)
        store = CollectionJobStore(job_store)
        with _verified(backup, plan.backup_sha256, deadline) as (root, manifest, _, _details):
            _require(
                sha256_fingerprint(manifest.model_dump(mode="json"))
                == plan.backup_manifest_fingerprint,
                "ARCHIVE_PLAN_MISMATCH",
            )
            with closing(_connect(root / "jobs.db", deadline)) as source:
                source_row, source_events = _snapshot(source, plan.job_id)
            with _reserve(job_store, deadline) as jobs, _reserve(database, deadline) as candidates:
                _job_schema(jobs)
                review = store.review_snapshot(jobs, plan.job_id, project_id=plan.project_id)
                if review.archive is not None:
                    _require(review.archive.plan == plan, "ARCHIVE_REPLAY_CONFLICT")
                    return review.archive
                _validate_live(jobs, store, source_row, source_events, plan)
                _candidate(candidates, database, plan)
                _require(
                    jobs.execute("SELECT count(*) FROM job_archives").fetchone()[0]
                    < MAX_ARCHIVED_JOBS,
                    "ARCHIVE_CAPACITY_EXCEEDED",
                )
                receipt = JobArchiveReceipt(
                    plan=plan, plan_fingerprint=fingerprint, archived_at=_now()
                )
                # One job-store transaction: an insertion/commit failure restores the result.
                # Candidate reservation is held until the job-store commit completes.
                jobs.execute("UPDATE jobs SET result=NULL WHERE job_id=?", (plan.job_id,))
                jobs.execute(
                    "INSERT INTO job_archives(job_id,receipt) VALUES(?,?)",
                    (plan.job_id, canonical_json(receipt.model_dump(mode="json"))),
                )
                _check_time(deadline)
                jobs.commit()
                return receipt


def read_archived_result(
    backup: Path, job_id: str, *, expected_sha256: str, timeout_seconds: float = 30
) -> CollectionJobResult:
    with _guard():
        _require(expected_sha256 is not None, "WORKSPACE_HASH_INVALID")
        deadline = _deadline(timeout_seconds)
        with (
            _verified(backup, expected_sha256, deadline) as (root, _, _digest, _details),
            closing(_connect(root / "jobs.db", deadline)) as source,
        ):
            row, _ = _snapshot(source, job_id)
            _require(row["result"] is not None, "ARCHIVE_RESULT_NOT_IN_BACKUP")
            return CollectionJobResult.model_validate_json(row["result"])
