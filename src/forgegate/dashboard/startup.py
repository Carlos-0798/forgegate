"""Existing-only paired startup; correlation is not process ownership or fencing."""

from __future__ import annotations

import secrets
import sqlite3
import stat
import time
from contextlib import ExitStack, closing
from dataclasses import dataclass
from pathlib import Path

from forgegate.candidates.store import CandidateStoreError, SQLiteCandidateRepository


class DashboardStartupError(ValueError):
    """A fixed, path-free refusal; never repair or initialize an input."""


def _identity(path: Path) -> tuple[int, int]:
    try:
        for entry in (path, *path.parents):
            if entry.is_symlink() or entry.is_junction():
                raise DashboardStartupError("DASHBOARD_PAIR_ALIAS_REJECTED")
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
            raise DashboardStartupError("DASHBOARD_PAIR_NONEMPTY_FILE_REQUIRED")
        if info.st_nlink != 1 or not info.st_ino:
            raise DashboardStartupError("DASHBOARD_PAIR_ALIAS_REJECTED")
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(str(path) + suffix)
            if sidecar.is_symlink() or sidecar.is_junction():
                raise DashboardStartupError("DASHBOARD_PAIR_ALIAS_REJECTED")
            if sidecar.exists():
                sidecar_info = sidecar.stat()
                if not stat.S_ISREG(sidecar_info.st_mode) or sidecar_info.st_nlink != 1:
                    raise DashboardStartupError("DASHBOARD_PAIR_ALIAS_REJECTED")
        return info.st_dev, info.st_ino
    except OSError as exc:
        raise DashboardStartupError("DASHBOARD_PAIR_FILE_UNAVAILABLE") from exc


@dataclass
class ExistingDashboardPair:
    """Private path/file-ID binding. No persistent generation or content identity."""

    candidate_path: Path
    job_path: Path
    candidate_identity: tuple[int, int]
    job_identity: tuple[int, int]
    runtime_id: str | None = None
    pair_id: str | None = None

    @classmethod
    def prepare(cls, candidate: Path, jobs: Path) -> ExistingDashboardPair:
        # Do not resolve away a reparse point before rejecting it.
        candidate = candidate.expanduser().absolute()
        jobs = jobs.expanduser().absolute()
        candidate_id, job_id = _identity(candidate), _identity(jobs)
        try:
            candidate, jobs = candidate.resolve(strict=True), jobs.resolve(strict=True)
        except OSError as exc:
            raise DashboardStartupError("DASHBOARD_PAIR_FILE_UNAVAILABLE") from exc
        if candidate_id == job_id:
            raise DashboardStartupError("DASHBOARD_PAIR_OVERLAP")
        candidate_names = {
            Path(str(candidate) + suffix) for suffix in ("", "-wal", "-shm", "-journal")
        }
        job_names = {Path(str(jobs) + suffix) for suffix in ("", "-wal", "-shm", "-journal")}
        if candidate_names & job_names:
            raise DashboardStartupError("DASHBOARD_PAIR_OVERLAP")
        pair = cls(candidate, jobs, candidate_id, job_id)
        pair.validate()
        return pair

    def check_files(self) -> None:
        if (_identity(self.candidate_path), _identity(self.job_path)) != (
            self.candidate_identity,
            self.job_identity,
        ):
            raise DashboardStartupError("DASHBOARD_PAIR_REPLACED")

    def validate(self) -> None:
        """Read current schemas and SQLite integrity; not full domain or lineage proof.

        Real SQLite read transactions include committed WAL. SQLite may maintain
        its own WAL/SHM files; this is not the cold-copy preservation operation.
        """
        from forgegate.collection_jobs import APP_ID

        self.check_files()
        deadline = time.monotonic() + 5
        try:
            with ExitStack() as stack:
                connections = []
                for path in (self.job_path, self.candidate_path):
                    con = stack.enter_context(
                        closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1))
                    )
                    con.row_factory = sqlite3.Row
                    con.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
                    con.execute("PRAGMA trusted_schema=OFF")
                    con.execute("PRAGMA query_only=ON")
                    con.execute("PRAGMA foreign_keys=ON")
                    con.execute("PRAGMA synchronous=FULL")
                    con.execute("BEGIN")
                    connections.append(con)
                jobs, candidates = connections
                SQLiteCandidateRepository(self.candidate_path)._validate_store(candidates)
                version = jobs.execute("PRAGMA user_version").fetchone()[0]
                if jobs.execute("PRAGMA application_id").fetchone()[0] != APP_ID or version not in (
                    3,
                    4,
                ):
                    raise DashboardStartupError("DASHBOARD_PAIR_SCHEMA_INVALID")
                jobs.execute(
                    "SELECT job_id,request_key,record,input,result,lease FROM jobs LIMIT 0"
                )
                jobs.execute("SELECT job_id,revision,record,actor FROM events LIMIT 0")
                required = {"events_no_update", "events_no_delete"}
                if version == 4:
                    jobs.execute("SELECT job_id,receipt FROM job_archives LIMIT 0")
                    required |= {
                        "archives_no_update",
                        "archives_no_delete",
                        "archived_jobs_no_update",
                        "archived_jobs_no_delete",
                    }
                triggers = {
                    row[0]
                    for row in jobs.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
                }
                if not required <= triggers:
                    raise DashboardStartupError("DASHBOARD_PAIR_SCHEMA_INVALID")
                for con in connections:
                    if (
                        con.execute("PRAGMA quick_check(1)").fetchone()[0] != "ok"
                        or con.execute("PRAGMA foreign_key_check").fetchone() is not None
                    ):
                        raise DashboardStartupError("DASHBOARD_PAIR_INTEGRITY_INVALID")
                if time.monotonic() > deadline:
                    raise DashboardStartupError("DASHBOARD_PAIR_CHECK_TIMEOUT")
                self.check_files()
        except (sqlite3.Error, CandidateStoreError) as exc:
            raise DashboardStartupError("DASHBOARD_PAIR_VALIDATION_FAILED") from exc

    def start(self) -> None:
        self.validate()
        self.runtime_id = secrets.token_hex(16)
        self.pair_id = secrets.token_hex(16)

    def stop(self) -> None:
        self.runtime_id = self.pair_id = None

    def headers(self) -> dict[str, str]:
        self.check_files()
        if self.runtime_id is None or self.pair_id is None:
            raise DashboardStartupError("DASHBOARD_PAIR_NOT_STARTED")
        return {
            "X-ForgeGate-Runtime-Id": self.runtime_id,
            "X-ForgeGate-Store-Pair-Id": self.pair_id,
        }

    def report(self) -> dict[str, str]:
        headers = self.headers()
        return {
            "runtime_id": headers["X-ForgeGate-Runtime-Id"],
            "store_pair_id": headers["X-ForgeGate-Store-Pair-Id"],
            "startup_mode": "EXISTING_PAIR",
            "scope": "process_lifetime_correlation_not_authentication",
            "store_validation": "startup_schema_sqlite_integrity_only",
            "process_ownership": "NOT_ESTABLISHED",
            "writer_fence": "NOT_IMPLEMENTED",
            "readiness": "CHECK_HTTP_SEPARATELY",
        }
