from datetime import UTC, datetime, timedelta

import pytest

from forgegate.application import CandidateAdvanceCommand, CandidateBindEvidenceCommand
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.collection_jobs import CollectionJobRequest
from tests.test_collection_jobs import fixture
from tests.test_dashboard import ORIGIN_HEADER, _activate
from tests.test_dashboard_jobs import client_for

job_fixture = fixture
MEDIA_TYPE = "application/vnd.forgegate.evidence-bundle-assembly+json"


def completed(application, store, request, *, key="handoff"):
    job = store.submit(request, application, key=key)
    job = store.run(job.job_id, 0, application)
    result = store.result(job.job_id)
    assert job.state == "SUCCEEDED" and result.assembly is not None
    return job, result


def export_command(job, result):
    assembly = result.assembly
    assert assembly is not None and job.result_fingerprint is not None
    return {
        "expected_job_revision": job.revision,
        "expected_result_fingerprint": job.result_fingerprint,
        "expected_assembly_id": assembly.assembly_id,
    }


def binding_command(job, result, *, bound_at=None):
    return {
        **export_command(job, result),
        "expected_candidate_revision": 1,
        "expected_candidate_fingerprint": job.candidate_fingerprint,
        "bound_at": (bound_at or datetime.now(UTC)).isoformat(),
    }


def write_headers(session, *, key=None):
    headers = {**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def test_exact_canonical_assembly_export_headers_and_no_mutation(job_fixture):
    application, store, request = job_fixture
    job, result = completed(application, store, request)
    assembly = result.assembly
    assert assembly is not None
    expected = canonical_json(assembly.model_dump(mode="json")).encode()
    before = application.get_history(request.candidate_id)
    route = f"/app/api/jobs/{job.job_id}/assembly-export?project_id=sample-api"
    with client_for(application, store) as client:
        session = _activate(client)
        first = client.post(route, json=export_command(job, result), headers=write_headers(session))
        second = client.post(
            route, json=export_command(job, result), headers=write_headers(session)
        )
    fingerprint = sha256_fingerprint(assembly.model_dump(mode="json"))
    filename = f"evidence-assembly-{assembly.assembly_id.removeprefix('sha256:')}.json"
    assert first.status_code == second.status_code == 200
    assert first.content == second.content == expected
    assert first.headers["content-type"] == MEDIA_TYPE
    assert first.headers["content-disposition"] == f'attachment; filename="{filename}"'
    assert first.headers["x-forgegate-job-result"] == job.result_fingerprint
    assert first.headers["x-forgegate-assembly"] == assembly.assembly_id
    assert first.headers["x-forgegate-assembly-fingerprint"] == fingerprint
    assert first.headers["cache-control"] == "no-store"
    assert b"content_base64" not in first.content and b"<testsuite" not in first.content
    assert application.get_history(request.candidate_id) == before
    assert store.show(job.job_id) == job


@pytest.mark.parametrize("mode", ["unauthenticated", "producer", "origin", "csrf"])
def test_assembly_export_authorization_is_fail_closed(job_fixture, mode):
    application, store, request = job_fixture
    job, result = completed(application, store, request)
    route = f"/app/api/jobs/{job.job_id}/assembly-export?project_id=sample-api"
    with client_for(application, store, producer=mode == "producer") as client:
        if mode == "unauthenticated":
            response = client.post(route, json=export_command(job, result), headers=ORIGIN_HEADER)
        else:
            session = _activate(client, role="producer" if mode == "producer" else "operator")
            headers = write_headers(session)
            if mode == "origin":
                headers["Origin"] = "https://example.invalid"
            if mode == "csrf":
                headers.pop("X-ForgeGate-CSRF")
            response = client.post(route, json=export_command(job, result), headers=headers)
    assert response.status_code == (401 if mode == "unauthenticated" else 403)
    assert application.get_history(request.candidate_id).evidence_binding is None


@pytest.mark.parametrize(
    "field", ["expected_job_revision", "expected_result_fingerprint", "expected_assembly_id"]
)
def test_assembly_export_rejects_stale_review_identity(job_fixture, field):
    application, store, request = job_fixture
    job, result = completed(application, store, request)
    command = export_command(job, result)
    command[field] = 1 if field == "expected_job_revision" else "sha256:" + "0" * 64
    with client_for(application, store) as client:
        session = _activate(client)
        response = client.post(
            f"/app/api/jobs/{job.job_id}/assembly-export?project_id=sample-api",
            json=command,
            headers=write_headers(session),
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] in {
        "JOB_STATE_CONFLICT",
        "JOB_RESULT_IDENTITY_CONFLICT",
    }
    assert application.get_history(request.candidate_id).evidence_binding is None


@pytest.mark.parametrize("case", ["queued", "warning", "rejected"])
def test_nonbindable_job_has_no_export_or_binding(case, job_fixture):
    application, store, request = job_fixture
    if case != "queued":
        raw = request.model_dump(mode="json")
        raw["collection"]["reports"][0]["content_base64"] = (
            "PHRlc3RzdWl0ZSB0ZXN0cz0iMiI+PHRlc3RjYXNlIG5hbWU9IngiLz48L3Rlc3RzdWl0ZT4="
            if case == "warning"
            else "PCFET0NUWVBFIHg+PHRlc3RzdWl0ZS8+"
        )
        request = CollectionJobRequest.model_validate(raw)
    job = store.submit(request, application, key=f"not-bindable:{case}")
    if case != "queued":
        job = store.run(job.job_id, 0, application)
    command = {
        "expected_job_revision": 2,
        "expected_result_fingerprint": "sha256:" + "0" * 64,
        "expected_assembly_id": "sha256:" + "0" * 64,
    }
    with client_for(application, store) as client:
        session = _activate(client)
        headers = write_headers(session, key="bind:not-bindable")
        export = client.post(
            f"/app/api/jobs/{job.job_id}/assembly-export?project_id=sample-api",
            json=command,
            headers=headers,
        )
        bind = client.post(
            f"/app/api/jobs/{job.job_id}/bind-evidence?project_id=sample-api",
            json={
                **command,
                "expected_candidate_revision": 1,
                "expected_candidate_fingerprint": job.candidate_fingerprint,
                "bound_at": datetime.now(UTC).isoformat(),
            },
            headers=headers,
        )
    assert export.status_code == bind.status_code == 409
    assert (
        export.json()["error"]["code"] == bind.json()["error"]["code"] == "JOB_RESULT_NOT_BINDABLE"
    )
    assert application.get_history(request.candidate_id).evidence_binding is None


def test_reviewed_job_result_binds_exact_assembly_with_operator_actor(job_fixture):
    application, store, request = job_fixture
    job, result = completed(application, store, request)
    assembly = result.assembly
    assert assembly is not None
    command = binding_command(job, result)
    before_job = store.review(job.job_id, project_id="sample-api")
    with client_for(application, store) as client:
        session = _activate(client)
        route = f"/app/api/jobs/{job.job_id}/bind-evidence?project_id=sample-api"
        headers = write_headers(session, key="job-result:binding")
        first = client.post(route, json=command, headers=headers)
        replay = client.post(route, json=command, headers=headers)
        audit = client.get(
            f"/app/api/audit-events?project_id=sample-api&candidate_id={request.candidate_id}&limit=100"
        )
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    payload = first.json()
    binding = application.get_history(request.candidate_id).evidence_binding
    assert binding is not None and binding.assembly == assembly
    assert payload["schema_version"] == "forgegate.dashboard-job-evidence-binding.v1"
    assert payload["job_id"] == job.job_id
    assert payload["result_fingerprint"] == job.result_fingerprint
    assert payload["assembly_id"] == assembly.assembly_id
    assert payload["assembly_fingerprint"] == binding.assembly_fingerprint
    assert payload["binding"] == binding.model_dump(mode="json")
    assert payload["candidate_transition"] == payload["policy_decision"] == "NOT_PERFORMED"
    assert payload["source_artifact_bytes"] == "not_embedded"
    assert "content_base64" not in first.text
    events = [
        event
        for event in audit.json()["events"]
        if event["event_type"] == "candidate.evidence-bound"
    ]
    assert (
        len(events) == 1
        and events[0]["actor"]["identity_id"] == session["principal"]["identity_id"]
    )
    assert application.get_candidate(request.candidate_id).revision == 1
    assert application.get_candidate(request.candidate_id).status == "COLLECTING"
    assert store.review(job.job_id, project_id="sample-api") == before_job


def test_binding_key_conflict_and_candidate_identity_checks(job_fixture):
    application, store, request = job_fixture
    job, result = completed(application, store, request)
    command = binding_command(job, result)
    with client_for(application, store) as client:
        session = _activate(client)
        route = f"/app/api/jobs/{job.job_id}/bind-evidence?project_id=sample-api"
        headers = write_headers(session, key="job-result:identity")
        wrong_revision = client.post(
            route, json={**command, "expected_candidate_revision": 0}, headers=headers
        )
        wrong_fingerprint = client.post(
            route,
            json={**command, "expected_candidate_fingerprint": "sha256:" + "0" * 64},
            headers=headers,
        )
        first = client.post(route, json=command, headers=headers)
        changed = client.post(
            route,
            json={**command, "bound_at": (datetime.now(UTC) + timedelta(seconds=1)).isoformat()},
            headers=headers,
        )
    assert wrong_revision.status_code == wrong_fingerprint.status_code == 409
    assert wrong_revision.json()["error"]["code"] == "JOB_CANDIDATE_CONFLICT"
    assert wrong_fingerprint.json()["error"]["code"] == "JOB_CANDIDATE_CONFLICT"
    assert first.status_code == 200
    assert (
        changed.status_code == 409
        and changed.json()["error"]["code"] == "STORE_IDEMPOTENCY_CONFLICT"
    )


@pytest.mark.parametrize("mode", ["producer", "csrf", "origin", "scope", "missing-key", "unknown"])
def test_binding_authorization_and_shape_rejections_do_not_write(job_fixture, mode):
    application, store, request = job_fixture
    job, result = completed(application, store, request)
    project = "forbidden-project" if mode == "scope" else "sample-api"
    with client_for(application, store, producer=mode == "producer") as client:
        session = _activate(client, role="producer" if mode == "producer" else "operator")
        headers = write_headers(session, key="job-result:denied")
        if mode == "csrf":
            headers.pop("X-ForgeGate-CSRF")
        if mode == "origin":
            headers["Origin"] = "https://example.invalid"
        if mode == "missing-key":
            headers.pop("Idempotency-Key")
        command = binding_command(job, result)
        if mode == "unknown":
            command["candidate_transition"] = "READY"
        response = client.post(
            f"/app/api/jobs/{job.job_id}/bind-evidence?project_id={project}",
            json=command,
            headers=headers,
        )
    assert response.status_code == (422 if mode in {"missing-key", "unknown"} else 403)
    assert application.get_history(request.candidate_id).evidence_binding is None


def test_bound_candidate_becoming_ready_is_stale_for_new_job_handoff(job_fixture):
    application, store, request = job_fixture
    job, result = completed(application, store, request)
    assembly = result.assembly
    assert assembly is not None
    bound_at = datetime.now(UTC)
    application.bind_evidence(
        request.candidate_id,
        CandidateBindEvidenceCommand(assembly=assembly, bound_at=bound_at),
        idempotency_key="preexisting-binding",
    )
    application.advance_candidate(
        request.candidate_id,
        CandidateAdvanceCommand(
            to_status="READY",
            expected_revision=1,
            occurred_at=bound_at + timedelta(seconds=1),
        ),
        idempotency_key="preexisting-ready",
    )
    with client_for(application, store) as client:
        session = _activate(client)
        response = client.post(
            f"/app/api/jobs/{job.job_id}/bind-evidence?project_id=sample-api",
            json=binding_command(job, result, bound_at=bound_at + timedelta(seconds=2)),
            headers=write_headers(session, key="job-result:stale"),
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "JOB_CANDIDATE_CONFLICT"
    assert application.get_candidate(request.candidate_id).status == "READY"


def test_disabled_job_store_rejects_export_and_binding(job_fixture):
    application, store, request = job_fixture
    job, result = completed(application, store, request)
    with client_for(application, None) as client:
        session = _activate(client)
        headers = write_headers(session, key="job-result:disabled")
        export = client.post(
            f"/app/api/jobs/{job.job_id}/assembly-export?project_id=sample-api",
            json=export_command(job, result),
            headers=headers,
        )
        bind = client.post(
            f"/app/api/jobs/{job.job_id}/bind-evidence?project_id=sample-api",
            json=binding_command(job, result),
            headers=headers,
        )
    assert export.status_code == bind.status_code == 503
    assert application.get_history(request.candidate_id).evidence_binding is None
