from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi import Request
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from forgegate import __version__
from forgegate.api import ApiErrorResponse, create_api_app
from forgegate.api.app import (
    MAX_REQUEST_BODY_BYTES,
    _error_message,
    _request_id,
    _store_error_status,
)
from forgegate.application import CandidateApplication, CandidateCreateCommand
from forgegate.candidates import (
    CandidateLifecycleError,
    CandidateStoreError,
    SQLiteCandidateRepository,
)
from forgegate.cli import app as cli_app
from forgegate.config import load_config
from forgegate.network import is_loopback_host

runner = CliRunner()


def candidate_payload(**updates: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "project_id": "sample-api",
        "version": "1.2.0",
        "commit_sha": "a" * 40,
        "source_branch": "main",
        "release_track": "pull-request",
        "created_at": "2026-08-30T12:00:00Z",
    }
    values.update(updates)
    return values


def assert_error(response: Any, status_code: int, code: str) -> dict[str, Any]:
    assert response.status_code == status_code
    payload = ApiErrorResponse.model_validate(response.json())
    assert payload.error.code == code
    assert response.headers["X-Request-ID"] == payload.error.request_id
    return payload.model_dump(mode="json")


def test_health_and_candidate_read_write_contract(tmp_path: Path) -> None:
    request_id = "test-request-0001"
    with TestClient(
        create_api_app(tmp_path / "forgegate.db"), base_url="http://127.0.0.1"
    ) as client:
        health = client.get("/healthz", headers={"X-Request-ID": request_id})
        created = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "api:create:001", "X-Request-ID": request_id},
            json=candidate_payload(),
        )
        replay = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "api:create:001"},
            json=candidate_payload(),
        )
        candidate_id = created.json()["candidate_id"]
        shown = client.get(f"/v1/candidates/{candidate_id}")
        history = client.get(f"/v1/candidates/{candidate_id}/history")

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "api_version": "v1",
        "forgegate_version": __version__,
        "store_schema": "forgegate.candidate-store.v3",
    }
    assert health.headers["X-Request-ID"] == request_id
    assert created.status_code == replay.status_code == 201
    assert created.json() == replay.json() == shown.json()
    assert history.json() == {
        "candidate": created.json(),
        "transitions": [],
        "evidence_binding_required": True,
        "evidence_binding": None,
    }
    assert replay.headers["X-Request-ID"].startswith("req-")


def test_api_rejects_invalid_request_ids_and_strict_inputs(tmp_path: Path) -> None:
    with TestClient(
        create_api_app(tmp_path / "forgegate.db"), base_url="http://127.0.0.1"
    ) as client:
        bad_id = client.get("/healthz", headers={"X-Request-ID": "bad id"})
        missing_key = client.post("/v1/candidates", json=candidate_payload())
        unknown_field = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "api:create:002"},
            json={**candidate_payload(), "unknown": True},
        )

    bad_id_payload = assert_error(bad_id, 400, "API_REQUEST_ID_INVALID")
    assert bad_id_payload["error"]["request_id"].startswith("req-")
    assert_error(missing_key, 422, "API_REQUEST_VALIDATION_FAILED")
    assert_error(unknown_field, 422, "API_REQUEST_VALIDATION_FAILED")


def test_api_enforces_local_host_and_bounded_content_length(tmp_path: Path) -> None:
    assert is_loopback_host(None) is False
    with TestClient(
        create_api_app(tmp_path / "external-host.db"), base_url="http://example.invalid"
    ) as external_client:
        external_host = external_client.get("/healthz")
    with TestClient(create_api_app(tmp_path / "length.db"), base_url="http://127.0.0.1") as client:
        invalid_length = client.get("/healthz", headers={"Content-Length": "invalid"})
        negative_length = client.get("/healthz", headers={"Content-Length": "-1"})
        oversized = client.get(
            "/healthz", headers={"Content-Length": str(MAX_REQUEST_BODY_BYTES + 1)}
        )

    assert_error(external_host, 400, "API_HOST_INVALID")
    assert_error(invalid_length, 400, "API_CONTENT_LENGTH_INVALID")
    assert_error(negative_length, 400, "API_CONTENT_LENGTH_INVALID")
    assert_error(oversized, 413, "API_BODY_TOO_LARGE")


@pytest.mark.parametrize(
    ("base_url", "host_header"),
    [
        ("http://localhost", None),
        ("http://127.0.0.1", None),
        ("http://127.0.0.1", "[::1]"),
    ],
)
def test_api_accepts_only_explicit_loopback_hosts(
    tmp_path: Path,
    base_url: str,
    host_header: str | None,
) -> None:
    with TestClient(create_api_app(tmp_path / "forgegate.db"), base_url=base_url) as client:
        headers = {"Host": host_header} if host_header is not None else None
        assert client.get("/healthz", headers=headers).status_code == 200


def test_api_maps_conflict_and_missing_resources(tmp_path: Path) -> None:
    with TestClient(
        create_api_app(tmp_path / "forgegate.db"), base_url="http://127.0.0.1"
    ) as client:
        created = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "api:create:conflict"},
            json=candidate_payload(),
        )
        conflict = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "api:create:conflict"},
            json=candidate_payload(version="2.0.0"),
        )
        candidate_id = created.json()["candidate_id"]
        missing_candidate = client.get("/v1/candidates/cand-000000000000000000000000")
        missing_evidence = client.get(f"/v1/candidates/{candidate_id}/evidence")
        missing_attestation = client.get(f"/v1/candidates/{candidate_id}/attestation")

    assert created.status_code == 201
    assert_error(conflict, 409, "STORE_IDEMPOTENCY_CONFLICT")
    assert_error(missing_candidate, 404, "STORE_CANDIDATE_NOT_FOUND")
    assert_error(missing_evidence, 404, "STORE_EVIDENCE_BINDING_NOT_FOUND")
    assert_error(missing_attestation, 404, "STORE_ATTESTATION_NOT_FOUND")


def test_api_command_endpoints_fail_closed_on_state_and_concurrency(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    assembly = load_config(repository_root / "tests/golden/evidence_bundle_assembly.json")
    policy = load_config(repository_root / "examples/sample-python-api/policies/pull-request.yaml")
    with TestClient(
        create_api_app(tmp_path / "forgegate.db"), base_url="http://127.0.0.1"
    ) as client:
        created = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "api:create:guarded"},
            json=candidate_payload(),
        ).json()
        candidate_id = created["candidate_id"]
        transition_path = f"/v1/candidates/{candidate_id}/transitions"
        bind_draft = client.post(
            f"/v1/candidates/{candidate_id}/evidence",
            headers={"Idempotency-Key": "api:bind:draft"},
            json={
                "assembly": assembly.model_dump(mode="json"),
                "bound_at": "2026-08-30T20:31:00Z",
            },
        )
        evaluate_without_binding = client.post(
            f"/v1/candidates/{candidate_id}/evaluate",
            headers={"Idempotency-Key": "api:evaluate:no-binding"},
            json={
                "policy": policy.model_dump(mode="json"),
                "expected_revision": 0,
                "evaluated_at": "2026-08-30T21:00:00Z",
            },
        )
        attest_draft = client.post(
            f"/v1/candidates/{candidate_id}/attestation",
            json={"issued_at": "2026-08-30T22:00:00Z"},
        )
        collecting_command = {
            "to_status": "COLLECTING",
            "expected_revision": 0,
            "occurred_at": "2026-08-30T12:01:00Z",
        }
        collecting = client.post(
            transition_path,
            headers={"Idempotency-Key": "api:advance:guarded"},
            json=collecting_command,
        )
        key_conflict = client.post(
            transition_path,
            headers={"Idempotency-Key": "api:advance:guarded"},
            json={**collecting_command, "reason": "different request"},
        )
        stale_revision = client.post(
            transition_path,
            headers={"Idempotency-Key": "api:advance:stale"},
            json={
                "to_status": "READY",
                "expected_revision": 0,
                "occurred_at": "2026-08-30T20:32:00Z",
            },
        )

    assert_error(bind_draft, 400, "STORE_EVIDENCE_BINDING_INVALID")
    assert_error(evaluate_without_binding, 404, "STORE_EVIDENCE_BINDING_NOT_FOUND")
    assert_error(attest_draft, 400, "STORE_ATTESTATION_INVALID")
    assert collecting.status_code == 200
    assert_error(key_conflict, 409, "STORE_IDEMPOTENCY_CONFLICT")
    assert_error(stale_revision, 409, "STORE_REVISION_CONFLICT")


def test_api_executes_and_replays_complete_local_candidate_workflow(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    database = tmp_path / "forgegate.db"
    with TestClient(create_api_app(database), base_url="http://127.0.0.1") as client:
        created = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "api:create:durable"},
            json=candidate_payload(),
        ).json()
        candidate_id = created["candidate_id"]
        transition_path = f"/v1/candidates/{candidate_id}/transitions"
        collecting_command = {
            "to_status": "COLLECTING",
            "expected_revision": 0,
            "occurred_at": "2026-08-30T12:01:00Z",
            "reason": "begin audited collection",
        }
        collecting = client.post(
            transition_path,
            headers={"Idempotency-Key": "api:advance:collecting"},
            json=collecting_command,
        )
        collecting_replay = client.post(
            transition_path,
            headers={"Idempotency-Key": "api:advance:collecting"},
            json=collecting_command,
        )
        assembly = load_config(repository_root / "tests/golden/evidence_bundle_assembly.json")
        binding = client.post(
            f"/v1/candidates/{candidate_id}/evidence",
            headers={"Idempotency-Key": "api:bind:evidence"},
            json={
                "assembly": assembly.model_dump(mode="json"),
                "bound_at": "2026-08-30T20:31:00Z",
            },
        )
        ready = client.post(
            transition_path,
            headers={"Idempotency-Key": "api:advance:ready"},
            json={
                "to_status": "READY",
                "expected_revision": 1,
                "occurred_at": "2026-08-30T20:32:00Z",
            },
        )
        evaluating = client.post(
            transition_path,
            headers={"Idempotency-Key": "api:advance:evaluating"},
            json={
                "to_status": "EVALUATING",
                "expected_revision": 2,
                "occurred_at": "2026-08-30T20:33:00Z",
            },
        )
        policy = load_config(
            repository_root / "examples/sample-python-api/policies/pull-request.yaml"
        )
        evaluation_command = {
            "policy": policy.model_dump(mode="json"),
            "expected_revision": 3,
            "evaluated_at": "2026-08-30T21:00:00Z",
            "reason": "evaluate the bound evidence",
        }
        invalid_evaluation = client.post(
            f"/v1/candidates/{candidate_id}/evaluate",
            headers={"Idempotency-Key": "api:evaluate:too-early"},
            json={**evaluation_command, "evaluated_at": "2026-08-30T20:30:00Z"},
        )
        mismatched_policy = client.post(
            f"/v1/candidates/{candidate_id}/evaluate",
            headers={"Idempotency-Key": "api:evaluate:wrong-track"},
            json={
                **evaluation_command,
                "policy": {**evaluation_command["policy"], "name": "production"},
            },
        )
        evaluated = client.post(
            f"/v1/candidates/{candidate_id}/evaluate",
            headers={"Idempotency-Key": "api:evaluate:pass"},
            json=evaluation_command,
        )
        evaluated_replay = client.post(
            f"/v1/candidates/{candidate_id}/evaluate",
            headers={"Idempotency-Key": "api:evaluate:pass"},
            json=evaluation_command,
        )
        attestation = client.post(
            f"/v1/candidates/{candidate_id}/attestation",
            json={"issued_at": "2026-08-30T22:00:00Z"},
        )
        attestation_replay = client.post(
            f"/v1/candidates/{candidate_id}/attestation",
            json={"issued_at": "2026-08-30T22:00:00Z"},
        )
        attestation_conflict = client.post(
            f"/v1/candidates/{candidate_id}/attestation",
            json={"issued_at": "2026-08-30T22:01:00Z"},
        )

        evidence_response = client.get(f"/v1/candidates/{candidate_id}/evidence")
        attestation_response = client.get(f"/v1/candidates/{candidate_id}/attestation")
        history_response = client.get(f"/v1/candidates/{candidate_id}/history")

    assert collecting.status_code == collecting_replay.status_code == 200
    assert collecting.json() == collecting_replay.json()
    assert binding.status_code == ready.status_code == evaluating.status_code == 200
    assert_error(invalid_evaluation, 422, "CANDIDATE_POLICY_EVALUATION_INVALID")
    assert_error(mismatched_policy, 422, "CANDIDATE_EVALUATION_POLICY_MISMATCH")
    assert evaluated.status_code == evaluated_replay.status_code == 200
    assert evaluated.json() == evaluated_replay.json()
    assert evaluated.json()["evaluation"]["decision"] == "PASS"
    assert attestation.status_code == attestation_replay.status_code == 200
    assert_error(attestation_conflict, 409, "STORE_ATTESTATION_CONFLICT")
    assert attestation.json() == attestation_replay.json() == attestation_response.json()
    assert evidence_response.json() == binding.json()
    assert history_response.json()["candidate"] == evaluated.json()["transition"]["candidate"]
    assert history_response.json()["evidence_binding_required"] is True


def test_api_exception_handlers_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def raise_lifecycle(
        _self: CandidateApplication,
        _command: CandidateCreateCommand,
        *,
        idempotency_key: str,
    ) -> Any:
        assert idempotency_key
        raise CandidateLifecycleError("CANDIDATE_TEST_FAILURE", "safe lifecycle message")

    monkeypatch.setattr(CandidateApplication, "create_candidate", raise_lifecycle)
    with TestClient(
        create_api_app(tmp_path / "lifecycle.db"), base_url="http://127.0.0.1"
    ) as client:
        lifecycle = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "api:create:lifecycle"},
            json=candidate_payload(),
        )
    assert_error(lifecycle, 422, "CANDIDATE_TEST_FAILURE")

    def raise_validation(
        _self: CandidateApplication,
        _command: CandidateCreateCommand,
        *,
        idempotency_key: str,
    ) -> Any:
        assert idempotency_key
        CandidateCreateCommand.model_validate({"created_at": "invalid"})

    monkeypatch.setattr(CandidateApplication, "create_candidate", raise_validation)
    with TestClient(
        create_api_app(tmp_path / "validation.db"), base_url="http://127.0.0.1"
    ) as client:
        validation = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "api:create:validation"},
            json=candidate_payload(),
        )
    assert_error(validation, 422, "API_DOMAIN_VALIDATION_FAILED")

    def raise_unexpected(_self: CandidateApplication, _candidate_id: str) -> Any:
        raise RuntimeError("sensitive internal detail")

    monkeypatch.setattr(CandidateApplication, "get_candidate", raise_unexpected)
    with TestClient(
        create_api_app(tmp_path / "unexpected.db"),
        base_url="http://127.0.0.1",
        raise_server_exceptions=False,
    ) as client:
        unexpected = client.get("/v1/candidates/cand-000000000000000000000000")
    payload = assert_error(unexpected, 500, "API_INTERNAL_ERROR")
    assert "sensitive" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("STORE_CANDIDATE_NOT_FOUND", 404),
        ("STORE_CANDIDATE_CONFLICT", 409),
        ("STORE_ATTESTATION_CONFLICT", 409),
        ("STORE_EVIDENCE_BINDING_CONFLICT", 409),
        ("STORE_EVALUATION_CONFLICT", 409),
        ("STORE_IDEMPOTENCY_CONFLICT", 409),
        ("STORE_REVISION_CONFLICT", 409),
        ("STORE_BUSY", 503),
        ("STORE_MIGRATION_REQUIRED", 503),
        ("STORE_NOT_INITIALIZED", 503),
        ("STORE_CORRUPT", 500),
        ("STORE_NOT_FORGEGATE", 500),
        ("STORE_SCHEMA_UNSUPPORTED", 500),
        ("STORE_PARENT_MISSING", 400),
    ],
)
def test_store_error_status_contract(code: str, expected: int) -> None:
    assert _store_error_status(code) == expected


def test_error_helpers_preserve_safe_messages_and_supply_request_ids() -> None:
    error = CandidateStoreError("STORE_BUSY", "database is busy")
    assert _error_message(error.code, str(error)) == "database is busy"

    request = Request({"type": "http", "headers": []})
    assert _request_id(request).startswith("req-")


def test_openapi_export_is_deterministic_and_complete(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"
    result = runner.invoke(cli_app, ["export-openapi", str(output)])
    schema = create_api_app(tmp_path / "unused.db").openapi()

    assert result.exit_code == 0, result.output
    assert b"\r\n" not in output.read_bytes()
    assert json.loads(output.read_text(encoding="utf-8")) == schema
    assert set(schema["paths"]) == {
        "/healthz",
        "/v1/candidates",
        "/v1/candidates/{candidate_id}",
        "/v1/candidates/{candidate_id}/history",
        "/v1/candidates/{candidate_id}/evidence",
        "/v1/candidates/{candidate_id}/attestation",
        "/v1/candidates/{candidate_id}/transitions",
        "/v1/candidates/{candidate_id}/evaluate",
    }
    assert schema["paths"]["/v1/candidates"]["post"]["operationId"] == "createCandidate"
    assert (
        schema["paths"]["/v1/candidates/{candidate_id}/evaluate"]["post"]["operationId"]
        == "evaluateCandidate"
    )
    assert (
        schema["paths"]["/v1/candidates"]["post"]["responses"]["409"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/ApiErrorResponse"
    )


def test_openapi_export_and_serve_cli_errors(tmp_path: Path) -> None:
    missing_parent = runner.invoke(
        cli_app, ["export-openapi", str(tmp_path / "missing" / "openapi.json")]
    )
    non_loopback = runner.invoke(
        cli_app,
        [
            "serve",
            "--database",
            str(tmp_path / "forgegate.db"),
            "--host",
            "0.0.0.0",
        ],
    )
    invalid_host = runner.invoke(
        cli_app,
        [
            "serve",
            "--database",
            str(tmp_path / "forgegate.db"),
            "--host",
            "not-an-address",
        ],
    )

    assert missing_parent.exit_code == 3
    assert "output parent does not exist" in missing_parent.output
    assert non_loopback.exit_code == invalid_host.exit_code == 3
    assert "loopback" in non_loopback.output
    assert "loopback" in invalid_host.output


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_serve_cli_accepts_only_loopback_hosts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    host: str,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(application: Any, **kwargs: Any) -> None:
        calls.append({"application": application, **kwargs})

    monkeypatch.setattr(uvicorn, "run", fake_run)
    database = tmp_path / f"{host.replace(':', '_')}.db"
    result = runner.invoke(
        cli_app,
        [
            "serve",
            "--database",
            str(database),
            "--host",
            host,
            "--port",
            "8123",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls[0]["host"] == host
    assert calls[0]["port"] == 8123
    assert calls[0]["log_level"] == "info"
    assert SQLiteCandidateRepository(database).history  # store construction remains valid


def test_cli_and_api_candidate_creation_share_the_same_contract(tmp_path: Path) -> None:
    api_database = tmp_path / "api.db"
    cli_database = tmp_path / "cli.db"
    SQLiteCandidateRepository(cli_database).initialize()
    with TestClient(create_api_app(api_database), base_url="http://127.0.0.1") as client:
        api_created = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "parity:create:001"},
            json=candidate_payload(),
        )
    cli_created = runner.invoke(
        cli_app,
        [
            "candidate",
            "create",
            "--project",
            "sample-api",
            "--version",
            "1.2.0",
            "--commit",
            "a" * 40,
            "--created-at",
            "2026-08-30T12:00:00Z",
            "--branch",
            "main",
            "--track",
            "pull-request",
            "--database",
            str(cli_database),
            "--idempotency-key",
            "parity:create:001",
        ],
    )

    assert api_created.status_code == 201
    assert cli_created.exit_code == 0, cli_created.output
    assert api_created.json() == json.loads(cli_created.stdout)
