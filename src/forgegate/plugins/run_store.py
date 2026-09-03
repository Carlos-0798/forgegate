from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from forgegate.canonical import canonical_json
from forgegate.plugins.execution_models import (
    PluginRunPlan,
    PluginRunReceipt,
    PluginRunTransition,
)

PLUGIN_RUN_STORE_APPLICATION_ID = 0x46475052
PLUGIN_RUN_STORE_SCHEMA_VERSION = 1
IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


class PluginRunStoreError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class PluginRunSnapshot:
    plan: PluginRunPlan
    transitions: tuple[PluginRunTransition, ...]
    receipt: PluginRunReceipt | None


@dataclass(frozen=True, slots=True)
class PluginRunReservation:
    snapshot: PluginRunSnapshot
    created: bool


SCHEMA = """
CREATE TABLE forgegate_plugin_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE plugin_run_plans (
    run_plan_id TEXT PRIMARY KEY,
    plan_json TEXT NOT NULL
);
CREATE TABLE plugin_run_idempotency (
    idempotency_key TEXT PRIMARY KEY,
    run_plan_id TEXT NOT NULL REFERENCES plugin_run_plans(run_plan_id)
);
CREATE TABLE plugin_run_transitions (
    run_plan_id TEXT NOT NULL REFERENCES plugin_run_plans(run_plan_id),
    sequence INTEGER NOT NULL,
    transition_id TEXT NOT NULL UNIQUE,
    transition_json TEXT NOT NULL,
    PRIMARY KEY (run_plan_id, sequence)
);
CREATE TABLE plugin_run_receipts (
    run_plan_id TEXT PRIMARY KEY REFERENCES plugin_run_plans(run_plan_id),
    receipt_id TEXT NOT NULL UNIQUE,
    receipt_json TEXT NOT NULL
);
CREATE TRIGGER plugin_run_plans_no_update BEFORE UPDATE ON plugin_run_plans
BEGIN SELECT RAISE(ABORT, 'plugin run plans are append-only'); END;
CREATE TRIGGER plugin_run_plans_no_delete BEFORE DELETE ON plugin_run_plans
BEGIN SELECT RAISE(ABORT, 'plugin run plans are append-only'); END;
CREATE TRIGGER plugin_run_idempotency_no_update BEFORE UPDATE ON plugin_run_idempotency
BEGIN SELECT RAISE(ABORT, 'plugin run idempotency is append-only'); END;
CREATE TRIGGER plugin_run_idempotency_no_delete BEFORE DELETE ON plugin_run_idempotency
BEGIN SELECT RAISE(ABORT, 'plugin run idempotency is append-only'); END;
CREATE TRIGGER plugin_run_transitions_no_update BEFORE UPDATE ON plugin_run_transitions
BEGIN SELECT RAISE(ABORT, 'plugin run transitions are append-only'); END;
CREATE TRIGGER plugin_run_transitions_no_delete BEFORE DELETE ON plugin_run_transitions
BEGIN SELECT RAISE(ABORT, 'plugin run transitions are append-only'); END;
CREATE TRIGGER plugin_run_receipts_no_update BEFORE UPDATE ON plugin_run_receipts
BEGIN SELECT RAISE(ABORT, 'plugin run receipts are append-only'); END;
CREATE TRIGGER plugin_run_receipts_no_delete BEFORE DELETE ON plugin_run_receipts
BEGIN SELECT RAISE(ABORT, 'plugin run receipts are append-only'); END;
"""


class SQLitePluginRunRepository:
    """Separate append-only store for external plugin execution records."""

    def __init__(self, database_path: Path) -> None:
        if database_path.is_symlink():
            raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "database path cannot be a symlink")
        parent = database_path.parent
        if not parent.is_dir():
            raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "database parent does not exist")
        self.database_path = database_path.resolve(strict=False)

    def initialize(self) -> None:
        if self.database_path.exists():
            self._validate_store()
            return
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.executescript(SCHEMA)
            connection.execute(
                "INSERT INTO forgegate_plugin_metadata(key, value) VALUES('schema_version', ?)",
                (str(PLUGIN_RUN_STORE_SCHEMA_VERSION),),
            )
            connection.execute(f"PRAGMA application_id = {PLUGIN_RUN_STORE_APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version = {PLUGIN_RUN_STORE_SCHEMA_VERSION}")
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "cannot initialize run store") from exc
        finally:
            connection.close()

    def reserve(
        self,
        plan: PluginRunPlan,
        initial: PluginRunTransition,
        *,
        idempotency_key: str,
    ) -> PluginRunReservation:
        if IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise PluginRunStoreError("PLUGIN_PLAN_INVALID", "idempotency key is invalid")
        if initial.run_plan_id != plan.run_plan_id or initial.sequence != 0:
            raise PluginRunStoreError("PLUGIN_PLAN_INVALID", "initial transition is invalid")
        created = False
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT run_plan_id FROM plugin_run_idempotency WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row is not None and row[0] != plan.run_plan_id:
                raise PluginRunStoreError(
                    "PLUGIN_PLAN_INVALID", "idempotency key is bound to another run plan"
                )
            existing = connection.execute(
                "SELECT plan_json FROM plugin_run_plans WHERE run_plan_id = ?",
                (plan.run_plan_id,),
            ).fetchone()
            plan_json = canonical_json(plan.model_dump(mode="json"))
            if existing is None:
                created = True
                connection.execute(
                    "INSERT INTO plugin_run_plans(run_plan_id, plan_json) VALUES(?, ?)",
                    (plan.run_plan_id, plan_json),
                )
                connection.execute(
                    "INSERT INTO plugin_run_transitions"
                    "(run_plan_id, sequence, transition_id, transition_json) VALUES(?, ?, ?, ?)",
                    (
                        plan.run_plan_id,
                        initial.sequence,
                        initial.transition_id,
                        canonical_json(initial.model_dump(mode="json")),
                    ),
                )
            elif existing[0] != plan_json:
                raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "stored run plan is corrupt")
            if row is None:
                connection.execute(
                    "INSERT INTO plugin_run_idempotency(idempotency_key, run_plan_id) VALUES(?, ?)",
                    (idempotency_key, plan.run_plan_id),
                )
        return PluginRunReservation(snapshot=self.get(plan.run_plan_id), created=created)

    def append_transition(self, transition: PluginRunTransition) -> PluginRunSnapshot:
        with self._transaction() as connection:
            snapshot = self._load_snapshot(connection, transition.run_plan_id)
            if snapshot.receipt is not None:
                raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "plugin run is already terminal")
            previous = snapshot.transitions[-1]
            if (
                transition.sequence != len(snapshot.transitions)
                or transition.previous_transition_id != previous.transition_id
                or transition.from_state is not previous.to_state
            ):
                raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "transition chain is invalid")
            connection.execute(
                "INSERT INTO plugin_run_transitions"
                "(run_plan_id, sequence, transition_id, transition_json) VALUES(?, ?, ?, ?)",
                (
                    transition.run_plan_id,
                    transition.sequence,
                    transition.transition_id,
                    canonical_json(transition.model_dump(mode="json")),
                ),
            )
        return self.get(transition.run_plan_id)

    def complete(self, receipt: PluginRunReceipt) -> PluginRunReceipt:
        plan_id = receipt.result.run_plan.run_plan_id
        terminal = receipt.result.transitions[-1]
        with self._transaction() as connection:
            snapshot = self._load_snapshot(connection, plan_id)
            if snapshot.receipt is not None:
                if snapshot.receipt.receipt_id != receipt.receipt_id:
                    raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "terminal receipt conflicts")
                return snapshot.receipt
            if receipt.result.transitions[:-1] != snapshot.transitions:
                raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "receipt history does not match")
            previous = snapshot.transitions[-1]
            if (
                terminal.sequence != len(snapshot.transitions)
                or terminal.previous_transition_id != previous.transition_id
                or terminal.from_state is not previous.to_state
            ):
                raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "terminal transition is invalid")
            connection.execute(
                "INSERT INTO plugin_run_transitions"
                "(run_plan_id, sequence, transition_id, transition_json) VALUES(?, ?, ?, ?)",
                (
                    plan_id,
                    terminal.sequence,
                    terminal.transition_id,
                    canonical_json(terminal.model_dump(mode="json")),
                ),
            )
            connection.execute(
                "INSERT INTO plugin_run_receipts(run_plan_id, receipt_id, receipt_json)"
                " VALUES(?, ?, ?)",
                (plan_id, receipt.receipt_id, canonical_json(receipt.model_dump(mode="json"))),
            )
        return receipt

    def get(self, run_plan_id: str) -> PluginRunSnapshot:
        connection = self._connect()
        try:
            self._validate_store(connection)
            return self._load_snapshot(connection, run_plan_id)
        finally:
            connection.close()

    def incomplete(self) -> tuple[PluginRunSnapshot, ...]:
        connection = self._connect()
        try:
            self._validate_store(connection)
            rows = connection.execute(
                "SELECT run_plan_id FROM plugin_run_plans WHERE run_plan_id NOT IN "
                "(SELECT run_plan_id FROM plugin_run_receipts) ORDER BY run_plan_id"
            ).fetchall()
            return tuple(self._load_snapshot(connection, row[0]) for row in rows)
        finally:
            connection.close()

    def _load_snapshot(self, connection: sqlite3.Connection, run_plan_id: str) -> PluginRunSnapshot:
        row = connection.execute(
            "SELECT plan_json FROM plugin_run_plans WHERE run_plan_id = ?", (run_plan_id,)
        ).fetchone()
        if row is None:
            raise PluginRunStoreError("PLUGIN_PLAN_INVALID", "plugin run plan was not found")
        transition_rows = connection.execute(
            "SELECT transition_json FROM plugin_run_transitions WHERE run_plan_id = ?"
            " ORDER BY sequence",
            (run_plan_id,),
        ).fetchall()
        receipt_row = connection.execute(
            "SELECT receipt_json FROM plugin_run_receipts WHERE run_plan_id = ?", (run_plan_id,)
        ).fetchone()
        try:
            plan = PluginRunPlan.model_validate(_strict_json(row[0]))
            transitions = tuple(
                PluginRunTransition.model_validate(_strict_json(item[0]))
                for item in transition_rows
            )
            receipt = (
                PluginRunReceipt.model_validate(_strict_json(receipt_row[0]))
                if receipt_row is not None
                else None
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "plugin run store is corrupt") from exc
        if not transitions or any(
            transition.sequence != index or transition.run_plan_id != plan.run_plan_id
            for index, transition in enumerate(transitions)
        ):
            raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "plugin transition chain is corrupt")
        if receipt is not None and receipt.result.transitions != transitions:
            raise PluginRunStoreError("PLUGIN_AUDIT_FAILED", "plugin receipt history is corrupt")
        return PluginRunSnapshot(plan=plan, transitions=transitions, receipt=receipt)

    def _validate_store(self, connection: sqlite3.Connection | None = None) -> None:
        owns = connection is None
        current = connection or self._connect()
        try:
            application_id = current.execute("PRAGMA application_id").fetchone()[0]
            user_version = current.execute("PRAGMA user_version").fetchone()[0]
            row = current.execute(
                "SELECT value FROM forgegate_plugin_metadata WHERE key = 'schema_version'"
            ).fetchone()
            if (
                application_id != PLUGIN_RUN_STORE_APPLICATION_ID
                or user_version != PLUGIN_RUN_STORE_SCHEMA_VERSION
                or row is None
                or row[0] != str(PLUGIN_RUN_STORE_SCHEMA_VERSION)
            ):
                raise PluginRunStoreError(
                    "PLUGIN_AUDIT_FAILED", "unsupported plugin run store identity"
                )
        except sqlite3.Error as exc:
            raise PluginRunStoreError(
                "PLUGIN_AUDIT_FAILED", "plugin run store is unavailable"
            ) from exc
        finally:
            if owns:
                current.close()

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(self.database_path, timeout=1.0, isolation_level=None)
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("PRAGMA journal_mode = WAL")
            return connection
        except sqlite3.Error as exc:
            raise PluginRunStoreError(
                "PLUGIN_AUDIT_FAILED", "cannot open plugin run store"
            ) from exc

    def _transaction(self) -> _Transaction:
        return _Transaction(self)


class _Transaction:
    def __init__(self, repository: SQLitePluginRunRepository) -> None:
        self.repository = repository
        self.connection: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self.connection = self.repository._connect()
        try:
            self.repository._validate_store(self.connection)
            self.connection.execute("BEGIN IMMEDIATE")
        except Exception:
            self.connection.close()
            raise
        return self.connection

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        assert self.connection is not None
        try:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        except sqlite3.Error as error:
            raise PluginRunStoreError(
                "PLUGIN_AUDIT_FAILED", "plugin run transaction failed"
            ) from error
        finally:
            self.connection.close()


def _strict_json(value: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = item
        return result

    def constant(_: str) -> None:
        raise ValueError("non-finite number")

    return json.loads(value, object_pairs_hook=pairs, parse_constant=constant)


__all__ = [
    "PLUGIN_RUN_STORE_APPLICATION_ID",
    "PLUGIN_RUN_STORE_SCHEMA_VERSION",
    "PluginRunReservation",
    "PluginRunSnapshot",
    "PluginRunStoreError",
    "SQLitePluginRunRepository",
]
