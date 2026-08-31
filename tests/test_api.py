from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi import Request
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from forgegate import __version__
from forgegate.api import ApiErrorResponse, create_api_app
from forgegate.api.app import _error_message, _request_id, _store_error_status
from forgegate.application import CandidateApplication, CandidateCreateCommand
from forgegate.assembly import EvidenceBundleAssembly
from forgegate.candidates import (
    CandidateLifecycleError,
    CandidateStoreError,
    SQLiteCandidateRepository,
)
from forgegate.cli import app as cli_app
from forgegate.config import load_config
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import PolicyConfig
from forgegate.policy import evaluate_policy

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
    with TestClient(create_api_app(tmp_path / "forgegate.db")) as client:
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
    with TestClient(create_api_app(tmp_path / "forgegate.db")) as client:
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


def test_api_maps_conflict_and_missing_resources(tmp_path: Path) -> None:
    with TestClient(create_api_app(tmp_path / "forgegate.db")) as client:
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


def test_api_reads_durable_evidence_and_attestation(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    database = tmp_path / "forgegate.db"
    application = CandidateApplication.for_database(database)
    with TestClient(create_api_app(database, application=application)) as client:
        created = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "api:create:durable"},
            json=candidate_payload(),
        ).json()
        candidate_id = created["candidate_id"]
        repository = application.repository
        collecting = repository.advance(
            candidate_id,
            CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
            idempotency_key="api:advance:collecting",
        ).candidate
        assembly = load_config(repository_root / "tests/golden/evidence_bundle_assembly.json")
        assert isinstance(assembly, EvidenceBundleAssembly)
        binding = repository.bind_evidence(
            candidate_id,
            assembly,
            bound_at=datetime(2026, 8, 30, 20, 31, tzinfo=UTC),
            idempotency_key="api:bind:evidence",
        )
        ready = repository.advance(
            candidate_id,
            CandidateStatus.READY,
            expected_revision=collecting.revision,
            occurred_at=datetime(2026, 8, 30, 20, 32, tzinfo=UTC),
            idempotency_key="api:advance:ready",
        ).candidate
        evaluating = repository.advance(
            candidate_id,
            CandidateStatus.EVALUATING,
            expected_revision=ready.revision,
            occurred_at=datetime(2026, 8, 30, 20, 33, tzinfo=UTC),
            idempotency_key="api:advance:evaluating",
        ).candidate
        policy = load_config(
            repository_root / "examples/sample-python-api/policies/pull-request.yaml"
        )
        assert isinstance(policy, PolicyConfig)
        evaluated_at = datetime(2026, 8, 30, 21, 0, tzinfo=UTC)
        evaluation = evaluate_policy(policy, assembly.bundle, evaluated_at=evaluated_at)
        terminal = repository.advance(
            candidate_id,
            CandidateStatus.PASS,
            expected_revision=evaluating.revision,
            occurred_at=evaluated_at,
            idempotency_key="api:advance:pass",
            evaluation=evaluation,
        ).candidate
        attestation = repository.attest(
            candidate_id,
            issued_at=datetime(2026, 8, 30, 22, 0, tzinfo=UTC),
            generator_version=__version__,
        )

        evidence_response = client.get(f"/v1/candidates/{candidate_id}/evidence")
        attestation_response = client.get(f"/v1/candidates/{candidate_id}/attestation")
        history_response = client.get(f"/v1/candidates/{candidate_id}/history")

    assert evidence_response.status_code == attestation_response.status_code == 200
    assert evidence_response.json() == binding.model_dump(mode="json")
    assert attestation_response.json() == attestation.model_dump(mode="json")
    assert history_response.json()["candidate"] == terminal.model_dump(mode="json")
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
    with TestClient(create_api_app(tmp_path / "lifecycle.db")) as client:
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
    with TestClient(create_api_app(tmp_path / "validation.db")) as client:
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
        create_api_app(tmp_path / "unexpected.db"), raise_server_exceptions=False
    ) as client:
        unexpected = client.get("/v1/candidates/cand-000000000000000000000000")
    payload = assert_error(unexpected, 500, "API_INTERNAL_ERROR")
    assert "sensitive" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("STORE_CANDIDATE_NOT_FOUND", 404),
        ("STORE_CANDIDATE_CONFLICT", 409),
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
    assert json.loads(output.read_text(encoding="utf-8")) == schema
    assert set(schema["paths"]) == {
        "/healthz",
        "/v1/candidates",
        "/v1/candidates/{candidate_id}",
        "/v1/candidates/{candidate_id}/history",
        "/v1/candidates/{candidate_id}/evidence",
        "/v1/candidates/{candidate_id}/attestation",
    }
    assert schema["paths"]["/v1/candidates"]["post"]["operationId"] == "createCandidate"
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
    with TestClient(create_api_app(api_database)) as client:
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
