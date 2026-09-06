from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forgegate.application import (
    CandidateApplication,
    CandidateAttestCommand,
    CandidateEvaluateCommand,
)
from forgegate.candidates import SQLiteCandidateRepository, backups
from forgegate.candidates.backups import StoreBackupError, backup_store, verify_store_backup
from forgegate.cli import app
from tests.test_policy_materialization import _advance_to_evaluating, _application


def _snapshot(path):
    with closing(sqlite3.connect(path)) as connection:
        return {
            table: connection.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()
            for table in backups.TABLES
        }


def test_live_wal_backup_and_cold_domain_readback(tmp_path, repository_root):
    application, cid = _application(tmp_path, repository_root)
    source = tmp_path / "forgegate.db"
    target = tmp_path / "snapshot with spaces #1.db"
    with closing(sqlite3.connect(source)) as writer:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("BEGIN")
        writer.execute("SELECT COUNT(*) FROM candidates").fetchone()
        _advance_to_evaluating(application, cid, repository_root)
        application.evaluate_candidate(
            cid,
            CandidateEvaluateCommand(
                policy_material=application.materialize_policy(
                    cid, repository_root / "examples/sample-python-api"
                ),
                expected_revision=3,
                evaluated_at=datetime(2026, 8, 30, 21, tzinfo=UTC),
            ),
            idempotency_key="backup:evaluate",
        )
        application.attest_candidate(
            cid,
            CandidateAttestCommand(issued_at=datetime(2026, 8, 30, 22, tzinfo=UTC)),
        )
        before = _snapshot(source)
        assert Path(str(source) + "-wal").stat().st_size > 0
        writer.rollback()
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("CREATE TABLE uncommitted_fixture(value TEXT)")
        receipt = backup_store(source, target)
        writer.rollback()
        assert _snapshot(source) == before == _snapshot(target)
    # Close every fixture DB before offline verification; WAL bytes must be self-contained.
    original = target.read_bytes()
    verified = verify_store_backup(target, expected_sha256=receipt["sha256"])
    assert target.read_bytes() == original
    assert not backups._sidecars(target)
    assert verified["expected_hash_matched"] is True
    assert verified["table_counts"]["attestations"] == 1
    assert verified["table_counts"]["candidate_policy_materials"] == 1
    with closing(sqlite3.connect(target)) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name='uncommitted_fixture'"
            ).fetchone()[0]
            == 0
        )
    cold = CandidateApplication.for_database(target)
    assert cold.get_candidate(cid) == application.get_candidate(cid)
    assert cold.get_attestation(cid) == application.get_attestation(cid)
    assert cold.get_evidence(cid) == application.get_evidence(cid)
    assert receipt["restore_performed"] is False
    assert receipt["producer_authenticity"] == "NOT_VERIFIED"
    assert str(tmp_path) not in json.dumps(receipt)


def _empty(tmp_path):
    source = tmp_path / "store.db"
    SQLiteCandidateRepository(source).initialize()
    return source


@pytest.mark.parametrize("kind", ["missing", "directory", "empty", "junk", "wrong_schema"])
def test_invalid_sources_are_not_published(tmp_path, kind):
    source = tmp_path / "source.db"
    if kind == "directory":
        source.mkdir()
    elif kind == "empty":
        source.touch()
    elif kind == "junk":
        source.write_bytes(b"private arbitrary data")
    elif kind == "wrong_schema":
        SQLiteCandidateRepository(source).initialize()
        with sqlite3.connect(source) as connection:
            connection.execute("PRAGMA user_version=8")
    destination = tmp_path / "backup.db"
    with pytest.raises(StoreBackupError) as error:
        backup_store(source, destination)
    assert "private" not in str(error.value) and str(tmp_path) not in str(error.value)
    assert not destination.exists()
    assert not list(tmp_path.glob(".forgegate-backup-*"))


@pytest.mark.parametrize("kind", ["same", "file", "directory", "wal", "shm", "journal", "parent"])
def test_destination_fail_closed(tmp_path, kind):
    source = _empty(tmp_path)
    destination = tmp_path / "copy.db"
    if kind == "same":
        destination = source
    elif kind == "directory":
        destination.mkdir()
    elif kind == "file":
        destination.write_bytes(b"do not overwrite")
    elif kind in {"wal", "shm", "journal"}:
        Path(str(destination) + "-" + kind).write_bytes(b"do not delete")
    else:
        destination = tmp_path / "absent" / "copy.db"
    before = source.read_bytes()
    with pytest.raises(StoreBackupError):
        backup_store(source, destination)
    assert source.read_bytes() == before
    if kind == "file":
        assert destination.read_bytes() == b"do not overwrite"


def test_publication_race_and_unsupported_links(tmp_path, monkeypatch):
    source = _empty(tmp_path)
    destination = tmp_path / "copy.db"

    def race(src, dst):
        Path(dst).write_bytes(b"other owner")
        raise FileExistsError

    monkeypatch.setattr(backups.os, "link", race)
    with pytest.raises(StoreBackupError, match="DESTINATION_EXISTS"):
        backup_store(source, destination)
    assert destination.read_bytes() == b"other owner"

    def unsupported(*args):
        raise OSError("private filesystem detail")

    monkeypatch.setattr(backups.os, "link", unsupported)
    with pytest.raises(StoreBackupError, match="CREATION_FAILED"):
        backup_store(source, tmp_path / "unsupported.db")
    assert not list(tmp_path.glob(".forgegate-backup-*"))


@pytest.mark.parametrize("timeout", [0, -1, 301, float("nan"), float("inf")])
def test_invalid_timeout(tmp_path, timeout):
    with pytest.raises(StoreBackupError, match="TIMEOUT_INVALID"):
        backup_store(tmp_path / "unused", tmp_path / "unused2", timeout_seconds=timeout)


def test_verifier_hash_limits_sidecar_and_corruption(tmp_path, monkeypatch):
    source = _empty(tmp_path)
    target = tmp_path / "backup.db"
    report = backup_store(source, target)
    assert report["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert verify_store_backup(target)["expected_hash_matched"] is False
    for expected, code in (("not a hash", "HASH_INVALID"), ("f" * 64, "HASH_MISMATCH")):
        with pytest.raises(StoreBackupError, match=code):
            verify_store_backup(target, expected_sha256=expected)
    wal = Path(str(target) + "-wal")
    wal.touch()
    with pytest.raises(StoreBackupError, match="NOT_STANDALONE"):
        verify_store_backup(target)
    wal.unlink()  # Only this test-created empty sentinel.
    monkeypatch.setattr(backups, "MAX_BACKUP_BYTES", 1)
    with pytest.raises(StoreBackupError, match="TOO_LARGE"):
        verify_store_backup(target)
    with pytest.raises(StoreBackupError, match="TOO_LARGE"):
        backup_store(source, tmp_path / "oversized.db")
    monkeypatch.undo()
    target.write_bytes(b"corrupt snapshot")
    with pytest.raises(StoreBackupError, match="VALIDATION_FAILED"):
        verify_store_backup(target)


def test_deadline_copy_bound_and_changed_source(tmp_path, monkeypatch):
    source = _empty(tmp_path)
    with pytest.raises(StoreBackupError, match="DEADLINE"):
        backups._check_time(0)
    monkeypatch.setattr(backups, "MAX_BACKUP_BYTES", 1)
    with pytest.raises(StoreBackupError, match="TOO_LARGE"):
        backups._copy_and_hash(source, tmp_path / "large.tmp", float("inf"))
    monkeypatch.undo()
    real_stat = Path.stat
    calls = 0

    def changed(path, *args, **kwargs):
        nonlocal calls
        if path == source:
            calls += 1
            if calls == 2:
                source.write_bytes(b"changed")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", changed)
    with pytest.raises(StoreBackupError, match="SOURCE_CHANGED"):
        backups._copy_and_hash(source, tmp_path / "changed.tmp", float("inf"))


def test_backup_cli_round_trip_and_sanitized_failures(tmp_path):
    source = _empty(tmp_path)
    destination = tmp_path / "backup.db"
    runner = CliRunner()
    result = runner.invoke(app, ["candidate", "backup-store", str(source), str(destination)])
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    result = runner.invoke(
        app, ["candidate", "verify-backup", str(destination), "--sha256", receipt["sha256"]]
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["expected_hash_matched"] is True
    assert (
        runner.invoke(app, ["candidate", "backup-store", str(source), str(destination)]).exit_code
        == 3
    )


def test_cli_hash_mismatch(tmp_path):
    source = _empty(tmp_path)
    assert (
        CliRunner()
        .invoke(app, ["candidate", "verify-backup", str(source), "--sha256", "f" * 64])
        .exit_code
        == 3
    )


def test_sidecar_appears_during_verification(tmp_path, monkeypatch):
    source = _empty(tmp_path)
    real_copy = backups._copy_and_hash

    def introduce_sidecar(src, dst, deadline):
        result = real_copy(src, dst, deadline)
        Path(str(src) + "-wal").touch()
        return result

    monkeypatch.setattr(backups, "_copy_and_hash", introduce_sidecar)
    with pytest.raises(StoreBackupError, match="NOT_STANDALONE"):
        verify_store_backup(source)


def test_sidecar_race_before_publication(tmp_path, monkeypatch):
    source = _empty(tmp_path)
    destination = tmp_path / "copy.db"
    real_verify = backups.verify_store_backup

    def introduce_sidecar(path, **kwargs):
        result = real_verify(path, **kwargs)
        Path(str(destination) + "-shm").write_bytes(b"other instance")
        return result

    monkeypatch.setattr(backups, "verify_store_backup", introduce_sidecar)
    with pytest.raises(StoreBackupError, match="DESTINATION_EXISTS"):
        backup_store(source, destination)
    assert not destination.exists()
    assert Path(str(destination) + "-shm").read_bytes() == b"other instance"


def test_progress_deadline_cleans_staging(tmp_path, monkeypatch):
    source = _empty(tmp_path)

    def expired(deadline):
        raise StoreBackupError("BACKUP_DEADLINE_EXCEEDED")

    monkeypatch.setattr(backups, "_check_time", expired)
    with pytest.raises(StoreBackupError, match="DEADLINE_EXCEEDED"):
        backup_store(source, tmp_path / "copy.db")
    assert not list(tmp_path.glob(".forgegate-backup-*"))
    assert not (tmp_path / "copy.db").exists()


def test_integrity_failure_is_not_a_verified_backup(tmp_path, monkeypatch):
    class BrokenIntegrityConnection:
        def execute(self, sql):
            return self

        def fetchone(self):
            return ("injected integrity failure",)

        def close(self):
            pass

    monkeypatch.setattr(backups, "_connect", lambda *args: BrokenIntegrityConnection())
    monkeypatch.setattr(SQLiteCandidateRepository, "_validate_store", lambda *args: None)
    with pytest.raises(StoreBackupError, match="INTEGRITY_FAILED"):
        backups._inspect(tmp_path / "unused", float("inf"))
