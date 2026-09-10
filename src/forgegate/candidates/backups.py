"""Local operational snapshots; not portable assurance or producer authentication."""

from __future__ import annotations

import hashlib
import math
import os
import re
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path
from typing import Any

from forgegate.candidates.store import (
    STORE_SCHEMA_NAME,
    CandidateStoreError,
    SQLiteCandidateRepository,
)

MAX_BACKUP_BYTES = 1024 * 1024 * 1024
TABLES = (
    "forgegate_metadata",
    "projects",
    "project_profiles",
    "project_profile_heads",
    "project_idempotency_records",
    "project_revision_idempotency_records",
    "candidates",
    "candidate_snapshots",
    "candidate_transitions",
    "candidate_profile_bindings",
    "candidate_evidence_bindings",
    "candidate_policy_materials",
    "candidate_evaluations",
    "attestations",
    "idempotency_records",
    "audit_events",
    "api_security_events",
)


class StoreBackupError(RuntimeError):
    """Fixed operational failure code; never include source data or host paths."""


def _deadline(timeout_seconds: float) -> float:
    if not math.isfinite(timeout_seconds) or not 0.1 <= timeout_seconds <= 300:
        raise StoreBackupError("BACKUP_TIMEOUT_INVALID")
    return time.monotonic() + timeout_seconds


def _check_time(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise StoreBackupError("BACKUP_DEADLINE_EXCEEDED")


def _source(path: Path) -> Path:
    if path.is_symlink() or path.is_junction() or not path.is_file():
        raise StoreBackupError("BACKUP_SOURCE_INVALID")
    return path.resolve(strict=True)


def _sidecars(path: Path) -> bool:
    return any(os.path.lexists(str(path) + suffix) for suffix in ("-wal", "-shm", "-journal"))


def _connect(path: Path, deadline: float) -> sqlite3.Connection:
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.1)
    try:
        connection.row_factory = sqlite3.Row
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA query_only=ON")
    except sqlite3.Error:
        connection.close()
        raise
    return connection


def _inspect(path: Path, deadline: float) -> dict[str, int]:
    with closing(_connect(path, deadline)) as connection:
        connection.execute("BEGIN")
        SQLiteCandidateRepository(path)._validate_store(connection)
        if connection.execute("PRAGMA integrity_check(1)").fetchone()[0] != "ok":
            raise StoreBackupError("BACKUP_INTEGRITY_FAILED")
        counts = {
            table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in TABLES
        }
    _check_time(deadline)
    return counts


def _copy_and_hash(source: Path, target: Path, deadline: float) -> tuple[str, int]:
    before = source.stat()
    size = 0
    digest = hashlib.sha256()
    with source.open("rb") as reader, target.open("xb") as writer:
        while chunk := reader.read(1024 * 1024):
            _check_time(deadline)
            size += len(chunk)
            if size > MAX_BACKUP_BYTES:
                raise StoreBackupError("BACKUP_TOO_LARGE")
            writer.write(chunk)
            digest.update(chunk)
        writer.flush()
        os.fsync(writer.fileno())
    after = source.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or size != before.st_size:
        raise StoreBackupError("BACKUP_SOURCE_CHANGED")
    return digest.hexdigest(), size


def verify_store_backup(
    backup: Path, *, expected_sha256: str | None = None, timeout_seconds: float = 30.0
) -> dict[str, Any]:
    """Validate an OFFLINE single file on a disposable copy, never modify the input."""
    deadline = _deadline(timeout_seconds)
    if expected_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise StoreBackupError("BACKUP_HASH_INVALID")
    try:
        source = _source(backup)
        if _sidecars(source):
            raise StoreBackupError("BACKUP_NOT_STANDALONE")
        if source.stat().st_size > MAX_BACKUP_BYTES:
            raise StoreBackupError("BACKUP_TOO_LARGE")
        with tempfile.TemporaryDirectory(prefix="forgegate-backup-check-") as temporary:
            copy = Path(temporary) / "snapshot.db"
            digest, size = _copy_and_hash(source, copy, deadline)
            if _sidecars(source):
                raise StoreBackupError("BACKUP_NOT_STANDALONE")
            if expected_sha256 is not None and digest != expected_sha256:
                raise StoreBackupError("BACKUP_HASH_MISMATCH")
            counts = _inspect(copy, deadline)
        return {
            "status": "VERIFIED",
            "store_schema": STORE_SCHEMA_NAME,
            "sha256": digest,
            "size_bytes": size,
            "table_counts": counts,
            "expected_hash_matched": expected_sha256 is not None,
            "validation_scope": "sqlite_integrity_foreign_keys_current_schema_and_counts",
            "domain_history_validation": "NOT_PERFORMED",
            "restore_performed": False,
            "producer_authenticity": "NOT_VERIFIED",
            "hardware_access": "NOT_PERFORMED",
            "contains_private_project_data": True,
        }
    except (OSError, sqlite3.Error, CandidateStoreError) as exc:
        raise StoreBackupError("BACKUP_VALIDATION_FAILED") from exc


def backup_store(
    source: Path, destination: Path, *, timeout_seconds: float = 30.0
) -> dict[str, Any]:
    """Snapshot a live current-schema WAL store and publish one file without overwrite."""
    deadline = _deadline(timeout_seconds)
    try:
        source = _source(source)
        destination = destination.absolute()
        if os.path.lexists(destination) or _sidecars(destination):
            raise StoreBackupError("BACKUP_DESTINATION_EXISTS")
        if not destination.parent.is_dir():
            raise StoreBackupError("BACKUP_PARENT_MISSING")
        with tempfile.TemporaryDirectory(
            prefix=".forgegate-backup-", dir=destination.parent
        ) as temp:
            snapshot = Path(temp) / "snapshot.db"
            with (
                closing(_connect(source, deadline)) as reader,
                closing(sqlite3.connect(snapshot)) as writer,
            ):
                reader.execute("BEGIN")
                SQLiteCandidateRepository(source)._validate_store(reader)
                page_size = int(reader.execute("PRAGMA page_size").fetchone()[0])

                def progress(status: int, remaining: int, total: int) -> None:
                    _check_time(deadline)
                    if total * page_size > MAX_BACKUP_BYTES:
                        raise StoreBackupError("BACKUP_TOO_LARGE")

                reader.backup(writer, pages=128, progress=progress, sleep=0.01)
            report = verify_store_backup(
                snapshot, timeout_seconds=max(0.1, deadline - time.monotonic())
            )
            _check_time(deadline)
            if _sidecars(destination):
                raise StoreBackupError("BACKUP_DESTINATION_EXISTS")
            # Same-filesystem hard link atomically creates only an absent destination.
            # Unsupported filesystems fail closed; never fall back to an overwrite operation.
            with snapshot.open("r+b") as stream:
                os.fsync(stream.fileno())
            os.link(snapshot, destination)
        return {**report, "status": "BACKUP_CREATED"}
    except FileExistsError as exc:
        raise StoreBackupError("BACKUP_DESTINATION_EXISTS") from exc
    except (OSError, sqlite3.Error, CandidateStoreError) as exc:
        raise StoreBackupError("BACKUP_CREATION_FAILED") from exc
