import json
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

import forgegate.collection_jobs as jobs_module
from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateCreateCommand,
    ProjectRegisterCommand,
)
from forgegate.cli import app as cli
from forgegate.collection_jobs import JobCapacity, JobError, JobProjectUsage
from forgegate.config import load_config
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import ProjectConfig
from tests import test_collection_jobs as job_tests
from tests.test_dashboard import _activate
from tests.test_dashboard_jobs import client_for
from tests.test_job_archival import apply, plan_for


@pytest.fixture
def fixture(tmp_path, repository_root):
    return job_tests.fixture.__wrapped__(tmp_path, repository_root)


def test_v3_and_v4_capacity_and_project_usage(fixture, tmp_path):
    app, store, request = fixture
    first = store.submit(request, app, key="capacity:first")
    first = store.run(first.job_id, 0, app)
    queued = store.submit(request, app, key="capacity:queued")
    v3 = store.capacity()
    assert v3.model_dump() == {
        "schema_version": "forgegate.job-capacity.v1",
        "scope": "store",
        "store_version": 3,
        "archiving_enabled": False,
        "current_jobs": 2,
        "current_job_limit": 100,
        "current_job_slots_available": 98,
        "archived_jobs": 0,
        "archived_job_limit": 1000,
        "archived_job_slots_available": 0,
        "pending_input_bytes": len(jobs_module._json(request).encode()),
        "pending_input_limit_bytes": 16777216,
        "live_result_bytes": len(jobs_module._json(store.result(first.job_id)).encode()),
        "live_result_limit_bytes": 33554432,
        "external_backup_dependencies": [],
        "dependency_availability": "NOT_CHECKED",
        "physical_database_size": "NOT_REPORTED",
    }
    record, backup, meta = prepare_new_archive(app, store, request, tmp_path)
    plan = plan_for(fixture, tmp_path, record, backup, meta)
    receipt = apply(fixture, tmp_path, backup, plan)
    v4 = store.capacity()
    assert v4.store_version == 4 and v4.current_jobs == 2 and v4.archived_jobs == 1
    assert v4.current_job_slots_available == 98 and v4.archived_job_slots_available == 999
    assert v4.external_backup_dependencies == [receipt.plan.backup_sha256]
    usage = store.project_usage("sample-api")
    assert usage.current_jobs == 2 and usage.archived_jobs == 1
    assert usage.external_backup_dependencies == v4.external_backup_dependencies
    assert usage.store_capacity_remaining == "NOT_DISCLOSED"
    assert store.show(queued.job_id) == queued


def prepare_new_archive(app, store, request, tmp_path):
    record = store.submit(request, app, key="capacity:archive")
    record = store.run(record.job_id, 0, app)
    from forgegate.workspace_backups import backup_workspace

    backup = tmp_path / "capacity-before.zip"
    meta = backup_workspace(tmp_path / "candidates.db", store.path, backup)
    store.enable_archiving()
    return record, backup, meta


def test_cli_capacity_and_archive_filters(fixture, tmp_path):
    app, store, request = fixture
    record, backup, meta = prepare_new_archive(app, store, request, tmp_path)
    apply(fixture, tmp_path, backup, plan_for(fixture, tmp_path, record, backup, meta))
    current = store.submit(request, app, key="capacity:current")
    runner = CliRunner()
    result = runner.invoke(cli, ["jobs", "capacity", str(store.path)])
    assert result.exit_code == 0
    capacity = JobCapacity.model_validate_json(result.stdout)
    assert capacity.current_jobs == 1 and capacity.archived_jobs == 1
    assert capacity.dependency_availability == "NOT_CHECKED"
    archived = json.loads(
        runner.invoke(cli, ["jobs", "list", str(store.path), "--archive-filter", "archived"]).stdout
    )
    active = json.loads(
        runner.invoke(cli, ["jobs", "list", str(store.path), "--archive-filter", "current"]).stdout
    )
    assert [row["job_id"] for row in archived] == [record.job_id]
    assert [row["job_id"] for row in active] == [current.job_id]


def test_archive_filter_scans_beyond_first_hundred_identities(fixture, tmp_path, monkeypatch):
    app, store, request = fixture
    with monkeypatch.context() as scoped:
        scoped.setattr(jobs_module.secrets, "token_hex", lambda _size: "f" * 32)
        record, backup, meta = prepare_new_archive(app, store, request, tmp_path)
    apply(fixture, tmp_path, backup, plan_for(fixture, tmp_path, record, backup, meta))
    values = iter(f"{index:032x}" for index in range(100))
    monkeypatch.setattr(jobs_module.secrets, "token_hex", lambda _size: next(values))
    for index in range(100):
        store.submit(request, app, key=f"capacity:page:{index}")
    assert len(store.list_jobs(limit=100, archive_filter="current")) == 100
    assert [item.job_id for item in store.list_jobs(limit=100, archive_filter="archived")] == [
        record.job_id
    ]
    first = store.list_jobs(limit=100)
    assert len(first) == 100 and record.job_id not in {item.job_id for item in first}
    assert store.list_jobs(after=first[-1].job_id, limit=100)[0].job_id == record.job_id


def test_dashboard_usage_is_project_scoped_and_filters_archive(fixture, tmp_path, repository_root):
    app, store, request = fixture
    record, backup, meta = prepare_new_archive(app, store, request, tmp_path)
    apply(fixture, tmp_path, backup, plan_for(fixture, tmp_path, record, backup, meta))
    other_config = load_config(repository_root / "examples/sample-python-api/forgegate.yaml")
    assert isinstance(other_config, ProjectConfig)
    other_config = other_config.model_copy(
        update={
            "project": other_config.project.model_copy(
                update={"id": "other-project", "name": "Other project"}
            )
        }
    )
    other_config = ProjectConfig.model_validate_json(other_config.model_dump_json(by_alias=True))
    app.register_project(
        ProjectRegisterCommand(config=other_config, registered_at=datetime.now(UTC)),
        idempotency_key="capacity:other-project",
    )
    other = app.create_candidate(
        CandidateCreateCommand(
            project_id="other-project",
            version="1.0.0",
            commit_sha="b" * 40,
            release_track="pull-request",
            created_at=datetime.now(UTC),
        ),
        idempotency_key="capacity:other-candidate",
    )
    app.advance_candidate(
        other.candidate_id,
        CandidateAdvanceCommand(
            to_status=CandidateStatus.COLLECTING, expected_revision=0, occurred_at=datetime.now(UTC)
        ),
        idempotency_key="capacity:other-collecting",
    )
    other_request = request.model_copy(
        update={
            "candidate_id": other.candidate_id,
            "collection": request.collection.model_copy(update={"reported_commit": "b" * 40}),
        }
    )
    store.submit(other_request, app, key="capacity:other-job")
    with client_for(app, store) as client:
        _activate(client)
        archived = client.get(
            "/app/api/jobs", params={"project_id": "sample-api", "archive_filter": "archived"}
        )
        assert archived.status_code == 200
        body = archived.json()
        assert [row["job_id"] for row in body["jobs"]] == [record.job_id]
        assert body["archived_job_ids"] == [record.job_id]
        usage = JobProjectUsage.model_validate(body["project_usage"])
        assert usage.project_id == "sample-api" and usage.current_jobs == 0
        assert usage.archived_jobs == 1 and usage.store_capacity_remaining == "NOT_DISCLOSED"
        assert "other-project" not in archived.text
        current = client.get(
            "/app/api/jobs", params={"project_id": "sample-api", "archive_filter": "current"}
        )
        assert current.status_code == 200 and current.json()["jobs"] == []
        assert (
            client.get("/app/api/jobs?project_id=sample-api&archive_filter=bad").status_code == 422
        )


@pytest.mark.parametrize("archive_filter", ["bad", "ARCHIVED", ""])
def test_store_filter_rejects_unknown_value(fixture, archive_filter):
    with pytest.raises(JobError, match="JOB_ARCHIVE_FILTER_INVALID"):
        fixture[1].list_jobs(archive_filter=archive_filter)


def test_legacy_read_only_filter_treats_all_jobs_as_current(fixture):
    app, store, request = fixture
    current = store.submit(request, app, key="capacity:legacy")
    with store._transaction() as con:
        con.execute("PRAGMA user_version=2")
    assert store.list_jobs(archive_filter="current") == [current]
    assert store.list_jobs(archive_filter="archived") == []
    with pytest.raises(JobError, match="JOB_STORE_MIGRATION_REQUIRED"):
        store.capacity()


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": "project"},
        {"current_job_slots_available": 99},
        {"archived_job_slots_available": 999},
        {"store_version": 3, "archived_jobs": 1},
    ],
)
def test_capacity_model_fails_closed(changes):
    baseline = dict(
        store_version=4,
        archiving_enabled=True,
        current_jobs=0,
        current_job_slots_available=100,
        archived_jobs=0,
        archived_job_slots_available=1000,
        pending_input_bytes=0,
        live_result_bytes=0,
        external_backup_dependencies=[],
    )
    with pytest.raises(ValueError):
        JobCapacity.model_validate({**baseline, **changes})
