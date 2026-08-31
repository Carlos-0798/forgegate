from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import forgegate.candidates.store as candidate_store_module
from forgegate.candidates import (
    CandidateLifecycleError,
    CandidateStoreError,
    ReleaseCandidate,
    SQLiteCandidateRepository,
    create_candidate,
    transition_candidate,
)
from forgegate.candidates.store import (
    LEGACY_STORE_SCHEMA_NAME,
    LEGACY_STORE_SCHEMA_VERSION,
    STORE_APPLICATION_ID,
    STORE_SCHEMA_VERSION,
)
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.enums import Aggregation, CandidateStatus, Decision, Operator
from forgegate.policy.models import PolicyEvaluation, RuleEvaluation

CREATED = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
COMMIT = "a" * 40


def draft(**updates: Any) -> ReleaseCandidate:
    values: dict[str, Any] = {
        "project_id": "sample-api",
        "version": "1.2.0",
        "commit_sha": COMMIT,
        "source_branch": "main",
        "release_track": "pull-request",
        "created_at": CREATED,
    }
    values.update(updates)
    return create_candidate(**values)


def evaluation(decision: Decision, evaluated_at: datetime) -> PolicyEvaluation:
    policy_fingerprint = "sha256:" + "2" * 64
    evidence_fingerprint = "sha256:" + "3" * 64
    return PolicyEvaluation(
        evaluation_id=sha256_fingerprint(
            {
                "policy_fingerprint": policy_fingerprint,
                "evidence_fingerprint": evidence_fingerprint,
                "evaluated_at": evaluated_at.isoformat(),
            }
        ),
        policy_name="pull-request",
        policy_fingerprint=policy_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
        candidate_commit=COMMIT,
        evaluated_at=evaluated_at,
        decision=decision,
        rule_results=[
            RuleEvaluation(
                rule_id="rule-01",
                claim="tests.required-pass",
                decision=decision,
                mandatory=True,
                evidence_kind="test.summary",
                aggregation=Aggregation.VALUE,
                operator=Operator.EQUALS,
                expected=0,
                actual=0,
                evidence_ids=["evidence-01"],
                reason_code="RULE_RESULT",
                explanation="deterministic store fixture",
            )
        ],
        evaluated_evidence_ids=["evidence-01"],
    )


def initialized_repository(tmp_path: Path) -> SQLiteCandidateRepository:
    tmp_path.mkdir(parents=True, exist_ok=True)
    repository = SQLiteCandidateRepository(tmp_path / "forgegate.db")
    repository.initialize()
    return repository


def create_in(repository: SQLiteCandidateRepository) -> ReleaseCandidate:
    candidate = draft()
    return repository.create(candidate, idempotency_key="create:sample-001")


def advance_to_evaluating(repository: SQLiteCandidateRepository) -> ReleaseCandidate:
    candidate = create_in(repository)
    for index, status in enumerate(
        (CandidateStatus.COLLECTING, CandidateStatus.READY, CandidateStatus.EVALUATING),
        start=1,
    ):
        candidate = repository.advance(
            candidate.candidate_id,
            status,
            expected_revision=candidate.revision,
            occurred_at=CREATED + timedelta(minutes=index),
            idempotency_key=f"advance:sample-{index:03d}",
        ).candidate
    return candidate


def advance_to_pass(
    repository: SQLiteCandidateRepository,
) -> tuple[ReleaseCandidate, PolicyEvaluation]:
    candidate = advance_to_evaluating(repository)
    evaluated_at = CREATED + timedelta(minutes=4)
    policy_result = evaluation(Decision.PASS, evaluated_at)
    result = repository.advance(
        candidate.candidate_id,
        CandidateStatus.PASS,
        expected_revision=3,
        occurred_at=evaluated_at,
        idempotency_key="advance:terminal-01",
        reason="policy passed",
        evaluation=policy_result,
    )
    return result.candidate, policy_result


def _downgrade_to_schema_v1(database: Path) -> None:
    """Turn a current fixture into an exact legacy schema without its new documents."""
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE attestations")
        connection.execute("DROP TABLE candidate_evaluations")
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_name'",
            (LEGACY_STORE_SCHEMA_NAME,),
        )
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_version'",
            (str(LEGACY_STORE_SCHEMA_VERSION),),
        )
        connection.execute(f"PRAGMA user_version = {LEGACY_STORE_SCHEMA_VERSION}")


def _rewrite_with_trigger_restored(
    database: Path,
    trigger_name: str,
    statement: str,
    parameters: tuple[object, ...] = (),
) -> None:
    with sqlite3.connect(database) as connection:
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
            (trigger_name,),
        ).fetchone()[0]
        connection.execute(f'DROP TRIGGER "{trigger_name}"')
        connection.execute(statement, parameters)
        connection.execute(trigger_sql)


def test_initialize_is_repeatable_and_marks_wal_schema(tmp_path: Path) -> None:
    database = tmp_path / "forgegate.db"
    repository = SQLiteCandidateRepository(database)
    repository.initialize()
    repository.initialize()

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA application_id").fetchone()[0] == STORE_APPLICATION_ID
        assert connection.execute("PRAGMA user_version").fetchone()[0] == STORE_SCHEMA_VERSION
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    with pytest.raises(CandidateStoreError, match="STORE_CANDIDATE_NOT_FOUND"):
        repository.get("cand-" + "0" * 24)


def test_create_replay_restart_and_history(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = draft()

    stored = repository.create(candidate, idempotency_key="create:sample-001")
    replay = repository.create(candidate, idempotency_key="create:sample-001")
    second_key = repository.create(candidate, idempotency_key="create:sample-002")
    reopened = SQLiteCandidateRepository(repository.database_path)

    assert stored == replay == second_key == candidate
    assert reopened.get(candidate.candidate_id) == candidate
    assert reopened.history(candidate.candidate_id).transitions == ()

    with sqlite3.connect(repository.database_path) as connection:
        payload = connection.execute(
            "SELECT current_candidate_json FROM candidates WHERE candidate_id = ?",
            (candidate.candidate_id,),
        ).fetchone()[0]
        assert payload == json.dumps(json.loads(payload), sort_keys=True, separators=(",", ":"))


def test_create_rejects_conflicts_non_drafts_and_bad_keys(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = create_in(repository)
    other = draft(created_at=CREATED + timedelta(seconds=1))
    conflicting_values = candidate.model_dump(mode="python")
    conflicting_values["version"] = "9.9.9"
    colliding = ReleaseCandidate.model_validate(conflicting_values)
    collecting = transition_candidate(
        candidate,
        CandidateStatus.COLLECTING,
        occurred_at=CREATED + timedelta(minutes=1),
    ).candidate

    with pytest.raises(CandidateStoreError, match="STORE_IDEMPOTENCY_CONFLICT"):
        repository.create(other, idempotency_key="create:sample-001")
    with pytest.raises(CandidateStoreError, match="STORE_CANDIDATE_CONFLICT"):
        repository.create(colliding, idempotency_key="create:collision-01")
    with pytest.raises(CandidateStoreError, match="STORE_CANDIDATE_NOT_DRAFT"):
        repository.create(collecting, idempotency_key="create:collecting-1")
    with pytest.raises(CandidateStoreError, match="STORE_IDEMPOTENCY_KEY_INVALID"):
        repository.create(other, idempotency_key="short")


def test_advance_compare_and_swap_replay_and_restart(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = create_in(repository)
    offset_time = (CREATED + timedelta(minutes=1)).astimezone(timezone(timedelta(hours=-4)))

    first = repository.advance(
        candidate.candidate_id,
        CandidateStatus.COLLECTING,
        expected_revision=0,
        occurred_at=offset_time,
        idempotency_key="advance:collect-001",
        reason="  begin collection  ",
    )
    replay = repository.advance(
        candidate.candidate_id,
        CandidateStatus.COLLECTING,
        expected_revision=0,
        occurred_at=offset_time,
        idempotency_key="advance:collect-001",
        reason="begin collection",
    )
    second = repository.advance(
        candidate.candidate_id,
        CandidateStatus.READY,
        expected_revision=1,
        occurred_at=CREATED + timedelta(minutes=2),
        idempotency_key="advance:ready-0001",
    )
    late_replay = repository.advance(
        candidate.candidate_id,
        CandidateStatus.COLLECTING,
        expected_revision=0,
        occurred_at=offset_time,
        idempotency_key="advance:collect-001",
        reason="begin collection",
    )

    assert first == replay == late_replay
    assert second.candidate.revision == 2
    reopened = SQLiteCandidateRepository(repository.database_path)
    history = reopened.history(candidate.candidate_id)
    assert history.candidate == second.candidate
    assert history.transitions == (first.transition, second.transition)

    with pytest.raises(CandidateStoreError, match="STORE_REVISION_CONFLICT"):
        repository.advance(
            candidate.candidate_id,
            CandidateStatus.READY,
            expected_revision=0,
            occurred_at=CREATED + timedelta(minutes=2),
            idempotency_key="advance:stale-0001",
        )
    with pytest.raises(CandidateStoreError, match="STORE_IDEMPOTENCY_CONFLICT"):
        repository.advance(
            candidate.candidate_id,
            CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=offset_time,
            idempotency_key="advance:collect-001",
            reason="different request",
        )


def test_advance_rejects_invalid_revision_time_and_reason(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = create_in(repository)

    with pytest.raises(CandidateStoreError, match="STORE_REVISION_INVALID"):
        repository.advance(
            candidate.candidate_id,
            CandidateStatus.COLLECTING,
            expected_revision=-1,
            occurred_at=CREATED,
            idempotency_key="advance:negative-01",
        )
    with pytest.raises(CandidateStoreError, match="STORE_IDEMPOTENCY_KEY_INVALID"):
        repository.advance(
            candidate.candidate_id,
            CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=CREATED,
            idempotency_key="bad",
        )
    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_TIMESTAMP_NAIVE"):
        repository.advance(
            candidate.candidate_id,
            CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=datetime(2026, 8, 31, 12, 1),
            idempotency_key="advance:naive-0001",
        )
    with pytest.raises(CandidateLifecycleError, match="CANDIDATE_REASON_EMPTY"):
        repository.advance(
            candidate.candidate_id,
            CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=CREATED + timedelta(minutes=1),
            idempotency_key="advance:blank-0001",
            reason=" ",
        )


def test_terminal_evaluation_is_durably_bound(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = advance_to_evaluating(repository)
    evaluated_at = CREATED + timedelta(minutes=4)
    policy_result = evaluation(Decision.PASS, evaluated_at)

    result = repository.advance(
        candidate.candidate_id,
        CandidateStatus.PASS,
        expected_revision=3,
        occurred_at=evaluated_at,
        idempotency_key="advance:terminal-01",
        reason="policy passed",
        evaluation=policy_result,
    )
    history = SQLiteCandidateRepository(repository.database_path).history(candidate.candidate_id)

    assert result.candidate.status is CandidateStatus.PASS
    assert history.candidate.evaluation_id == policy_result.evaluation_id
    assert history.transitions[-1].evaluation_id == policy_result.evaluation_id
    assert repository.evaluation(candidate.candidate_id) == policy_result


def test_schema_v1_requires_explicit_migration_and_evaluation_backfill(
    tmp_path: Path,
) -> None:
    repository = initialized_repository(tmp_path)
    candidate, policy_result = advance_to_pass(repository)
    _downgrade_to_schema_v1(repository.database_path)

    legacy = SQLiteCandidateRepository(repository.database_path)
    with pytest.raises(CandidateStoreError, match="STORE_MIGRATION_REQUIRED"):
        legacy.initialize()

    legacy.migrate()
    legacy.migrate()
    assert legacy.get(candidate.candidate_id) == candidate
    with pytest.raises(CandidateStoreError, match="STORE_EVALUATION_NOT_FOUND"):
        legacy.evaluation(candidate.candidate_id)

    assert legacy.record_evaluation(candidate.candidate_id, policy_result) == policy_result
    assert legacy.record_evaluation(candidate.candidate_id, policy_result) == policy_result
    assert legacy.evaluation(candidate.candidate_id) == policy_result

    conflicting = policy_result.model_copy(update={"policy_name": "different-policy"})
    with pytest.raises(CandidateStoreError, match="STORE_EVALUATION_CONFLICT"):
        legacy.record_evaluation(candidate.candidate_id, conflicting)


def test_migration_rejects_invalid_legacy_and_unknown_schemas(tmp_path: Path) -> None:
    invalid_legacy = initialized_repository(tmp_path / "legacy")
    _downgrade_to_schema_v1(invalid_legacy.database_path)
    with sqlite3.connect(invalid_legacy.database_path) as connection:
        connection.execute("DROP TRIGGER candidate_snapshots_guard_update")
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        invalid_legacy.migrate()

    future_root = tmp_path / "future"
    future_root.mkdir()
    future = initialized_repository(future_root)
    with sqlite3.connect(future.database_path) as connection:
        connection.execute(f"PRAGMA user_version = {STORE_SCHEMA_VERSION + 1}")
    with pytest.raises(CandidateStoreError, match="STORE_SCHEMA_UNSUPPORTED"):
        future.migrate()


def test_evaluation_backfill_rejects_nonterminal_or_mismatched_inputs(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = create_in(repository)
    assert repository.evaluation(candidate.candidate_id) is None
    with pytest.raises(CandidateStoreError, match="STORE_EVALUATION_UNEXPECTED"):
        repository.record_evaluation(
            candidate.candidate_id,
            evaluation(Decision.PASS, CREATED + timedelta(minutes=4)),
        )

    terminal, policy_result = advance_to_pass(initialized_repository(tmp_path / "mismatch"))
    mismatch_repository = SQLiteCandidateRepository(tmp_path / "mismatch" / "forgegate.db")
    mismatched = policy_result.model_copy(update={"candidate_commit": "b" * 40})
    with pytest.raises(CandidateStoreError, match="STORE_EVALUATION_MISMATCH"):
        mismatch_repository.record_evaluation(terminal.candidate_id, mismatched)


def test_attestation_is_durable_replayable_and_content_bound(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate, policy_result = advance_to_pass(repository)
    issued_at = candidate.updated_at + timedelta(minutes=1)

    first = repository.attest(
        candidate.candidate_id,
        issued_at=issued_at,
        generator_version="0.1.0.dev8",
    )
    replay = repository.attest(
        candidate.candidate_id,
        issued_at=issued_at,
        generator_version="0.1.0.dev8",
    )
    reopened = SQLiteCandidateRepository(repository.database_path)

    assert first == replay == reopened.get_attestation(candidate.candidate_id)
    assert first.policy_evaluation == policy_result
    with sqlite3.connect(repository.database_path) as connection:
        row = connection.execute(
            "SELECT attestation_json, markdown_text FROM attestations"
        ).fetchone()
    assert row is not None
    assert row[0] == json.dumps(json.loads(row[0]), sort_keys=True, separators=(",", ":"))
    assert "unsigned local ForgeGate record" in row[1]

    with pytest.raises(CandidateStoreError, match="STORE_ATTESTATION_CONFLICT"):
        repository.attest(
            candidate.candidate_id,
            issued_at=issued_at + timedelta(seconds=1),
            generator_version="0.1.0.dev8",
        )


def test_attestation_rejects_nonterminal_and_reports_missing_record(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = create_in(repository)
    with pytest.raises(CandidateStoreError, match="STORE_ATTESTATION_NOT_FOUND"):
        repository.get_attestation(candidate.candidate_id)
    with pytest.raises(CandidateStoreError, match="STORE_ATTESTATION_INVALID"):
        repository.attest(
            candidate.candidate_id,
            issued_at=CREATED + timedelta(minutes=1),
            generator_version="0.1.0.dev8",
        )


def test_evaluation_and_attestation_failure_injection_rolls_back(tmp_path: Path) -> None:
    healthy = initialized_repository(tmp_path)
    evaluating = advance_to_evaluating(healthy)
    policy_result = evaluation(Decision.PASS, CREATED + timedelta(minutes=4))

    def fail_evaluation(name: str, _connection: sqlite3.Connection) -> None:
        if name == "after_transition_append":
            raise RuntimeError("injected terminal failure")

    failing_terminal = SQLiteCandidateRepository(
        healthy.database_path, _failure_injector=fail_evaluation
    )
    with pytest.raises(RuntimeError, match="injected terminal failure"):
        failing_terminal.advance(
            evaluating.candidate_id,
            CandidateStatus.PASS,
            expected_revision=3,
            occurred_at=CREATED + timedelta(minutes=4),
            idempotency_key="advance:terminal-rollback",
            evaluation=policy_result,
        )
    assert healthy.get(evaluating.candidate_id) == evaluating
    assert healthy.evaluation(evaluating.candidate_id) is None

    terminal = healthy.advance(
        evaluating.candidate_id,
        CandidateStatus.PASS,
        expected_revision=3,
        occurred_at=CREATED + timedelta(minutes=4),
        idempotency_key="advance:terminal-recovered",
        evaluation=policy_result,
    ).candidate

    def fail_attestation(name: str, _connection: sqlite3.Connection) -> None:
        if name == "after_attestation_insert":
            raise RuntimeError("injected attestation failure")

    failing_attestation = SQLiteCandidateRepository(
        healthy.database_path, _failure_injector=fail_attestation
    )
    with pytest.raises(RuntimeError, match="injected attestation failure"):
        failing_attestation.attest(
            terminal.candidate_id,
            issued_at=terminal.updated_at + timedelta(minutes=1),
            generator_version="0.1.0.dev8",
        )
    with pytest.raises(CandidateStoreError, match="STORE_ATTESTATION_NOT_FOUND"):
        healthy.get_attestation(terminal.candidate_id)


def test_corrupt_evaluation_and_attestation_documents_are_rejected(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate, _ = advance_to_pass(repository)
    repository.attest(
        candidate.candidate_id,
        issued_at=candidate.updated_at + timedelta(minutes=1),
        generator_version="0.1.0.dev8",
    )
    _rewrite_with_trigger_restored(
        repository.database_path,
        "attestations_guard_update",
        "UPDATE attestations SET markdown_text = 'detached'",
    )
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        repository.get_attestation(candidate.candidate_id)

    evaluation_root = tmp_path / "evaluation-corrupt"
    evaluation_root.mkdir()
    evaluation_repository = initialized_repository(evaluation_root)
    evaluation_candidate, _ = advance_to_pass(evaluation_repository)
    _rewrite_with_trigger_restored(
        evaluation_repository.database_path,
        "candidate_evaluations_guard_update",
        "UPDATE candidate_evaluations SET evaluation_json = '{}'",
    )
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        evaluation_repository.evaluation(evaluation_candidate.candidate_id)


@pytest.mark.parametrize("checkpoint", ["after_candidate_insert", "after_idempotency_insert"])
def test_create_failure_injection_rolls_back(tmp_path: Path, checkpoint: str) -> None:
    database = tmp_path / "forgegate.db"
    SQLiteCandidateRepository(database).initialize()

    def fail(name: str, _connection: sqlite3.Connection) -> None:
        if name == checkpoint:
            raise RuntimeError("injected create failure")

    repository = SQLiteCandidateRepository(database, _failure_injector=fail)
    candidate = draft()
    with pytest.raises(RuntimeError, match="injected create failure"):
        repository.create(candidate, idempotency_key="create:rollback-01")

    healthy = SQLiteCandidateRepository(database)
    with pytest.raises(CandidateStoreError, match="STORE_CANDIDATE_NOT_FOUND"):
        healthy.get(candidate.candidate_id)
    assert healthy.create(candidate, idempotency_key="create:rollback-01") == candidate


@pytest.mark.parametrize(
    "checkpoint",
    ["after_transition_append", "after_current_update", "after_idempotency_insert"],
)
def test_advance_failure_injection_rolls_back(tmp_path: Path, checkpoint: str) -> None:
    healthy = initialized_repository(tmp_path)
    candidate = create_in(healthy)

    def fail(name: str, _connection: sqlite3.Connection) -> None:
        if name == checkpoint:
            raise RuntimeError("injected advance failure")

    failing = SQLiteCandidateRepository(healthy.database_path, _failure_injector=fail)
    with pytest.raises(RuntimeError, match="injected advance failure"):
        failing.advance(
            candidate.candidate_id,
            CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=CREATED + timedelta(minutes=1),
            idempotency_key="advance:rollback-01",
        )

    assert healthy.history(candidate.candidate_id).transitions == ()
    recovered = healthy.advance(
        candidate.candidate_id,
        CandidateStatus.COLLECTING,
        expected_revision=0,
        occurred_at=CREATED + timedelta(minutes=1),
        idempotency_key="advance:rollback-01",
    )
    assert recovered.candidate.revision == 1


def test_compare_and_swap_defense_rolls_back_on_zero_row_update(tmp_path: Path) -> None:
    healthy = initialized_repository(tmp_path)
    candidate = create_in(healthy)

    def move_pointer(name: str, connection: sqlite3.Connection) -> None:
        if name == "after_transition_append":
            connection.execute(
                "UPDATE candidates SET current_revision = 1 WHERE candidate_id = ?",
                (candidate.candidate_id,),
            )

    repository = SQLiteCandidateRepository(healthy.database_path, _failure_injector=move_pointer)
    with pytest.raises(CandidateStoreError, match="STORE_REVISION_CONFLICT"):
        repository.advance(
            candidate.candidate_id,
            CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=CREATED + timedelta(minutes=1),
            idempotency_key="advance:cas-defense",
        )
    assert healthy.get(candidate.candidate_id).revision == 0


def test_writer_lock_reports_busy_without_partial_write(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = draft()
    lock = sqlite3.connect(repository.database_path, isolation_level=None)
    try:
        lock.execute("BEGIN IMMEDIATE")
        impatient = SQLiteCandidateRepository(repository.database_path, timeout_seconds=0)
        with pytest.raises(CandidateStoreError, match="STORE_BUSY"):
            impatient.create(candidate, idempotency_key="create:busy-000001")
    finally:
        lock.rollback()
        lock.close()
    assert repository.create(candidate, idempotency_key="create:busy-000001") == candidate


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE candidates SET project_id = 'other-api'",
        "DELETE FROM candidates",
        "UPDATE candidate_snapshots SET status = 'READY'",
        "DELETE FROM candidate_snapshots",
        "UPDATE candidate_transitions SET occurred_at = '2026-08-31T00:00:00Z'",
        "DELETE FROM candidate_transitions",
        "UPDATE idempotency_records SET recorded_at = '2026-08-31T00:00:00Z'",
        "DELETE FROM idempotency_records",
    ],
)
def test_database_triggers_enforce_append_only_records(tmp_path: Path, statement: str) -> None:
    repository = initialized_repository(tmp_path)
    candidate = create_in(repository)
    repository.advance(
        candidate.candidate_id,
        CandidateStatus.COLLECTING,
        expected_revision=0,
        occurred_at=CREATED + timedelta(minutes=1),
        idempotency_key="advance:trigger-001",
    )
    with (
        sqlite3.connect(repository.database_path) as connection,
        pytest.raises(sqlite3.IntegrityError),
    ):
        connection.execute(statement)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE candidate_evaluations SET recorded_at = '2026-08-31T00:00:00Z'",
        "DELETE FROM candidate_evaluations",
        "UPDATE attestations SET issued_at = '2026-08-31T00:00:00Z'",
        "DELETE FROM attestations",
    ],
)
def test_v2_database_triggers_enforce_append_only_records(tmp_path: Path, statement: str) -> None:
    repository = initialized_repository(tmp_path)
    candidate, _ = advance_to_pass(repository)
    repository.attest(
        candidate.candidate_id,
        issued_at=candidate.updated_at + timedelta(minutes=1),
        generator_version="0.1.0.dev8",
    )
    with (
        sqlite3.connect(repository.database_path) as connection,
        pytest.raises(sqlite3.IntegrityError),
    ):
        connection.execute(statement)


def test_repository_path_and_initialization_errors(tmp_path: Path) -> None:
    missing = SQLiteCandidateRepository(tmp_path / "missing.db")
    with pytest.raises(CandidateStoreError, match="STORE_NOT_INITIALIZED"):
        missing.history("cand-" + "0" * 24)
    with pytest.raises(CandidateStoreError, match="STORE_PARENT_MISSING"):
        SQLiteCandidateRepository(tmp_path / "missing-parent" / "store.db").initialize()
    directory = tmp_path / "directory.db"
    directory.mkdir()
    with pytest.raises(CandidateStoreError, match="STORE_PATH_INVALID"):
        SQLiteCandidateRepository(directory).initialize()
    with pytest.raises(ValueError, match="timeout_seconds"):
        SQLiteCandidateRepository(tmp_path / "invalid.db", timeout_seconds=-0.1)


def test_foreign_and_future_databases_are_rejected(tmp_path: Path) -> None:
    foreign = tmp_path / "foreign.db"
    with sqlite3.connect(foreign) as connection:
        connection.execute("CREATE TABLE unrelated(value TEXT)")
    with pytest.raises(CandidateStoreError, match="STORE_NOT_FORGEGATE"):
        SQLiteCandidateRepository(foreign).initialize()

    foreign_id = tmp_path / "foreign-id.db"
    with sqlite3.connect(foreign_id) as connection:
        connection.execute("PRAGMA application_id = 1234")
    with pytest.raises(CandidateStoreError, match="STORE_NOT_FORGEGATE"):
        SQLiteCandidateRepository(foreign_id).initialize()

    foreign_current_root = tmp_path / "foreign-current"
    foreign_current = initialized_repository(foreign_current_root)
    with sqlite3.connect(foreign_current.database_path) as connection:
        connection.execute("PRAGMA application_id = 1234")
    with pytest.raises(CandidateStoreError, match="STORE_NOT_FORGEGATE"):
        foreign_current.initialize()

    repository = SQLiteCandidateRepository(tmp_path / "future.db")
    repository.initialize()
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(f"PRAGMA user_version = {STORE_SCHEMA_VERSION + 1}")
    with pytest.raises(CandidateStoreError, match="STORE_SCHEMA_UNSUPPORTED"):
        repository.initialize()


@pytest.mark.parametrize("corruption", ["application", "metadata", "trigger", "journal"])
def test_store_header_and_schema_corruption_is_detected(tmp_path: Path, corruption: str) -> None:
    repository = initialized_repository(tmp_path)
    with sqlite3.connect(repository.database_path) as connection:
        if corruption == "application":
            connection.execute("PRAGMA application_id = 1234")
        elif corruption == "metadata":
            connection.execute(
                "UPDATE forgegate_metadata SET value = 'wrong' WHERE key = 'schema_name'"
            )
        elif corruption == "trigger":
            connection.execute("DROP TRIGGER candidate_snapshots_guard_update")
        else:
            connection.execute("PRAGMA journal_mode = DELETE")
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        repository.get("cand-" + "0" * 24)


def test_foreign_key_corruption_is_detected(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """
            INSERT INTO candidate_snapshots(
                candidate_id, revision, status, candidate_fingerprint,
                candidate_json, recorded_at
            ) VALUES (?, 0, 'DRAFT', ?, '{}', ?)
            """,
            ("cand-" + "0" * 24, "sha256:" + "0" * 64, "2026-08-31T00:00:00Z"),
        )
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        repository.get("cand-" + "0" * 24)


@pytest.mark.parametrize("payload_kind", ["invalid", "noncanonical"])
def test_stored_snapshot_document_corruption_is_detected(tmp_path: Path, payload_kind: str) -> None:
    repository = initialized_repository(tmp_path)
    candidate = create_in(repository)
    if payload_kind == "invalid":
        payload = "{}"
    else:
        payload = json.dumps(candidate.model_dump(mode="json"), indent=2)
    _rewrite_with_trigger_restored(
        repository.database_path,
        "candidate_snapshots_guard_update",
        "UPDATE candidate_snapshots SET candidate_json = ?",
        (payload,),
    )
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        repository.get(candidate.candidate_id)


def test_current_pointer_corruption_is_detected(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = create_in(repository)
    _rewrite_with_trigger_restored(
        repository.database_path,
        "candidates_guard_update",
        "UPDATE candidates SET current_status = 'COLLECTING'",
    )
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        repository.get(candidate.candidate_id)


def test_idempotency_response_corruption_is_detected(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = create_in(repository)
    _rewrite_with_trigger_restored(
        repository.database_path,
        "idempotency_records_guard_update",
        "UPDATE idempotency_records SET response_json = '{}'",
    )
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        repository.create(candidate, idempotency_key="create:sample-001")


def test_create_replay_revalidates_the_complete_history(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = create_in(repository)
    _rewrite_with_trigger_restored(
        repository.database_path,
        "candidate_snapshots_guard_update",
        "UPDATE candidate_snapshots SET status = 'READY'",
    )
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        repository.create(candidate, idempotency_key="create:sample-001")


def test_transition_replay_revalidates_the_complete_history(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = create_in(repository)
    repository.advance(
        candidate.candidate_id,
        CandidateStatus.COLLECTING,
        expected_revision=0,
        occurred_at=CREATED + timedelta(minutes=1),
        idempotency_key="advance:revalidate-01",
    )
    _rewrite_with_trigger_restored(
        repository.database_path,
        "candidate_transitions_guard_update",
        "UPDATE candidate_transitions SET occurred_at = '2026-08-31T00:00:00Z'",
    )
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        repository.advance(
            candidate.candidate_id,
            CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=CREATED + timedelta(minutes=1),
            idempotency_key="advance:revalidate-01",
        )


def test_invalid_sqlite_file_and_connect_failure_are_translated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalid = tmp_path / "invalid.db"
    invalid.write_bytes(b"not a sqlite database")
    with pytest.raises(CandidateStoreError, match="STORE_DATABASE_ERROR"):
        SQLiteCandidateRepository(invalid).initialize()

    def fail_connect(*_args: object, **_kwargs: object) -> sqlite3.Connection:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(sqlite3, "connect", fail_connect)
    with pytest.raises(CandidateStoreError, match="STORE_BUSY"):
        SQLiteCandidateRepository(tmp_path / "connect.db").initialize()


def test_connection_configuration_failure_is_translated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenConnection:
        row_factory: object = None
        closed = False

        def execute(self, _statement: str) -> None:
            raise sqlite3.DatabaseError("configuration failed")

        def close(self) -> None:
            self.closed = True

    broken = BrokenConnection()

    def broken_connect(*_args: object, **_kwargs: object) -> Any:
        return broken

    monkeypatch.setattr(sqlite3, "connect", broken_connect)
    with pytest.raises(CandidateStoreError, match="STORE_DATABASE_ERROR"):
        SQLiteCandidateRepository(tmp_path / "configuration.db").initialize()
    assert broken.closed is True


def test_schema_creation_sqlite_failure_is_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "schema-failure.db"
    monkeypatch.setattr(candidate_store_module, "_SCHEMA_V1_STATEMENTS", ("INVALID SQL",))
    with pytest.raises(CandidateStoreError, match="STORE_DATABASE_ERROR"):
        SQLiteCandidateRepository(database).initialize()
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            == []
        )


def test_schema_migration_sqlite_failure_is_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = initialized_repository(tmp_path)
    _downgrade_to_schema_v1(repository.database_path)
    monkeypatch.setattr(
        candidate_store_module,
        "_SCHEMA_V2_STATEMENTS",
        (candidate_store_module._SCHEMA_V2_STATEMENTS[0], "INVALID SQL"),
    )
    with pytest.raises(CandidateStoreError, match="STORE_DATABASE_ERROR"):
        repository.migrate()
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name IN ('candidate_evaluations', 'attestations')"
            ).fetchall()
            == []
        )
