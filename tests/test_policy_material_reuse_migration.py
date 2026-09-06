"""Regression for shared policy content across independent candidate bindings."""

import sqlite3
from datetime import UTC, datetime

import pytest

from forgegate.application import CandidateEvaluateCommand
from forgegate.candidates import CandidateStoreError, SQLiteCandidateRepository
from forgegate.candidates import store as store_module
from tests.test_policy_materialization import _advance_to_evaluating, _application


def _legacy_store(tmp_path, repository_root):
    application, cid = _application(tmp_path, repository_root)
    _advance_to_evaluating(application, cid, repository_root)
    material = application.materialize_policy(cid, repository_root / "examples/sample-python-api")
    application.evaluate_candidate(
        cid,
        CandidateEvaluateCommand(
            policy_material=material,
            expected_revision=3,
            evaluated_at=datetime(2026, 8, 30, 21, tzinfo=UTC),
        ),
        idempotency_key="migration:original-evaluate",
    )
    database = tmp_path / "forgegate.db"
    # Reconstruct the exact historical table, including its faulty uniqueness.
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER candidate_policy_materials_guard_update")
        connection.execute("DROP TRIGGER candidate_policy_materials_guard_delete")
        connection.execute("ALTER TABLE candidate_policy_materials RENAME TO saved_materials")
        connection.execute(store_module._SCHEMA_V7_STATEMENTS[1])
        connection.execute("INSERT INTO candidate_policy_materials SELECT * FROM saved_materials")
        connection.execute("DROP TABLE saved_materials")
        for statement in store_module._SCHEMA_V7_STATEMENTS[3:]:
            connection.execute(statement)
        connection.execute("UPDATE forgegate_metadata SET value='8' WHERE key='schema_version'")
        connection.execute(
            "UPDATE forgegate_metadata SET value='forgegate.candidate-store.v8' "
            "WHERE key='schema_name'"
        )
        connection.execute("PRAGMA user_version=8")
    return database, cid


def _snapshot(database):
    with sqlite3.connect(database) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {
            name: connection.execute(f'SELECT * FROM "{name}" ORDER BY 1').fetchall()
            for (name,) in tables
        }


def test_v8_requires_explicit_migration_and_preserves_all_retained_rows(tmp_path, repository_root):
    database, cid = _legacy_store(tmp_path, repository_root)
    repository = SQLiteCandidateRepository(database)
    before = _snapshot(database)
    with pytest.raises(CandidateStoreError, match="STORE_MIGRATION_REQUIRED"):
        repository.initialize()
    repository.migrate()
    repository.migrate()  # No duplicate write on an already-current store.
    after = _snapshot(database)
    before.pop("forgegate_metadata")
    after.pop("forgegate_metadata")
    assert before == after
    assert repository.history(cid).policy_material is not None
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 9
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='candidate_policy_materials'"
        ).fetchone()[0]
        assert "material_id TEXT NOT NULL UNIQUE" not in sql
        for query in (
            "UPDATE candidate_policy_materials SET bound_at=bound_at",
            "DELETE FROM candidate_policy_materials",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(query)
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            connection.execute(
                "INSERT INTO candidate_policy_materials SELECT * FROM candidate_policy_materials"
            )


@pytest.mark.parametrize("cut", [3, 5, 7])
def test_v8_migration_failure_rolls_back_table_rows_and_guards(
    tmp_path, repository_root, monkeypatch, cut
):
    database, _ = _legacy_store(tmp_path, repository_root)
    before = _snapshot(database)
    with sqlite3.connect(database) as connection:
        schema = connection.execute(
            "SELECT type,name,sql FROM sqlite_master ORDER BY name"
        ).fetchall()
    monkeypatch.setattr(
        store_module,
        "_SCHEMA_V9_STATEMENTS",
        (*store_module._SCHEMA_V9_STATEMENTS[:cut], "INVALID SQL"),
    )
    with pytest.raises(CandidateStoreError, match="STORE_DATABASE_ERROR"):
        SQLiteCandidateRepository(database).migrate()
    assert _snapshot(database) == before
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 8
        assert (
            connection.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall()
            == schema
        )
