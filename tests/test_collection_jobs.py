import base64
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import forgegate.collection_jobs as jobs
from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    ProjectRegisterCommand,
)
from forgegate.cli import app as cli
from forgegate.collection_jobs_cli import load_request
from forgegate.config import load_config
from forgegate.domain.models import ProjectConfig

NOW = datetime(2026, 9, 1, tzinfo=UTC)
XML = b'<testsuite tests="4" failures="0" errors="0" skipped="0" time="0.5"/>'


@pytest.fixture
def fixture(tmp_path, repository_root):
    application = CandidateApplication.for_database(tmp_path / "candidates.db")
    application.initialize()
    config = load_config(repository_root / "examples/dashboard-multi-report/forgegate.yaml")
    assert isinstance(config, ProjectConfig)
    application.register_project(
        ProjectRegisterCommand(config=config, registered_at=NOW), idempotency_key="project:jobs"
    )
    candidate = application.create_candidate(
        CandidateCreateCommand(
            project_id="sample-api",
            version="jobs-test",
            commit_sha="a" * 40,
            release_track="pull-request",
            created_at=NOW,
        ),
        idempotency_key="candidate",
    )
    application.advance_candidate(
        candidate.candidate_id,
        CandidateAdvanceCommand(
            to_status="COLLECTING",
            expected_revision=0,
            occurred_at=NOW,
        ),
        idempotency_key="collecting",
    )
    request = jobs.CollectionJobRequest(
        candidate_id=candidate.candidate_id,
        collection={
            "expected_revision": 1,
            "reported_commit": "a" * 40,
            "reports": [
                {
                    "format": "junit",
                    "content_base64": base64.b64encode(XML).decode(),
                    "source_tool": "synthetic",
                    "source_version": "1",
                    "collected_at": NOW,
                }
            ],
        },
    )
    store = jobs.CollectionJobStore(tmp_path / "jobs.db")
    store.initialize()
    return application, store, request


def test_restart_replay_result_and_separate_binding(fixture):
    app, store, request = fixture
    before = app.get_history(request.candidate_id)
    first = store.submit(request, app, key="one")
    assert store.submit(request, app, key="one") == first
    assert "content_base64" not in first.model_dump_json()
    store = jobs.CollectionJobStore(store.path)
    assert store.show(first.job_id).state == "QUEUED"
    complete = store.run(first.job_id, 0, app)
    assert complete.state == "SUCCEEDED" and complete.revision == 2
    assert app.get_history(request.candidate_id) == before
    result = jobs.CollectionJobStore(store.path).result(first.job_id)
    assert result.assembly.bundle.evidence[0].value["total"] == 4
    assert store.submit(request, app, key="one") == complete
    with sqlite3.connect(store.path) as con:
        assert con.execute("select input,lease from jobs").fetchone() == (None, None)
        assert con.execute("select count(*) from events").fetchone()[0] == 3
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("delete from events")
    app.bind_evidence(
        request.candidate_id,
        CandidateBindEvidenceCommand(assembly=result.assembly, bound_at=datetime.now(UTC)),
        idempotency_key="explicit-bind",
    )
    with pytest.raises(jobs.JobError, match="ALREADY_BOUND"):
        store.submit(request, app, key="two")


@pytest.mark.parametrize(
    "content,retain,state",
    [
        (b'<testsuite tests="2"><testcase name="x"/></testsuite>', False, "REVIEW_REQUIRED"),
        (b'<testsuite tests="2"><testcase name="x"/></testsuite>', True, "SUCCEEDED"),
        (b"<!DOCTYPE x><testsuite/>", False, "REJECTED"),
    ],
)
def test_warning_and_rejection(fixture, content, retain, state):
    app, store, request = fixture
    raw = request.model_dump()
    raw["collection"]["reports"][0]["content_base64"] = base64.b64encode(content).decode()
    raw["collection"]["retain_warnings"] = retain
    record = store.submit(jobs.CollectionJobRequest.model_validate(raw), app, key="case")
    assert store.run(record.job_id, 0, app).state == state
    assert (store.result(record.job_id).assembly is not None) == (state == "SUCCEEDED")


def test_cancel_claim_race_and_late_completion(fixture):
    app, store, request = fixture
    first = store.submit(request, app, key="race")

    def claim():
        try:
            return jobs.CollectionJobStore(store.path).claim(first.job_id, 0)
        except jobs.JobError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(lambda _: claim(), range(2)))
    won = [value for value in values if value is not None]
    assert len(won) == 1
    running, token, _ = won[0]
    assert store.cancel(first.job_id, running.revision).state == "CANCELLED"
    with pytest.raises(jobs.JobError, match="LEASE_LOST"):
        store.finish(first.job_id, token, None)
    for method in (store.cancel, store.claim):
        with pytest.raises(jobs.JobError, match="STATE_CONFLICT"):
            method(first.job_id, 0)
    with pytest.raises(jobs.JobError, match="RESULT_UNAVAILABLE"):
        store.result(first.job_id)


def test_recovery_is_explicit_and_expired_only(fixture, monkeypatch):
    app, store, request = fixture
    first = store.submit(request, app, key="crash")
    running, token, _ = store.claim(first.job_id, 0)
    with pytest.raises(jobs.JobError, match="RECOVERY_NOT_DUE"):
        jobs.CollectionJobStore(store.path).recover(first.job_id, 1)
    monkeypatch.setattr(jobs, "_now", lambda: running.lease_expires_at)
    with pytest.raises(jobs.JobError, match="LEASE_LOST"):
        store.finish(first.job_id, token, None)
    recovered = jobs.CollectionJobStore(store.path).recover(first.job_id, 1)
    assert recovered.state == "INTERRUPTED" and recovered.error_code == "JOB_LEASE_EXPIRED"
    assert recovered.source_bytes == "released_logically"


def test_parser_failure_is_retained_and_sanitized(fixture, monkeypatch):
    app, store, request = fixture
    record = store.submit(request, app, key="fail")

    def fail(*args):
        raise RuntimeError("private-path-and-token")

    monkeypatch.setattr(jobs, "preview_collection", fail)
    failed = store.run(record.job_id, 0, app)
    assert failed.state == "FAILED" and "private-path" not in failed.model_dump_json()


def test_cancellation_during_parse_wins(fixture, monkeypatch):
    app, store, request = fixture
    record = store.submit(request, app, key="cancel-parse")
    real = jobs.preview_collection

    def cancel(*args):
        store.cancel(record.job_id, 1)
        return real(*args)

    monkeypatch.setattr(jobs, "preview_collection", cancel)
    assert store.run(record.job_id, 0, app).state == "CANCELLED"


def test_capacity_and_conflicting_replay(fixture, monkeypatch):
    app, store, request = fixture
    first = store.submit(request, app, key="one")
    raw = request.model_dump()
    raw["collection"]["retain_warnings"] = True
    with pytest.raises(jobs.JobError, match="KEY_CONFLICT"):
        store.submit(jobs.CollectionJobRequest.model_validate(raw), app, key="one")
    for setting in ("MAX_INPUT_BYTES", "MAX_JOBS"):
        with monkeypatch.context() as patch:
            patch.setattr(jobs, setting, 0)
            with pytest.raises(jobs.JobError, match="CAPACITY"):
                store.submit(request, app, key="two")
    assert store.submit(request, app, key="one") == first
    monkeypatch.setattr(jobs, "MAX_RESULT_BYTES", 0)
    assert store.run(first.job_id, 0, app).state == "FAILED"


def test_paging_cancel_and_invalid_commands(fixture, monkeypatch):
    app, store, request = fixture
    records = [store.submit(request, app, key=f"k{i}") for i in range(3)]
    first = store.list_jobs(limit=2)
    assert len(first) == 2
    assert len(store.list_jobs(after=first[-1].job_id)) == 1
    assert store.list_jobs(after="z") == []
    for limit in (0, 101):
        with pytest.raises(jobs.JobError, match="PAGE_INVALID"):
            store.list_jobs(limit=limit)
    with pytest.raises(jobs.JobError, match="KEY_INVALID"):
        store.submit(request, app, key="contains spaces")
    with pytest.raises(jobs.JobError, match="NOT_FOUND"):
        store.show("missing")
    monkeypatch.setattr(jobs, "_now", lambda: records[0].created_at - timedelta(seconds=1))
    with pytest.raises(jobs.JobError, match="CLOCK_REGRESSED"):
        store.cancel(records[0].job_id, 0)
    assert store.show(records[0].job_id) == records[0]


@pytest.mark.parametrize("column,value", [("record", "{}"), ("input", "{}"), ("lease", "fake")])
def test_tampering_is_rejected(fixture, column, value):
    app, store, request = fixture
    record = store.submit(request, app, key="one")
    with sqlite3.connect(store.path) as con:
        con.execute(f"update jobs set {column}=?", (value,))
    with pytest.raises(jobs.JobError, match="CORRUPT"):
        store.show(record.job_id)


def test_store_create_refuses_existing_and_foreign_database(tmp_path):
    store = jobs.CollectionJobStore(tmp_path / "jobs.db")
    store.initialize()
    before = store.path.read_bytes()
    with pytest.raises(jobs.JobError, match="CREATE_FAILED"):
        store.initialize()
    assert store.path.read_bytes() == before
    with pytest.raises(jobs.JobError, match="PATH_INVALID"):
        jobs.CollectionJobStore(tmp_path / "missing" / "jobs.db")
    with pytest.raises(jobs.JobError, match="IO_FAILED"):
        jobs.CollectionJobStore(tmp_path / "absent.db").list_jobs()
    other = tmp_path / "foreign.db"
    with sqlite3.connect(other) as con:
        con.execute("create table keep(value)")
    original = other.read_bytes()
    with pytest.raises(jobs.JobError, match="VERSION_INVALID"):
        jobs.CollectionJobStore(other).list_jobs()
    assert other.read_bytes() == original


def test_initialize_closes_its_sqlite_handle(tmp_path, monkeypatch):
    # Retain the connection so garbage collection cannot conceal an open handle.
    connection = sqlite3.connect(tmp_path / "actual.db")
    monkeypatch.setattr(jobs.sqlite3, "connect", lambda *args, **kwargs: connection)
    jobs.CollectionJobStore(tmp_path / "exclusive-marker.db").initialize()
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("select 1")


def test_cli_flow_and_private_error(fixture, tmp_path):
    app, store, request = fixture
    runner = CliRunner()
    path = tmp_path / "request.json"
    path.write_text(request.model_dump_json(), encoding="utf-8")

    def call(*args):
        return runner.invoke(cli, ["jobs", *map(str, args)])

    submitted = call(
        "submit", store.path, path, "--database", app.repository.database_path, "--key", "cli"
    )
    assert submitted.exit_code == 0, submitted.output
    job_id = json.loads(submitted.output)["job_id"]
    assert call("show", store.path, job_id).exit_code == 0
    assert len(json.loads(call("list", store.path).output)) == 1
    assert (
        call(
            "run", store.path, job_id, "--database", app.repository.database_path, "--revision", 0
        ).exit_code
        == 0
    )
    assert (
        json.loads(call("result", store.path, job_id, "--assembly").output)["schema_version"]
        == "forgegate.evidence-bundle-assembly.v1"
    )
    assert call("result", store.path, job_id).exit_code == 0
    assert call("init", tmp_path / "new.db").exit_code == 0
    assert call("init", store.path).exit_code == 3
    path.write_text('{"secret":"private-token", "secret":"duplicate"}', encoding="utf-8")
    error = call(
        "submit", store.path, path, "--database", app.repository.database_path, "--key", "bad"
    )
    assert error.exit_code == 3 and "private-token" not in error.output
    assert "JOB_INPUT_DUPLICATE_KEY" in error.output


@pytest.mark.parametrize(
    "raw", ["[]", '{"schema_version":"bad"}', '{"x":NaN}', "[" * 13 + "]" * 13]
)
def test_strict_loader_rejects_invalid(tmp_path, raw):
    path = tmp_path / "request.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        load_request(path)


@pytest.mark.parametrize(
    "change",
    [
        {"created_at": datetime(2026, 1, 1)},
        {"updated_at": NOW},
        {"state": "RUNNING"},
        {"result_fingerprint": "sha256:" + "a" * 64},
        {"source_bytes": "released_logically"},
        {"error_code": "JOB_EXECUTION_FAILED"},
        {"revision": 1},
    ],
)
def test_record_rejects_inconsistent_fields(fixture, change):
    app, store, request = fixture
    record = store.submit(request, app, key="one")
    with pytest.raises(ValidationError):
        jobs.CollectionJobRecord.model_validate({**record.model_dump(), **change})


def test_candidate_conflicts_and_unexpected_store_error(fixture, monkeypatch):
    from forgegate.candidates import CandidateStoreError

    app, store, request = fixture
    raw = request.model_dump()
    raw["collection"]["reported_commit"] = "b" * 40
    with pytest.raises(jobs.JobError, match="CANDIDATE_CONFLICT"):
        store.submit(jobs.CollectionJobRequest.model_validate(raw), app, key="wrong-commit")

    def fail(*args):
        raise CandidateStoreError("STORE_TEST_FAILURE", "private")

    monkeypatch.setattr(CandidateApplication, "get_evidence", fail)
    with pytest.raises(CandidateStoreError):
        store.submit(request, app, key="store-failure")
    assert store.list_jobs() == []


@pytest.mark.parametrize("changed_call", [1, 2])
def test_candidate_fingerprint_change_discards_result(fixture, monkeypatch, changed_call):
    app, store, request = fixture
    record = store.submit(request, app, key="changed")
    original = jobs._candidate
    calls = 0

    def changed(*args):
        nonlocal calls
        calls += 1
        project, fingerprint = original(*args)
        return project, "sha256:" + "0" * 64 if calls == changed_call else fingerprint

    monkeypatch.setattr(jobs, "_candidate", changed)
    assert store.run(record.job_id, 0, app).state == "FAILED"
    with pytest.raises(jobs.JobError, match="RESULT_UNAVAILABLE"):
        store.result(record.job_id)


def test_result_identity_coherence_and_corruption(fixture):
    app, store, request = fixture
    record = store.submit(request, app, key="result")
    running, token, _ = store.claim(record.job_id, 0)
    preview = jobs.preview_collection(request.candidate_id, request.collection)
    result = jobs.CollectionJobResult(
        job_id=record.job_id, collections=preview.collections, assembly=preview.assembly
    )
    with pytest.raises(jobs.JobError, match="RESULT_MISMATCH"):
        store.finish(record.job_id, token, result.model_copy(update={"job_id": "job-" + "0" * 32}))
    with pytest.raises(ValidationError, match="duplicate"):
        jobs.CollectionJobResult.model_validate(
            {**result.model_dump(), "collections": result.collections * 2}
        )
    other = result.model_dump()
    other["collections"][0]["collector_version"] = "different"
    with pytest.raises(ValidationError, match="collection mismatch"):
        jobs.CollectionJobResult.model_validate(other)
    rejected = request.model_dump()
    rejected["collection"]["reports"][0]["content_base64"] = base64.b64encode(
        b"<!DOCTYPE x>"
    ).decode()
    rejected_preview = jobs.preview_collection(
        request.candidate_id, jobs.CollectionJobRequest.model_validate(rejected).collection
    )
    with pytest.raises(ValidationError, match="complete collections"):
        jobs.CollectionJobResult.model_validate(
            {**result.model_dump(), "collections": rejected_preview.collections}
        )
    with pytest.raises(ValidationError, match="expire after"):
        jobs.CollectionJobRecord.model_validate(
            {**running.model_dump(), "lease_expires_at": running.updated_at}
        )
    assert store.finish(record.job_id, token, result).state == "SUCCEEDED"
    with sqlite3.connect(store.path) as con:
        con.execute("update jobs set result='{}'")
    with pytest.raises(jobs.JobError, match="CORRUPT"):
        store.result(record.job_id)


def test_cli_cancel_recover_and_review(fixture, tmp_path, monkeypatch):
    app, store, request = fixture
    runner = CliRunner()
    record = store.submit(request, app, key="cli-cancel")
    cancelled = runner.invoke(
        cli, ["jobs", "cancel", str(store.path), record.job_id, "--revision", "0"]
    )
    assert cancelled.exit_code == 0 and json.loads(cancelled.output)["state"] == "CANCELLED"
    record = store.submit(request, app, key="cli-recover")
    running, _, _ = store.claim(record.job_id, 0)
    with monkeypatch.context() as patch:
        patch.setattr(jobs, "_now", lambda: running.lease_expires_at)
        recovered = runner.invoke(
            cli, ["jobs", "recover", str(store.path), record.job_id, "--revision", "1"]
        )
        assert recovered.exit_code == 0 and json.loads(recovered.output)["state"] == "INTERRUPTED"
    raw = request.model_dump()
    raw["collection"]["reports"][0]["content_base64"] = base64.b64encode(b"<!DOCTYPE x>").decode()
    record = store.submit(jobs.CollectionJobRequest.model_validate(raw), app, key="cli-reject")
    rejected = runner.invoke(
        cli,
        [
            "jobs",
            "run",
            str(store.path),
            record.job_id,
            "--database",
            str(app.repository.database_path),
            "--revision",
            "0",
        ],
    )
    assert rejected.exit_code == 3 and json.loads(rejected.output)["state"] == "REJECTED"
    unavailable = runner.invoke(
        cli, ["jobs", "result", str(store.path), record.job_id, "--assembly"]
    )
    assert unavailable.exit_code == 3 and "JOB_ASSEMBLY_UNAVAILABLE" in unavailable.output
