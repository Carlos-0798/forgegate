import base64
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

import forgegate.collection_jobs as jobs
from tests.test_collection_jobs import fixture
from tests.test_dashboard import ORIGIN_HEADER, _activate
from tests.test_dashboard_jobs import client_for, downgrade_fixture

job_fixture = fixture


def headers(session, key="submit:one"):
    return {**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"], "Idempotency-Key": key}


def submit(client, request, session, *, key="submit:one", project="sample-api"):
    return client.post(
        f"/app/api/jobs?project_id={project}",
        json=request.model_dump(mode="json"),
        headers=headers(session, key),
    )


def run(client, job, session, revision=0):
    return client.post(
        f"/app/api/jobs/{job.job_id}/run?project_id=sample-api",
        json={"expected_revision": revision},
        headers=headers(session),
    )


def test_submit_run_exact_results_actors_replay_and_no_binding(job_fixture):
    application, store, request = job_fixture
    before = application.get_history(request.candidate_id)
    with client_for(application, store) as client:
        session = _activate(client)
        response = submit(client, request, session)
        assert response.status_code == 200
        job = jobs.CollectionJobRecord.model_validate(response.json())
        assert job.state == "QUEUED" and job.authority == "AUTHENTICATED_DASHBOARD"
        assert "content_base64" not in response.text and "request_key" not in response.text
        assert response.headers["Cache-Control"] == "no-store"
        assert submit(client, request, session).json() == response.json()
        assert len(store.list_jobs()) == 1
        completed = run(client, job, session)
        assert completed.status_code == 200 and completed.json()["state"] == "SUCCEEDED"
        review = store.review(job.job_id, project_id="sample-api")
        assert len(review.events) == 5 and all(e.actor is not None for e in review.events)
        assert review.record.execution_owner_id is not None
        assert review.record.lease_renewal_count == 2
        assert all(
            e.actor.identity_id == session["principal"]["identity_id"] for e in review.events
        )
        result = review.result
        assert result.collections[0].evidence[0].value["total"] == 4
        assert (
            result.collections[0].artifacts[0].sha256
            == jobs.hashlib.sha256(
                base64.b64decode(request.collection.reports[0].content_base64)
            ).hexdigest()
        )
        assert run(client, job, session).status_code == 409  # Never re-execute.
        assert submit(client, request, session).json() == completed.json()
        assert len(store.review(job.job_id, project_id="sample-api").events) == 5
        assert application.get_history(request.candidate_id) == before


@pytest.mark.parametrize(
    "mode",
    [
        "producer",
        "csrf",
        "origin",
        "scope",
        "missing-key",
        "bad-key",
        "unknown",
        "bytes",
        "revision",
        "commit",
    ],
)
def test_rejected_submission_never_creates_job(job_fixture, mode):
    application, store, request = job_fixture
    with client_for(application, store, producer=mode == "producer") as client:
        session = _activate(client, role="producer" if mode == "producer" else "operator")
        h = headers(session)
        body = request.model_dump(mode="json")
        project = "sample-api"
        if mode == "csrf":
            h.pop("X-ForgeGate-CSRF")
        if mode == "origin":
            h["Origin"] = "https://example.invalid"
        if mode == "scope":
            project = "other-project"
        if mode == "missing-key":
            h.pop("Idempotency-Key")
        if mode == "bad-key":
            h["Idempotency-Key"] = "bad key"
        if mode == "unknown":
            body["actor"] = {"role": "operator"}
        if mode == "bytes":
            body["collection"]["reports"][0]["content_base64"] = "!!!!"
        if mode == "revision":
            body["collection"]["expected_revision"] = 0
        if mode == "commit":
            body["collection"]["reported_commit"] = "b" * 40
        result = client.post(f"/app/api/jobs?project_id={project}", json=body, headers=h)
        expected = (
            403
            if mode in {"producer", "csrf", "origin", "scope"}
            else 409
            if mode in {"revision", "commit"}
            else 422
        )
        assert result.status_code == expected
        assert store.list_jobs() == []


def test_key_conflict_cli_namespace_and_disabled_store(job_fixture):
    application, store, request = job_fixture
    cli_job = store.submit(request, application, key="submit:one")
    with client_for(application, store) as client:
        session = _activate(client)
        browser_job = submit(client, request, session)
        assert browser_job.json()["job_id"] != cli_job.job_id
        changed = request.model_copy(
            update={"collection": request.collection.model_copy(update={"retain_warnings": True})}
        )
        assert submit(client, changed, session).status_code == 409
        assert len(store.list_jobs()) == 2
    with client_for(application, None) as client:
        session = _activate(client)
        assert submit(client, request, session).status_code == 503
        assert run(client, cli_job, session).status_code == 503


@pytest.mark.parametrize(
    "xml,state,retain",
    [
        (
            b'<testsuite tests="4" failures="1" errors="0" skipped="0" time="0.5"/>',
            "SUCCEEDED",
            False,
        ),
        (b'<testsuite tests="2"><testcase name="one"/></testsuite>', "REVIEW_REQUIRED", False),
        (b'<testsuite tests="2"><testcase name="one"/></testsuite>', "SUCCEEDED", True),
        (b"<!DOCTYPE x><testsuite/>", "REJECTED", False),
    ],
)
def test_execution_retains_failure_warning_and_rejection_semantics(job_fixture, xml, state, retain):
    application, store, request = job_fixture
    body = request.model_dump(mode="json")
    body["collection"]["reports"][0]["content_base64"] = base64.b64encode(xml).decode()
    body["collection"]["retain_warnings"] = retain
    request = jobs.CollectionJobRequest.model_validate(body)
    with client_for(application, store) as client:
        session = _activate(client)
        job = jobs.CollectionJobRecord.model_validate(submit(client, request, session).json())
        assert run(client, job, session).json()["state"] == state
        result = store.result(job.job_id)
        assert (result.assembly is not None) == (state == "SUCCEEDED")
        if b'failures="1"' in xml:
            assert result.collections[0].evidence[0].value["failures"] == 1
        assert application.get_history(request.candidate_id).evidence_binding is None


@pytest.mark.parametrize("mode", ["producer", "csrf", "origin", "revision"])
def test_run_authorization_and_revision_leave_queue_untouched(job_fixture, mode):
    application, store, request = job_fixture
    job = store.submit(request, application, key="denied:run")
    with client_for(application, store, producer=mode == "producer") as client:
        session = _activate(client, role="producer" if mode == "producer" else "operator")
        h = headers(session)
        if mode == "csrf":
            h.pop("X-ForgeGate-CSRF")
        if mode == "origin":
            h.pop("Origin")
        response = client.post(
            f"/app/api/jobs/{job.job_id}/run?project_id=sample-api",
            json={"expected_revision": 1 if mode == "revision" else 0},
            headers=h,
        )
        assert response.status_code == (409 if mode == "revision" else 403)
        assert store.show(job.job_id) == job


def test_foreground_single_flight_cancellation_wins_and_lock_releases(job_fixture, monkeypatch):
    application, store, request = job_fixture
    first = store.submit(request, application, key="race:one")
    second = store.submit(request, application, key="race:two")
    entered, finish = Event(), Event()
    original = jobs.preview_collection

    def blocked(*args, **kwargs):
        entered.set()
        assert finish.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(jobs, "preview_collection", blocked)
    with client_for(application, store) as client, ThreadPoolExecutor() as pool:
        session = _activate(client)
        future = pool.submit(run, client, first, session)
        try:
            assert entered.wait(10)
            busy = run(client, second, session)
            assert (
                busy.status_code == 429 and busy.json()["error"]["code"] == "DASHBOARD_JOB_RUN_BUSY"
            )
            assert store.show(second.job_id).state == "QUEUED"
            cancelled = client.post(
                f"/app/api/jobs/{first.job_id}/cancel?project_id=sample-api",
                json={"expected_revision": 1},
                headers=headers(session),
            )
            assert cancelled.json()["state"] == "CANCELLED"
        finally:
            finish.set()
        assert future.result(timeout=10).json()["state"] == "CANCELLED"
        assert len(store.review(first.job_id, project_id="sample-api").events) == 3
        assert run(client, second, session).json()["state"] == "SUCCEEDED"


def test_execution_exception_retains_failed_actor_not_private_error(job_fixture, monkeypatch):
    application, store, request = job_fixture
    job = store.submit(request, application, key="failed")

    def fail(*args):
        raise RuntimeError("private parser exception")

    monkeypatch.setattr(jobs, "preview_collection", fail)
    with client_for(application, store) as client:
        session = _activate(client)
        response = run(client, job, session)
        assert response.json()["state"] == "FAILED" and "private parser" not in response.text
        review = store.review(job.job_id, project_id="sample-api")
        assert review.events[-1].actor is not None and review.result is None


def test_actor_submission_is_atomic_and_legacy_rejects_attribution(job_fixture):
    application, store, request = job_fixture
    with client_for(application, store) as client:
        _activate(client)
        actor = client.app.state.dashboard_session_manager.session(
            client.cookies.get("forgegate_dashboard")
        )[1].audit_actor()
    with pytest.raises(jobs.JobError, match="ACTOR_INVALID"):
        store.submit(
            request, application, key="invalid", actor=actor.model_copy(update={"role": "producer"})
        )
    assert store.list_jobs() == []
    with pytest.raises(jobs.JobError, match="NOT_FOUND"):
        store.submit(request, application, key="scope", actor=actor, project_id="other-project")
    downgrade_fixture(store)
    with pytest.raises(jobs.JobError, match="MIGRATION_REQUIRED"):
        store.submit(request, application, key="legacy", actor=actor)
    assert store.list_jobs() == []
