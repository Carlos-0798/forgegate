import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner

import forgegate.collection_jobs as cj
import forgegate.job_archival as ja
from forgegate.application import CandidateAdvanceCommand, CandidateBindEvidenceCommand
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.cli import app as cli
from forgegate.collection_jobs import CollectionJobStore, JobError
from forgegate.job_archival import (
    archive_job,
    load_archive_plan,
    plan_job_archive,
    read_archived_result,
)
from forgegate.job_archive_models import JobArchivePlan, JobArchiveReceipt
from forgegate.workspace_backups import (
    WorkspaceBackupError,
    backup_workspace,
    plan_workspace_retention,
    restore_workspace,
    verify_workspace_backup,
)
from tests import test_collection_jobs as job_tests
from tests.test_dashboard import _activate
from tests.test_dashboard_job_result_handoff import binding_command, export_command, write_headers
from tests.test_dashboard_jobs import client_for
from tests.test_workspace_backups import _tables


@pytest.fixture
def fixture(tmp_path, repository_root):
    return job_tests.fixture.__wrapped__(tmp_path, repository_root)


def prepare(fixture, tmp_path, state="SUCCEEDED", migrate=True):
    app, store, request = fixture
    queued = store.submit(request, app, key="archive:original")
    if state == "SUCCEEDED":
        record = store.run(queued.job_id, 0, app)
    elif state == "CANCELLED":
        record = store.cancel(queued.job_id, 0)
    else:
        record = queued
    backup = tmp_path / "before.zip"
    metadata = backup_workspace(tmp_path / "candidates.db", store.path, backup)
    if migrate:
        store.enable_archiving()
    return record, backup, metadata


def plan_for(fixture, tmp_path, record, backup, metadata, **changes):
    kwargs = dict(
        expected_sha256=metadata["sha256"],
        expected_revision=record.revision,
        terminal_before=datetime.now(UTC),
    )
    kwargs.update(changes)
    return plan_job_archive(
        tmp_path / "candidates.db", fixture[1].path, backup, record.job_id, **kwargs
    )


def apply(fixture, tmp_path, backup, plan, **changes):
    kwargs = dict(confirm_plan=sha256_fingerprint(plan.model_dump(mode="json")))
    kwargs.update(changes)
    return archive_job(tmp_path / "candidates.db", fixture[1].path, backup, plan, **kwargs)


@pytest.mark.parametrize("state", ["SUCCEEDED", "CANCELLED"])
def test_round_trip_preserves_identity_history_replay_and_external_payload(
    fixture, tmp_path, state
):
    app, store, request = fixture
    record, backup, metadata = prepare(fixture, tmp_path, state)
    before = _tables(store.path)
    candidate_before = _tables(tmp_path / "candidates.db")
    plan = plan_for(fixture, tmp_path, record, backup, metadata)
    assert _tables(store.path) == before
    receipt = apply(fixture, tmp_path, backup, plan)
    assert receipt.logical_job_slots_reclaimed == 1
    assert receipt.physical_file_shrink == receipt.secure_erasure == "NOT_PERFORMED"
    assert apply(fixture, tmp_path, backup, plan) == receipt
    assert store.submit(request, app, key="archive:original") == record
    assert store.show(record.job_id) == record
    assert store.review(record.job_id, project_id="sample-api").archive == receipt
    assert store.review(record.job_id, project_id="sample-api").result is None
    assert _tables(store.path)["events"] == before["events"]
    assert _tables(tmp_path / "candidates.db") == candidate_before
    assert _tables(store.path)["jobs"][0][:4] == before["jobs"][0][:4]
    with pytest.raises(JobError, match="JOB_RESULT_ARCHIVED"):
        store.result(record.job_id)
    if state == "SUCCEEDED":
        result = read_archived_result(backup, record.job_id, expected_sha256=metadata["sha256"])
        assert (
            result.model_dump_json()
            == cj.CollectionJobResult.model_validate_json(before["jobs"][0][4]).model_dump_json()
        )
        assert result.collections[0].evidence[0].value["total"] == 4
    else:
        with pytest.raises(WorkspaceBackupError, match="ARCHIVE_RESULT_NOT_IN_BACKUP"):
            read_archived_result(backup, record.job_id, expected_sha256=metadata["sha256"])
    after_backup = tmp_path / "after.zip"
    after_meta = backup_workspace(tmp_path / "candidates.db", store.path, after_backup)
    assert after_meta["job_store_version"] == 4 and after_meta["archived_job_count"] == 1
    assert after_meta["external_archive_dependencies"] == [metadata["sha256"]]
    dest = tmp_path / "restored"
    restore_workspace(after_backup, dest, expected_sha256=after_meta["sha256"])
    restored = CollectionJobStore(dest / "jobs.db")
    assert restored.review(record.job_id, project_id="sample-api").archive == receipt
    assert _tables(dest / "jobs.db") == _tables(store.path)
    retention = plan_workspace_retention(
        after_backup,
        expected_sha256=after_meta["sha256"],
        as_of=datetime.now(UTC),
        terminal_before=plan.terminal_before,
    )
    assert retention["jobs"][0]["reason"] == "ALREADY_ARCHIVED"
    with pytest.raises(WorkspaceBackupError, match="ARCHIVE_RESULT_NOT_IN_BACKUP"):
        read_archived_result(after_backup, record.job_id, expected_sha256=after_meta["sha256"])
    with pytest.raises(WorkspaceBackupError, match="ARCHIVE_ALREADY_ARCHIVED"):
        plan_for(fixture, tmp_path, record, after_backup, after_meta)


def test_migration_is_explicit_idempotent_preserves_raw_rows(fixture, tmp_path):
    _, store, _ = fixture
    record, backup, meta = prepare(fixture, tmp_path, migrate=False)
    before = _tables(store.path)
    with pytest.raises(WorkspaceBackupError, match="ARCHIVE_MIGRATION_REQUIRED"):
        plan_for(fixture, tmp_path, record, backup, meta)
    store.enable_archiving()
    store.enable_archiving()
    store.migrate()
    store.require_dashboard_store()
    after = _tables(store.path)
    assert after.pop("job_archives") == [] and after == before
    with closing(sqlite3.connect(store.path)) as con:
        assert con.execute("PRAGMA user_version").fetchone()[0] == 4


def test_capacity_freed_without_losing_request_keys(fixture, tmp_path, monkeypatch):
    app, store, request = fixture
    record, backup, meta = prepare(fixture, tmp_path)
    monkeypatch.setattr(cj, "MAX_JOBS", 1)
    with pytest.raises(JobError, match="JOB_CAPACITY_EXCEEDED"):
        store.submit(request, app, key="archive:second")
    plan = plan_for(fixture, tmp_path, record, backup, meta)
    apply(fixture, tmp_path, backup, plan)
    assert store.submit(request, app, key="archive:original") == record
    second = store.submit(request, app, key="archive:second")
    assert second.job_id != record.job_id
    assert store.run(second.job_id, 0, app).state == "SUCCEEDED"
    with pytest.raises(JobError, match="JOB_CAPACITY_EXCEEDED"):
        store.submit(request, app, key="archive:third")


@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
@pytest.mark.parametrize("table", ["jobs", "job_archives", "events"])
def test_archived_rows_and_history_immutable(fixture, tmp_path, operation, table):
    record, backup, meta = prepare(fixture, tmp_path)
    apply(fixture, tmp_path, backup, plan_for(fixture, tmp_path, record, backup, meta))
    column = "receipt" if table == "job_archives" else "record"
    sql = (
        f"UPDATE {table} SET {column}={column}" if operation == "UPDATE" else f"DELETE FROM {table}"
    )
    with closing(sqlite3.connect(fixture[1].path)) as con, pytest.raises(sqlite3.IntegrityError):
        con.execute(sql)


@pytest.mark.parametrize(
    "change",
    [
        "confirm",
        "revision",
        "manifest",
        "events",
        "row",
        "retained",
        "candidate",
        "assembly",
        "time",
    ],
)
def test_tampered_or_stale_plan_rejected_without_write(fixture, tmp_path, change):
    record, backup, meta = prepare(fixture, tmp_path)
    plan = plan_for(fixture, tmp_path, record, backup, meta)
    changes = {
        "revision": {"expected_revision": record.revision + 1},
        "manifest": {"backup_manifest_fingerprint": "sha256:" + "0" * 64},
        "events": {"events_fingerprint": "sha256:" + "0" * 64},
        "row": {"source_row_fingerprint": "sha256:" + "0" * 64},
        "retained": {"retained_row_fingerprint": "sha256:" + "0" * 64},
        "candidate": {"expected_candidate_fingerprint": "sha256:" + "0" * 64},
        "assembly": {"assembly_id": "sha256:" + "0" * 64},
        "time": {"planned_at": datetime.now(UTC) + timedelta(days=1)},
    }
    plan = plan.model_copy(update=changes.get(change, {}))
    before = _tables(fixture[1].path)
    with pytest.raises(WorkspaceBackupError, match="ARCHIVE_"):
        apply(
            fixture,
            tmp_path,
            backup,
            plan,
            **({"confirm_plan": "wrong"} if change == "confirm" else {}),
        )
    assert _tables(fixture[1].path) == before


@pytest.mark.parametrize("when", ["before_plan", "after_plan"])
def test_bound_result_protected_even_when_candidate_revision_unchanged(fixture, tmp_path, when):
    app, store, request = fixture
    record, backup, meta = prepare(fixture, tmp_path)
    plan = plan_for(fixture, tmp_path, record, backup, meta)
    app.bind_evidence(
        request.candidate_id,
        CandidateBindEvidenceCommand(
            assembly=store.result(record.job_id).assembly, bound_at=datetime.now(UTC)
        ),
        idempotency_key="archive:bind",
    )
    before = _tables(store.path)
    with pytest.raises(WorkspaceBackupError, match="ARCHIVE_BOUND_EVIDENCE"):
        if when == "before_plan":
            plan_for(fixture, tmp_path, record, backup, meta)
        else:
            apply(fixture, tmp_path, backup, plan)
    assert _tables(store.path) == before


def test_candidate_revision_changed_after_plan(fixture, tmp_path):
    app, store, request = fixture
    record, backup, meta = prepare(fixture, tmp_path)
    plan = plan_for(fixture, tmp_path, record, backup, meta)
    app.bind_evidence(
        request.candidate_id,
        CandidateBindEvidenceCommand(
            assembly=store.result(record.job_id).assembly, bound_at=datetime.now(UTC)
        ),
        idempotency_key="archive:advance-bind",
    )
    app.advance_candidate(
        request.candidate_id,
        CandidateAdvanceCommand(
            to_status="READY", expected_revision=1, occurred_at=datetime.now(UTC)
        ),
        idempotency_key="archive:advance",
    )
    with pytest.raises(WorkspaceBackupError, match="ARCHIVE_CANDIDATE_CHANGED"):
        apply(fixture, tmp_path, backup, plan)


def test_queued_and_stale_backup_protected(fixture, tmp_path):
    _, store, _ = fixture
    record, backup, meta = prepare(fixture, tmp_path, "QUEUED")
    with pytest.raises(WorkspaceBackupError, match="ARCHIVE_ACTIVE_JOB"):
        plan_for(fixture, tmp_path, record, backup, meta)
    record = store.cancel(record.job_id, 0)
    with pytest.raises(WorkspaceBackupError, match="ARCHIVE_BACKUP_STALE"):
        plan_for(fixture, tmp_path, record, backup, meta)


@pytest.mark.parametrize("change", ["recent", "future", "naive", "revision"])
def test_invalid_plan_input(fixture, tmp_path, change):
    record, backup, meta = prepare(fixture, tmp_path)
    changes = {
        "recent": dict(terminal_before=record.updated_at),
        "future": dict(terminal_before=datetime.now(UTC) + timedelta(days=1)),
        "naive": dict(terminal_before=datetime.now()),
        "revision": dict(expected_revision=record.revision + 1),
    }
    with pytest.raises(WorkspaceBackupError):
        plan_for(fixture, tmp_path, record, backup, meta, **changes[change])


def test_capacity_guard_and_insertion_failure_roll_back(fixture, tmp_path, monkeypatch):
    _, store, _ = fixture
    record, backup, meta = prepare(fixture, tmp_path)
    plan = plan_for(fixture, tmp_path, record, backup, meta)
    before = _tables(store.path)
    with monkeypatch.context() as scoped:
        scoped.setattr(ja, "MAX_ARCHIVED_JOBS", 0)
        with pytest.raises(WorkspaceBackupError, match="ARCHIVE_CAPACITY_EXCEEDED"):
            apply(fixture, tmp_path, backup, plan)
    with closing(sqlite3.connect(store.path)) as con:
        con.execute(
            "CREATE TRIGGER fail_archive BEFORE INSERT ON job_archives "
            "BEGIN SELECT RAISE(ABORT,'injected'); END"
        )
    with pytest.raises(WorkspaceBackupError, match="WORKSPACE_INVALID"):
        apply(fixture, tmp_path, backup, plan)
    assert _tables(store.path) == before


def test_backup_missing_or_changed_and_replay_conflict(fixture, tmp_path):
    record, backup, meta = prepare(fixture, tmp_path)
    plan = plan_for(fixture, tmp_path, record, backup, meta)
    apply(fixture, tmp_path, backup, plan)
    changed = plan.model_copy(
        update={"terminal_before": plan.terminal_before - timedelta(microseconds=1)}
    )
    with pytest.raises(WorkspaceBackupError, match="ARCHIVE_REPLAY_CONFLICT"):
        apply(fixture, tmp_path, backup, changed)
    with pytest.raises(WorkspaceBackupError):
        apply(fixture, tmp_path, tmp_path / "absent.zip", plan)
    with pytest.raises(WorkspaceBackupError, match="WORKSPACE_HASH_MISMATCH"):
        read_archived_result(backup, record.job_id, expected_sha256="0" * 64)


@pytest.mark.parametrize("payload", [b"{", b'{"a":1,"a":2}', b"x" * 16385, b"[]"])
def test_bounded_plan_loader_rejects_bad_documents(tmp_path, payload):
    path = tmp_path / "bad.json"
    path.write_bytes(payload)
    with pytest.raises(WorkspaceBackupError):
        load_archive_plan(path)


def test_cli_review_apply_readback_and_error_boundaries(fixture, tmp_path):
    record, backup, meta = prepare(fixture, tmp_path, migrate=False)
    runner = CliRunner()
    store = fixture[1]
    result = runner.invoke(cli, ["jobs", "enable-archiving", str(store.path)])
    assert result.exit_code == 0, result.output
    assert (
        runner.invoke(cli, ["jobs", "archive-info", str(store.path), record.job_id]).exit_code == 3
    )
    args = [str(tmp_path / "candidates.db"), str(store.path), str(backup)]
    output = tmp_path / "review.json"
    plan_args = [
        "workspace",
        "plan-job-archive",
        *args,
        record.job_id,
        "--sha256",
        meta["sha256"],
        "--revision",
        str(record.revision),
        "--terminal-before",
        datetime.now(UTC).isoformat(),
        "--output",
        str(output),
    ]
    result = runner.invoke(cli, plan_args)
    assert result.exit_code == 0, result.output
    plan = load_archive_plan(output)
    fp = json.loads(result.stdout)["plan_fingerprint"]
    assert fp == sha256_fingerprint(plan.model_dump(mode="json"))
    duplicate = runner.invoke(cli, plan_args)
    assert duplicate.exit_code == 3 and str(tmp_path) not in duplicate.output
    result = runner.invoke(
        cli, ["workspace", "archive-job", *args, str(output), "--confirm-plan", fp]
    )
    assert result.exit_code == 0, result.output
    receipt = JobArchiveReceipt.model_validate_json(result.stdout)
    info = runner.invoke(cli, ["jobs", "archive-info", str(store.path), record.job_id])
    assert JobArchiveReceipt.model_validate_json(info.stdout) == receipt
    for extra in [[], ["--assembly"]]:
        result = runner.invoke(
            cli,
            [
                "workspace",
                "archived-result",
                str(backup),
                record.job_id,
                "--sha256",
                meta["sha256"],
                *extra,
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)


@pytest.mark.parametrize(
    "field,value",
    [("planned_at", "2026-01-01T00:00:00"), ("result_size_bytes", 0), ("result_fingerprint", None)],
)
def test_plan_model_coherence(fixture, tmp_path, field, value):
    record, backup, meta = prepare(fixture, tmp_path)
    raw = plan_for(fixture, tmp_path, record, backup, meta).model_dump(mode="json")
    raw[field] = value
    with pytest.raises(ValueError):
        JobArchivePlan.model_validate(raw)


def test_receipt_model_and_database_tampering_rejected(fixture, tmp_path):
    _, store, _ = fixture
    record, backup, meta = prepare(fixture, tmp_path)
    receipt = apply(fixture, tmp_path, backup, plan_for(fixture, tmp_path, record, backup, meta))
    raw = receipt.model_dump(mode="json")
    for change in [
        {"plan_fingerprint": "sha256:" + "0" * 64},
        {"archived_at": "2020-01-01T00:00:00Z"},
    ]:
        with pytest.raises(ValueError):
            JobArchiveReceipt.model_validate({**raw, **change})
    with closing(sqlite3.connect(store.path)) as con:
        con.execute("DROP TRIGGER archives_no_update")
        con.execute("UPDATE job_archives SET receipt=?", (json.dumps(raw),))
        con.commit()
    with pytest.raises(JobError, match="JOB_STORE_CORRUPT"):
        store.show(record.job_id)
    assert canonical_json(raw) != json.dumps(raw)


def test_backup_v4_empty_and_missing_job(fixture, tmp_path):
    _, store, _ = fixture
    store.enable_archiving()
    backup = tmp_path / "empty.zip"
    meta = backup_workspace(tmp_path / "candidates.db", store.path, backup)
    assert verify_workspace_backup(backup)["archived_job_count"] == 0
    with pytest.raises(WorkspaceBackupError, match="ARCHIVE_JOB_NOT_FOUND"):
        read_archived_result(backup, "job-" + "a" * 32, expected_sha256=meta["sha256"])


def test_dashboard_archived_detail_and_stale_result_actions(fixture, tmp_path):
    app, store, _ = fixture
    record, backup, meta = prepare(fixture, tmp_path)
    result = store.result(record.job_id)
    receipt = apply(fixture, tmp_path, backup, plan_for(fixture, tmp_path, record, backup, meta))
    with client_for(app, store) as client:
        session = _activate(client)
        route = f"/app/api/jobs/{record.job_id}"
        detail = client.get(route + "?project_id=sample-api")
        assert detail.status_code == 200 and detail.headers["Cache-Control"] == "no-store"
        assert detail.json()["archive"] == receipt.model_dump(mode="json")
        assert detail.json()["result"] is None
        assert "request_key" not in detail.text and "content_base64" not in detail.text
        for action, command in [
            ("assembly-export", export_command(record, result)),
            ("bind-evidence", binding_command(record, result)),
        ]:
            response = client.post(
                route + f"/{action}?project_id=sample-api",
                json=command,
                headers=write_headers(session, key="archival:stale-browser"),
            )
            assert response.status_code == 409
            assert "JOB_RESULT_NOT_BINDABLE" in response.text
    assert app.get_history(record.candidate_id).evidence_binding is None


@pytest.mark.parametrize("lock_target", ["jobs.db", "candidates.db"])
def test_live_lock_conflict_rejects_without_changing_payload(fixture, tmp_path, lock_target):
    record, backup, meta = prepare(fixture, tmp_path)
    plan = plan_for(fixture, tmp_path, record, backup, meta)
    before = _tables(fixture[1].path)
    with closing(sqlite3.connect(tmp_path / lock_target)) as con:
        con.execute("BEGIN IMMEDIATE")
        with pytest.raises(WorkspaceBackupError, match="WORKSPACE_BUSY"):
            apply(fixture, tmp_path, backup, plan)
    assert _tables(fixture[1].path) == before


def test_deadline_after_receipt_insert_rolls_back(fixture, tmp_path, monkeypatch):
    from forgegate.candidates.backups import StoreBackupError

    record, backup, meta = prepare(fixture, tmp_path)
    plan = plan_for(fixture, tmp_path, record, backup, meta)
    before = _tables(fixture[1].path)

    def expired(_deadline):
        raise StoreBackupError("BACKUP_TIMEOUT")

    monkeypatch.setattr(ja, "_check_time", expired)
    with pytest.raises(WorkspaceBackupError, match="WORKSPACE_TIMEOUT"):
        apply(fixture, tmp_path, backup, plan)
    assert _tables(fixture[1].path) == before


def test_candidate_and_job_writers_reserved_during_final_recheck(fixture, tmp_path, monkeypatch):
    record, backup, meta = prepare(fixture, tmp_path)
    plan = plan_for(fixture, tmp_path, record, backup, meta)
    real = ja._candidate
    probed = []

    def probe(con, database, reviewed):
        real(con, database, reviewed)
        for path in (database, fixture[1].path):
            with (
                closing(sqlite3.connect(path, timeout=0)) as other,
                pytest.raises(sqlite3.OperationalError, match="locked"),
            ):
                other.execute("BEGIN IMMEDIATE")
            probed.append(path.name)

    monkeypatch.setattr(ja, "_candidate", probe)
    apply(fixture, tmp_path, backup, plan)
    assert probed == ["candidates.db", "jobs.db"]


def test_no_result_cannot_claim_assembly_and_cli_cannot_export_one(fixture, tmp_path):
    record, backup, meta = prepare(fixture, tmp_path, "CANCELLED")
    raw = plan_for(fixture, tmp_path, record, backup, meta).model_dump(mode="json")
    raw["assembly_id"] = "sha256:" + "a" * 64
    with pytest.raises(ValueError, match="assembly requires result"):
        JobArchivePlan.model_validate(raw)
    # A rejected collection has retained diagnostics but no assembled evidence.
    app, store, request = fixture
    import base64

    changed = request.model_dump(mode="json")
    changed["collection"]["reports"][0]["content_base64"] = base64.b64encode(
        b"<!DOCTYPE x><testsuite/>"
    ).decode()
    reject = store.submit(
        cj.CollectionJobRequest.model_validate(changed), app, key="archive:rejected"
    )
    store.run(reject.job_id, 0, app)
    target = tmp_path / "rejected.zip"
    receipt = backup_workspace(tmp_path / "candidates.db", store.path, target)
    output = CliRunner().invoke(
        cli,
        [
            "workspace",
            "archived-result",
            str(target),
            reject.job_id,
            "--sha256",
            receipt["sha256"],
            "--assembly",
        ],
    )
    assert output.exit_code == 3 and "ARCHIVE_ASSEMBLY_UNAVAILABLE" in output.output


def test_previously_exported_result_can_bind_later_with_dependency_retained(fixture, tmp_path):
    app, store, request = fixture
    record, backup, meta = prepare(fixture, tmp_path)
    assembly = store.result(record.job_id).assembly
    apply(fixture, tmp_path, backup, plan_for(fixture, tmp_path, record, backup, meta))
    app.bind_evidence(
        request.candidate_id,
        CandidateBindEvidenceCommand(assembly=assembly, bound_at=datetime.now(UTC)),
        idempotency_key="archive:external-later-bind",
    )
    target = tmp_path / "late-binding.zip"
    receipt = backup_workspace(tmp_path / "candidates.db", store.path, target)
    retained = plan_workspace_retention(
        target,
        expected_sha256=receipt["sha256"],
        as_of=datetime.now(UTC),
        terminal_before=datetime.now(UTC) - timedelta(seconds=1),
    )
    assert retained["jobs"][0]["result_bound"] is True
    assert receipt["external_archive_dependencies"] == [meta["sha256"]]
