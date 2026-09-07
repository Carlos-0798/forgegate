import hashlib
import json
import sqlite3
import time
from contextlib import closing

import pytest
from typer.testing import CliRunner

import forgegate.recovery_readiness as rr
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.cli import app as cli
from forgegate.job_archive_models import JobArchivePlan
from forgegate.workspace_backups import WorkspaceBackupError, backup_workspace, restore_workspace
from tests import test_collection_jobs as job_tests
from tests.test_job_archival import apply, plan_for, prepare
from tests.test_workspace_backups import _tables


@pytest.fixture
def fixture(tmp_path, repository_root):
    return job_tests.fixture.__wrapped__(tmp_path, repository_root)


def archived(fixture, tmp_path, state="SUCCEEDED", change=None):
    record, original, meta = prepare(fixture, tmp_path, state)
    plan = plan_for(fixture, tmp_path, record, original, meta)
    receipt = apply(fixture, tmp_path, original, plan)
    if change:
        raw = receipt.model_dump(mode="json")
        raw["plan"].update(change)
        raw["plan_fingerprint"] = sha256_fingerprint(raw["plan"])
        with closing(sqlite3.connect(fixture[1].path)) as con:
            trigger = con.execute(
                "SELECT sql FROM sqlite_master WHERE name='archives_no_update'"
            ).fetchone()[0]
            con.execute("DROP TRIGGER archives_no_update")
            con.execute("UPDATE job_archives SET receipt=?", (canonical_json(raw),))
            con.execute(trigger)
            con.commit()
    target = tmp_path / "after.zip"
    after = backup_workspace(tmp_path / "candidates.db", fixture[1].path, target)
    return target, after["sha256"], original, meta["sha256"], record, plan


@pytest.mark.parametrize("state", ["SUCCEEDED", "CANCELLED"])
def test_exact_readiness_restore_and_no_source_mutation(fixture, tmp_path, state):
    root, digest, original, old_digest, record, _ = archived(fixture, tmp_path, state)
    sources = [root, original, fixture[1].path, tmp_path / "candidates.db"]
    before = [p.read_bytes() for p in sources]
    report = rr.check_recovery_readiness(
        root, expected_sha256=digest, dependencies={old_digest: original}
    )
    assert report.status == "READY" and report.archived_job_count == 1
    dependency = report.dependencies[0]
    assert dependency.job_ids == [record.job_id]
    assert dependency.result_payloads_verified == (state == "SUCCEEDED")
    assert dependency.jobs_without_result == (state == "CANCELLED")
    assert report.restore == "NOT_PERFORMED"
    assert report.producer_authenticity == "NOT_VERIFIED"
    assert [p.read_bytes() for p in sources] == before
    assert str(tmp_path) not in report.model_dump_json()
    restore_workspace(root, tmp_path / "recovered", expected_sha256=digest)
    assert _tables(tmp_path / "recovered/jobs.db") == _tables(fixture[1].path)


@pytest.mark.parametrize("v4", [False, True])
def test_no_archives_need_no_external_payloads(fixture, tmp_path, v4):
    if v4:
        fixture[1].enable_archiving()
    root = tmp_path / "empty.zip"
    meta = backup_workspace(tmp_path / "candidates.db", fixture[1].path, root)
    report = rr.check_recovery_readiness(root, expected_sha256=meta["sha256"], dependencies={})
    assert report.status == "READY" and report.dependencies == [] and report.archived_job_count == 0


@pytest.mark.parametrize("kind", ["unsupplied", "missing", "wrong", "sidecar", "directory"])
def test_unavailable_dependency_never_ready(fixture, tmp_path, kind):
    root, digest, original, old_digest, _, _ = archived(fixture, tmp_path)
    mappings = {old_digest: original}
    expected = "FAILED"
    if kind == "unsupplied":
        mappings = {}
        expected = "NOT_SUPPLIED"
    elif kind == "missing":
        mappings[old_digest] = tmp_path / "private-missing.zip"
    elif kind == "wrong":
        mappings[old_digest] = root
    elif kind == "sidecar":
        original.with_name(original.name + "-wal").write_bytes(b"private-data")
    else:
        mappings[old_digest] = tmp_path
    report = rr.check_recovery_readiness(root, expected_sha256=digest, dependencies=mappings)
    assert report.status == "INCOMPLETE" and report.dependencies[0].status == expected
    assert report.dependencies[0].result_payloads_verified == 0
    assert "private-" not in report.model_dump_json()


@pytest.mark.parametrize(
    "change,code",
    [
        ({"backup_manifest_fingerprint": "sha256:" + "0" * 64}, "RECOVERY_MANIFEST_MISMATCH"),
        ({"source_row_fingerprint": "sha256:" + "0" * 64}, "RECOVERY_JOB_MISMATCH"),
        ({"assembly_id": "sha256:" + "0" * 64}, "RECOVERY_JOB_MISMATCH"),
        ({"result_size_bytes": 1}, "RECOVERY_JOB_MISMATCH"),
    ],
)
def test_valid_zip_but_wrong_archive_association(fixture, tmp_path, change, code):
    root, digest, original, old_digest, _, _ = archived(fixture, tmp_path, change=change)
    report = rr.check_recovery_readiness(
        root, expected_sha256=digest, dependencies={old_digest: original}
    )
    assert report.status == "INCOMPLETE" and report.dependencies[0].error_code == code


def test_corrupt_dependency_with_matching_hash(fixture, tmp_path):
    corrupt = tmp_path / "corrupt.zip"
    corrupt.write_bytes(b"not-a-workspace-zip")
    corrupt_hash = hashlib.sha256(corrupt.read_bytes()).hexdigest()
    root, digest, _, _, _, _ = archived(fixture, tmp_path, change={"backup_sha256": corrupt_hash})
    report = rr.check_recovery_readiness(
        root, expected_sha256=digest, dependencies={corrupt_hash: corrupt}
    )
    assert (
        report.status == "INCOMPLETE" and report.dependencies[0].error_code == "WORKSPACE_INVALID"
    )


@pytest.mark.parametrize(
    "kind", ["root_hash", "root_missing", "map_hash", "unused", "limit", "timeout"]
)
def test_request_or_root_failure_raises(fixture, tmp_path, kind):
    root, digest, original, old_digest, _, _ = archived(fixture, tmp_path)
    mappings = {old_digest: original}
    timeout = 30
    if kind == "root_hash":
        digest = "0" * 64
    elif kind == "root_missing":
        root = tmp_path / "missing.zip"
    elif kind == "map_hash":
        mappings = {"invalid": original}
    elif kind == "unused":
        mappings = {"0" * 64: original}
    elif kind == "limit":
        mappings = {f"{i:064x}": original for i in range(1001)}
    else:
        timeout = float("nan")
    with pytest.raises(WorkspaceBackupError):
        rr.check_recovery_readiness(
            root, expected_sha256=digest, dependencies=mappings, timeout_seconds=timeout
        )


def test_one_shared_deadline_never_returns_ready(fixture, tmp_path, monkeypatch):
    root, digest, original, old_digest, _, _ = archived(fixture, tmp_path)
    monkeypatch.setattr(rr, "_deadline", lambda _: time.monotonic() - 1)
    with pytest.raises(WorkspaceBackupError, match="DEADLINE"):
        rr.check_recovery_readiness(
            root, expected_sha256=digest, dependencies={old_digest: original}
        )


def test_cli_status_exits_duplicate_and_path_privacy(fixture, tmp_path):
    root, digest, original, old_digest, _, _ = archived(fixture, tmp_path)
    runner = CliRunner()
    args = ["workspace", "recovery-check", str(root), "--sha256", digest]
    incomplete = runner.invoke(cli, args)
    assert incomplete.exit_code == 2 and json.loads(incomplete.stdout)["status"] == "INCOMPLETE"
    pair = ["--dependency", f"{old_digest}={original}"]
    ready = runner.invoke(cli, args + pair)
    assert ready.exit_code == 0 and json.loads(ready.stdout)["status"] == "READY"
    for extra, code in [
        (pair + pair, "RECOVERY_DUPLICATE_DEPENDENCY"),
        (["--dependency", "secret-invalid-path"], "RECOVERY_DEPENDENCY_MAP_INVALID"),
        (["--dependency", f"{old_digest}="], "RECOVERY_DEPENDENCY_MAP_INVALID"),
    ]:
        result = runner.invoke(cli, args + extra)
        assert result.exit_code == 3 and code in result.stderr
        assert str(tmp_path) not in result.output and "secret-invalid-path" not in result.output


def test_report_cannot_claim_ready_or_duplicate_success(fixture, tmp_path):
    root, digest, _, _, _, _ = archived(fixture, tmp_path)
    report = rr.check_recovery_readiness(root, expected_sha256=digest, dependencies={})
    raw = report.model_dump(mode="json")
    for change in [
        {"status": "READY"},
        {"archived_job_count": 0},
        {"checked_at": "2026-09-07T00:00:00"},
        {"dependencies": raw["dependencies"] * 2},
    ]:
        with pytest.raises(ValueError):
            rr.WorkspaceRecoveryReadiness.model_validate({**raw, **change})
    item = raw["dependencies"][0]
    for change in [
        {"result_payloads_verified": 1},
        {"status": "FAILED"},
        {"job_ids": ["bad"]},
        {"error_code": "PRIVATE_DATA"},
    ]:
        with pytest.raises(ValueError):
            rr.ArchiveDependencyCheck.model_validate({**item, **change})


def test_dependency_missing_job_and_absent_result_association(fixture, tmp_path):
    _, _, original, old_digest, _, plan = archived(fixture, tmp_path)
    raw = plan.model_dump(mode="json")
    missing = JobArchivePlan.model_validate({**raw, "job_id": "job-" + "0" * 32})
    with pytest.raises(WorkspaceBackupError, match="ARCHIVE_JOB_NOT_FOUND"):
        rr._check_dependency(original, old_digest, [missing], time.monotonic() + 30)


def test_shared_backup_checked_once_and_multi_generation_requirements(
    fixture, tmp_path, monkeypatch
):
    app, store, request = fixture
    first, original, meta = prepare(fixture, tmp_path)
    second = store.submit(request, app, key="second")
    second = store.run(second.job_id, 0, app)
    shared = tmp_path / "shared.zip"
    shared_meta = backup_workspace(tmp_path / "candidates.db", store.path, shared)
    for record in (first, second):
        apply(fixture, tmp_path, shared, plan_for(fixture, tmp_path, record, shared, shared_meta))
    third = store.submit(request, app, key="third")
    third = store.cancel(third.job_id, 0)
    middle = tmp_path / "middle.zip"
    middle_meta = backup_workspace(tmp_path / "candidates.db", store.path, middle)
    apply(fixture, tmp_path, middle, plan_for(fixture, tmp_path, third, middle, middle_meta))
    root = tmp_path / "final.zip"
    final_meta = backup_workspace(tmp_path / "candidates.db", store.path, root)
    calls = []
    original_check = rr._check_dependency

    def counted(path, digest, plans, deadline):
        calls.append(digest)
        return original_check(path, digest, plans, deadline)

    monkeypatch.setattr(rr, "_check_dependency", counted)
    mappings = {shared_meta["sha256"]: shared, middle_meta["sha256"]: middle}
    report = rr.check_recovery_readiness(
        root, expected_sha256=final_meta["sha256"], dependencies=mappings
    )
    assert report.status == "READY" and report.archived_job_count == 3
    assert calls == sorted(mappings)
    assert sorted(len(d.job_ids) for d in report.dependencies) == [1, 2]
    assert sum(d.result_payloads_verified for d in report.dependencies) == 2
    partial = rr.check_recovery_readiness(
        root, expected_sha256=final_meta["sha256"], dependencies={middle_meta["sha256"]: middle}
    )
    assert partial.status == "INCOMPLETE"
    assert [d.status for d in partial.dependencies].count("NOT_SUPPLIED") == 1
    assert meta["sha256"] not in mappings and original.exists()


def test_dependency_deadline_is_global_failure(fixture, tmp_path, monkeypatch):
    root, digest, original, old_digest, _, _ = archived(fixture, tmp_path)

    def expired(*args):
        monkeypatch.setattr(
            rr,
            "_check_time",
            lambda _: (_ for _ in ()).throw(rr.WorkspaceBackupError("WORKSPACE_DEADLINE_EXCEEDED")),
        )
        raise rr.WorkspaceBackupError("WORKSPACE_DEADLINE_EXCEEDED")

    monkeypatch.setattr(rr, "_check_dependency", expired)
    with pytest.raises(WorkspaceBackupError, match="DEADLINE"):
        rr.check_recovery_readiness(
            root, expected_sha256=digest, dependencies={old_digest: original}
        )
