"""Bounded cold-copy inspection using current store readers and exact schema templates."""

import json
import re
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any

from forgegate.adoption_models import MAX_INVENTORY_ROWS
from forgegate.bounded_parsing import enforce_json_structure_limits
from forgegate.candidates.backups import TABLES, _check_time, _connect
from forgegate.candidates.store import (
    IDEMPOTENCY_KEY_PATTERN,
    SQLiteCandidateRepository,
    _decode_project_profile,
)
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.collection_jobs import CollectionJobStore
from forgegate.recovery_models import _unique
from forgegate.workspace_backups import _require

MAX_INVENTORY_BYTES = 128 * 1024 * 1024
MAX_CELL_BYTES = 40 * 1024 * 1024
JOB_TABLES = ("jobs", "events", "job_archives")
type Inventory = dict[str, dict[str, str]]


def _schema(con: sqlite3.Connection) -> list[tuple[str, str, str, str | None]]:
    _require(
        con.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] <= 128,
        "ADOPTION_SCHEMA_UNSUPPORTED",
    )
    _require(
        con.execute("SELECT coalesce(sum(length(sql)),0) FROM sqlite_master").fetchone()[0]
        <= 128 * 1024,
        "ADOPTION_SCHEMA_UNSUPPORTED",
    )
    return [
        tuple(row)
        for row in con.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )
    ]


def inspect_bounds(root: Path, deadline: float) -> None:
    """Run BEFORE existing readers materialize JSON/history. Only disposable copies are opened."""
    with tempfile.TemporaryDirectory(prefix="adoption-schema-") as temp:
        reference = Path(temp)
        SQLiteCandidateRepository(reference / "candidates.db").initialize()
        template_jobs = CollectionJobStore(reference / "jobs.db")
        template_jobs.initialize()
        total_rows = total_bytes = 0
        for store, tables in (("candidates", TABLES), ("jobs", JOB_TABLES)):
            with closing(_connect(root / f"{store}.db", deadline)) as con:
                con.execute("PRAGMA trusted_schema=OFF")
                if store == "jobs" and con.execute("PRAGMA user_version").fetchone()[0] == 4:
                    template_jobs.enable_archiving()
                with closing(_connect(reference / f"{store}.db", deadline)) as trusted:
                    _require(_schema(con) == _schema(trusted), "ADOPTION_SCHEMA_UNSUPPORTED")
                existing = {
                    row[0]
                    for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                for table in tables:
                    _check_time(deadline)
                    if table not in existing:
                        continue
                    columns = [row[1] for row in con.execute(f'PRAGMA table_info("{table}")')]
                    total_rows += con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                    _require(total_rows <= MAX_INVENTORY_ROWS, "ADOPTION_ROW_LIMIT")
                    for column in columns:
                        size = f'length(cast("{column}" as blob))'
                        maximum, total = con.execute(
                            f'SELECT coalesce(max({size}),0),coalesce(sum({size}),0) FROM "{table}"'
                        ).fetchone()
                        total_bytes += total
                        _require(
                            maximum <= MAX_CELL_BYTES and total_bytes <= MAX_INVENTORY_BYTES,
                            "ADOPTION_BYTE_LIMIT",
                        )
                    for row in con.execute(f'SELECT * FROM "{table}"'):
                        _check_time(deadline)
                        for name, value in zip(columns, row, strict=True):
                            _require(
                                value is None or type(value) in (str, int),
                                "ADOPTION_VALUE_UNSUPPORTED",
                            )
                            if value is not None and (
                                name.endswith("_json")
                                or name in {"record", "input", "result", "receipt", "actor"}
                            ):
                                raw = value.encode("utf-8")
                                enforce_json_structure_limits(raw, max_nodes=500_000, max_depth=40)
                                json.loads(
                                    raw, object_pairs_hook=_unique, parse_constant=_nonfinite
                                )
        _check_time(deadline)


def _nonfinite(_: str) -> None:
    raise ValueError("non-finite JSON")


def _replays(repo: SQLiteCandidateRepository, con: sqlite3.Connection, deadline: float) -> None:
    for table in (
        "idempotency_records",
        "project_idempotency_records",
        "project_revision_idempotency_records",
    ):
        for row in con.execute(f'SELECT * FROM "{table}"'):
            _check_time(deadline)
            _require(
                IDEMPOTENCY_KEY_PATTERN.fullmatch(row["idempotency_key"]) is not None
                and re.fullmatch(r"sha256:[0-9a-f]{64}", row["request_fingerprint"]) is not None,
                "ADOPTION_REPLAY_INVALID",
            )
            payload = json.loads(row["response_json"])
            _require(
                row["response_schema_version"] == payload["schema_version"],
                "ADOPTION_REPLAY_INVALID",
            )
            if table != "idempotency_records":
                profile = _decode_project_profile(row["response_json"])
                durable = repo._load_project_profile(
                    con, row["project_id"], profile.profile_version
                )
                _require(profile == durable, "ADOPTION_REPLAY_INVALID")
                stamp = payload.get("effective_at", payload.get("registered_at"))
                _require(
                    row["recorded_at"] == stamp
                    and (table == "project_idempotency_records") == (profile.profile_version == 1),
                    "ADOPTION_REPLAY_INVALID",
                )
            else:
                operation = row["operation_kind"]
                method = {
                    "candidate.create": repo._candidate_replay,
                    "candidate.advance": repo._transition_replay,
                    "candidate.bind-evidence": repo._binding_replay,
                }[operation]
                method(
                    con,
                    key=row["idempotency_key"],
                    candidate_id=row["candidate_id"],
                    request_fingerprint=row["request_fingerprint"],
                )
                stamp = (
                    payload["updated_at"]
                    if operation == "candidate.create"
                    else payload["transition"]["occurred_at"]
                    if operation == "candidate.advance"
                    else payload["bound_at"]
                )
                _require(row["recorded_at"] == stamp, "ADOPTION_REPLAY_INVALID")


def inspect_domain(root: Path, deadline: float) -> None:
    """Check all candidates/profiles, audit subjects and retained replay responses.

    Original request bodies are not fully retained: request authenticity is not inferred.
    Legacy missing evaluations/audit subjects and unknown layouts fail closed.
    """
    repo = SQLiteCandidateRepository(root / "candidates.db")
    with closing(_connect(root / "candidates.db", deadline)) as con:
        for row in con.execute("SELECT project_id FROM projects"):
            _check_time(deadline)
            repo._load_current_project_profile(con, row[0])
        for row in con.execute("SELECT candidate_id FROM candidates"):
            _check_time(deadline)
            history = repo._load_history(con, row[0])
            evaluation = repo._load_evaluation(con, history.candidate)
            attestation = con.execute(
                "SELECT * FROM attestations WHERE candidate_id=?", (row[0],)
            ).fetchone()
            if attestation is not None:
                repo._decode_attestation_row(attestation, history, evaluation)
        _replays(repo, con, deadline)
        _audit_subjects(con, repo, deadline)
        for sequence, row in enumerate(
            con.execute("SELECT * FROM api_security_events ORDER BY sequence"), 1
        ):
            _check_time(deadline)
            _require(
                repo._decode_api_security_event_row(row).sequence == sequence,
                "ADOPTION_SECURITY_SEQUENCE_INVALID",
            )


def _audit_subjects(
    con: sqlite3.Connection, repo: SQLiteCandidateRepository, deadline: float
) -> None:
    expected: set[tuple[str, str, str | None, str, str, str, str]] = set()
    specs = (
        ("projects", "project_json", "project.registered", "registration_id", "registered_at"),
        (
            "project_profiles",
            "profile_json",
            "project.profile-revised",
            "revision_id",
            "effective_at",
        ),
        ("candidates", "initial_candidate_json", "candidate.created", "candidate_id", "created_at"),
        (
            "candidate_transitions",
            "transition_json",
            "candidate.transitioned",
            "transition_id",
            "occurred_at",
        ),
        (
            "candidate_evidence_bindings",
            "binding_json",
            "candidate.evidence-bound",
            "binding_id",
            "bound_at",
        ),
        (
            "candidate_evaluations",
            "evaluation_json",
            "candidate.evaluation-recorded",
            "evaluation_id",
            "evaluated_at",
        ),
        (
            "attestations",
            "attestation_json",
            "candidate.attestation-recorded",
            "attestation_id",
            "issued_at",
        ),
    )
    for table, column, event_type, id_field, time_field in specs:
        for row in con.execute(f'SELECT * FROM "{table}"'):
            _check_time(deadline)
            document = json.loads(row[column])
            if event_type == "project.profile-revised" and document["profile_version"] == 1:
                continue
            metadata = dict(row)
            candidate_id = metadata.get("candidate_id")
            project_id = (
                row["project_id"]
                if "project_id" in metadata
                else con.execute(
                    "SELECT project_id FROM candidates WHERE candidate_id=?", (candidate_id,)
                ).fetchone()[0]
            )
            expected.add(
                (
                    event_type,
                    project_id,
                    candidate_id,
                    document["schema_version"],
                    document[id_field],
                    sha256_fingerprint(document),
                    document[time_field],
                )
            )
    actual = set()
    for sequence, row in enumerate(con.execute("SELECT * FROM audit_events ORDER BY sequence"), 1):
        _check_time(deadline)
        event = repo._decode_audit_row(row)
        stamp = event.occurred_at.isoformat().replace("+00:00", "Z")
        item = (
            event.event_type.value,
            event.project_id,
            event.candidate_id,
            event.subject_schema_version,
            event.subject_id,
            event.subject_fingerprint,
            stamp,
        )
        _require(event.sequence == sequence and item not in actual, "ADOPTION_AUDIT_INVALID")
        actual.add(item)
    _require(actual == expected, "ADOPTION_AUDIT_SUBJECT_MISMATCH")


def inventory(root: Path, deadline: float) -> tuple[Inventory, str]:
    """Hash exact typed column values; export neither row contents nor request keys."""
    result: Inventory = {}
    schemas: dict[str, Any] = {}
    for store, tables in (("candidates", TABLES), ("jobs", JOB_TABLES)):
        with closing(_connect(root / f"{store}.db", deadline)) as con:
            schemas[store] = _schema(con)
            existing = {
                row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            for table in tables:
                values: dict[str, str] = {}
                result[f"{store}.{table}"] = values
                if table not in existing:
                    continue
                columns = list(con.execute(f'PRAGMA table_info("{table}")'))
                keys = [r[1] for r in sorted(columns, key=lambda r: r[5]) if r[5]]
                _require(bool(keys), "ADOPTION_SCHEMA_UNSUPPORTED")
                for row in con.execute(f'SELECT * FROM "{table}"'):
                    _check_time(deadline)
                    key = sha256_fingerprint({k: row[k] for k in keys})
                    _require(key not in values, "ADOPTION_DUPLICATE_KEY")
                    values[key] = sha256_fingerprint(dict(row))
    # Canonical JSON sorts mapping keys, making SELECT row order irrelevant.
    _check_time(deadline)
    canonical_json(result)
    return result, sha256_fingerprint(schemas)
