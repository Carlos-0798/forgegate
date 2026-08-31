from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ValidationError

from forgegate.assembly import EvidenceBundleAssembly
from forgegate.attestations import (
    ReleaseAttestation,
    create_release_attestation,
    render_attestation_markdown,
)
from forgegate.candidates.evidence_binding import (
    CandidateEvidenceBinding,
    create_candidate_evidence_binding,
)
from forgegate.candidates.lifecycle import CandidateLifecycleError, transition_candidate
from forgegate.candidates.models import (
    CandidateTransition,
    CandidateTransitionResult,
    ReleaseCandidate,
)
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.domain.enums import CandidateStatus
from forgegate.policy.models import PolicyEvaluation

STORE_APPLICATION_ID = 0x46474154  # ASCII "FGAT"
LEGACY_STORE_SCHEMA_VERSION = 1
LEGACY_STORE_SCHEMA_NAME = "forgegate.candidate-store.v1"
PREVIOUS_STORE_SCHEMA_VERSION = 2
PREVIOUS_STORE_SCHEMA_NAME = "forgegate.candidate-store.v2"
STORE_SCHEMA_VERSION = 3
STORE_SCHEMA_NAME = "forgegate.candidate-store.v3"
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")

_SCHEMA_V1_STATEMENTS = (
    """
    CREATE TABLE forgegate_metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    ) STRICT
    """,
    """
    CREATE TABLE candidates (
        candidate_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        version TEXT NOT NULL,
        commit_sha TEXT NOT NULL,
        source_branch TEXT NOT NULL,
        release_track TEXT NOT NULL,
        created_at TEXT NOT NULL,
        initial_fingerprint TEXT NOT NULL,
        initial_candidate_json TEXT NOT NULL,
        current_revision INTEGER NOT NULL CHECK (current_revision BETWEEN 0 AND 4),
        current_status TEXT NOT NULL CHECK (
            current_status IN ('DRAFT', 'COLLECTING', 'READY', 'EVALUATING',
                               'PASS', 'FAIL', 'REVIEW', 'ERROR')
        ),
        updated_at TEXT NOT NULL,
        current_fingerprint TEXT NOT NULL,
        current_candidate_json TEXT NOT NULL,
        evaluation_id TEXT
    ) STRICT
    """,
    """
    CREATE TABLE candidate_snapshots (
        candidate_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision BETWEEN 0 AND 4),
        status TEXT NOT NULL CHECK (
            status IN ('DRAFT', 'COLLECTING', 'READY', 'EVALUATING',
                       'PASS', 'FAIL', 'REVIEW', 'ERROR')
        ),
        candidate_fingerprint TEXT NOT NULL,
        candidate_json TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        PRIMARY KEY (candidate_id, revision),
        FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    CREATE TABLE candidate_transitions (
        transition_id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        from_revision INTEGER NOT NULL CHECK (from_revision BETWEEN 0 AND 3),
        to_revision INTEGER NOT NULL CHECK (to_revision BETWEEN 1 AND 4),
        occurred_at TEXT NOT NULL,
        transition_json TEXT NOT NULL,
        UNIQUE (candidate_id, from_revision),
        UNIQUE (candidate_id, to_revision),
        FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    CREATE TABLE idempotency_records (
        idempotency_key TEXT PRIMARY KEY,
        operation_kind TEXT NOT NULL CHECK (
            operation_kind IN ('candidate.create', 'candidate.advance')
        ),
        candidate_id TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        response_schema_version TEXT NOT NULL,
        response_json TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    CREATE TRIGGER candidates_guard_update
    BEFORE UPDATE ON candidates
    WHEN OLD.candidate_id IS NOT NEW.candidate_id
      OR OLD.project_id IS NOT NEW.project_id
      OR OLD.version IS NOT NEW.version
      OR OLD.commit_sha IS NOT NEW.commit_sha
      OR OLD.source_branch IS NOT NEW.source_branch
      OR OLD.release_track IS NOT NEW.release_track
      OR OLD.created_at IS NOT NEW.created_at
      OR OLD.initial_fingerprint IS NOT NEW.initial_fingerprint
      OR OLD.initial_candidate_json IS NOT NEW.initial_candidate_json
      OR NEW.current_revision != OLD.current_revision + 1
    BEGIN
        SELECT RAISE(ABORT, 'candidate identity is immutable and revisions advance by one');
    END
    """,
    """
    CREATE TRIGGER candidates_guard_delete
    BEFORE DELETE ON candidates
    BEGIN
        SELECT RAISE(ABORT, 'candidates are append-only records');
    END
    """,
    """
    CREATE TRIGGER candidate_snapshots_guard_update
    BEFORE UPDATE ON candidate_snapshots
    BEGIN
        SELECT RAISE(ABORT, 'candidate snapshots are append-only');
    END
    """,
    """
    CREATE TRIGGER candidate_snapshots_guard_delete
    BEFORE DELETE ON candidate_snapshots
    BEGIN
        SELECT RAISE(ABORT, 'candidate snapshots are append-only');
    END
    """,
    """
    CREATE TRIGGER candidate_transitions_guard_update
    BEFORE UPDATE ON candidate_transitions
    BEGIN
        SELECT RAISE(ABORT, 'candidate transitions are append-only');
    END
    """,
    """
    CREATE TRIGGER candidate_transitions_guard_delete
    BEFORE DELETE ON candidate_transitions
    BEGIN
        SELECT RAISE(ABORT, 'candidate transitions are append-only');
    END
    """,
    """
    CREATE TRIGGER idempotency_records_guard_update
    BEFORE UPDATE ON idempotency_records
    BEGIN
        SELECT RAISE(ABORT, 'idempotency records are immutable');
    END
    """,
    """
    CREATE TRIGGER idempotency_records_guard_delete
    BEFORE DELETE ON idempotency_records
    BEGIN
        SELECT RAISE(ABORT, 'idempotency records are immutable');
    END
    """,
)

_SCHEMA_V2_STATEMENTS = (
    """
    CREATE TABLE candidate_evaluations (
        candidate_id TEXT PRIMARY KEY,
        evaluation_id TEXT NOT NULL,
        evaluation_fingerprint TEXT NOT NULL,
        evaluation_json TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    CREATE TABLE attestations (
        candidate_id TEXT PRIMARY KEY,
        attestation_id TEXT NOT NULL UNIQUE,
        attestation_json TEXT NOT NULL,
        markdown_text TEXT NOT NULL,
        issued_at TEXT NOT NULL,
        FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    CREATE TRIGGER candidate_evaluations_guard_update
    BEFORE UPDATE ON candidate_evaluations
    BEGIN
        SELECT RAISE(ABORT, 'candidate evaluations are immutable');
    END
    """,
    """
    CREATE TRIGGER candidate_evaluations_guard_delete
    BEFORE DELETE ON candidate_evaluations
    BEGIN
        SELECT RAISE(ABORT, 'candidate evaluations are immutable');
    END
    """,
    """
    CREATE TRIGGER attestations_guard_update
    BEFORE UPDATE ON attestations
    BEGIN
        SELECT RAISE(ABORT, 'attestations are immutable');
    END
    """,
    """
    CREATE TRIGGER attestations_guard_delete
    BEFORE DELETE ON attestations
    BEGIN
        SELECT RAISE(ABORT, 'attestations are immutable');
    END
    """,
)

_SCHEMA_V3_STATEMENTS = (
    """
    ALTER TABLE candidates
    ADD COLUMN evidence_binding_required INTEGER NOT NULL DEFAULT 0
        CHECK (evidence_binding_required IN (0, 1))
    """,
    """
    CREATE TABLE candidate_evidence_bindings (
        candidate_id TEXT PRIMARY KEY,
        binding_id TEXT NOT NULL UNIQUE,
        candidate_fingerprint TEXT NOT NULL,
        assembly_id TEXT NOT NULL,
        assembly_fingerprint TEXT NOT NULL,
        binding_json TEXT NOT NULL,
        bound_at TEXT NOT NULL,
        FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    CREATE TRIGGER candidates_binding_requirement_guard_update
    BEFORE UPDATE ON candidates
    WHEN OLD.evidence_binding_required IS NOT NEW.evidence_binding_required
    BEGIN
        SELECT RAISE(ABORT, 'candidate evidence-binding requirement is immutable');
    END
    """,
    """
    CREATE TRIGGER candidate_evidence_bindings_guard_update
    BEFORE UPDATE ON candidate_evidence_bindings
    BEGIN
        SELECT RAISE(ABORT, 'candidate evidence bindings are immutable');
    END
    """,
    """
    CREATE TRIGGER candidate_evidence_bindings_guard_delete
    BEFORE DELETE ON candidate_evidence_bindings
    BEGIN
        SELECT RAISE(ABORT, 'candidate evidence bindings are immutable');
    END
    """,
    "DROP TRIGGER idempotency_records_guard_update",
    "DROP TRIGGER idempotency_records_guard_delete",
    "ALTER TABLE idempotency_records RENAME TO idempotency_records_v2",
    """
    CREATE TABLE idempotency_records (
        idempotency_key TEXT PRIMARY KEY,
        operation_kind TEXT NOT NULL CHECK (
            operation_kind IN (
                'candidate.create', 'candidate.bind-evidence', 'candidate.advance'
            )
        ),
        candidate_id TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        response_schema_version TEXT NOT NULL,
        response_json TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    INSERT INTO idempotency_records(
        idempotency_key, operation_kind, candidate_id, request_fingerprint,
        response_schema_version, response_json, recorded_at
    )
    SELECT idempotency_key, operation_kind, candidate_id, request_fingerprint,
           response_schema_version, response_json, recorded_at
    FROM idempotency_records_v2
    """,
    "DROP TABLE idempotency_records_v2",
    """
    CREATE TRIGGER idempotency_records_guard_update
    BEFORE UPDATE ON idempotency_records
    BEGIN
        SELECT RAISE(ABORT, 'idempotency records are immutable');
    END
    """,
    """
    CREATE TRIGGER idempotency_records_guard_delete
    BEFORE DELETE ON idempotency_records
    BEGIN
        SELECT RAISE(ABORT, 'idempotency records are immutable');
    END
    """,
)

_REQUIRED_OBJECTS_V1 = frozenset(
    {
        ("table", "forgegate_metadata"),
        ("table", "candidates"),
        ("table", "candidate_snapshots"),
        ("table", "candidate_transitions"),
        ("table", "idempotency_records"),
        ("trigger", "candidates_guard_update"),
        ("trigger", "candidates_guard_delete"),
        ("trigger", "candidate_snapshots_guard_update"),
        ("trigger", "candidate_snapshots_guard_delete"),
        ("trigger", "candidate_transitions_guard_update"),
        ("trigger", "candidate_transitions_guard_delete"),
        ("trigger", "idempotency_records_guard_update"),
        ("trigger", "idempotency_records_guard_delete"),
    }
)

_REQUIRED_OBJECTS_V2 = _REQUIRED_OBJECTS_V1 | frozenset(
    {
        ("table", "candidate_evaluations"),
        ("table", "attestations"),
        ("trigger", "candidate_evaluations_guard_update"),
        ("trigger", "candidate_evaluations_guard_delete"),
        ("trigger", "attestations_guard_update"),
        ("trigger", "attestations_guard_delete"),
    }
)

_REQUIRED_OBJECTS_V3 = _REQUIRED_OBJECTS_V2 | frozenset(
    {
        ("table", "candidate_evidence_bindings"),
        ("trigger", "candidates_binding_requirement_guard_update"),
        ("trigger", "candidate_evidence_bindings_guard_update"),
        ("trigger", "candidate_evidence_bindings_guard_delete"),
    }
)


class CandidateStoreError(RuntimeError):
    """Stable failure returned by the local candidate persistence boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class CandidateHistory:
    candidate: ReleaseCandidate
    transitions: tuple[CandidateTransition, ...]
    evidence_binding: CandidateEvidenceBinding | None
    evidence_binding_required: bool


class SQLiteCandidateRepository:
    """Transactional SQLite storage for immutable candidate lifecycle documents."""

    def __init__(
        self,
        database_path: Path,
        *,
        timeout_seconds: float = 5.0,
        _failure_injector: Callable[[str, sqlite3.Connection], None] | None = None,
    ) -> None:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds cannot be negative")
        self.database_path = database_path.expanduser().resolve(strict=False)
        self.timeout_seconds = timeout_seconds
        self._failure_injector = _failure_injector

    def initialize(self) -> None:
        """Create schema v3 or validate an existing current ForgeGate store."""
        connection = self._open(require_exists=False)
        try:
            journal_mode = str(connection.execute("PRAGMA journal_mode = WAL").fetchone()[0])
            _require(journal_mode.lower() == "wal", "SQLite WAL mode could not be enabled")
            application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
            user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if user_version == 0:
                existing_objects = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    )
                }
                if application_id not in {0, STORE_APPLICATION_ID} or existing_objects:
                    raise CandidateStoreError(
                        "STORE_NOT_FORGEGATE",
                        "refusing to initialize a non-empty or foreign SQLite database",
                    )
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(f"PRAGMA application_id = {STORE_APPLICATION_ID}")
                for statement in (
                    *_SCHEMA_V1_STATEMENTS,
                    *_SCHEMA_V2_STATEMENTS,
                    *_SCHEMA_V3_STATEMENTS,
                ):
                    connection.execute(statement)
                connection.executemany(
                    "INSERT INTO forgegate_metadata(key, value) VALUES (?, ?)",
                    (
                        ("schema_name", STORE_SCHEMA_NAME),
                        ("schema_version", str(STORE_SCHEMA_VERSION)),
                    ),
                )
                connection.execute(f"PRAGMA user_version = {STORE_SCHEMA_VERSION}")
                connection.commit()
            elif application_id != STORE_APPLICATION_ID:
                raise CandidateStoreError(
                    "STORE_NOT_FORGEGATE", "database application ID is not ForgeGate"
                )
            elif user_version in {
                LEGACY_STORE_SCHEMA_VERSION,
                PREVIOUS_STORE_SCHEMA_VERSION,
            }:
                raise CandidateStoreError(
                    "STORE_MIGRATION_REQUIRED",
                    f"candidate database schema v{user_version} requires explicit migration to v3",
                )
            self._validate_store(connection)
        except sqlite3.Error as exc:
            connection.rollback()
            raise _translated_sqlite_error(exc) from exc
        finally:
            connection.close()

    def migrate(self) -> None:
        """Explicitly migrate a validated schema-v1/v2 store to schema v3."""
        connection = self._open(require_exists=True)
        try:
            user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if user_version == STORE_SCHEMA_VERSION:
                self._validate_store(connection)
                return
            if user_version not in {
                LEGACY_STORE_SCHEMA_VERSION,
                PREVIOUS_STORE_SCHEMA_VERSION,
            }:
                raise CandidateStoreError(
                    "STORE_SCHEMA_UNSUPPORTED",
                    f"database schema version {user_version} cannot migrate to v3",
                )
            self._validate_store_version(connection, user_version)
            connection.execute("BEGIN IMMEDIATE")
            migration_statements = (
                (*_SCHEMA_V2_STATEMENTS, *_SCHEMA_V3_STATEMENTS)
                if user_version == LEGACY_STORE_SCHEMA_VERSION
                else _SCHEMA_V3_STATEMENTS
            )
            for statement in migration_statements:
                connection.execute(statement)
            connection.execute(
                "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_name'",
                (STORE_SCHEMA_NAME,),
            )
            connection.execute(
                "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_version'",
                (str(STORE_SCHEMA_VERSION),),
            )
            connection.execute(f"PRAGMA user_version = {STORE_SCHEMA_VERSION}")
            connection.commit()
            self._validate_store(connection)
        except sqlite3.Error as exc:
            connection.rollback()
            raise _translated_sqlite_error(exc) from exc
        finally:
            connection.close()

    def create(
        self,
        candidate: ReleaseCandidate,
        *,
        idempotency_key: str,
    ) -> ReleaseCandidate:
        """Persist a DRAFT candidate exactly once and return the durable snapshot."""
        key = _validated_idempotency_key(idempotency_key)
        if candidate.status is not CandidateStatus.DRAFT or candidate.revision != 0:
            raise CandidateStoreError(
                "STORE_CANDIDATE_NOT_DRAFT", "only revision-zero DRAFT candidates can be created"
            )
        candidate_json = _model_json(candidate)
        candidate_fingerprint = sha256_fingerprint(candidate.model_dump(mode="json"))
        request_fingerprint = sha256_fingerprint(
            {"operation": "candidate.create", "candidate": candidate.model_dump(mode="json")}
        )
        with self._transaction(write=True) as connection:
            replay = self._candidate_replay(
                connection,
                key=key,
                candidate_id=candidate.candidate_id,
                request_fingerprint=request_fingerprint,
            )
            if replay is not None:
                return replay
            existing_row = connection.execute(
                "SELECT candidate_id FROM candidates WHERE candidate_id = ?",
                (candidate.candidate_id,),
            ).fetchone()
            if existing_row is None:
                timestamp = _json_timestamp(candidate.created_at)
                connection.execute(
                    """
                    INSERT INTO candidates(
                        candidate_id, project_id, version, commit_sha, source_branch,
                        release_track, created_at, initial_fingerprint, initial_candidate_json,
                        current_revision, current_status, updated_at, current_fingerprint,
                        current_candidate_json, evaluation_id, evidence_binding_required
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate.candidate_id,
                        candidate.project_id,
                        candidate.version,
                        candidate.commit_sha,
                        candidate.source_branch,
                        candidate.release_track,
                        timestamp,
                        candidate_fingerprint,
                        candidate_json,
                        candidate.revision,
                        candidate.status.value,
                        timestamp,
                        candidate_fingerprint,
                        candidate_json,
                        candidate.evaluation_id,
                        1,
                    ),
                )
                self._insert_snapshot(connection, candidate, candidate_fingerprint, candidate_json)
                self._checkpoint("after_candidate_insert", connection)
            else:
                existing = self._load_history(connection, candidate.candidate_id).candidate
                if existing != candidate:
                    raise CandidateStoreError(
                        "STORE_CANDIDATE_CONFLICT",
                        "candidate ID already exists with different content or lifecycle state",
                    )
            self._insert_idempotency(
                connection,
                key=key,
                operation_kind="candidate.create",
                candidate_id=candidate.candidate_id,
                request_fingerprint=request_fingerprint,
                response_schema_version=candidate.schema_version,
                response_json=candidate_json,
                recorded_at=_json_timestamp(candidate.created_at),
            )
            self._checkpoint("after_idempotency_insert", connection)
        return candidate

    def get(self, candidate_id: str) -> ReleaseCandidate:
        """Load and validate the current candidate plus its complete audit chain."""
        with self._transaction(write=False) as connection:
            return self._load_history(connection, candidate_id).candidate

    def history(self, candidate_id: str) -> CandidateHistory:
        """Load the current candidate and all ordered append-only transitions."""
        with self._transaction(write=False) as connection:
            return self._load_history(connection, candidate_id)

    def bind_evidence(
        self,
        candidate_id: str,
        assembly: EvidenceBundleAssembly,
        *,
        bound_at: datetime,
        idempotency_key: str,
    ) -> CandidateEvidenceBinding:
        """Persist one immutable assembly binding for a COLLECTING candidate."""
        key = _validated_idempotency_key(idempotency_key)
        timestamp = _normalized_timestamp(bound_at)
        request_fingerprint = sha256_fingerprint(
            {
                "operation": "candidate.bind-evidence",
                "candidate_id": candidate_id,
                "assembly": assembly.model_dump(mode="json"),
                "bound_at": _json_timestamp(timestamp),
            }
        )
        with self._transaction(write=True) as connection:
            replay = self._binding_replay(
                connection,
                key=key,
                candidate_id=candidate_id,
                request_fingerprint=request_fingerprint,
            )
            if replay is not None:
                return replay
            history = self._load_history(connection, candidate_id)
            if not history.evidence_binding_required:
                raise CandidateStoreError(
                    "STORE_EVIDENCE_BINDING_LEGACY",
                    "migrated legacy candidates do not gain a fabricated binding requirement",
                )
            try:
                binding = create_candidate_evidence_binding(
                    history.candidate,
                    assembly,
                    bound_at=timestamp,
                )
            except (ValidationError, ValueError) as exc:
                raise CandidateStoreError(
                    "STORE_EVIDENCE_BINDING_INVALID", f"cannot bind evidence assembly: {exc}"
                ) from exc
            existing = history.evidence_binding
            if existing is not None:
                if existing != binding:
                    raise CandidateStoreError(
                        "STORE_EVIDENCE_BINDING_CONFLICT",
                        "candidate already has a different durable evidence binding",
                    )
            else:
                self._insert_evidence_binding(connection, binding)
                self._checkpoint("after_evidence_binding_insert", connection)
            binding_json = _model_json(binding)
            self._insert_idempotency(
                connection,
                key=key,
                operation_kind="candidate.bind-evidence",
                candidate_id=candidate_id,
                request_fingerprint=request_fingerprint,
                response_schema_version=binding.schema_version,
                response_json=binding_json,
                recorded_at=_json_timestamp(binding.bound_at),
            )
            self._checkpoint("after_idempotency_insert", connection)
        return binding

    def get_evidence_binding(self, candidate_id: str) -> CandidateEvidenceBinding:
        """Read and validate the candidate's durable assembly binding."""
        with self._transaction(write=False) as connection:
            history = self._load_history(connection, candidate_id)
            if history.evidence_binding is None:
                raise CandidateStoreError(
                    "STORE_EVIDENCE_BINDING_NOT_FOUND",
                    f"candidate has no evidence binding: {candidate_id}",
                )
            return history.evidence_binding

    def record_evaluation(
        self, candidate_id: str, evaluation: PolicyEvaluation
    ) -> PolicyEvaluation:
        """Backfill an exact terminal evaluation after an explicit v1-to-v2 migration."""
        with self._transaction(write=True) as connection:
            candidate = self._load_history(connection, candidate_id).candidate
            self._require_evaluation_matches_candidate(candidate, evaluation)
            existing = connection.execute(
                "SELECT evaluation_json FROM candidate_evaluations WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            evaluation_json = _model_json(evaluation)
            if existing is not None:
                if existing[0] != evaluation_json:
                    raise CandidateStoreError(
                        "STORE_EVALUATION_CONFLICT",
                        "candidate already has a different durable policy evaluation",
                    )
                return cast(PolicyEvaluation, self._load_evaluation(connection, candidate))
            self._insert_evaluation(connection, candidate, evaluation)
            self._checkpoint("after_evaluation_insert", connection)
        return evaluation

    def evaluation(self, candidate_id: str) -> PolicyEvaluation | None:
        """Read and validate the policy evaluation bound to a terminal candidate."""
        with self._transaction(write=False) as connection:
            candidate = self._load_history(connection, candidate_id).candidate
            return self._load_evaluation(connection, candidate)

    def attest(
        self,
        candidate_id: str,
        *,
        issued_at: datetime,
        generator_version: str,
    ) -> ReleaseAttestation:
        """Create or exactly replay one durable self-contained attestation per candidate."""
        with self._transaction(write=True) as connection:
            history = self._load_history(connection, candidate_id)
            evaluation = self._load_evaluation(connection, history.candidate)
            try:
                attestation = create_release_attestation(
                    history.candidate,
                    history.transitions,
                    policy_evaluation=evaluation,
                    issued_at=issued_at,
                    generator_version=generator_version,
                )
            except (ValidationError, ValueError) as exc:
                raise CandidateStoreError(
                    "STORE_ATTESTATION_INVALID", f"cannot attest candidate: {exc}"
                ) from exc
            attestation_json = _model_json(attestation)
            markdown = render_attestation_markdown(attestation)
            existing = connection.execute(
                "SELECT * FROM attestations WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()
            if existing is not None:
                stored = self._decode_attestation_row(existing, history, evaluation)
                if stored != attestation:
                    raise CandidateStoreError(
                        "STORE_ATTESTATION_CONFLICT",
                        "candidate already has a different durable attestation",
                    )
                return stored
            connection.execute(
                """
                INSERT INTO attestations(
                    candidate_id, attestation_id, attestation_json, markdown_text, issued_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    attestation.attestation_id,
                    attestation_json,
                    markdown,
                    _json_timestamp(attestation.issued_at),
                ),
            )
            self._checkpoint("after_attestation_insert", connection)
        return attestation

    def get_attestation(self, candidate_id: str) -> ReleaseAttestation:
        """Read and validate the candidate's durable attestation and all associations."""
        with self._transaction(write=False) as connection:
            history = self._load_history(connection, candidate_id)
            evaluation = self._load_evaluation(connection, history.candidate)
            row = connection.execute(
                "SELECT * FROM attestations WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()
            if row is None:
                raise CandidateStoreError(
                    "STORE_ATTESTATION_NOT_FOUND", f"candidate has no attestation: {candidate_id}"
                )
            return self._decode_attestation_row(row, history, evaluation)

    def advance(
        self,
        candidate_id: str,
        to_status: CandidateStatus,
        *,
        expected_revision: int,
        occurred_at: datetime,
        idempotency_key: str,
        reason: str | None = None,
        evaluation: PolicyEvaluation | None = None,
    ) -> CandidateTransitionResult:
        """Atomically append one legal transition using compare-and-swap revision control."""
        if expected_revision < 0:
            raise CandidateStoreError(
                "STORE_REVISION_INVALID", "expected_revision cannot be negative"
            )
        key = _validated_idempotency_key(idempotency_key)
        timestamp = _normalized_timestamp(occurred_at)
        normalized_reason = _normalized_reason(reason)
        request = {
            "operation": "candidate.advance",
            "candidate_id": candidate_id,
            "to_status": to_status.value,
            "expected_revision": expected_revision,
            "occurred_at": _json_timestamp(timestamp),
            "reason": normalized_reason,
            "evaluation": evaluation.model_dump(mode="json") if evaluation is not None else None,
        }
        request_fingerprint = sha256_fingerprint(request)
        with self._transaction(write=True) as connection:
            replay = self._transition_replay(
                connection,
                key=key,
                candidate_id=candidate_id,
                request_fingerprint=request_fingerprint,
            )
            if replay is not None:
                return replay
            history = self._load_history(connection, candidate_id)
            current = history.candidate
            if current.revision != expected_revision:
                raise CandidateStoreError(
                    "STORE_REVISION_CONFLICT",
                    "expected revision "
                    f"{expected_revision}, current revision is {current.revision}",
                )
            binding = history.evidence_binding
            if to_status is CandidateStatus.READY and history.evidence_binding_required:
                if binding is None:
                    raise CandidateStoreError(
                        "STORE_EVIDENCE_BINDING_REQUIRED",
                        "COLLECTING to READY requires a durable evidence assembly binding",
                    )
                if timestamp < binding.bound_at:
                    raise CandidateStoreError(
                        "STORE_EVIDENCE_BINDING_TIME_MISMATCH",
                        "READY transition cannot precede evidence binding time",
                    )
            if evaluation is not None and binding is not None:
                evidence_fingerprint = sha256_fingerprint(
                    binding.assembly.bundle.model_dump(mode="json")
                )
                if evaluation.evidence_fingerprint != evidence_fingerprint:
                    raise CandidateStoreError(
                        "STORE_EVALUATION_EVIDENCE_MISMATCH",
                        "policy evaluation does not reference the bound evidence bundle",
                    )
            result = transition_candidate(
                current,
                to_status,
                occurred_at=timestamp,
                reason=normalized_reason,
                evaluation=evaluation,
            )
            result_json = _model_json(result)
            next_candidate_json = _model_json(result.candidate)
            next_fingerprint = result.transition.result_candidate_fingerprint
            transition_json = _model_json(result.transition)
            self._insert_snapshot(
                connection, result.candidate, next_fingerprint, next_candidate_json
            )
            connection.execute(
                """
                INSERT INTO candidate_transitions(
                    transition_id, candidate_id, from_revision, to_revision,
                    occurred_at, transition_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result.transition.transition_id,
                    candidate_id,
                    result.transition.from_revision,
                    result.transition.to_revision,
                    _json_timestamp(result.transition.occurred_at),
                    transition_json,
                ),
            )
            if evaluation is not None:
                self._insert_evaluation(connection, result.candidate, evaluation)
            self._checkpoint("after_transition_append", connection)
            updated = connection.execute(
                """
                UPDATE candidates
                SET current_revision = ?, current_status = ?, updated_at = ?,
                    current_fingerprint = ?, current_candidate_json = ?, evaluation_id = ?
                WHERE candidate_id = ? AND current_revision = ?
                """,
                (
                    result.candidate.revision,
                    result.candidate.status.value,
                    _json_timestamp(result.candidate.updated_at),
                    next_fingerprint,
                    next_candidate_json,
                    result.candidate.evaluation_id,
                    candidate_id,
                    expected_revision,
                ),
            )
            if updated.rowcount != 1:
                raise CandidateStoreError(
                    "STORE_REVISION_CONFLICT", "candidate revision changed during transition"
                )
            self._checkpoint("after_current_update", connection)
            self._insert_idempotency(
                connection,
                key=key,
                operation_kind="candidate.advance",
                candidate_id=candidate_id,
                request_fingerprint=request_fingerprint,
                response_schema_version=result.schema_version,
                response_json=result_json,
                recorded_at=_json_timestamp(timestamp),
            )
            self._checkpoint("after_idempotency_insert", connection)
        return result

    @contextmanager
    def _transaction(self, *, write: bool) -> Iterator[sqlite3.Connection]:
        connection = self._open(require_exists=True)
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            self._validate_store(connection)
            yield connection
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise _translated_sqlite_error(exc) from exc
        finally:
            connection.close()

    def _open(self, *, require_exists: bool) -> sqlite3.Connection:
        path = self.database_path
        if require_exists and not path.is_file():
            raise CandidateStoreError(
                "STORE_NOT_INITIALIZED", f"candidate database does not exist: {path}"
            )
        if path.exists() and not path.is_file():
            raise CandidateStoreError("STORE_PATH_INVALID", f"database path is not a file: {path}")
        if not path.parent.is_dir():
            raise CandidateStoreError(
                "STORE_PARENT_MISSING", f"database parent directory does not exist: {path.parent}"
            )
        try:
            connection = sqlite3.connect(
                path,
                timeout=self.timeout_seconds,
                isolation_level=None,
            )
        except sqlite3.Error as exc:
            raise _translated_sqlite_error(exc) from exc
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute(f"PRAGMA busy_timeout = {round(self.timeout_seconds * 1000)}")
        except sqlite3.Error as exc:
            connection.close()
            raise _translated_sqlite_error(exc) from exc
        return connection

    def _validate_store(self, connection: sqlite3.Connection) -> None:
        self._validate_store_version(connection, STORE_SCHEMA_VERSION)

    def _validate_store_version(
        self, connection: sqlite3.Connection, expected_version: int
    ) -> None:
        application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        foreign_keys = int(connection.execute("PRAGMA foreign_keys").fetchone()[0])
        synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
        _require(application_id == STORE_APPLICATION_ID, "database application ID is not ForgeGate")
        if user_version != expected_version:
            raise CandidateStoreError(
                "STORE_SCHEMA_UNSUPPORTED",
                f"database schema version {user_version} is not supported",
            )
        _require(journal_mode.lower() == "wal", "candidate database is not in WAL mode")
        _require(foreign_keys == 1, "candidate database foreign keys are disabled")
        _require(synchronous == 2, "candidate database durability mode is not FULL")
        objects = {
            (str(row[0]), str(row[1]))
            for row in connection.execute(
                "SELECT type, name FROM sqlite_master WHERE type IN ('table', 'trigger')"
            )
        }
        required_objects = {
            LEGACY_STORE_SCHEMA_VERSION: _REQUIRED_OBJECTS_V1,
            PREVIOUS_STORE_SCHEMA_VERSION: _REQUIRED_OBJECTS_V2,
            STORE_SCHEMA_VERSION: _REQUIRED_OBJECTS_V3,
        }.get(expected_version)
        if required_objects is None:
            raise CandidateStoreError(
                "STORE_SCHEMA_UNSUPPORTED",
                f"database schema version {expected_version} is not supported",
            )
        _require(objects >= required_objects, "candidate database schema objects are missing")
        metadata = {
            str(row[0]): str(row[1])
            for row in connection.execute("SELECT key, value FROM forgegate_metadata")
        }
        _require(
            metadata
            == {
                "schema_name": {
                    LEGACY_STORE_SCHEMA_VERSION: LEGACY_STORE_SCHEMA_NAME,
                    PREVIOUS_STORE_SCHEMA_VERSION: PREVIOUS_STORE_SCHEMA_NAME,
                    STORE_SCHEMA_VERSION: STORE_SCHEMA_NAME,
                }[expected_version],
                "schema_version": str(expected_version),
            },
            "candidate database metadata is invalid",
        )
        foreign_key_errors = list(connection.execute("PRAGMA foreign_key_check"))
        _require(not foreign_key_errors, "candidate database foreign-key integrity failed")

    def _load_history(self, connection: sqlite3.Connection, candidate_id: str) -> CandidateHistory:
        candidate_row = connection.execute(
            "SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
        if candidate_row is None:
            raise CandidateStoreError(
                "STORE_CANDIDATE_NOT_FOUND", f"candidate does not exist: {candidate_id}"
            )
        snapshot_rows = list(
            connection.execute(
                "SELECT * FROM candidate_snapshots WHERE candidate_id = ? ORDER BY revision",
                (candidate_id,),
            )
        )
        transition_rows = list(
            connection.execute(
                "SELECT * FROM candidate_transitions WHERE candidate_id = ? ORDER BY to_revision",
                (candidate_id,),
            )
        )
        current_revision = int(candidate_row["current_revision"])
        _require(
            len(snapshot_rows) == current_revision + 1, "candidate snapshot chain is incomplete"
        )
        _require(
            len(transition_rows) == current_revision, "candidate transition chain is incomplete"
        )

        snapshots: list[ReleaseCandidate] = []
        fingerprints: list[str] = []
        for expected_revision, row in enumerate(snapshot_rows):
            candidate = _decode_model(str(row["candidate_json"]), ReleaseCandidate)
            fingerprint = sha256_fingerprint(candidate.model_dump(mode="json"))
            _require(
                (
                    row["candidate_id"],
                    int(row["revision"]),
                    row["status"],
                    row["candidate_fingerprint"],
                    row["recorded_at"],
                )
                == (
                    candidate.candidate_id,
                    expected_revision,
                    candidate.status.value,
                    fingerprint,
                    _json_timestamp(candidate.updated_at),
                ),
                "candidate snapshot metadata does not match its document",
            )
            snapshots.append(candidate)
            fingerprints.append(fingerprint)

        transitions: list[CandidateTransition] = []
        for index, row in enumerate(transition_rows):
            transition = _decode_model(str(row["transition_json"]), CandidateTransition)
            before = snapshots[index]
            after = snapshots[index + 1]
            _require(
                (
                    row["transition_id"],
                    row["candidate_id"],
                    int(row["from_revision"]),
                    int(row["to_revision"]),
                    row["occurred_at"],
                )
                == (
                    transition.transition_id,
                    transition.candidate_id,
                    transition.from_revision,
                    transition.to_revision,
                    _json_timestamp(transition.occurred_at),
                ),
                "candidate transition metadata does not match its document",
            )
            _require(
                (
                    transition.from_revision,
                    transition.to_revision,
                    transition.from_status,
                    transition.to_status,
                    transition.prior_candidate_fingerprint,
                    transition.result_candidate_fingerprint,
                )
                == (
                    before.revision,
                    after.revision,
                    before.status,
                    after.status,
                    fingerprints[index],
                    fingerprints[index + 1],
                ),
                "candidate transition does not link adjacent snapshots",
            )
            transitions.append(transition)

        initial = snapshots[0]
        current = snapshots[-1]
        current_json = _model_json(current)
        _require(
            (
                candidate_row["candidate_id"],
                candidate_row["project_id"],
                candidate_row["version"],
                candidate_row["commit_sha"],
                candidate_row["source_branch"],
                candidate_row["release_track"],
                candidate_row["created_at"],
                candidate_row["initial_fingerprint"],
                candidate_row["initial_candidate_json"],
                int(candidate_row["current_revision"]),
                candidate_row["current_status"],
                candidate_row["updated_at"],
                candidate_row["current_fingerprint"],
                candidate_row["current_candidate_json"],
                candidate_row["evaluation_id"],
            )
            == (
                initial.candidate_id,
                initial.project_id,
                initial.version,
                initial.commit_sha,
                initial.source_branch,
                initial.release_track,
                _json_timestamp(initial.created_at),
                fingerprints[0],
                _model_json(initial),
                current.revision,
                current.status.value,
                _json_timestamp(current.updated_at),
                fingerprints[-1],
                current_json,
                current.evaluation_id,
            ),
            "candidate current pointer or immutable identity is corrupt",
        )
        required_value = int(candidate_row["evidence_binding_required"])
        _require(required_value in {0, 1}, "candidate evidence-binding requirement is invalid")
        binding_required = bool(required_value)
        binding = self._load_evidence_binding(connection, snapshots)
        if not binding_required:
            _require(binding is None, "legacy candidate has an unexpected evidence binding")
        if binding_required and current.revision >= 2:
            _require(binding is not None, "READY candidate is missing its evidence binding")
            assert binding is not None
            _require(
                snapshots[2].updated_at >= binding.bound_at,
                "candidate advanced before its evidence binding timestamp",
            )
            if current.evaluation_id is not None:
                evaluation = self._load_evaluation(connection, current)
                assert evaluation is not None
                _require(
                    evaluation.evidence_fingerprint
                    == sha256_fingerprint(binding.assembly.bundle.model_dump(mode="json")),
                    "candidate evaluation is detached from its evidence binding",
                )
        return CandidateHistory(
            candidate=current,
            transitions=tuple(transitions),
            evidence_binding=binding,
            evidence_binding_required=binding_required,
        )

    @staticmethod
    def _insert_evidence_binding(
        connection: sqlite3.Connection,
        binding: CandidateEvidenceBinding,
    ) -> None:
        connection.execute(
            """
            INSERT INTO candidate_evidence_bindings(
                candidate_id, binding_id, candidate_fingerprint, assembly_id,
                assembly_fingerprint, binding_json, bound_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                binding.candidate.candidate_id,
                binding.binding_id,
                binding.candidate_fingerprint,
                binding.assembly.assembly_id,
                binding.assembly_fingerprint,
                _model_json(binding),
                _json_timestamp(binding.bound_at),
            ),
        )

    @staticmethod
    def _load_evidence_binding(
        connection: sqlite3.Connection,
        snapshots: list[ReleaseCandidate],
    ) -> CandidateEvidenceBinding | None:
        row = connection.execute(
            "SELECT * FROM candidate_evidence_bindings WHERE candidate_id = ?",
            (snapshots[0].candidate_id,),
        ).fetchone()
        if row is None:
            return None
        binding = _decode_model(str(row["binding_json"]), CandidateEvidenceBinding)
        _require(
            len(snapshots) >= 2 and binding.candidate == snapshots[1],
            "evidence binding is detached from the COLLECTING candidate snapshot",
        )
        _require(
            (
                row["candidate_id"],
                row["binding_id"],
                row["candidate_fingerprint"],
                row["assembly_id"],
                row["assembly_fingerprint"],
                row["bound_at"],
            )
            == (
                binding.candidate.candidate_id,
                binding.binding_id,
                binding.candidate_fingerprint,
                binding.assembly.assembly_id,
                binding.assembly_fingerprint,
                _json_timestamp(binding.bound_at),
            ),
            "evidence binding metadata does not match its document",
        )
        return binding

    @staticmethod
    def _require_evaluation_matches_candidate(
        candidate: ReleaseCandidate, evaluation: PolicyEvaluation
    ) -> None:
        if candidate.revision != 4 or candidate.evaluation_id is None:
            raise CandidateStoreError(
                "STORE_EVALUATION_UNEXPECTED",
                "candidate does not have a terminal policy-evaluation reference",
            )
        if (
            candidate.evaluation_id != evaluation.evaluation_id
            or candidate.commit_sha.lower() != evaluation.candidate_commit.lower()
            or candidate.status.value != evaluation.decision.value
            or candidate.updated_at != evaluation.evaluated_at
        ):
            raise CandidateStoreError(
                "STORE_EVALUATION_MISMATCH",
                "policy evaluation does not match candidate ID, commit, decision, and time",
            )

    def _insert_evaluation(
        self,
        connection: sqlite3.Connection,
        candidate: ReleaseCandidate,
        evaluation: PolicyEvaluation,
    ) -> None:
        self._require_evaluation_matches_candidate(candidate, evaluation)
        evaluation_json = _model_json(evaluation)
        connection.execute(
            """
            INSERT INTO candidate_evaluations(
                candidate_id, evaluation_id, evaluation_fingerprint,
                evaluation_json, recorded_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                candidate.candidate_id,
                evaluation.evaluation_id,
                sha256_fingerprint(evaluation.model_dump(mode="json")),
                evaluation_json,
                _json_timestamp(evaluation.evaluated_at),
            ),
        )

    def _load_evaluation(
        self, connection: sqlite3.Connection, candidate: ReleaseCandidate
    ) -> PolicyEvaluation | None:
        row = connection.execute(
            "SELECT * FROM candidate_evaluations WHERE candidate_id = ?",
            (candidate.candidate_id,),
        ).fetchone()
        if candidate.evaluation_id is None:
            _require(row is None, "candidate has an unexpected durable policy evaluation")
            return None
        if row is None:
            raise CandidateStoreError(
                "STORE_EVALUATION_NOT_FOUND",
                "candidate evaluation document is absent; import it after legacy migration",
            )
        evaluation = _decode_model(str(row["evaluation_json"]), PolicyEvaluation)
        fingerprint = sha256_fingerprint(evaluation.model_dump(mode="json"))
        _require(
            (
                row["candidate_id"],
                row["evaluation_id"],
                row["evaluation_fingerprint"],
                row["recorded_at"],
            )
            == (
                candidate.candidate_id,
                evaluation.evaluation_id,
                fingerprint,
                _json_timestamp(evaluation.evaluated_at),
            ),
            "candidate evaluation metadata does not match its document",
        )
        self._require_evaluation_matches_candidate(candidate, evaluation)
        return evaluation

    def _decode_attestation_row(
        self,
        row: sqlite3.Row,
        history: CandidateHistory,
        evaluation: PolicyEvaluation | None,
    ) -> ReleaseAttestation:
        attestation = _decode_model(str(row["attestation_json"]), ReleaseAttestation)
        markdown = render_attestation_markdown(attestation)
        _require(
            (
                row["candidate_id"],
                row["attestation_id"],
                row["markdown_text"],
                row["issued_at"],
            )
            == (
                history.candidate.candidate_id,
                attestation.attestation_id,
                markdown,
                _json_timestamp(attestation.issued_at),
            ),
            "stored attestation metadata or Markdown rendering is corrupt",
        )
        _require(
            (
                attestation.candidate,
                tuple(attestation.transitions),
                attestation.policy_evaluation,
            )
            == (history.candidate, history.transitions, evaluation),
            "stored attestation is detached from durable candidate inputs",
        )
        return attestation

    def _candidate_replay(
        self,
        connection: sqlite3.Connection,
        *,
        key: str,
        candidate_id: str,
        request_fingerprint: str,
    ) -> ReleaseCandidate | None:
        row = self._idempotency_row(connection, key)
        if row is None:
            return None
        self._validate_replay_row(
            row,
            operation_kind="candidate.create",
            candidate_id=candidate_id,
            request_fingerprint=request_fingerprint,
            response_schema_version="forgegate.release-candidate.v1",
        )
        replay = _decode_model(str(row["response_json"]), ReleaseCandidate)
        self._load_history(connection, candidate_id)
        initial_row = connection.execute(
            "SELECT initial_candidate_json FROM candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        _require(
            initial_row is not None and initial_row[0] == row["response_json"],
            "candidate creation replay does not match the initial durable snapshot",
        )
        return replay

    def _transition_replay(
        self,
        connection: sqlite3.Connection,
        *,
        key: str,
        candidate_id: str,
        request_fingerprint: str,
    ) -> CandidateTransitionResult | None:
        row = self._idempotency_row(connection, key)
        if row is None:
            return None
        self._validate_replay_row(
            row,
            operation_kind="candidate.advance",
            candidate_id=candidate_id,
            request_fingerprint=request_fingerprint,
            response_schema_version="forgegate.candidate-transition-result.v1",
        )
        replay = _decode_model(str(row["response_json"]), CandidateTransitionResult)
        history = self._load_history(connection, candidate_id)
        snapshot_row = connection.execute(
            "SELECT candidate_json FROM candidate_snapshots "
            "WHERE candidate_id = ? AND revision = ?",
            (candidate_id, replay.candidate.revision),
        ).fetchone()
        _require(
            snapshot_row is not None and snapshot_row[0] == _model_json(replay.candidate),
            "transition replay does not match its durable candidate snapshot",
        )
        _require(
            replay.transition in history.transitions,
            "transition replay event is absent from the durable audit chain",
        )
        return replay

    def _binding_replay(
        self,
        connection: sqlite3.Connection,
        *,
        key: str,
        candidate_id: str,
        request_fingerprint: str,
    ) -> CandidateEvidenceBinding | None:
        row = self._idempotency_row(connection, key)
        if row is None:
            return None
        self._validate_replay_row(
            row,
            operation_kind="candidate.bind-evidence",
            candidate_id=candidate_id,
            request_fingerprint=request_fingerprint,
            response_schema_version="forgegate.candidate-evidence-binding.v1",
        )
        replay = _decode_model(str(row["response_json"]), CandidateEvidenceBinding)
        history = self._load_history(connection, candidate_id)
        _require(
            history.evidence_binding == replay,
            "evidence-binding replay does not match the durable binding",
        )
        return replay

    @staticmethod
    def _idempotency_row(connection: sqlite3.Connection, key: str) -> sqlite3.Row | None:
        row = connection.execute(
            "SELECT * FROM idempotency_records WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    @staticmethod
    def _validate_replay_row(
        row: sqlite3.Row,
        *,
        operation_kind: str,
        candidate_id: str,
        request_fingerprint: str,
        response_schema_version: str,
    ) -> None:
        if (
            row["operation_kind"],
            row["candidate_id"],
            row["request_fingerprint"],
            row["response_schema_version"],
        ) != (
            operation_kind,
            candidate_id,
            request_fingerprint,
            response_schema_version,
        ):
            raise CandidateStoreError(
                "STORE_IDEMPOTENCY_CONFLICT",
                "idempotency key was already used for a different request",
            )

    @staticmethod
    def _insert_snapshot(
        connection: sqlite3.Connection,
        candidate: ReleaseCandidate,
        fingerprint: str,
        candidate_json: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO candidate_snapshots(
                candidate_id, revision, status, candidate_fingerprint,
                candidate_json, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.candidate_id,
                candidate.revision,
                candidate.status.value,
                fingerprint,
                candidate_json,
                _json_timestamp(candidate.updated_at),
            ),
        )

    @staticmethod
    def _insert_idempotency(
        connection: sqlite3.Connection,
        *,
        key: str,
        operation_kind: str,
        candidate_id: str,
        request_fingerprint: str,
        response_schema_version: str,
        response_json: str,
        recorded_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO idempotency_records(
                idempotency_key, operation_kind, candidate_id, request_fingerprint,
                response_schema_version, response_json, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                operation_kind,
                candidate_id,
                request_fingerprint,
                response_schema_version,
                response_json,
                recorded_at,
            ),
        )

    def _checkpoint(self, name: str, connection: sqlite3.Connection) -> None:
        if self._failure_injector is not None:
            self._failure_injector(name, connection)


def _validated_idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(normalized):
        raise CandidateStoreError(
            "STORE_IDEMPOTENCY_KEY_INVALID",
            "idempotency key must be 8-128 safe ASCII characters",
        )
    return normalized


def _normalized_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CandidateLifecycleError(
            "CANDIDATE_TIMESTAMP_NAIVE", "occurred_at must include a UTC offset"
        )
    return value.astimezone(UTC)


def _normalized_reason(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise CandidateLifecycleError("CANDIDATE_REASON_EMPTY", "transition reason cannot be blank")
    return normalized


def _json_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _model_json(model: BaseModel) -> str:
    return canonical_json(model.model_dump(mode="json"))


def _decode_model[ModelT: BaseModel](payload: str, model: type[ModelT]) -> ModelT:
    try:
        decoded = model.model_validate_json(payload)
    except (ValidationError, ValueError) as exc:
        raise CandidateStoreError(
            "STORE_CORRUPT", f"stored {model.__name__} document is invalid"
        ) from exc
    _require(payload == _model_json(decoded), f"stored {model.__name__} JSON is not canonical")
    return decoded


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CandidateStoreError("STORE_CORRUPT", message)


def _translated_sqlite_error(exc: sqlite3.Error) -> CandidateStoreError:
    message = str(exc)
    if "locked" in message.lower() or "busy" in message.lower():
        return CandidateStoreError("STORE_BUSY", "candidate database is busy")
    return CandidateStoreError("STORE_DATABASE_ERROR", f"SQLite operation failed: {message}")
