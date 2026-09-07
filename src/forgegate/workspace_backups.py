"""Coordinated local database snapshots and recovery into a new private directory."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import struct
import tempfile
import time
import zipfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any, Literal, Self

from pydantic import Field, model_validator

from forgegate.bounded_parsing import enforce_json_structure_limits
from forgegate.candidates.backups import (
    TABLES,
    StoreBackupError,
    _check_time,
    _connect,
    _deadline,
    _sidecars,
    _source,
)
from forgegate.candidates.store import CandidateStoreError, SQLiteCandidateRepository
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.collection_jobs import (
    ACTIVE,
    APP_ID,
    MAX_INPUT_BYTES,
    MAX_JOBS,
    MAX_RESULT_BYTES,
    CollectionJobRequest,
    CollectionJobStore,
)
from forgegate.domain.models import SHA256_PATTERN, StrictModel
from forgegate.job_archive_models import MAX_ARCHIVED_JOBS

MAX_STORE_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_BYTES = MAX_STORE_BYTES + 128 * 1024
MAX_MANIFEST_BYTES = 16 * 1024
MEMBERS = ("candidates.db", "jobs.db", "manifest.json")


class WorkspaceBackupError(RuntimeError):
    """Fixed path-free operational code."""


class SnapshotMember(StrictModel):
    sha256: str = Field(pattern=SHA256_PATTERN)
    size_bytes: int = Field(ge=1, le=MAX_ARCHIVE_BYTES)


class _WorkspaceBackupFields(StrictModel):
    created_at: datetime
    candidate_store_version: Literal[9] = 9
    candidate_store: SnapshotMember
    job_store: SnapshotMember
    consistency: Literal["simultaneous_sqlite_write_reservations"] = (
        "simultaneous_sqlite_write_reservations"
    )
    running_jobs: Literal[0] = 0
    encrypted: Literal[False] = False
    includes_pending_report_bytes: Literal[True] = True
    external_identity_and_artifact_files: Literal["not_included"] = "not_included"
    producer_authenticity: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.created_at.utcoffset() is None:
            raise ValueError("backup timestamp requires offset")
        if self.candidate_store.size_bytes + self.job_store.size_bytes > MAX_STORE_BYTES:
            raise ValueError("combined snapshot exceeds limit")
        return self


class WorkspaceBackupManifest(_WorkspaceBackupFields):
    schema_version: Literal["forgegate.workspace-backup.v1"] = "forgegate.workspace-backup.v1"
    job_store_version: Literal[3] = 3


class WorkspaceBackupManifestV2(_WorkspaceBackupFields):
    schema_version: Literal["forgegate.workspace-backup.v2"] = "forgegate.workspace-backup.v2"
    job_store_version: Literal[4] = 4
    archived_result_payloads: Literal["external_backups_required"] = "external_backups_required"


BackupManifest = WorkspaceBackupManifest | WorkspaceBackupManifestV2


@contextmanager
def _guard() -> Iterator[None]:
    try:
        yield
    except FileExistsError as exc:
        raise WorkspaceBackupError("WORKSPACE_DESTINATION_EXISTS") from exc
    except sqlite3.OperationalError as exc:
        code = getattr(exc, "sqlite_errorcode", 0) & 0xFF
        label = "BUSY" if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) else "INVALID"
        raise WorkspaceBackupError(f"WORKSPACE_{label}") from exc
    except StoreBackupError as exc:
        # Helpers only emit fixed BACKUP_* codes.
        raise WorkspaceBackupError(str(exc).replace("BACKUP_", "WORKSPACE_", 1)) from exc
    except (
        OSError,
        sqlite3.Error,
        CandidateStoreError,
        ValueError,
        zipfile.BadZipFile,
        struct.error,
    ) as exc:
        raise WorkspaceBackupError("WORKSPACE_INVALID") from exc


def _require(ok: bool, code: str = "WORKSPACE_INVALID") -> None:
    if not ok:
        raise WorkspaceBackupError(code)


def _stream(
    reader: IO[bytes], writer: IO[bytes] | None, deadline: float, limit: int
) -> SnapshotMember:
    digest = hashlib.sha256()
    size = 0
    while chunk := reader.read(1024 * 1024):
        _check_time(deadline)
        size += len(chunk)
        _require(size <= limit, "WORKSPACE_TOO_LARGE")
        digest.update(chunk)
        if writer is not None:
            writer.write(chunk)
    _check_time(deadline)
    return SnapshotMember(sha256=digest.hexdigest(), size_bytes=size)


def _hash(path: Path, deadline: float, limit: int = MAX_STORE_BYTES) -> SnapshotMember:
    with path.open("rb") as stream:
        return _stream(stream, None, deadline, limit)


def _flush(path: Path) -> None:
    with path.open("r+b") as stream:
        os.fsync(stream.fileno())


@contextmanager
def _reserve(path: Path, deadline: float) -> Iterator[sqlite3.Connection]:
    # The lock connection never changes records and always rolls back. A separate
    # read connection drives backup: backing up an active writer can self-block.
    with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=0.1)) as con:
        con.row_factory = sqlite3.Row
        con.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("BEGIN IMMEDIATE")
        try:
            _check_time(deadline)
            yield con
        finally:
            con.rollback()


def _job_schema(con: sqlite3.Connection) -> None:
    _require(
        con.execute("PRAGMA application_id").fetchone()[0] == APP_ID
        and con.execute("PRAGMA user_version").fetchone()[0] in (3, 4),
        "WORKSPACE_JOB_SCHEMA_INVALID",
    )
    objects = {(r[0], r[1]) for r in con.execute("SELECT type,name FROM sqlite_master")}
    _require(
        {
            ("table", "jobs"),
            ("table", "events"),
            ("trigger", "events_no_update"),
            ("trigger", "events_no_delete"),
        }
        <= objects
    )
    _require(con.execute("PRAGMA integrity_check(1)").fetchone()[0] == "ok")
    _require(con.execute("PRAGMA foreign_key_check").fetchone() is None)
    con.execute("SELECT job_id,revision,record,actor FROM events LIMIT 0")
    count, inputs, results = con.execute(
        "SELECT count(*),coalesce(sum(length(cast(input as blob))),0),"
        "coalesce(sum(length(cast(result as blob))),0) FROM jobs"
    ).fetchone()
    archived = 0
    if con.execute("PRAGMA user_version").fetchone()[0] == 4:
        _require(
            {
                ("table", "job_archives"),
                ("trigger", "archives_no_update"),
                ("trigger", "archives_no_delete"),
                ("trigger", "archived_jobs_no_update"),
                ("trigger", "archived_jobs_no_delete"),
            }
            <= objects
        )
        archived = con.execute("SELECT count(*) FROM job_archives").fetchone()[0]
        _require(archived <= MAX_ARCHIVED_JOBS)
        _require(
            con.execute(
                "SELECT 1 FROM job_archives WHERE length(cast(receipt as blob))>16384 LIMIT 1"
            ).fetchone()
            is None
        )
    _require(
        count - archived <= MAX_JOBS and inputs <= MAX_INPUT_BYTES and results <= MAX_RESULT_BYTES
    )
    _require(con.execute("SELECT count(*) FROM events").fetchone()[0] <= (MAX_JOBS + archived) * 65)
    _require(
        con.execute(
            "SELECT 1 FROM jobs WHERE length(cast(record as blob))>8192 "
            "OR length(cast(input as blob))>4194304 OR length(cast(result as blob))>4194304 LIMIT 1"
        ).fetchone()
        is None
    )
    _require(
        con.execute(
            "SELECT 1 FROM events WHERE length(cast(record as blob))>8192 "
            "OR length(cast(actor as blob))>8192 LIMIT 1"
        ).fetchone()
        is None
    )


def _inspect_pair(root: Path, deadline: float) -> dict[str, Any]:
    """Structural checks plus exact job histories and referenced candidate histories."""
    cp, jp = root / MEMBERS[0], root / MEMBERS[1]
    repository = SQLiteCandidateRepository(cp)
    store = CollectionJobStore(jp)
    with closing(_connect(cp, deadline)) as candidates, closing(_connect(jp, deadline)) as jobs:
        candidates.execute("BEGIN")
        jobs.execute("BEGIN")
        repository._validate_store(candidates)
        _require(candidates.execute("PRAGMA integrity_check(1)").fetchone()[0] == "ok")
        _job_schema(jobs)
        states: dict[str, int] = {}
        archive_dependencies: set[str] = set()
        archived_count = 0
        rows: list[dict[str, Any]] = []
        for item in jobs.execute("SELECT job_id FROM jobs ORDER BY job_id"):
            _check_time(deadline)
            record, row = store._read(jobs, item[0])
            _require(
                isinstance(row["request_key"], str)
                and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", row["request_key"])
                is not None
            )
            _require(record.state != "RUNNING", "WORKSPACE_RUNNING_JOBS")
            review = store.review_snapshot(jobs, item[0], project_id=record.project_id)
            if review.archive is not None:
                archived_count += 1
                archive_dependencies.add(review.archive.plan.backup_sha256)
                events_fingerprint = sha256_fingerprint(
                    [
                        dict(e)
                        for e in jobs.execute(
                            "SELECT * FROM events WHERE job_id=? ORDER BY revision",
                            (record.job_id,),
                        )
                    ]
                )
                _require(events_fingerprint == review.archive.plan.events_fingerprint)
            # Validate the submitted historical snapshot, not only today's revision.
            history = repository._load_history(candidates, record.candidate_id)
            snapshot = candidates.execute(
                "SELECT candidate_json FROM candidate_snapshots WHERE candidate_id=? "
                "AND candidate_fingerprint=? AND revision=1 AND status='COLLECTING'",
                (record.candidate_id, record.candidate_fingerprint),
            ).fetchone()
            _require(snapshot is not None, "WORKSPACE_ASSOCIATION_INVALID")
            _require(
                history.candidate.project_id == record.project_id, "WORKSPACE_ASSOCIATION_INVALID"
            )
            stable_fields = (
                "candidate_id",
                "project_id",
                "candidate_fingerprint",
                "request_fingerprint",
                "created_at",
                "authority",
            )
            for event in review.events:
                _require(all(getattr(event.record, f) == getattr(record, f) for f in stable_fields))
                _require(event.record.updated_at <= record.updated_at)
            for previous, following in zip(review.events, review.events[1:], strict=False):
                old, new = previous.record, following.record
                allowed = (
                    {"RUNNING", "CANCELLED"}
                    if old.state == "QUEUED"
                    else {
                        "RUNNING",
                        "SUCCEEDED",
                        "REVIEW_REQUIRED",
                        "REJECTED",
                        "FAILED",
                        "CANCELLED",
                        "INTERRUPTED",
                    }
                    if old.state == "RUNNING"
                    else set()
                )
                _require(new.state in allowed and new.updated_at >= old.updated_at)
            if row["input"] is not None:
                request = CollectionJobRequest.model_validate_json(row["input"])
                _require(canonical_json(request.model_dump(mode="json")) == row["input"])
                _require(
                    request.candidate_id == record.candidate_id
                    and request.collection.expected_revision == 1
                    and request.collection.reported_commit == history.candidate.commit_sha
                )
            if review.result is not None:
                for collection in review.result.collections:
                    _require(
                        all(
                            e.execution_context.commit_sha == history.candidate.commit_sha
                            for e in collection.evidence
                        )
                    )
                if review.result.assembly is not None:
                    _require(
                        review.result.assembly.bundle.candidate_commit
                        == history.candidate.commit_sha
                    )
            binding = history.evidence_binding
            bound = (
                binding is not None
                and review.result is not None
                and review.result.assembly is not None
                and binding.assembly == review.result.assembly
            )
            if review.archive is not None and binding is not None:
                bound = binding.assembly.assembly_id == review.archive.plan.assembly_id
            states[record.state] = states.get(record.state, 0) + 1
            rows.append(
                {
                    "job_id": record.job_id,
                    "state": record.state,
                    "revision": record.revision,
                    "updated_at": record.updated_at.isoformat(),
                    "result_bound": bound,
                    "archived": review.archive is not None,
                }
            )
        counts = {
            table: int(candidates.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])
            for table in TABLES
        }
        event_count = jobs.execute("SELECT count(*) FROM events").fetchone()[0]
        job_version = jobs.execute("PRAGMA user_version").fetchone()[0]
    _check_time(deadline)
    return {
        "candidate_table_counts": counts,
        "job_states": states,
        "job_count": len(rows),
        "job_event_count": event_count,
        "job_store_version": job_version,
        "archived_job_count": archived_count,
        "external_archive_dependencies": sorted(archive_dependencies),
        "jobs": rows,
    }


def _snapshot(source: Path, target: Path, deadline: float) -> None:
    with closing(_connect(source, deadline)) as reader, closing(sqlite3.connect(target)) as writer:
        reader.execute("BEGIN")
        page_size = reader.execute("PRAGMA page_size").fetchone()[0]

        def progress(status: int, remaining: int, total: int) -> None:
            _check_time(deadline)
            _require(total * page_size <= MAX_STORE_BYTES, "WORKSPACE_TOO_LARGE")

        reader.backup(writer, pages=128, progress=progress, sleep=0.01)
    _flush(target)


def _receipt(
    manifest: BackupManifest, archive: SnapshotMember, details: dict[str, Any], status: str
) -> dict[str, Any]:
    return {
        "status": status,
        "sha256": archive.sha256,
        "size_bytes": archive.size_bytes,
        "manifest_fingerprint": sha256_fingerprint(manifest.model_dump(mode="json")),
        "created_at": manifest.created_at.isoformat(),
        **{key: value for key, value in details.items() if key != "jobs"},
        "validation_scope": "sqlite_structure_job_history_and_referenced_candidate_history",
        "all_candidate_domain_history_validation": "NOT_PERFORMED",
        "contains_private_project_data": True,
        "encrypted": False,
        "producer_authenticity": "NOT_VERIFIED",
        "hardware_access": "NOT_PERFORMED",
        "live_workspace_changed": False,
        "automatic_execution": "NOT_PERFORMED",
    }


def backup_workspace(
    database: Path, job_store: Path, destination: Path, *, timeout_seconds: float = 30
) -> dict[str, Any]:
    with _guard():
        deadline = _deadline(timeout_seconds)
        database, job_store = _source(database), _source(job_store)
        _require(not database.samefile(job_store), "WORKSPACE_SOURCES_IDENTICAL")
        destination = destination.absolute()
        _require(
            not os.path.lexists(destination) and not _sidecars(destination),
            "WORKSPACE_DESTINATION_EXISTS",
        )
        _require(destination.parent.is_dir(), "WORKSPACE_PARENT_MISSING")
        with tempfile.TemporaryDirectory(
            prefix=".forgegate-workspace-", dir=destination.parent
        ) as temp:
            root = Path(temp)
            # Match submit/run lock ordering: job reservation, then candidate reservation.
            with _reserve(job_store, deadline) as jc, _reserve(database, deadline) as cc:
                _job_schema(jc)
                SQLiteCandidateRepository(database)._validate_store(cc)
                # Reject before retaining any snapshot containing a live private lease.
                _require(
                    jc.execute("SELECT 1 FROM jobs WHERE lease IS NOT NULL LIMIT 1").fetchone()
                    is None,
                    "WORKSPACE_RUNNING_JOBS",
                )
                _snapshot(database, root / MEMBERS[0], deadline)
                _snapshot(job_store, root / MEMBERS[1], deadline)
                created_at = datetime.now(UTC)
            details = _inspect_pair(root, deadline)
            manifest_type = (
                WorkspaceBackupManifest
                if details["job_store_version"] == 3
                else WorkspaceBackupManifestV2
            )
            manifest = manifest_type(
                created_at=created_at,
                candidate_store=_hash(root / MEMBERS[0], deadline),
                job_store=_hash(root / MEMBERS[1], deadline),
            )
            payload = canonical_json(manifest.model_dump(mode="json")).encode()
            archive = root / "backup.zip"
            with zipfile.ZipFile(
                archive, "x", compression=zipfile.ZIP_STORED, allowZip64=False
            ) as z:
                for name in MEMBERS[:2]:
                    with (root / name).open("rb") as reader, z.open(name, "w") as writer:
                        _stream(reader, writer, deadline, MAX_STORE_BYTES)
                z.writestr(MEMBERS[2], payload)
            _flush(archive)
            digest = _hash(archive, deadline, MAX_ARCHIVE_BYTES)
            _require(not _sidecars(destination), "WORKSPACE_DESTINATION_EXISTS")
            os.link(archive, destination)
        return _receipt(manifest, digest, details, "WORKSPACE_BACKUP_CREATED")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _extract(source: Path, root: Path, deadline: float) -> BackupManifest:
    # Bound the central directory BEFORE ZipFile materializes it. This format has
    # exactly three stored entries, no ZIP64, comment, prepended data or extra members.
    with source.open("rb") as stream:
        stream.seek(-22, os.SEEK_END)
        signature, disk, cd_disk, entries_disk, entries, cd_size, offset, comment = struct.unpack(
            "<4s4H2IH", stream.read(22)
        )
        _require(
            signature == b"PK\x05\x06"
            and disk == cd_disk == comment == 0
            and entries_disk == entries == 3
            and cd_size <= 4096
            and offset + cd_size + 22 == source.stat().st_size
        )
    with zipfile.ZipFile(source) as z:
        infos = z.infolist()
        _require(tuple(i.filename for i in infos) == MEMBERS)
        _require(infos[0].header_offset == 0)
        for i in infos:
            _require(
                i.compress_type == zipfile.ZIP_STORED
                and i.orig_filename == i.filename
                and i.flag_bits & 1 == 0
                and i.file_size == i.compress_size
                and not i.extra
                and not i.comment
            )
        _require(infos[2].file_size <= MAX_MANIFEST_BYTES)
        payload = z.read(MEMBERS[2])
        enforce_json_structure_limits(payload, max_nodes=100, max_depth=5)
        raw = json.loads(payload, object_pairs_hook=_unique)
        manifest_type = (
            WorkspaceBackupManifestV2
            if isinstance(raw, dict)
            and raw.get("schema_version") == "forgegate.workspace-backup.v2"
            else WorkspaceBackupManifest
        )
        manifest = manifest_type.model_validate(raw)
        _require(canonical_json(manifest.model_dump(mode="json")).encode() == payload)
        for info, expected in zip(
            infos[:2], (manifest.candidate_store, manifest.job_store), strict=True
        ):
            _require(info.file_size == expected.size_bytes)
            with z.open(info) as reader, (root / info.filename).open("xb") as writer:
                actual = _stream(reader, writer, deadline, expected.size_bytes)
                writer.flush()
                os.fsync(writer.fileno())
            _require(actual == expected, "WORKSPACE_MEMBER_HASH_MISMATCH")
    return manifest


@contextmanager
def _verified(
    backup: Path, expected_sha256: str | None, deadline: float
) -> Iterator[tuple[Path, BackupManifest, SnapshotMember, dict[str, Any]]]:
    _require(
        expected_sha256 is None or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
        "WORKSPACE_HASH_INVALID",
    )
    source = _source(backup)
    _require(not _sidecars(source), "WORKSPACE_NOT_STANDALONE")
    _require(source.stat().st_size <= MAX_ARCHIVE_BYTES, "WORKSPACE_TOO_LARGE")
    with tempfile.TemporaryDirectory(prefix="forgegate-workspace-check-") as temp:
        root = Path(temp)
        local = root / "backup.zip"
        before = source.stat()
        with source.open("rb") as reader, local.open("xb") as writer:
            digest = _stream(reader, writer, deadline, MAX_ARCHIVE_BYTES)
        after = source.stat()
        _require(
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            and digest.size_bytes == before.st_size,
            "WORKSPACE_SOURCE_CHANGED",
        )
        _require(not _sidecars(source), "WORKSPACE_NOT_STANDALONE")
        _require(
            expected_sha256 is None or digest.sha256 == expected_sha256, "WORKSPACE_HASH_MISMATCH"
        )
        manifest = _extract(local, root, deadline)
        details = _inspect_pair(root, deadline)
        _require(details["job_store_version"] == manifest.job_store_version)
        yield root, manifest, digest, details


def verify_workspace_backup(
    backup: Path, *, expected_sha256: str | None = None, timeout_seconds: float = 30
) -> dict[str, Any]:
    with (
        _guard(),
        _verified(backup, expected_sha256, _deadline(timeout_seconds)) as (
            _,
            manifest,
            digest,
            details,
        ),
    ):
        return {
            **_receipt(manifest, digest, details, "WORKSPACE_BACKUP_VERIFIED"),
            "expected_hash_matched": expected_sha256 is not None,
        }


def restore_workspace(
    backup: Path, destination: Path, *, expected_sha256: str, timeout_seconds: float = 30
) -> dict[str, Any]:
    with _guard():
        _require(expected_sha256 is not None, "WORKSPACE_HASH_INVALID")
        deadline = _deadline(timeout_seconds)
        with _verified(backup, expected_sha256, deadline) as (root, manifest, digest, details):
            destination = destination.absolute()
            _require(destination.parent.is_dir(), "WORKSPACE_PARENT_MISSING")
            destination.mkdir()  # Exclusive reservation; no existing directory is adopted.
            try:
                for name in MEMBERS[:2]:
                    with (
                        (root / name).open("rb") as reader,
                        (destination / name).open("xb") as writer,
                    ):
                        _stream(reader, writer, deadline, MAX_STORE_BYTES)
                        writer.flush()
                        os.fsync(writer.fileno())
                _require(
                    _hash(destination / MEMBERS[0], deadline) == manifest.candidate_store
                    and _hash(destination / MEMBERS[1], deadline) == manifest.job_store
                )
                receipt = {
                    **_receipt(manifest, digest, details, "WORKSPACE_RESTORED_COPY"),
                    "expected_hash_matched": True,
                    "restore_mode": "new_directory_only",
                }
                # Readiness marker is last. A partial directory is never reported ready.
                marker = destination / ".RESTORED.pending"
                with marker.open("xb") as stream:
                    stream.write((canonical_json(receipt) + "\n").encode())
                    stream.flush()
                    os.fsync(stream.fileno())
                _check_time(deadline)
                os.link(marker, destination / "RESTORED.json")
                marker.unlink()
            except (OSError, ValueError, StoreBackupError, WorkspaceBackupError) as exc:
                raise WorkspaceBackupError("WORKSPACE_RESTORE_INCOMPLETE") from exc
        return receipt


def plan_workspace_retention(
    backup: Path,
    *,
    expected_sha256: str,
    as_of: datetime,
    terminal_before: datetime,
    timeout_seconds: float = 30,
) -> dict[str, Any]:
    with _guard():
        _require(expected_sha256 is not None, "WORKSPACE_HASH_INVALID")
        _require(
            as_of.utcoffset() is not None
            and terminal_before.utcoffset() is not None
            and terminal_before <= as_of,
            "WORKSPACE_RETENTION_TIME_INVALID",
        )
        with _verified(backup, expected_sha256, _deadline(timeout_seconds)) as (
            _,
            manifest,
            digest,
            details,
        ):
            _require(as_of >= manifest.created_at, "WORKSPACE_RETENTION_TIME_INVALID")
            decisions = []
            for job in details["jobs"]:
                stamp = datetime.fromisoformat(job["updated_at"])
                _require(stamp <= as_of, "WORKSPACE_RETENTION_TIME_INVALID")
                reason = (
                    "ALREADY_ARCHIVED"
                    if job["archived"]
                    else "ACTIVE_JOB"
                    if job["state"] in ACTIVE
                    else "BOUND_EVIDENCE"
                    if job["result_bound"]
                    else "WITHIN_RETENTION_WINDOW"
                    if stamp >= terminal_before
                    else "TERMINAL_UNBOUND_REVIEW"
                )
                decisions.append(
                    {
                        **job,
                        "action": "RETAIN"
                        if reason != "TERMINAL_UNBOUND_REVIEW"
                        else "REVIEW_ARCHIVAL",
                        "reason": reason,
                    }
                )
            return {
                "status": "WORKSPACE_RETENTION_PLAN",
                "backup_sha256": digest.sha256,
                "as_of": as_of.isoformat(),
                "terminal_before": terminal_before.isoformat(),
                "jobs": decisions,
                "deletion_performed": False,
                "executable_purge_plan": False,
                "audit_and_idempotency_records": "RETAIN_ALL",
                "capacity_reclaimed": 0,
                "scope": "verified_snapshot_only_recheck_live_state_before_any_future_purge",
            }
