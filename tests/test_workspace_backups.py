import base64
import hashlib
import json
import sqlite3
import struct
import time
import warnings
import zipfile
from contextlib import closing
from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner

import forgegate.workspace_backups as wb
from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateEvaluateCommand,
)
from forgegate.canonical import canonical_json
from forgegate.cli import app as cli
from forgegate.collection_jobs import CollectionJobStore
from forgegate.workspace_backups import (
    WorkspaceBackupError,
    backup_workspace,
    plan_workspace_retention,
    restore_workspace,
    verify_workspace_backup,
)
from tests import test_collection_jobs as job_tests
from tests.test_policy_materialization import _advance_to_evaluating, _application


@pytest.fixture
def fixture(tmp_path, repository_root):
    return job_tests.fixture.__wrapped__(tmp_path, repository_root)


def _backup(fixture, tmp_path):
    _app, store, _request = fixture
    target = tmp_path / "backup.zip"
    return target, backup_workspace(tmp_path / "candidates.db", store.path, target)


def _tables(path):
    with closing(sqlite3.connect(path)) as con:
        return {
            r[0]: con.execute(f'SELECT * FROM "{r[0]}" ORDER BY 1').fetchall()
            for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


def test_paired_round_trip_and_queued_execution(fixture, tmp_path):
    app, store, request = fixture
    done = store.submit(request, app, key="done")
    store.run(done.job_id, 0, app)
    queued = store.submit(request, app, key="queued")
    before = (_tables(tmp_path / "candidates.db"), _tables(store.path))
    backup, receipt = _backup(fixture, tmp_path)
    assert receipt["job_states"] == {"QUEUED": 1, "SUCCEEDED": 1}
    assert receipt["job_event_count"] == 6
    assert receipt["sha256"] == hashlib.sha256(backup.read_bytes()).hexdigest()
    assert verify_workspace_backup(backup)["expected_hash_matched"] is False
    verified = verify_workspace_backup(backup, expected_sha256=receipt["sha256"])
    assert verified["expected_hash_matched"]
    dest = tmp_path / "recovered space"
    restored = restore_workspace(backup, dest, expected_sha256=receipt["sha256"])
    assert restored["status"] == "WORKSPACE_RESTORED_COPY"
    assert {p.name for p in dest.iterdir()} == {"candidates.db", "jobs.db", "RESTORED.json"}
    assert (_tables(dest / "candidates.db"), _tables(dest / "jobs.db")) == before
    assert (_tables(tmp_path / "candidates.db"), _tables(store.path)) == before
    cold = type(app).for_database(dest / "candidates.db")
    recovered = CollectionJobStore(dest / "jobs.db")
    assert recovered.result(done.job_id) == store.result(done.job_id)
    assert recovered.run(queued.job_id, 0, cold).state == "SUCCEEDED"
    assert store.show(queued.job_id).state == "QUEUED"
    assert str(tmp_path) not in json.dumps(receipt)


def test_bound_historical_snapshot_and_retention(fixture, tmp_path):
    app, store, request = fixture
    first = store.submit(request, app, key="bound")
    store.run(first.job_id, 0, app)
    queued = store.submit(request, app, key="pending")
    cancel = store.submit(request, app, key="cancel")
    store.cancel(cancel.job_id, 0)
    result = store.result(first.job_id)
    app.bind_evidence(
        request.candidate_id,
        CandidateBindEvidenceCommand(assembly=result.assembly, bound_at=datetime.now(UTC)),
        idempotency_key="backup:bind",
    )
    app.advance_candidate(
        request.candidate_id,
        CandidateAdvanceCommand(
            to_status="READY", expected_revision=1, occurred_at=datetime.now(UTC)
        ),
        idempotency_key="backup:ready",
    )
    backup, receipt = _backup(fixture, tmp_path)
    after = datetime.now(UTC) + timedelta(days=1)
    plan = plan_workspace_retention(
        backup, expected_sha256=receipt["sha256"], as_of=after, terminal_before=after
    )
    reasons = {r["job_id"]: r["reason"] for r in plan["jobs"]}
    assert reasons == {
        first.job_id: "BOUND_EVIDENCE",
        queued.job_id: "ACTIVE_JOB",
        cancel.job_id: "TERMINAL_UNBOUND_REVIEW",
    }
    assert plan["deletion_performed"] is False and plan["capacity_reclaimed"] == 0
    recent = plan_workspace_retention(
        backup,
        expected_sha256=receipt["sha256"],
        as_of=after,
        terminal_before=datetime(2020, 1, 1, tzinfo=UTC),
    )
    assert (
        next(r for r in recent["jobs"] if r["job_id"] == cancel.job_id)["reason"]
        == "WITHIN_RETENTION_WINDOW"
    )


def test_running_jobs_block_without_mutation(fixture, tmp_path):
    app, store, request = fixture
    job = store.submit(request, app, key="running")
    store.claim(job.job_id, 0)
    before = _tables(store.path)
    with pytest.raises(WorkspaceBackupError, match="RUNNING_JOBS"):
        _backup(fixture, tmp_path)
    assert _tables(store.path) == before
    assert not (tmp_path / "backup.zip").exists()


@pytest.mark.parametrize("source", ["candidates.db", "jobs.db"])
def test_writer_reservation_blocks_both_stores(fixture, tmp_path, monkeypatch, source):
    original = wb._snapshot
    attempted = []

    def checked(src, dst, deadline):
        with closing(sqlite3.connect(tmp_path / source, timeout=0)) as writer:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                writer.execute("BEGIN IMMEDIATE")
            attempted.append(source)
        original(src, dst, deadline)

    monkeypatch.setattr(wb, "_snapshot", checked)
    _backup(fixture, tmp_path)
    assert len(attempted) == 2
    # Both reservations released after success.
    with closing(sqlite3.connect(tmp_path / source, timeout=0)) as con:
        con.execute("BEGIN IMMEDIATE")


@pytest.mark.parametrize("name", ["candidates.db", "jobs.db"])
def test_busy_writer_fails_closed(fixture, tmp_path, name):
    with closing(sqlite3.connect(tmp_path / name)) as con:
        con.execute("BEGIN IMMEDIATE")
        with pytest.raises(WorkspaceBackupError, match="BUSY"):
            _backup(fixture, tmp_path)
    assert not (tmp_path / "backup.zip").exists()


def test_wrong_pair_rejected(fixture, tmp_path):
    app, store, request = fixture
    store.submit(request, app, key="one")
    other = tmp_path / "unrelated.db"
    type(app).for_database(other).initialize()
    with pytest.raises(WorkspaceBackupError):
        backup_workspace(other, store.path, tmp_path / "no.zip")
    assert not (tmp_path / "no.zip").exists()


def test_cli_chain_and_errors(fixture, tmp_path):
    runner = CliRunner()
    target = tmp_path / "cli.zip"
    args = [
        "workspace",
        "backup",
        str(tmp_path / "candidates.db"),
        str(tmp_path / "jobs.db"),
        str(target),
    ]
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    digest = json.loads(result.stdout)["sha256"]
    for command in (
        ["verify-backup", str(target), "--sha256", digest],
        ["restore", str(target), str(tmp_path / "cli-copy"), "--sha256", digest],
        [
            "retention-plan",
            str(target),
            "--sha256",
            digest,
            "--as-of",
            "2099-01-01T00:00:00Z",
            "--terminal-before",
            "2098-01-01T00:00:00Z",
        ],
    ):
        result = runner.invoke(cli, ["workspace", *command])
        assert result.exit_code == 0, result.output
    result = runner.invoke(cli, args)
    assert result.exit_code == 3 and "WORKSPACE_DESTINATION_EXISTS" in result.output
    assert str(tmp_path) not in result.output
    assert runner.invoke(cli, [*args, "--timeout-seconds", "0"]).exit_code == 2


@pytest.mark.parametrize(
    "kind",
    [
        "existing",
        "directory",
        "sidecar",
        "parent",
        "same_sources",
        "missing",
        "wrong_job_version",
        "wrong_candidate_version",
    ],
)
def test_source_and_destination_refusals(fixture, tmp_path, kind):
    cp, jp, dst = tmp_path / "candidates.db", tmp_path / "jobs.db", tmp_path / "no.zip"
    if kind == "existing":
        dst.write_bytes(b"retained by owner")
    elif kind == "directory":
        dst.mkdir()
    elif kind == "sidecar":
        (tmp_path / "no.zip-wal").touch()
    elif kind == "parent":
        dst = tmp_path / "missing" / "no.zip"
    elif kind == "same_sources":
        jp = cp
    elif kind == "missing":
        cp = tmp_path / "absent.db"
    else:
        with closing(sqlite3.connect(jp if kind == "wrong_job_version" else cp)) as con:
            con.execute("PRAGMA user_version=2")
    with pytest.raises(WorkspaceBackupError):
        backup_workspace(cp, jp, dst)
    if kind == "existing":
        assert dst.read_bytes() == b"retained by owner"
    assert not list(tmp_path.glob(".forgegate-workspace-*"))


def test_publication_race_and_link_failure(fixture, tmp_path, monkeypatch):
    def race(source, target):
        target.write_bytes(b"other owner's file")
        raise FileExistsError

    monkeypatch.setattr(wb.os, "link", race)
    with pytest.raises(WorkspaceBackupError, match="DESTINATION_EXISTS"):
        _backup(fixture, tmp_path)
    assert (tmp_path / "backup.zip").read_bytes() == b"other owner's file"

    def unsupported(source, target):
        raise OSError("sensitive details")

    monkeypatch.setattr(wb.os, "link", unsupported)
    with pytest.raises(WorkspaceBackupError, match=r"^WORKSPACE_INVALID$"):
        backup_workspace(tmp_path / "candidates.db", tmp_path / "jobs.db", tmp_path / "other.zip")
    assert not (tmp_path / "other.zip").exists()


def _rewrite(backup, mutate):
    with zipfile.ZipFile(backup) as archive:
        entries = [(i.filename, archive.read(i)) for i in archive.infolist()]
    entries = mutate(entries)
    with zipfile.ZipFile(backup, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in entries:
            archive.writestr(name, data)


@pytest.mark.parametrize(
    "kind",
    [
        "member_bytes",
        "missing",
        "extra",
        "traversal",
        "duplicate",
        "manifest_unknown",
        "manifest_duplicate",
        "manifest_large",
        "manifest_noncanonical",
        "timestamp",
        "size",
        "schema",
        "compressed",
        "cd_size",
        "truncated",
        "junk",
    ],
)
def test_corrupt_archives_fail_before_restoring(fixture, tmp_path, kind):
    backup, _receipt = _backup(fixture, tmp_path)
    if kind in {"truncated", "junk", "cd_size"}:
        raw = backup.read_bytes()
        if kind == "truncated":
            raw = raw[:100]
        elif kind == "junk":
            raw = b"not an archive"
        else:
            raw = raw[:-10] + struct.pack("<I", 99999) + raw[-6:]
        backup.write_bytes(raw)
    elif kind == "compressed":
        with zipfile.ZipFile(backup) as z:
            entries = [(i.filename, z.read(i)) for i in z.infolist()]
        with zipfile.ZipFile(backup, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, payload in entries:
                z.writestr(name, payload)
    else:

        def mutate(entries):
            if kind == "member_bytes":
                name, data = entries[0]
                entries[0] = (name, data[:100] + b"X" + data[101:])
            elif kind == "missing":
                return entries[:2]
            elif kind == "extra":
                return [*entries, ("extra.txt", b"secret")]
            elif kind in {"traversal", "duplicate"}:
                entries[0] = (
                    ("../outside.db" if kind == "traversal" else "jobs.db"),
                    entries[0][1],
                )
            else:
                manifest = json.loads(entries[2][1])
                if kind == "manifest_unknown":
                    manifest["unexpected"] = True
                elif kind == "timestamp":
                    manifest["created_at"] = "2026-09-07T00:00:00"
                elif kind == "size":
                    manifest["job_store"]["size_bytes"] += 1
                elif kind == "schema":
                    manifest["job_store_version"] = 2
                payload = canonical_json(manifest).encode()
                if kind == "manifest_noncanonical":
                    payload += b"\n"
                elif kind == "manifest_duplicate":
                    payload = b'{"encrypted":false,' + payload[1:]
                elif kind == "manifest_large":
                    payload = b" " * (wb.MAX_MANIFEST_BYTES + 1)
                entries[2] = ("manifest.json", payload)
            return entries

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            _rewrite(backup, mutate)
    with pytest.raises(WorkspaceBackupError):
        restore_workspace(
            backup,
            tmp_path / "refused",
            expected_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
        )
    assert not (tmp_path / "refused").exists()
    assert not (tmp_path / "outside.db").exists()


def test_verifier_hash_sidecar_size_deadline_and_readonly(fixture, tmp_path, monkeypatch):
    backup, _receipt = _backup(fixture, tmp_path)
    before = backup.read_bytes()
    for digest, code in (("bad", "HASH_INVALID"), ("f" * 64, "HASH_MISMATCH")):
        with pytest.raises(WorkspaceBackupError, match=code):
            verify_workspace_backup(backup, expected_sha256=digest)
    sidecar = tmp_path / "backup.zip-wal"
    sidecar.touch()
    with pytest.raises(WorkspaceBackupError, match="NOT_STANDALONE"):
        verify_workspace_backup(backup)
    sidecar.unlink()
    with pytest.raises(WorkspaceBackupError, match="TIMEOUT_INVALID"):
        verify_workspace_backup(backup, timeout_seconds=float("nan"))
    monkeypatch.setattr(wb, "MAX_ARCHIVE_BYTES", 1)
    with pytest.raises(WorkspaceBackupError, match="TOO_LARGE"):
        verify_workspace_backup(backup)
    monkeypatch.undo()
    monkeypatch.setattr(wb, "_deadline", lambda _: time.monotonic() - 1)
    with pytest.raises(WorkspaceBackupError, match="DEADLINE_EXCEEDED"):
        verify_workspace_backup(backup)
    assert backup.read_bytes() == before


def test_restore_refusals_and_partial_recovery(fixture, tmp_path, monkeypatch):
    backup, receipt = _backup(fixture, tmp_path)
    digest = receipt["sha256"]
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(WorkspaceBackupError, match="DESTINATION_EXISTS"):
        restore_workspace(backup, existing, expected_sha256=digest)
    assert list(existing.iterdir()) == []
    with pytest.raises(WorkspaceBackupError, match="PARENT_MISSING"):
        restore_workspace(backup, tmp_path / "absent" / "child", expected_sha256=digest)
    with pytest.raises(WorkspaceBackupError, match="HASH_INVALID"):
        restore_workspace(backup, existing, expected_sha256=None)
    original = wb._stream
    dest = tmp_path / "interrupted"

    def fail_second(reader, writer, deadline, limit):
        if writer is not None and str(getattr(writer, "name", "")) == str(dest / "jobs.db"):
            raise OSError("private failed disk detail")
        return original(reader, writer, deadline, limit)

    monkeypatch.setattr(wb, "_stream", fail_second)
    with pytest.raises(WorkspaceBackupError, match="RESTORE_INCOMPLETE"):
        restore_workspace(backup, dest, expected_sha256=digest)
    assert (dest / "candidates.db").is_file()
    assert not (dest / "RESTORED.json").exists()
    assert _tables(tmp_path / "candidates.db") == _tables(dest / "candidates.db")


@pytest.mark.parametrize(
    "kind", ["naive", "future_cutoff", "predates_backup", "job_future", "hash"]
)
def test_retention_time_and_hash_boundaries(fixture, tmp_path, kind):
    app, store, request = fixture
    store.submit(request, app, key="pending")
    backup, receipt = _backup(fixture, tmp_path)
    after = datetime.now(UTC) + timedelta(days=1)
    cutoff = after
    if kind == "naive":
        cutoff = cutoff.replace(tzinfo=None)
    elif kind == "future_cutoff":
        cutoff += timedelta(days=1)
    elif kind == "predates_backup":
        after = cutoff = datetime(2020, 1, 1, tzinfo=UTC)
    elif kind == "job_future":
        with pytest.MonkeyPatch.context() as m:
            original = wb._inspect_pair

            def inspect(root, deadline):
                details = original(root, deadline)
                details["jobs"][0]["updated_at"] = (after + timedelta(days=1)).isoformat()
                return details

            m.setattr(wb, "_inspect_pair", inspect)
            with pytest.raises(WorkspaceBackupError, match="TIME_INVALID"):
                plan_workspace_retention(
                    backup, expected_sha256=receipt["sha256"], as_of=after, terminal_before=cutoff
                )
        return
    with pytest.raises(WorkspaceBackupError):
        plan_workspace_retention(
            backup,
            expected_sha256=None if kind == "hash" else receipt["sha256"],
            as_of=after,
            terminal_before=cutoff,
        )


def test_job_history_corruption_and_association(fixture, tmp_path):
    app, store, request = fixture
    record = store.submit(request, app, key="job")
    store.cancel(record.job_id, 0)
    with closing(sqlite3.connect(store.path)) as con:
        con.execute("DROP TRIGGER events_no_update")
        row = con.execute("SELECT record FROM events WHERE revision=0").fetchone()[0]
        changed = json.loads(row)
        changed["candidate_fingerprint"] = "sha256:" + "0" * 64
        con.execute("UPDATE events SET record=? WHERE revision=0", (canonical_json(changed),))
        con.execute(
            "CREATE TRIGGER events_no_update BEFORE UPDATE ON events "
            "BEGIN SELECT RAISE(ABORT, 'immutable'); END"
        )
        con.commit()
    with pytest.raises(WorkspaceBackupError):
        _backup(fixture, tmp_path)
    assert not (tmp_path / "backup.zip").exists()


def test_legacy_public_record_preserved_in_current_store(fixture, tmp_path):
    app, store, request = fixture
    job = store.submit(request, app, key="legacy")
    with closing(sqlite3.connect(store.path)) as con:
        raw = job.model_dump(mode="json")
        raw["schema_version"] = "forgegate.collection-job.v1"
        raw.pop("execution_owner_id")
        raw.pop("lease_renewal_count")
        payload = canonical_json(raw)
        con.execute("DROP TRIGGER events_no_update")
        con.execute("UPDATE jobs SET record=?", (payload,))
        con.execute("UPDATE events SET record=?", (payload,))
        con.execute(
            "CREATE TRIGGER events_no_update BEFORE UPDATE ON events "
            "BEGIN SELECT RAISE(ABORT, 'immutable'); END"
        )
        con.commit()
    backup, receipt = _backup(fixture, tmp_path)
    restore_workspace(backup, tmp_path / "legacy-restored", expected_sha256=receipt["sha256"])
    assert _tables(store.path) == _tables(tmp_path / "legacy-restored/jobs.db")


def test_committed_wal_terminal_candidate_roundtrip(tmp_path, repository_root):
    application, cid = _application(tmp_path, repository_root)
    cp, jp = tmp_path / "forgegate.db", tmp_path / "jobs.db"
    CollectionJobStore(jp).initialize()
    with closing(sqlite3.connect(cp)) as reader:
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM candidates").fetchone()
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
            idempotency_key="workspace:evaluate",
        )
        application.attest_candidate(
            cid, CandidateAttestCommand(issued_at=datetime(2026, 8, 30, 22, tzinfo=UTC))
        )
        assert cp.with_name(cp.name + "-wal").stat().st_size > 0
        backup = tmp_path / "terminal.zip"
        receipt = backup_workspace(cp, jp, backup)
    dest = tmp_path / "terminal"
    restore_workspace(backup, dest, expected_sha256=receipt["sha256"])
    cold = type(application).for_database(dest / "candidates.db")
    assert cold.get_candidate(cid).status.value == "PASS"
    assert cold.get_attestation(cid) == application.get_attestation(cid)
    assert cold.get_evidence(cid) == application.get_evidence(cid)
    assert _tables(cp) == _tables(dest / "candidates.db")


@pytest.mark.parametrize(
    "state,xml",
    [
        ("REVIEW_REQUIRED", b'<testsuite tests="2"><testcase name="x"/></testsuite>'),
        ("REJECTED", b"<!DOCTYPE x><testsuite/>"),
    ],
)
def test_warning_and_rejected_result_recovery(fixture, tmp_path, state, xml):
    app, store, request = fixture
    raw = request.model_dump()
    raw["collection"]["reports"][0]["content_base64"] = base64.b64encode(xml).decode()
    request = job_tests.jobs.CollectionJobRequest.model_validate(raw)
    job = store.submit(request, app, key="negative")
    assert store.run(job.job_id, 0, app).state == state
    backup, receipt = _backup(fixture, tmp_path)
    restore_workspace(backup, tmp_path / "negative", expected_sha256=receipt["sha256"])
    assert CollectionJobStore(tmp_path / "negative/jobs.db").result(job.job_id) == store.result(
        job.job_id
    )


def test_manifest_combined_size_bound():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="combined snapshot"):
        wb.WorkspaceBackupManifest(
            created_at=datetime.now(UTC),
            candidate_store={"sha256": "a" * 64, "size_bytes": wb.MAX_STORE_BYTES},
            job_store={"sha256": "b" * 64, "size_bytes": 1},
        )


def test_backup_source_change_is_detected(fixture, tmp_path, monkeypatch):
    backup, _ = _backup(fixture, tmp_path)
    original = wb._stream

    def changed(reader, writer, deadline, limit):
        result = original(reader, writer, deadline, limit)
        if str(getattr(reader, "name", "")) == str(backup):
            with backup.open("ab") as stream:
                stream.write(b"changed")
        return result

    monkeypatch.setattr(wb, "_stream", changed)
    with pytest.raises(WorkspaceBackupError, match="SOURCE_CHANGED"):
        verify_workspace_backup(backup)
