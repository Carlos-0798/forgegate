import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import forgegate.collection_jobs as jobs
from forgegate.api import ApiAuthenticator, create_api_app
from forgegate.cli import app as cli
from tests.api_auth_support import TEST_TRUST_STORE
from tests.test_collection_jobs import fixture
from tests.test_dashboard import ORIGIN, ORIGIN_HEADER, _activate, _producer_trust_store

job_fixture = fixture


def client_for(application, store, *, producer=False):
    return TestClient(
        create_api_app(
            application.repository.database_path,
            application=application,
            authenticator=ApiAuthenticator(
                _producer_trust_store() if producer else TEST_TRUST_STORE
            ),
            dashboard=True,
            dashboard_job_store_path=None if store is None else store.path,
        ),
        base_url=ORIGIN,
    )


def test_disabled_surface_and_no_implicit_initialization(job_fixture):
    application, _, _ = job_fixture
    with client_for(application, None) as client:
        assert client.get("/app/api/jobs?project_id=sample-api").status_code == 401
        _activate(client)
        result = client.get("/app/api/jobs?project_id=sample-api")
        assert result.json()["enabled"] is False and result.json()["jobs"] == []
        assert result.headers["Cache-Control"] == "no-store"
        assert (
            client.get("/app/api/jobs/job-" + "a" * 32 + "?project_id=sample-api").status_code
            == 503
        )


def test_scoped_list_detail_cancel_actor_and_nonmutation(job_fixture):
    application, store, request = job_fixture
    record = store.submit(request, application, key="browser:job")
    before = application.get_history(request.candidate_id)
    with client_for(application, store) as client:
        session = _activate(client)
        page = client.get("/app/api/jobs?project_id=sample-api").json()
        assert page["jobs"] == [record.model_dump(mode="json")] and page["enabled"]
        route = f"/app/api/jobs/{record.job_id}?project_id=sample-api"
        review = client.get(route)
        assert review.status_code == 200 and review.json()["events"][0]["actor"] is None
        assert "content_base64" not in review.text and "request_key" not in review.text
        cancelled = client.post(
            f"/app/api/jobs/{record.job_id}/cancel?project_id=sample-api",
            json={"expected_revision": 0},
            headers={**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]},
        )
        assert cancelled.status_code == 200 and cancelled.json()["state"] == "CANCELLED"
        after = client.get(route).json()
        assert after["events"][-1]["actor"]["identity_id"] == session["principal"]["identity_id"]
        assert after["events"][-1]["actor"]["role"] == "operator"
        assert len(after["events"]) == 2 and after["record"]["source_bytes"] == "released_logically"
        assert application.get_history(request.candidate_id) == before
        again = client.post(
            f"/app/api/jobs/{record.job_id}/cancel?project_id=sample-api",
            json={"expected_revision": 0},
            headers={**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]},
        )
        assert (
            again.status_code == 409
            and len(store.review(record.job_id, project_id="sample-api").events) == 2
        )


@pytest.mark.parametrize(
    "mode", ["producer", "csrf", "origin", "cross-project", "unknown-field", "bad-revision"]
)
def test_write_rejections_leave_job_unchanged(job_fixture, mode):
    application, store, request = job_fixture
    job = store.submit(request, application, key="reject")
    with client_for(application, store, producer=mode == "producer") as client:
        session = _activate(client, role="producer" if mode == "producer" else "operator")
        headers = {**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]}
        body = {"expected_revision": 0}
        project = "sample-api"
        if mode == "csrf":
            headers.pop("X-ForgeGate-CSRF")
        if mode == "origin":
            headers["Origin"] = "https://example.invalid"
        if mode == "cross-project":
            project = "forbidden-project"
        if mode == "unknown-field":
            body["actor"] = {"role": "operator"}
        if mode == "bad-revision":
            body["expected_revision"] = 4
        result = client.post(
            f"/app/api/jobs/{job.job_id}/cancel?project_id={project}", json=body, headers=headers
        )
        assert result.status_code == (422 if mode in {"unknown-field", "bad-revision"} else 403)
        assert store.show(job.job_id) == job
        if mode == "producer":
            assert client.get("/app/api/jobs?project_id=sample-api").status_code == 403
            assert (
                client.get(f"/app/api/jobs/{job.job_id}?project_id=sample-api").status_code == 403
            )


def test_filters_pagination_and_non_enumerating_lookup(job_fixture):
    application, store, request = job_fixture
    records = [store.submit(request, application, key=f"page:{index}") for index in range(27)]
    with client_for(application, store) as client:
        _activate(client)
        first = client.get("/app/api/jobs?project_id=sample-api").json()
        assert len(first["jobs"]) == 25 and first["has_more"]
        second = client.get(
            "/app/api/jobs",
            params={"project_id": "sample-api", "after_job_id": first["next_after_job_id"]},
        ).json()
        assert len(second["jobs"]) == 2 and not second["has_more"]
        assert len({j["job_id"] for j in first["jobs"] + second["jobs"]}) == len(records)
        assert (
            client.get(
                "/app/api/jobs",
                params={"project_id": "sample-api", "candidate_id": "cand-" + "0" * 24},
            ).json()["jobs"]
            == []
        )
        assert client.get("/app/api/jobs?project_id=forbidden").status_code == 403
        assert client.get("/app/api/jobs?project_id=sample-api&limit=26").status_code == 422
        assert client.get("/app/api/jobs?project_id=sample-api&after_job_id=bad").status_code == 422
        assert (
            client.get("/app/api/jobs/job-" + "0" * 32 + "?project_id=sample-api").status_code
            == 404
        )


def test_recover_expired_only_with_actor_and_revoke_late_result(job_fixture, monkeypatch):
    application, store, request = job_fixture
    job = store.submit(request, application, key="recover")
    running, token, _ = store.claim(job.job_id, 0)
    with client_for(application, store) as client:
        session = _activate(client)
        path = f"/app/api/jobs/{job.job_id}/recover?project_id=sample-api"
        headers = {**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]}
        assert client.post(path, json={"expected_revision": 1}, headers=headers).status_code == 409
        monkeypatch.setattr(jobs, "_now", lambda: running.lease_expires_at)
        result = client.post(path, json={"expected_revision": 1}, headers=headers)
        assert result.status_code == 200 and result.json()["state"] == "INTERRUPTED"
        assert store.review(job.job_id, project_id="sample-api").events[-1].actor is not None
        with pytest.raises(jobs.JobError, match="LEASE_LOST"):
            store.finish(job.job_id, token, None)


def test_completed_result_is_exact_and_no_binding(job_fixture):
    application, store, request = job_fixture
    job = store.submit(request, application, key="completed")
    store.run(job.job_id, 0, application)
    before = application.get_history(request.candidate_id)
    with client_for(application, store) as client:
        _activate(client)
        review = client.get(f"/app/api/jobs/{job.job_id}?project_id=sample-api").json()
        assert review["result"] == store.result(job.job_id).model_dump(mode="json")
        assert review["result"]["collections"][0]["evidence"][0]["value"]["total"] == 4
        assert application.get_history(request.candidate_id) == before


def downgrade_fixture(store):
    with closing(sqlite3.connect(store.path)) as connection:
        connection.execute("ALTER TABLE events DROP COLUMN actor")
        connection.execute("PRAGMA user_version=1")
        connection.commit()


def test_explicit_migration_preserves_rows_and_refuses_implicit_upgrade(job_fixture):
    application, store, request = job_fixture
    job = store.submit(request, application, key="legacy")
    downgrade_fixture(store)
    original = store.path.read_bytes()
    assert store.review(job.job_id, project_id="sample-api").events[0].actor is None
    with pytest.raises(jobs.JobError, match="MIGRATION_REQUIRED"):
        client_for(application, store)
    assert store.path.read_bytes() == original
    result = CliRunner().invoke(cli, ["jobs", "migrate", str(store.path)])
    assert result.exit_code == 0
    assert store.show(job.job_id) == job
    assert store.review(job.job_id, project_id="sample-api").events[0].actor is None
    store.require_dashboard_store()
    store.migrate()
    with closing(sqlite3.connect(store.path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE events SET actor='{}'")


def test_actor_failure_rolls_back_state_and_migration(job_fixture, monkeypatch):
    application, store, request = job_fixture
    job = store.submit(request, application, key="actor")
    with client_for(application, store) as client:
        _activate(client)
        actor = client.app.state.dashboard_session_manager.session(
            client.cookies.get("forgegate_dashboard")
        )[1].audit_actor()
    with pytest.raises(jobs.JobError, match="ACTOR_INVALID"):
        store.cancel(job.job_id, 0, actor=actor.model_copy(update={"role": "producer"}))
    assert store.show(job.job_id) == job
    with pytest.raises(jobs.JobError, match="NOT_FOUND"):
        store.cancel(job.job_id, 0, project_id="other")
    with pytest.raises(jobs.JobError, match="NOT_FOUND"):
        store.recover(job.job_id, 0, project_id="other")
    with pytest.raises(jobs.JobError, match="NOT_FOUND"):
        store.review(job.job_id, project_id="other")
    downgrade_fixture(store)
    with pytest.raises(jobs.JobError, match="MIGRATION_REQUIRED"):
        store.cancel(job.job_id, 0, actor=actor)
    assert store.show(job.job_id) == job


def test_corrupt_history_blocks_review_and_wrong_store_refused(job_fixture, tmp_path):
    application, store, request = job_fixture
    job = store.submit(request, application, key="corrupt")
    with client_for(application, store) as client:
        _activate(client)
        with closing(sqlite3.connect(store.path)) as connection:
            connection.execute("DROP TRIGGER events_no_update")
            connection.execute("UPDATE events SET actor='{}'")
            connection.commit()
        response = client.get(f"/app/api/jobs/{job.job_id}?project_id=sample-api")
        assert (
            response.status_code == 503 and response.json()["error"]["code"] == "JOB_STORE_CORRUPT"
        )
        assert str(store.path) not in response.text
    with pytest.raises(jobs.JobError):
        client_for(application, jobs.CollectionJobStore(application.repository.database_path))


def test_migration_ddl_failure_is_transactional(job_fixture, monkeypatch):
    _, store, _ = job_fixture
    downgrade_fixture(store)
    original_connect = sqlite3.connect

    class FailVersionChange(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == "PRAGMA user_version=2":
                raise sqlite3.OperationalError("injected failure")
            return super().execute(sql, parameters)

    with monkeypatch.context() as patch:
        patch.setattr(
            jobs.sqlite3,
            "connect",
            lambda *args, **kwargs: original_connect(*args, **kwargs, factory=FailVersionChange),
        )
        with pytest.raises(jobs.JobError, match="IO_FAILED"):
            store.migrate()
    with closing(original_connect(store.path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert "actor" not in {row[1] for row in connection.execute("PRAGMA table_info(events)")}


def test_foreign_project_job_is_filtered_and_hidden(job_fixture):
    from forgegate.application import (
        CandidateAdvanceCommand,
        CandidateCreateCommand,
        ProjectRegisterCommand,
    )
    from forgegate.domain.models import ProjectConfig
    from tests.test_collection_jobs import NOW

    application, store, request = job_fixture
    config = application.get_project("sample-api").config.model_dump(mode="json", by_alias=True)
    config["project"]["id"] = "other-project"
    application.register_project(
        ProjectRegisterCommand(config=ProjectConfig.model_validate(config), registered_at=NOW),
        idempotency_key="other:project",
    )
    candidate = application.create_candidate(
        CandidateCreateCommand(
            project_id="other-project",
            version="other",
            commit_sha="a" * 40,
            release_track="pull-request",
            created_at=NOW,
        ),
        idempotency_key="other:candidate",
    )
    application.advance_candidate(
        candidate.candidate_id,
        CandidateAdvanceCommand(to_status="COLLECTING", expected_revision=0, occurred_at=NOW),
        idempotency_key="other:advance",
    )
    own = store.submit(request, application, key="own:job")
    foreign = store.submit(
        request.model_copy(update={"candidate_id": candidate.candidate_id}),
        application,
        key="foreign:job",
    )
    with client_for(application, store) as client:
        session = _activate(client)
        assert [
            job["job_id"]
            for job in client.get("/app/api/jobs?project_id=sample-api").json()["jobs"]
        ] == [own.job_id]
        response = client.get(f"/app/api/jobs/{foreign.job_id}?project_id=sample-api")
        assert response.status_code == 404 and candidate.candidate_id not in response.text
        response = client.post(
            f"/app/api/jobs/{foreign.job_id}/cancel?project_id=sample-api",
            json={"expected_revision": 0},
            headers={**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]},
        )
        assert response.status_code == 404 and store.show(foreign.job_id) == foreign
