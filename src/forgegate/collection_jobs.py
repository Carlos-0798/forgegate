"""Explicit local collection jobs; no daemon, candidate write, network or device I/O."""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Self

from pydantic import ConfigDict, Field, ValidationError, model_validator

from forgegate.application import CandidateApplication
from forgegate.assembly.models import EvidenceBundleAssembly
from forgegate.audit.models import AuditActor
from forgegate.candidates import CandidateStoreError
from forgegate.candidates.models import CANDIDATE_ID_PATTERN, FINGERPRINT_PATTERN
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.collectors.base import CollectionResult, CollectionStatus
from forgegate.dashboard.collection import DashboardCollectionPreviewRequest, preview_collection
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import SLUG_PATTERN, StrictModel

APP_ID = 0x4647434A
MAX_JOBS = 100
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_RESULT_BYTES = 32 * 1024 * 1024
LEASE_SECONDS = 300
MAX_JOB_REVISION = 64
MAX_LEASE_RENEWALS = MAX_JOB_REVISION - 2
JobState = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "REVIEW_REQUIRED",
    "REJECTED",
    "FAILED",
    "CANCELLED",
    "INTERRUPTED",
]
ACTIVE = {"QUEUED", "RUNNING"}
HAS_RESULT = {"SUCCEEDED", "REVIEW_REQUIRED", "REJECTED"}


class JobError(ValueError):
    """Stable, path-free operator error."""


class CollectionJobRequest(StrictModel):
    schema_version: Literal["forgegate.collection-job-request.v1"] = (
        "forgegate.collection-job-request.v1"
    )
    candidate_id: str = Field(pattern=CANDIDATE_ID_PATTERN)
    collection: DashboardCollectionPreviewRequest


class _CollectionJobRecordFields(StrictModel):
    job_id: str = Field(pattern=r"^job-[0-9a-f]{32}$")
    candidate_id: str = Field(pattern=CANDIDATE_ID_PATTERN)
    project_id: str = Field(pattern=SLUG_PATTERN)
    candidate_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    request_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    authority: Literal["LOCAL_CLI_NOT_AUTHENTICATED", "AUTHENTICATED_DASHBOARD"] = (
        "LOCAL_CLI_NOT_AUTHENTICATED"
    )
    state: JobState = "QUEUED"
    revision: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    lease_expires_at: datetime | None = None
    result_fingerprint: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)
    error_code: Literal["JOB_EXECUTION_FAILED", "JOB_LEASE_EXPIRED"] | None = None
    source_bytes: Literal["retained_pending", "released_logically"] = "retained_pending"
    candidate_write: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        for stamp in (self.created_at, self.updated_at, self.lease_expires_at):
            if stamp is not None and stamp.utcoffset() is None:
                raise ValueError("job timestamps require UTC offsets")
        if self.updated_at < self.created_at:
            raise ValueError("job time regressed")
        if (self.state == "RUNNING") != (self.lease_expires_at is not None):
            raise ValueError("lease must exist only while running")
        if self.lease_expires_at is not None and self.lease_expires_at <= self.updated_at:
            raise ValueError("lease must expire after claim")
        if (self.state in HAS_RESULT) != (self.result_fingerprint is not None):
            raise ValueError("terminal collection result mismatch")
        if (self.state in ACTIVE) != (self.source_bytes == "retained_pending"):
            raise ValueError("source retention mismatch")
        expected_error = {"FAILED": "JOB_EXECUTION_FAILED", "INTERRUPTED": "JOB_LEASE_EXPIRED"}.get(
            self.state
        )
        if self.error_code != expected_error:
            raise ValueError("job error mismatch")
        if (self.state == "QUEUED") != (self.revision == 0):
            raise ValueError("job revision mismatch")
        return self


class LegacyCollectionJobRecord(_CollectionJobRecordFields):
    # Frozen Phase 34-37 public record retained for exact historical reads.
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        title="CollectionJobRecord",
    )

    schema_version: Literal["forgegate.collection-job.v1"] = "forgegate.collection-job.v1"
    revision: int = Field(default=0, ge=0, le=2)


class CollectionJobRecord(_CollectionJobRecordFields):
    """Current record with visible, non-credential execution ownership and renewals."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        title="CollectionJobRecord",
    )

    schema_version: Literal["forgegate.collection-job.v2"] = "forgegate.collection-job.v2"
    revision: int = Field(default=0, ge=0, le=MAX_JOB_REVISION)
    execution_owner_id: str | None = Field(default=None, pattern=r"^executor-[0-9a-f]{32}$")
    lease_renewal_count: int = Field(default=0, ge=0, le=MAX_LEASE_RENEWALS)

    @model_validator(mode="after")
    def execution_lifecycle_must_be_coherent(self) -> Self:
        if self.state == "QUEUED" and (
            self.execution_owner_id is not None or self.lease_renewal_count != 0
        ):
            raise ValueError("queued job cannot claim execution ownership")
        if self.state == "RUNNING" and self.execution_owner_id is None:
            raise ValueError("running job requires execution ownership")
        if self.execution_owner_id is None and self.lease_renewal_count != 0:
            raise ValueError("lease renewal requires execution ownership")
        if self.lease_renewal_count > max(0, self.revision - 1):
            raise ValueError("lease renewal count exceeds job history")
        return self


CollectionJobRecordLike = LegacyCollectionJobRecord | CollectionJobRecord


class CollectionJobResult(StrictModel):
    schema_version: Literal["forgegate.collection-job-result.v1"] = (
        "forgegate.collection-job-result.v1"
    )
    job_id: str = Field(pattern=r"^job-[0-9a-f]{32}$")
    collections: list[CollectionResult] = Field(min_length=1, max_length=2)
    assembly: EvidenceBundleAssembly | None
    candidate_write: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    producer_authentication: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    source_artifact_bytes: Literal["not_embedded"] = "not_embedded"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        fingerprints = [sha256_fingerprint(c.model_dump(mode="json")) for c in self.collections]
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("duplicate collection result")
        if self.assembly is not None:
            if any(c.status != CollectionStatus.COMPLETE for c in self.collections):
                raise ValueError("assembly requires complete collections")
            if set(fingerprints) != {c.result_fingerprint for c in self.assembly.collections}:
                raise ValueError("assembly collection mismatch")
            expected = {
                e.evidence_id: e.model_dump(mode="json")
                for c in self.collections
                for e in c.evidence
            }
            actual = {
                e.evidence_id: e.model_dump(mode="json") for e in self.assembly.bundle.evidence
            }
            if expected != actual:
                raise ValueError("assembly evidence mismatch")
        return self

    def terminal_state(self) -> JobState:
        if any(c.status != CollectionStatus.COMPLETE for c in self.collections):
            return "REJECTED"
        return "REVIEW_REQUIRED" if self.assembly is None else "SUCCEEDED"


class CollectionJobEvent(StrictModel):
    record: CollectionJobRecordLike
    actor: AuditActor | None = None


class CollectionJobReview(StrictModel):
    record: CollectionJobRecordLike
    events: list[CollectionJobEvent] = Field(min_length=1, max_length=MAX_JOB_REVISION + 1)
    result: CollectionJobResult | None


def _json(model: StrictModel) -> str:
    return canonical_json(model.model_dump(mode="json"))


def _fingerprint(payload: str) -> str:
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _record(payload: str) -> CollectionJobRecordLike:
    last_error: ValidationError | None = None
    for model in (CollectionJobRecord, LegacyCollectionJobRecord):
        try:
            return model.model_validate_json(payload)
        except ValidationError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError("inconsistent job storage")


def _candidate(application: CandidateApplication, request: CollectionJobRequest) -> tuple[str, str]:
    candidate = application.get_candidate(request.candidate_id)
    if (
        candidate.status != CandidateStatus.COLLECTING
        or candidate.revision != request.collection.expected_revision
        or candidate.commit_sha != request.collection.reported_commit
    ):
        raise JobError("JOB_CANDIDATE_CONFLICT")
    try:
        application.get_evidence(request.candidate_id)
    except CandidateStoreError as exc:
        if exc.code != "STORE_EVIDENCE_BINDING_NOT_FOUND":
            raise
    else:
        raise JobError("JOB_CANDIDATE_ALREADY_BOUND")
    return candidate.project_id, sha256_fingerprint(candidate.model_dump(mode="json"))


class CollectionJobStore:
    """Separate SQLite store; v3 enables cooperative execution lifecycle records."""

    def __init__(self, path: Path) -> None:
        if path.is_symlink() or not path.parent.is_dir():
            raise JobError("JOB_STORE_PATH_INVALID")
        self.path = path.resolve()

    def initialize(self) -> None:
        # Explicit exclusive creation; never migrate, overwrite or adopt another database.
        try:
            with self.path.open("xb"):
                pass
            with closing(sqlite3.connect(self.path)) as con:
                con.executescript(f"""
                    PRAGMA application_id={APP_ID};
                    PRAGMA user_version=3;
                    CREATE TABLE jobs (
                        job_id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,
                        record TEXT NOT NULL, input TEXT, result TEXT, lease TEXT
                    );
                    CREATE TABLE events (
                        job_id TEXT NOT NULL REFERENCES jobs(job_id),
                        revision INTEGER NOT NULL, record TEXT NOT NULL, actor TEXT,
                        PRIMARY KEY(job_id, revision)
                    );
                    CREATE TRIGGER events_no_update BEFORE UPDATE ON events
                    BEGIN SELECT RAISE(ABORT, 'job events are append-only'); END;
                    CREATE TRIGGER events_no_delete BEFORE DELETE ON events
                    BEGIN SELECT RAISE(ABORT, 'job events are append-only'); END;
                """)
        except (OSError, sqlite3.Error) as exc:
            raise JobError("JOB_STORE_CREATE_FAILED") from exc

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        con: sqlite3.Connection | None = None
        try:
            if self.path.is_symlink():
                raise JobError("JOB_STORE_PATH_INVALID")
            con = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5)
            con.row_factory = sqlite3.Row
            if con.execute("PRAGMA application_id").fetchone()[0] != APP_ID or con.execute(
                "PRAGMA user_version"
            ).fetchone()[0] not in (1, 2, 3):
                raise JobError("JOB_STORE_VERSION_INVALID")
            con.execute("PRAGMA synchronous=FULL")
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except sqlite3.Error as exc:
            raise JobError("JOB_STORE_IO_FAILED") from exc
        finally:
            if con is not None:
                con.close()

    def require_dashboard_store(self) -> None:
        with self._transaction() as con:
            if con.execute("PRAGMA user_version").fetchone()[0] != 3:
                raise JobError("JOB_STORE_MIGRATION_REQUIRED")
            # Validate schema without initializing or upgrading a configured file.
            con.execute("SELECT job_id,revision,record,actor FROM events LIMIT 1")

    def migrate(self) -> None:
        """Explicit transactional v1/v2-to-v3 upgrade; preserve raw rows and actors."""
        with self._transaction() as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version == 3:
                return
            for row in con.execute("SELECT job_id FROM jobs").fetchall():
                self._read(con, row[0])
            if version == 1:
                con.execute("ALTER TABLE events ADD COLUMN actor TEXT")
            con.execute("PRAGMA user_version=3")

    @staticmethod
    def _require_current(con: sqlite3.Connection) -> None:
        if con.execute("PRAGMA user_version").fetchone()[0] != 3:
            raise JobError("JOB_STORE_MIGRATION_REQUIRED")

    def _read(
        self, con: sqlite3.Connection, job_id: str
    ) -> tuple[CollectionJobRecordLike, sqlite3.Row]:
        row = con.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise JobError("JOB_NOT_FOUND")
        try:
            record = _record(row["record"])
            _require(record.job_id == job_id and _json(record) == row["record"])
            _require((record.state in ACTIVE) == (row["input"] is not None))
            _require((record.state == "RUNNING") == (row["lease"] is not None))
            _require((record.state in HAS_RESULT) == (row["result"] is not None))
            if row["input"] is not None:
                _require(_fingerprint(row["input"]) == record.request_fingerprint)
            if row["result"] is not None:
                _require(_fingerprint(row["result"]) == record.result_fingerprint)
                result = CollectionJobResult.model_validate_json(row["result"])
                _require(result.job_id == job_id and _json(result) == row["result"])
                _require(result.terminal_state() == record.state)
            event = con.execute(
                "SELECT record FROM events WHERE job_id=? AND revision=?",
                (job_id, record.revision),
            ).fetchone()
            _require(event is not None and event[0] == row["record"])
        except ValueError as exc:
            raise JobError("JOB_STORE_CORRUPT") from exc
        return record, row

    def submit(
        self,
        request: CollectionJobRequest,
        application: CandidateApplication,
        *,
        key: str,
        actor: AuditActor | None = None,
        project_id: str | None = None,
    ) -> CollectionJobRecordLike:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", key) is None:
            raise JobError("JOB_KEY_INVALID")
        # Revalidate at the boundary, including model_copy callers.
        request = CollectionJobRequest.model_validate_json(request.model_dump_json())
        payload = _json(request)
        fingerprint = _fingerprint(payload)
        with self._transaction() as con:
            self._require_current(con)
            existing = con.execute("SELECT job_id FROM jobs WHERE request_key=?", (key,)).fetchone()
            if existing is not None:
                record, _ = self._read(con, existing[0])
                if project_id is not None and record.project_id != project_id:
                    raise JobError("JOB_NOT_FOUND")
                if record.request_fingerprint != fingerprint:
                    raise JobError("JOB_KEY_CONFLICT")
                return record
            actual_project, candidate_fingerprint = _candidate(application, request)
            if project_id is not None and actual_project != project_id:
                raise JobError("JOB_NOT_FOUND")
            count, size = con.execute(
                "SELECT count(*),coalesce(sum(length(cast(input as blob))),0) FROM jobs"
            ).fetchone()
            if count >= MAX_JOBS or size + len(payload.encode()) > MAX_INPUT_BYTES:
                raise JobError("JOB_CAPACITY_EXCEEDED")
            now = _now()
            record = CollectionJobRecord(
                job_id="job-" + secrets.token_hex(16),
                candidate_id=request.candidate_id,
                project_id=actual_project,
                candidate_fingerprint=candidate_fingerprint,
                request_fingerprint=fingerprint,
                created_at=now,
                updated_at=now,
                authority="LOCAL_CLI_NOT_AUTHENTICATED"
                if actor is None
                else "AUTHENTICATED_DASHBOARD",
            )
            con.execute(
                "INSERT INTO jobs VALUES(?,?,?,?,NULL,NULL)",
                (record.job_id, key, _json(record), payload),
            )
            self._append_event(con, record, actor)
            return record

    def show(self, job_id: str) -> CollectionJobRecordLike:
        with self._transaction() as con:
            return self._read(con, job_id)[0]

    def review(self, job_id: str, *, project_id: str) -> CollectionJobReview:
        with self._transaction() as con:
            return self.review_snapshot(con, job_id, project_id=project_id)

    def review_snapshot(
        self, con: sqlite3.Connection, job_id: str, *, project_id: str
    ) -> CollectionJobReview:
        """Validate history on a caller-owned pinned transaction, without opening a writer."""
        record, row = self._read(con, job_id)
        if record.project_id != project_id:
            raise JobError("JOB_NOT_FOUND")
        try:
            events: list[CollectionJobEvent] = []
            for event in con.execute(
                "SELECT * FROM events WHERE job_id=? ORDER BY revision", (job_id,)
            ):
                snapshot = _record(event["record"])
                _require(snapshot.job_id == job_id and snapshot.project_id == project_id)
                _require(
                    snapshot.revision == len(events) == event["revision"]
                    and _json(snapshot) == event["record"]
                )
                actor_raw = dict(event).get("actor")
                actor = None if actor_raw is None else AuditActor.model_validate_json(actor_raw)
                if actor is not None:
                    _require(actor.role == "operator" and _json(actor) == actor_raw)
                events.append(CollectionJobEvent(record=snapshot, actor=actor))
            _require(len(events) == record.revision + 1 and events[-1].record == record)
            return CollectionJobReview(
                record=record,
                events=events,
                result=None
                if row["result"] is None
                else CollectionJobResult.model_validate_json(row["result"]),
            )
        except ValueError as exc:
            raise JobError("JOB_STORE_CORRUPT") from exc

    def list_jobs(self, *, after: str = "", limit: int = 25) -> list[CollectionJobRecordLike]:
        if not 1 <= limit <= 100:
            raise JobError("JOB_PAGE_INVALID")
        with self._transaction() as con:
            ids = con.execute(
                "SELECT job_id FROM jobs WHERE job_id>? ORDER BY job_id LIMIT ?", (after, limit)
            ).fetchall()
            return [self._read(con, row[0])[0] for row in ids]

    def _update(
        self,
        con: sqlite3.Connection,
        old: CollectionJobRecordLike,
        *,
        actor: AuditActor | None = None,
        **changes: object,
    ) -> CollectionJobRecord:
        now = _now()
        if now < old.updated_at:
            raise JobError("JOB_CLOCK_REGRESSED")
        values = {
            **old.model_dump(),
            **changes,
            "updated_at": now,
            "revision": old.revision + 1,
        }
        if isinstance(old, LegacyCollectionJobRecord) and not isinstance(old, CollectionJobRecord):
            values.update(
                schema_version="forgegate.collection-job.v2",
                execution_owner_id=None,
                lease_renewal_count=0,
            )
            values.update(changes)
        record = CollectionJobRecord.model_validate(values)
        con.execute("UPDATE jobs SET record=? WHERE job_id=?", (_json(record), old.job_id))
        self._append_event(con, record, actor)
        if record.state not in ACTIVE:
            con.execute("UPDATE jobs SET input=NULL,lease=NULL WHERE job_id=?", (old.job_id,))
        return record

    def _append_event(
        self,
        con: sqlite3.Connection,
        record: CollectionJobRecordLike,
        actor: AuditActor | None,
    ) -> None:
        if actor is None:
            con.execute(
                "INSERT INTO events(job_id,revision,record) VALUES(?,?,?)",
                (record.job_id, record.revision, _json(record)),
            )
        else:
            actor = AuditActor.model_validate_json(actor.model_dump_json())
            if actor.role != "operator" or actor.authenticated_at > record.updated_at:
                raise JobError("JOB_ACTOR_INVALID")
            if con.execute("PRAGMA user_version").fetchone()[0] != 3:
                raise JobError("JOB_STORE_MIGRATION_REQUIRED")
            con.execute(
                "INSERT INTO events(job_id,revision,record,actor) VALUES(?,?,?,?)",
                (record.job_id, record.revision, _json(record), _json(actor)),
            )

    def claim(
        self,
        job_id: str,
        revision: int,
        *,
        actor: AuditActor | None = None,
        project_id: str | None = None,
        execution_owner_id: str | None = None,
    ) -> tuple[CollectionJobRecord, str, CollectionJobRequest]:
        with self._transaction() as con:
            self._require_current(con)
            old, row = self._read(con, job_id)
            if project_id is not None and old.project_id != project_id:
                raise JobError("JOB_NOT_FOUND")
            if old.state != "QUEUED" or old.revision != revision:
                raise JobError("JOB_STATE_CONFLICT")
            request = CollectionJobRequest.model_validate_json(row["input"])
            token = secrets.token_hex(32)
            record = self._update(
                con,
                old,
                state="RUNNING",
                actor=actor,
                lease_expires_at=_now() + timedelta(seconds=LEASE_SECONDS),
                execution_owner_id=execution_owner_id or "executor-" + secrets.token_hex(16),
            )
            con.execute("UPDATE jobs SET lease=? WHERE job_id=?", (token, job_id))
            return record, token, request

    def renew_lease(
        self,
        job_id: str,
        token: str,
        *,
        actor: AuditActor | None = None,
    ) -> CollectionJobRecord:
        """Renew current ownership at a cooperative parser checkpoint."""

        with self._transaction() as con:
            self._require_current(con)
            old, row = self._read(con, job_id)
            if not isinstance(old, CollectionJobRecord) or (
                old.state != "RUNNING"
                or row["lease"] != token
                or old.lease_expires_at is None
                or _now() >= old.lease_expires_at
            ):
                raise JobError("JOB_LEASE_LOST")
            if old.lease_renewal_count >= MAX_LEASE_RENEWALS:
                raise JobError("JOB_LEASE_RENEWAL_LIMIT")
            return self._update(
                con,
                old,
                actor=actor,
                lease_expires_at=_now() + timedelta(seconds=LEASE_SECONDS),
                lease_renewal_count=old.lease_renewal_count + 1,
            )

    def finish(
        self,
        job_id: str,
        token: str,
        result: CollectionJobResult | None,
        *,
        actor: AuditActor | None = None,
    ) -> CollectionJobRecord:
        with self._transaction() as con:
            self._require_current(con)
            old, row = self._read(con, job_id)
            if (
                old.state != "RUNNING"
                or row["lease"] != token
                or old.lease_expires_at is None
                or _now() >= old.lease_expires_at
            ):
                raise JobError("JOB_LEASE_LOST")
            if result is None:
                return self._update(
                    con,
                    old,
                    state="FAILED",
                    actor=actor,
                    lease_expires_at=None,
                    source_bytes="released_logically",
                    error_code="JOB_EXECUTION_FAILED",
                )
            if result.job_id != job_id:
                raise JobError("JOB_RESULT_MISMATCH")
            result = CollectionJobResult.model_validate_json(result.model_dump_json())
            payload = _json(result)
            size = con.execute(
                "SELECT coalesce(sum(length(cast(result as blob))),0) FROM jobs"
            ).fetchone()[0]
            if (
                len(payload.encode()) > 4 * 1024 * 1024
                or size + len(payload.encode()) > MAX_RESULT_BYTES
            ):
                raise JobError("JOB_RESULT_CAPACITY_EXCEEDED")
            record = self._update(
                con,
                old,
                state=result.terminal_state(),
                actor=actor,
                lease_expires_at=None,
                source_bytes="released_logically",
                result_fingerprint=_fingerprint(payload),
            )
            con.execute("UPDATE jobs SET result=? WHERE job_id=?", (payload, job_id))
            return record

    def cancel(
        self,
        job_id: str,
        revision: int,
        *,
        actor: AuditActor | None = None,
        project_id: str | None = None,
    ) -> CollectionJobRecord:
        with self._transaction() as con:
            self._require_current(con)
            old, _ = self._read(con, job_id)
            if project_id is not None and old.project_id != project_id:
                raise JobError("JOB_NOT_FOUND")
            if old.state not in ACTIVE or old.revision != revision:
                raise JobError("JOB_STATE_CONFLICT")
            return self._update(
                con,
                old,
                actor=actor,
                state="CANCELLED",
                lease_expires_at=None,
                source_bytes="released_logically",
            )

    def recover(
        self,
        job_id: str,
        revision: int,
        *,
        actor: AuditActor | None = None,
        project_id: str | None = None,
    ) -> CollectionJobRecord:
        with self._transaction() as con:
            self._require_current(con)
            old, _ = self._read(con, job_id)
            if project_id is not None and old.project_id != project_id:
                raise JobError("JOB_NOT_FOUND")
            if (
                old.state != "RUNNING"
                or old.revision != revision
                or old.lease_expires_at is None
                or _now() < old.lease_expires_at
            ):
                raise JobError("JOB_RECOVERY_NOT_DUE")
            return self._update(
                con,
                old,
                actor=actor,
                state="INTERRUPTED",
                lease_expires_at=None,
                source_bytes="released_logically",
                error_code="JOB_LEASE_EXPIRED",
            )

    def result(self, job_id: str) -> CollectionJobResult:
        with self._transaction() as con:
            _, row = self._read(con, job_id)
            if row["result"] is None:
                raise JobError("JOB_RESULT_UNAVAILABLE")
            return CollectionJobResult.model_validate_json(row["result"])

    def run(
        self,
        job_id: str,
        revision: int,
        application: CandidateApplication,
        *,
        actor: AuditActor | None = None,
        project_id: str | None = None,
        execution_owner_id: str | None = None,
    ) -> CollectionJobRecordLike:
        record, token, request = self.claim(
            job_id,
            revision,
            actor=actor,
            project_id=project_id,
            execution_owner_id=execution_owner_id,
        )
        try:
            if _candidate(application, request)[1] != record.candidate_fingerprint:
                raise JobError("JOB_CANDIDATE_CONFLICT")

            def checkpoint() -> None:
                self.renew_lease(job_id, token, actor=actor)

            preview = preview_collection(
                request.candidate_id,
                request.collection,
                checkpoint=checkpoint,
            )
            if _candidate(application, request)[1] != record.candidate_fingerprint:
                raise JobError("JOB_CANDIDATE_CONFLICT")
            result = CollectionJobResult(
                job_id=job_id, collections=preview.collections, assembly=preview.assembly
            )
            return self.finish(job_id, token, result, actor=actor)
        except Exception:
            # Cancellation/expired ownership wins; never overwrite another terminal result.
            latest = self.show(job_id)
            if latest.state != "RUNNING":
                return latest
            return self.finish(job_id, token, None, actor=actor)
