from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from forgegate.api import (
    ApiAuthChallenge,
    ApiAuthenticationError,
    ApiAuthenticator,
    ApiChallengeRequest,
    ApiSessionCreateRequest,
    create_api_app,
    sign_api_challenge,
)
from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    CandidateEvaluateCommand,
    ProjectRegisterCommand,
)
from forgegate.cli import app
from forgegate.config import load_config
from forgegate.dashboard import DashboardSessionManager
from forgegate.dashboard.assets import (
    DashboardAsset,
    DashboardAssetInventory,
    build_dashboard_asset_inventory,
    validate_dashboard_assets,
    write_dashboard_asset_inventory,
)
from forgegate.dashboard.client import DashboardClientError
from forgegate.dashboard.openapi import create_dashboard_openapi
from forgegate.domain.enums import CandidateStatus
from forgegate.identity import IdentityRole
from forgegate.live_status import LiveSourceStatus, LiveStatusPage
from tests.api_auth_support import TEST_IDENTITY, TEST_PRIVATE_KEY, TEST_TRUST_STORE
from tools.manual_dashboard_fault_server import (
    FAULT_PRESENTATIONS,
    create_fault_presentation_app,
)

ORIGIN = "http://127.0.0.1"
ORIGIN_HEADER = {"Origin": ORIGIN}
runner = CliRunner()


def _application_with_project(tmp_path: Path, repository_root: Path) -> CandidateApplication:
    application = CandidateApplication.for_database(tmp_path / "forgegate.db")
    application.initialize()
    application.register_project(
        ProjectRegisterCommand(
            config=load_config(repository_root / "examples/sample-python-api/forgegate.yaml"),
            registered_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
        ),
        idempotency_key="dashboard:test:project",
    )
    return application


def _dashboard_client(
    tmp_path: Path,
    repository_root: Path,
    *,
    role: IdentityRole = IdentityRole.OPERATOR,
    live_status_provider: Any | None = None,
) -> TestClient:
    authenticator = ApiAuthenticator(
        TEST_TRUST_STORE if role is IdentityRole.OPERATOR else _producer_trust_store()
    )
    return TestClient(
        create_api_app(
            tmp_path / "forgegate.db",
            application=_application_with_project(tmp_path, repository_root),
            authenticator=authenticator,
            dashboard=True,
            dashboard_live_status_provider=live_status_provider,
        ),
        base_url=ORIGIN,
    )


def _completed_dashboard_application(
    tmp_path: Path,
    repository_root: Path,
) -> tuple[CandidateApplication, str]:
    application = _application_with_project(tmp_path, repository_root)
    candidate = application.create_candidate(
        CandidateCreateCommand.model_validate(_candidate_payload()),
        idempotency_key="dashboard:review:candidate",
    )
    application.advance_candidate(
        candidate.candidate_id,
        CandidateAdvanceCommand(
            to_status=CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=datetime(2026, 9, 4, 12, 31, tzinfo=UTC),
        ),
        idempotency_key="dashboard:review:collecting",
    )
    application.bind_evidence(
        candidate.candidate_id,
        CandidateBindEvidenceCommand(
            assembly=load_config(repository_root / "tests/golden/evidence_bundle_assembly.json"),
            bound_at=datetime(2026, 9, 4, 20, 31, tzinfo=UTC),
        ),
        idempotency_key="dashboard:review:evidence",
    )
    for revision, target, occurred_at in (
        (1, CandidateStatus.READY, datetime(2026, 9, 4, 20, 32, tzinfo=UTC)),
        (2, CandidateStatus.EVALUATING, datetime(2026, 9, 4, 20, 33, tzinfo=UTC)),
    ):
        application.advance_candidate(
            candidate.candidate_id,
            CandidateAdvanceCommand(
                to_status=target,
                expected_revision=revision,
                occurred_at=occurred_at,
            ),
            idempotency_key=f"dashboard:review:{target.value.lower()}",
        )
    material = application.materialize_policy(
        candidate.candidate_id,
        repository_root / "examples/sample-python-api",
    )
    application.evaluate_candidate(
        candidate.candidate_id,
        CandidateEvaluateCommand(
            policy_material=material,
            expected_revision=3,
            evaluated_at=datetime(2026, 9, 4, 21, 0, tzinfo=UTC),
        ),
        idempotency_key="dashboard:review:evaluate",
    )
    application.attest_candidate(
        candidate.candidate_id,
        CandidateAttestCommand(issued_at=datetime(2026, 9, 4, 22, 0, tzinfo=UTC)),
    )
    return application, candidate.candidate_id


def _producer_trust_store():
    from forgegate.identity import IdentityStatus, TrustedIdentity, create_trust_store

    return create_trust_store(
        (
            TrustedIdentity(
                identity=TEST_IDENTITY,
                roles=(IdentityRole.PRODUCER,),
                project_ids=("sample-api",),
                status=IdentityStatus.ACTIVE,
            ),
        )
    )


def _activate(client: TestClient, *, role: str = "operator") -> dict[str, Any]:
    started = client.post("/app/api/activations", headers=ORIGIN_HEADER, json={})
    assert started.status_code == 201, started.text
    code = started.json()["activation_code"]
    challenge_response = client.post(
        f"/app/api/activations/{code}/challenge",
        json={
            "identity_id": TEST_IDENTITY.identity_id,
            "role": role,
            "project_ids": ["sample-api"],
        },
    )
    assert challenge_response.status_code == 201, challenge_response.text
    challenge = ApiAuthChallenge.model_validate(challenge_response.json())
    signed = sign_api_challenge(
        challenge,
        identity=TEST_IDENTITY,
        private_key=TEST_PRIVATE_KEY,
    )
    completed = client.post(
        f"/app/api/activations/{code}/complete",
        json=signed.model_dump(mode="json"),
    )
    assert completed.status_code == 201, completed.text
    assert "access_token" not in completed.text
    polled = client.get("/app/api/activation")
    assert polled.status_code == 200, polled.text
    assert polled.json()["status"] == "AUTHENTICATED"
    assert "access_token" not in polled.text
    return polled.json()


def _candidate_payload(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_id": "sample-api",
        "version": "1.2.0",
        "commit_sha": "a" * 40,
        "source_branch": "main",
        "release_track": "pull-request",
        "created_at": "2026-09-04T12:30:00Z",
    }
    payload.update(updates)
    return payload


def _activate_manager(manager: DashboardSessionManager) -> tuple[str, str]:
    started, browser_cookie = manager.start_activation()
    challenge = manager.issue_challenge(
        started.activation_code,
        ApiChallengeRequest(
            identity_id=TEST_IDENTITY.identity_id,
            role=IdentityRole.OPERATOR,
            project_ids=("sample-api",),
        ),
    )
    signed = sign_api_challenge(
        challenge,
        identity=TEST_IDENTITY,
        private_key=TEST_PRIVATE_KEY,
    )
    manager.complete_activation(started.activation_code, signed)
    polled, dashboard_cookie = manager.poll_activation(browser_cookie)
    assert polled.status == "AUTHENTICATED"
    assert dashboard_cookie is not None
    return started.activation_code, dashboard_cookie


def test_manual_dashboard_fault_harness_is_isolated_and_exact(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    database = tmp_path / "forgegate.db"
    _application_with_project(tmp_path, repository_root)
    trust_store = tmp_path / "trust-store.json"
    trust_store.write_text(TEST_TRUST_STORE.model_dump_json(indent=2), encoding="utf-8")
    with TestClient(
        create_fault_presentation_app(database, trust_store),
        base_url=ORIGIN,
    ) as client:
        activated = _activate(client)
        headers = {
            **ORIGIN_HEADER,
            "X-ForgeGate-CSRF": activated["csrf_token"],
            "Idempotency-Key": "manual:fault:presentation",
        }
        for version, expected in FAULT_PRESENTATIONS.items():
            response = client.post(
                "/app/api/candidates",
                headers=headers,
                json=_candidate_payload(version=version),
            )
            assert response.status_code == expected.status
            assert response.json()["error"]["code"] == expected.code
            assert response.headers["X-Request-ID"] == f"manual-browser-fault-{expected.status}"
            if expected.retry_after is not None:
                assert response.headers["Retry-After"] == str(expected.retry_after)
        candidates = client.get("/app/api/projects/sample-api/candidates?limit=25")

    assert candidates.status_code == 200
    assert candidates.json()["candidates"] == []


def test_dashboard_portfolio_capture_record_matches_retained_generic_assets(
    repository_root: Path,
) -> None:
    evidence_path = (
        repository_root / "reports" / "DASHBOARD_PORTFOLIO_CAPTURE_EVIDENCE_2026-09-04.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert evidence["record_format"] == "forgegate-portfolio-capture-evidence-v1"
    assert evidence["environment"]["evidence_level"] == "LOCAL_BROWSER_TEST"
    assert evidence["fixture"]["classification"] == "GENERIC_EPHEMERAL_TEST_DATA"
    assert evidence["fixture"]["candidate"]["status"] == "DRAFT"
    assert evidence["fixture"]["candidate"]["evaluation_id"] is None
    assert evidence["fixture"]["candidate"]["hardware_access"] == "NOT_PERFORMED"

    validation = evidence["browser_validation_case"]
    assert validation["actual"]["result"] == "PASS"
    assert validation["actual"]["http_status"] == 422
    assert validation["actual"]["error_code"] == "API_REQUEST_VALIDATION_FAILED"
    assert validation["actual"]["candidate_count_before"] == 1
    assert validation["actual"]["candidate_count_after"] == 1
    assert validation["actual"]["audit_event_count_before"] == 2
    assert validation["actual"]["audit_event_count_after"] == 2
    assert evidence["cli_cross_check"]["invalid_candidate_present"] is False

    gallery = (repository_root / "docs" / "PORTFOLIO_EVIDENCE.md").read_text(encoding="utf-8")
    readme = (repository_root / "README.md").read_text(encoding="utf-8")
    for asset in evidence["assets"]:
        payload = (repository_root / asset["path"]).read_bytes()
        assert len(payload) == asset["bytes"]
        assert hashlib.sha256(payload).hexdigest() == asset["sha256"]
        assert asset["path"].endswith(".jpg")
        assert asset["media_type"] == "image/jpeg"
        assert payload.startswith(b"\xff\xd8\xff")
        assert Path(asset["path"]).name in gallery

    assert "docs/PORTFOLIO_EVIDENCE.md" in readme
    assert "docs/assets/forgegate-dashboard-overview.jpg" in readme
    assert "docs/assets/forgegate-dashboard-candidate-detail.jpg" in readme

    boundaries = evidence["boundaries"]
    assert boundaries["private_key_or_token_visible"] is False
    assert boundaries["personal_data_used"] is False
    assert boundaries["hardware_access"] == "NOT_PERFORMED"
    assert boundaries["production_readiness_proven"] is False
    assert boundaries["public_release_authorized"] is False


def test_dashboard_assurance_review_and_msp430_follow_up_records_match_assets(
    repository_root: Path,
) -> None:
    review_path = (
        repository_root / "reports" / "DASHBOARD_ASSURANCE_REVIEW_EVIDENCE_2026-09-05.json"
    )
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["record_format"] == "forgegate-dashboard-assurance-review-evidence-v1"
    assert review["fixture"]["classification"] == "GENERIC_EPHEMERAL_TEST_DATA"
    assert review["actual"]["decision"] == "PASS"
    assert review["actual"]["rule_expected"] == review["actual"]["rule_actual"] == 0
    assert review["actual"]["attestation_assurance"] == "unsigned_local"
    assert review["boundaries"]["personal_data_used"] is False
    assert review["boundaries"]["production_readiness_proven"] is False

    gallery = (repository_root / "docs" / "PORTFOLIO_EVIDENCE.md").read_text(encoding="utf-8")
    for asset in review["assets"]:
        payload = (repository_root / asset["path"]).read_bytes()
        assert payload.startswith(b"\xff\xd8\xff")
        assert len(payload) == asset["bytes"]
        assert hashlib.sha256(payload).hexdigest() == asset["sha256"]
        assert Path(asset["path"]).name in gallery

    msp_path = repository_root / "reports" / "MSP430_MANUAL_UNPLUG_REPLUG_EVIDENCE_2026-09-05.json"
    msp = json.loads(msp_path.read_text(encoding="utf-8"))
    assert msp["physical_action"]["performed_by"] == "project owner"
    assert msp["physical_action"]["owner_observed_live_transition"] is True
    assert msp["post_reconnect_window"]["result"] == "PASS"
    assert msp["post_reconnect_window"]["reconnects_end"] == 1
    assert [item["code"] for item in msp["decoded_fault_follow_up"]["reported_issues"]] == [
        "DS18B20_MISSING",
        "NTC_RANGE",
        "INA219_COMM",
    ]
    screenshot = msp["decoded_fault_follow_up"]["screenshot"]
    payload = (repository_root / screenshot["path"]).read_bytes()
    assert len(payload) == screenshot["bytes"]
    assert hashlib.sha256(payload).hexdigest() == screenshot["sha256"]
    boundaries = msp["boundaries"]
    assert boundaries["bytes_transmitted_to_device"] == 0
    assert all(
        value is False for key, value in boundaries.items() if key != "bytes_transmitted_to_device"
    )


def test_dashboard_static_assets_headers_and_contract_boundary(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    with _dashboard_client(tmp_path, repository_root) as client:
        redirect = client.get("/app", follow_redirects=False)
        index = client.get("/app/")
        asset_names = re.findall(r'/app/assets/([^"\']+)', index.text)
        assets = [client.get(f"/app/assets/{name}") for name in asset_names]
        missing = client.get("/app/assets/missing.js")
        hidden = client.get("/app/.vite/manifest.json")
        openapi = client.get("/openapi.json")

    assert redirect.status_code == 307
    assert redirect.headers["location"] == "/app/"
    assert index.status_code == 200
    assert "ForgeGate" in index.text
    assert index.headers["content-security-policy"].startswith("default-src 'none'")
    assert index.headers["x-frame-options"] == "DENY"
    assert index.headers["x-content-type-options"] == "nosniff"
    assert index.headers["referrer-policy"] == "no-referrer"
    assert index.headers["cache-control"] == "no-cache"
    assert asset_names and all(response.status_code == 200 for response in assets)
    assert all("immutable" in response.headers["cache-control"] for response in assets)
    scripts = [
        response.text
        for name, response in zip(asset_names, assets, strict=True)
        if name.endswith(".js")
    ]
    assert scripts
    assert all("Your Dashboard session expired" in script for script in scripts)
    assert all("--role ROLE" in script for script in scripts)
    assert all("Candidate pages" in script for script in scripts)
    assert all("Live devices" in script for script in scripts)
    assert all("Connection" in script and "Heartbeat" in script for script in scripts)
    assert all("Decoded firmware reports" in script for script in scripts)
    assert all("Bound evidence" in script and "Policy decision" in script for script in scripts)
    assert all("Release assurance" in script and "assurance-review" in script for script in scripts)
    assert all("producer authenticity" in script for script in scripts)
    assert all("hardware_control=" in script for script in scripts)
    assert all("Previous page" in script and "Next page" in script for script in scripts)
    assert all("Showing " in script for script in scripts)
    assert all("candidate-dialog-title" in script for script in scripts)
    assert all("DRAFT CREATED" in script for script in scripts)
    assert all(
        "Draft values restored for review; no request has been submitted." in script
        for script in scripts
    )
    assert all("Retry-After" in script and "Retry in" in script for script in scripts)
    assert all("This write will not be retried automatically" in script for script in scripts)
    assert all("stated 4 MiB service limit" in script for script in scripts)
    assert all("Do not assume the write failed" in script for script in scripts)
    assert all("aria-live" in script and "assertive" in script for script in scripts)
    frontend_source = (repository_root / "frontend" / "src" / "main.ts").read_text(encoding="utf-8")
    assert "function paginatedReviewTable" in frontend_source
    assert "const pageSize = 25" in frontend_source
    assert 'window.scrollTo({ top: 0, left: 0, behavior: "auto" })' in frontend_source
    assert not any(
        unsafe in script
        for script in scripts
        for unsafe in (
            ".innerHTML",
            ".outerHTML",
            "insertAdjacentHTML",
            "localStorage",
            "sessionStorage",
            "serviceWorker",
            "eval(",
            "new Function",
        )
    )
    assert missing.status_code == hidden.status_code == 404
    assert "immutable" not in missing.headers.get("cache-control", "")
    assert not any(path.startswith("/app") for path in openapi.json()["paths"])


def test_dashboard_openapi_export_is_deterministic_and_complete(tmp_path: Path) -> None:
    output = tmp_path / "dashboard-openapi.json"
    result = runner.invoke(app, ["export-dashboard-openapi", str(output)])
    first = create_dashboard_openapi()
    second = create_dashboard_openapi()

    assert result.exit_code == 0, result.output
    assert first == second == json.loads(output.read_text(encoding="utf-8"))
    assert b"\r\n" not in output.read_bytes()
    assert set(first["paths"]) == {
        "/app/api/activation",
        "/app/api/activations",
        "/app/api/activations/{activation_code}/challenge",
        "/app/api/activations/{activation_code}/complete",
        "/app/api/audit-events",
        "/app/api/candidates",
        "/app/api/candidates/{candidate_id}",
        "/app/api/candidates/{candidate_id}/assurance-review",
        "/app/api/live-status",
        "/app/api/overview",
        "/app/api/projects",
        "/app/api/projects/{project_id}/candidates",
        "/app/api/session",
    }
    assert first["paths"]["/app/api/candidates"]["post"]["operationId"] == (
        "createDashboardCandidate"
    )
    assert first["paths"]["/app/api/session"]["delete"]["operationId"] == ("endDashboardSession")
    assert first["paths"]["/app/api/live-status"]["get"]["operationId"] == (
        "getDashboardLiveStatus"
    )
    assert (
        first["paths"]["/app/api/candidates/{candidate_id}/assurance-review"]["get"]["operationId"]
        == "getDashboardCandidateAssuranceReview"
    )
    assert "HTTPBearer" not in first.get("components", {}).get("securitySchemes", {})

    rejected = runner.invoke(
        app,
        ["export-dashboard-openapi", str(tmp_path / "missing" / "openapi.json")],
    )
    assert rejected.exit_code == 3
    assert "output parent does not exist" in rejected.output


def test_dashboard_rejects_foreign_origin_and_requires_browser_binding(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    with _dashboard_client(tmp_path, repository_root) as client:
        foreign = client.post(
            "/app/api/activations",
            headers={"Origin": "https://attacker.invalid"},
            json={},
        )
        missing_origin = client.post("/app/api/activations", json={})
        unbound_poll = client.get("/app/api/activation")
        unauthenticated = client.get("/app/api/session")

    assert foreign.status_code == missing_origin.status_code == 403
    assert foreign.json()["error"]["code"] == "DASHBOARD_ORIGIN_INVALID"
    assert missing_origin.json()["error"]["code"] == "DASHBOARD_ORIGIN_REQUIRED"
    assert unbound_poll.status_code == unauthenticated.status_code == 401
    assert "no-store" in unauthenticated.headers["cache-control"]
    assert unauthenticated.headers["www-authenticate"] == "Bearer"


def test_dashboard_activation_session_overview_and_logout(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    with _dashboard_client(tmp_path, repository_root) as client:
        activated = _activate(client)
        session = client.get("/app/api/session")
        overview = client.get("/app/api/overview")
        wrong_csrf = client.delete(
            "/app/api/session",
            headers={**ORIGIN_HEADER, "X-ForgeGate-CSRF": "x" * 43},
        )
        still_active = client.get("/app/api/session")
        logout = client.delete(
            "/app/api/session",
            headers={**ORIGIN_HEADER, "X-ForgeGate-CSRF": activated["csrf_token"]},
        )
        ended = client.get("/app/api/session")

    assert session.status_code == overview.status_code == 200
    assert session.json()["principal"]["role"] == "operator"
    assert session.json()["csrf_token"] == activated["csrf_token"]
    assert overview.json()["database_schema_version"] == 8
    assert overview.json()["hardware_access"] == "NOT_PERFORMED"
    assert len(overview.json()["limitations"]) == 4
    assert wrong_csrf.status_code == 403
    assert wrong_csrf.json()["error"]["code"] == "DASHBOARD_CSRF_INVALID"
    assert still_active.status_code == 200
    assert logout.status_code == 200
    assert logout.json()["status"] == "SESSION_ENDED"
    assert ended.status_code == 401


def test_dashboard_live_status_is_authenticated_and_retains_read_only_boundary(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    class StaticLiveStatusProvider:
        hardware_access = "READ_ONLY_TELEMETRY"

        def snapshot(self) -> LiveStatusPage:
            observed = datetime(2026, 9, 5, 12, 0, 1, tzinfo=UTC)
            return LiveStatusPage(
                observed_at=observed,
                sources=(
                    LiveSourceStatus(
                        source_id="msp430-uart",
                        source_type="msp430.uart.v1",
                        display_name="MSP430 UART monitor",
                        connection="CONNECTED",
                        heartbeat="NORMAL",
                        device_health="FAULT",
                        detail_code="HEARTBEAT_NORMAL",
                        detail_message="Valid read-only telemetry is current.",
                        endpoint="COM4",
                        protocol="msp430.uart.v1",
                        baud_rate=115200,
                        expected_interval_seconds=1,
                        stale_after_seconds=3,
                        observed_at=observed,
                        last_heartbeat_at=observed,
                        heartbeat_age_seconds=0,
                        sequence=42,
                        uptime_ms=42000,
                        device_state="FAULT",
                        fault_flags="0015",
                        frames_received=42,
                        protocol_errors=0,
                        sequence_gaps=0,
                        reconnects=0,
                    ),
                ),
            )

    with _dashboard_client(
        tmp_path,
        repository_root,
        live_status_provider=StaticLiveStatusProvider(),
    ) as client:
        unauthenticated = client.get("/app/api/live-status")
        _activate(client)
        overview = client.get("/app/api/overview")
        status_page = client.get("/app/api/live-status")

    assert unauthenticated.status_code == 401
    assert overview.status_code == 200
    assert overview.json()["hardware_access"] == "READ_ONLY_TELEMETRY"
    assert "no command" in overview.json()["limitations"][2].lower()
    assert status_page.status_code == 200
    source = status_page.json()["sources"][0]
    assert source["connection"] == "CONNECTED"
    assert source["heartbeat"] == "NORMAL"
    assert source["device_health"] == "FAULT"
    assert source["fault_flags"] == "0015"
    assert source["hardware_control"] == "NOT_PERFORMED"
    assert source["evidence_boundary"] == "LIVE_STATUS_ONLY_NOT_RELEASE_EVIDENCE"


def test_dashboard_assurance_review_joins_retained_documents_without_new_claims(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _completed_dashboard_application(tmp_path, repository_root)
    with TestClient(
        create_api_app(
            tmp_path / "forgegate.db",
            application=application,
            authenticator=ApiAuthenticator(TEST_TRUST_STORE),
            dashboard=True,
        ),
        base_url=ORIGIN,
    ) as client:
        unauthenticated = client.get(f"/app/api/candidates/{candidate_id}/assurance-review")
        _activate(client)
        response = client.get(f"/app/api/candidates/{candidate_id}/assurance-review")

    assert unauthenticated.status_code == 401
    assert response.status_code == 200, response.text
    review = response.json()
    assert review["schema_version"] == "forgegate.dashboard-candidate-assurance-review.v1"
    assert review["candidate"]["status"] == "PASS"
    assert review["evidence_binding"]["assembly"]["bundle"]["evidence"]
    assert (
        review["policy_material"]["material_id"]
        == (review["policy_evaluation"]["policy_material_id"])
    )
    assert review["policy_evaluation"]["decision"] == "PASS"
    assert review["attestation"]["candidate"]["candidate_id"] == candidate_id
    assert review["assurance_bundle_id"].startswith("sha256:")
    assert review["assurance"] == "unsigned_local"
    assert review["source_artifact_bytes"] == "not_embedded"
    assert any("not producer authenticity" in item for item in review["limitations"])


def test_dashboard_project_candidate_replay_conflict_and_audit(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    with _dashboard_client(tmp_path, repository_root) as client:
        activated = _activate(client)
        projects = client.get("/app/api/projects?limit=100")
        empty = client.get("/app/api/projects/sample-api/candidates")
        headers = {
            **ORIGIN_HEADER,
            "X-ForgeGate-CSRF": activated["csrf_token"],
            "Idempotency-Key": "dashboard:candidate:test-001",
        }
        no_origin = client.post(
            "/app/api/candidates",
            headers={
                "X-ForgeGate-CSRF": activated["csrf_token"],
                "Idempotency-Key": "dashboard:candidate:no-origin",
            },
            json=_candidate_payload(),
        )
        no_csrf = client.post(
            "/app/api/candidates",
            headers={**ORIGIN_HEADER, "Idempotency-Key": "dashboard:candidate:no-csrf"},
            json=_candidate_payload(),
        )
        created = client.post("/app/api/candidates", headers=headers, json=_candidate_payload())
        replay = client.post("/app/api/candidates", headers=headers, json=_candidate_payload())
        conflict = client.post(
            "/app/api/candidates",
            headers=headers,
            json=_candidate_payload(version="1.2.1"),
        )
        candidate_id = created.json()["candidate_id"]
        detail = client.get(f"/app/api/candidates/{candidate_id}")
        review = client.get(f"/app/api/candidates/{candidate_id}/assurance-review")
        audit = client.get(
            f"/app/api/audit-events?project_id=sample-api&candidate_id={candidate_id}&limit=100"
        )
        missing_scope = client.get("/app/api/projects/another-project/candidates")

    assert projects.status_code == 200
    assert [item["project_id"] for item in projects.json()["projects"]] == ["sample-api"]
    assert empty.status_code == 200 and empty.json()["candidates"] == []
    assert no_origin.status_code == no_csrf.status_code == 403
    assert created.status_code == replay.status_code == 201
    assert created.json() == replay.json() == detail.json()
    assert review.status_code == 200
    assert review.json()["candidate"]["status"] == "DRAFT"
    assert review.json()["evidence_binding"] is None
    assert review.json()["policy_evaluation"] is None
    assert review.json()["attestation"] is None
    assert review.json()["assurance_bundle_id"] is None
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "STORE_IDEMPOTENCY_CONFLICT"
    assert [event["event_type"] for event in audit.json()["events"]] == ["candidate.created"]
    assert missing_scope.status_code == 403


def test_dashboard_candidate_pages_are_bounded_and_cursor_complete(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    with _dashboard_client(tmp_path, repository_root) as client:
        activated = _activate(client)
        created_ids = set()
        for index in range(3):
            response = client.post(
                "/app/api/candidates",
                headers={
                    **ORIGIN_HEADER,
                    "X-ForgeGate-CSRF": activated["csrf_token"],
                    "Idempotency-Key": f"dashboard:candidate:page-{index}",
                },
                json=_candidate_payload(
                    version=f"1.2.{index}",
                    commit_sha=f"{index + 1:x}" * 40,
                ),
            )
            assert response.status_code == 201, response.text
            created_ids.add(response.json()["candidate_id"])

        first = client.get("/app/api/projects/sample-api/candidates?limit=2")
        assert first.status_code == 200, first.text
        first_document = first.json()
        second = client.get(
            "/app/api/projects/sample-api/candidates",
            params={
                "limit": 2,
                "after_candidate_id": first_document["next_after_candidate_id"],
            },
        )
        assert second.status_code == 200, second.text
        second_document = second.json()

    first_ids = {item["candidate_id"] for item in first_document["candidates"]}
    second_ids = {item["candidate_id"] for item in second_document["candidates"]}
    assert len(first_ids) == 2 and first_document["has_more"] is True
    assert len(second_ids) == 1 and second_document["has_more"] is False
    assert first_ids.isdisjoint(second_ids)
    assert first_ids | second_ids == created_ids


def test_dashboard_producer_is_read_only_and_cannot_query_audit(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    with _dashboard_client(tmp_path, repository_root, role=IdentityRole.PRODUCER) as client:
        activated = _activate(client, role="producer")
        assert client.get("/app/api/projects").status_code == 200
        denied_write = client.post(
            "/app/api/candidates",
            headers={
                **ORIGIN_HEADER,
                "X-ForgeGate-CSRF": activated["csrf_token"],
                "Idempotency-Key": "dashboard:producer:denied",
            },
            json=_candidate_payload(),
        )
        denied_audit = client.get("/app/api/audit-events?project_id=sample-api")

    assert denied_write.status_code == denied_audit.status_code == 403
    assert denied_write.json()["error"]["code"] == "API_ROLE_FORBIDDEN"


def test_dashboard_activation_replay_conflict_and_wrong_browser(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    authenticator = ApiAuthenticator(TEST_TRUST_STORE)
    application = _application_with_project(tmp_path, repository_root)
    app = create_api_app(
        tmp_path / "forgegate.db",
        application=application,
        authenticator=authenticator,
        dashboard=True,
    )
    with TestClient(app, base_url=ORIGIN) as client:
        started = client.post("/app/api/activations", headers=ORIGIN_HEADER, json={})
        code = started.json()["activation_code"]
        request = {
            "identity_id": TEST_IDENTITY.identity_id,
            "role": "operator",
            "project_ids": ["sample-api"],
        }
        challenge = client.post(f"/app/api/activations/{code}/challenge", json=request)
        challenge_replay = client.post(f"/app/api/activations/{code}/challenge", json=request)
        challenge_conflict = client.post(
            f"/app/api/activations/{code}/challenge",
            json={**request, "project_ids": ["another-project"]},
        )
        signed = sign_api_challenge(
            ApiAuthChallenge.model_validate(challenge.json()),
            identity=TEST_IDENTITY,
            private_key=TEST_PRIVATE_KEY,
        )
        completed = client.post(
            f"/app/api/activations/{code}/complete",
            json=signed.model_dump(mode="json"),
        )
        completed_replay = client.post(
            f"/app/api/activations/{code}/complete",
            json=signed.model_dump(mode="json"),
        )
        with TestClient(app, base_url=ORIGIN) as other_browser:
            wrong_browser = other_browser.get("/app/api/activation")
        authenticated = client.get("/app/api/activation")
        code_reuse = client.post(f"/app/api/activations/{code}/challenge", json=request)

    assert challenge.status_code == challenge_replay.status_code == 201
    assert challenge.json() == challenge_replay.json()
    assert challenge_conflict.status_code == 409
    assert completed.status_code == completed_replay.status_code == 201
    assert completed.json() == completed_replay.json()
    assert wrong_browser.status_code == 401
    assert authenticated.status_code == 200
    assert code_reuse.status_code == 401


def test_dashboard_session_manager_expiry_capacity_and_invalid_sequences() -> None:
    current = [datetime(2026, 9, 4, 15, 0, tzinfo=UTC)]
    authenticator = ApiAuthenticator(TEST_TRUST_STORE, clock=lambda: current[0])
    manager = DashboardSessionManager(
        authenticator,
        activation_ttl=timedelta(seconds=10),
        max_pending_activations=1,
        max_dashboard_sessions=1,
        clock=lambda: current[0],
    )
    started, browser = manager.start_activation()
    with pytest.raises(ApiAuthenticationError, match="DASHBOARD_ACTIVATION_CAPACITY_REACHED"):
        manager.start_activation()
    with pytest.raises(ApiAuthenticationError, match="CHALLENGE_REQUIRED"):
        manager.complete_activation(
            started.activation_code,
            ApiSessionCreateRequest(
                challenge_id="chal-" + "0" * 32,
                signature_base64=base64.b64encode(bytes(64)).decode("ascii"),
            ),
        )
    pending, cookie = manager.poll_activation(browser)
    assert pending.status == "PENDING" and cookie is None
    current[0] += timedelta(seconds=10)
    with pytest.raises(ApiAuthenticationError, match="DASHBOARD_ACTIVATION_INVALID"):
        manager.poll_activation(browser)
    replacement, _ = manager.start_activation()
    assert replacement.activation_code != started.activation_code
    with pytest.raises(ValueError, match="timezone-aware"):
        DashboardSessionManager(
            authenticator,
            clock=lambda: datetime(2026, 9, 4, 15, 0),
        ).start_activation()


def test_dashboard_session_manager_completed_activation_guards() -> None:
    manager = DashboardSessionManager(ApiAuthenticator(TEST_TRUST_STORE))
    started, browser_cookie = manager.start_activation()
    request = ApiChallengeRequest(
        identity_id=TEST_IDENTITY.identity_id,
        role=IdentityRole.OPERATOR,
        project_ids=("sample-api",),
    )
    challenge = manager.issue_challenge(started.activation_code, request)
    with pytest.raises(ApiAuthenticationError, match="CHALLENGE_MISMATCH"):
        manager.complete_activation(
            started.activation_code,
            ApiSessionCreateRequest(
                challenge_id="chal-" + "0" * 32,
                signature_base64=base64.b64encode(bytes(64)).decode("ascii"),
            ),
        )
    signed = sign_api_challenge(
        challenge,
        identity=TEST_IDENTITY,
        private_key=TEST_PRIVATE_KEY,
    )
    manager.complete_activation(started.activation_code, signed)
    with pytest.raises(ApiAuthenticationError, match="ALREADY_COMPLETED"):
        manager.issue_challenge(started.activation_code, request)
    changed = signed.model_copy(
        update={"signature_base64": base64.b64encode(b"x" * 64).decode("ascii")}
    )
    with pytest.raises(ApiAuthenticationError, match="ACTIVATION_CONFLICT"):
        manager.complete_activation(started.activation_code, changed)
    first, first_cookie = manager.poll_activation(browser_cookie)
    second, second_cookie = manager.poll_activation(browser_cookie)
    assert first == second
    assert first_cookie == second_cookie


def test_dashboard_session_manager_capacity_and_underlying_expiry() -> None:
    auth_time = [datetime(2026, 9, 4, 16, 0, tzinfo=UTC)]
    dashboard_time = [auth_time[0]]
    authenticator = ApiAuthenticator(
        TEST_TRUST_STORE,
        session_ttl=timedelta(minutes=1),
        clock=lambda: auth_time[0],
    )
    manager = DashboardSessionManager(
        authenticator,
        max_pending_activations=3,
        max_dashboard_sessions=1,
        clock=lambda: dashboard_time[0],
    )
    _, dashboard_cookie = _activate_manager(manager)

    started, browser_cookie = manager.start_activation()
    challenge = manager.issue_challenge(
        started.activation_code,
        ApiChallengeRequest(
            identity_id=TEST_IDENTITY.identity_id,
            role=IdentityRole.OPERATOR,
            project_ids=("sample-api",),
        ),
    )
    manager.complete_activation(
        started.activation_code,
        sign_api_challenge(
            challenge,
            identity=TEST_IDENTITY,
            private_key=TEST_PRIVATE_KEY,
        ),
    )
    with pytest.raises(ApiAuthenticationError, match="SESSION_CAPACITY_REACHED"):
        manager.poll_activation(browser_cookie)

    auth_time[0] += timedelta(minutes=1)
    with pytest.raises(ApiAuthenticationError, match="API_SESSION_INVALID"):
        manager.session(dashboard_cookie)
    with pytest.raises(ApiAuthenticationError, match="DASHBOARD_SESSION_INVALID"):
        manager.session(dashboard_cookie)


def test_dashboard_session_manager_rejects_exhausted_code_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("forgegate.dashboard.sessions.secrets.choice", lambda _: "A")
    manager = DashboardSessionManager(
        ApiAuthenticator(TEST_TRUST_STORE),
        max_pending_activations=2,
    )
    manager.start_activation()
    with pytest.raises(ApiAuthenticationError, match="ACTIVATION_CAPACITY_REACHED"):
        manager.start_activation()


@pytest.mark.parametrize(
    ("ttl", "pending", "sessions", "message"),
    [
        (timedelta(0), 10, 10, "activation TTL"),
        (timedelta(minutes=6), 10, 10, "activation TTL"),
        (timedelta(seconds=10), 0, 10, "pending Dashboard activations"),
        (timedelta(seconds=10), 10, 1001, "Dashboard sessions"),
    ],
)
def test_dashboard_session_manager_rejects_invalid_limits(
    ttl: timedelta,
    pending: int,
    sessions: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        DashboardSessionManager(
            ApiAuthenticator(TEST_TRUST_STORE),
            activation_ttl=ttl,
            max_pending_activations=pending,
            max_dashboard_sessions=sessions,
        )


def test_dashboard_requires_packaged_static_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="index is missing"):
        create_api_app(
            tmp_path / "forgegate.db",
            authenticator=ApiAuthenticator(TEST_TRUST_STORE),
            dashboard=True,
            dashboard_static_root=tmp_path / "missing",
        )

    static_root = tmp_path / "static"
    static_root.mkdir()
    (static_root / "index.html").write_text("<!doctype html>", encoding="utf-8")
    with pytest.raises(ValueError, match="asset inventory is missing"):
        create_api_app(
            tmp_path / "forgegate.db",
            authenticator=ApiAuthenticator(TEST_TRUST_STORE),
            dashboard=True,
            dashboard_static_root=static_root,
        )


def test_dashboard_asset_inventory_detects_tampering(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    source = repository_root / "src/forgegate/dashboard/static"
    copied = tmp_path / "static"
    shutil.copytree(source, copied)
    inventory = validate_dashboard_assets(copied)
    assert inventory == build_dashboard_asset_inventory(copied)
    script = next((copied / "assets").glob("*.js"))
    script.write_bytes(script.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="do not match"):
        validate_dashboard_assets(copied)
    write_dashboard_asset_inventory(copied)
    assert validate_dashboard_assets(copied).assets


def test_dashboard_asset_inventory_rejects_invalid_document(tmp_path: Path) -> None:
    root = tmp_path / "static"
    root.mkdir()
    (root / "asset-inventory.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="missing or invalid"):
        validate_dashboard_assets(root)
    with pytest.raises(ValueError, match="safe relative path"):
        DashboardAsset(path="../escape.js", sha256="0" * 64, size_bytes=1)
    (root / "asset-inventory.json").write_bytes(b"x" * (64 * 1024 + 1))
    with pytest.raises(ValueError, match="missing or invalid"):
        validate_dashboard_assets(root)


def test_dashboard_asset_inventory_requires_canonical_hashed_assets() -> None:
    common = {
        "sha256": "0" * 64,
        "size_bytes": 1,
    }
    plain_assets = tuple(
        DashboardAsset(path=path, **common)
        for path in (".vite/manifest.json", "a.js", "b.css", "index.html")
    )
    with pytest.raises(ValueError, match="content-hashed"):
        DashboardAssetInventory(assets=plain_assets)
    duplicated = (
        DashboardAsset(path=".vite/manifest.json", **common),
        DashboardAsset(path="assets/index-ABCDEFGH.js", **common),
        DashboardAsset(path="index.html", **common),
        DashboardAsset(path="index.html", **common),
    )
    with pytest.raises(ValueError, match="unique canonical"):
        DashboardAssetInventory(assets=duplicated)
    missing_index = tuple(
        DashboardAsset(path=path, **common)
        for path in (
            ".vite/manifest.json",
            "assets/index-ABCDEFGH.css",
            "assets/index-ABCDEFGH.js",
            "third-party-licenses.json",
        )
    )
    with pytest.raises(ValueError, match="must include index"):
        DashboardAssetInventory(assets=missing_index)


def test_dashboard_cli_starts_loopback_app_and_rejects_wrong_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trust_path = tmp_path / "trust-store.json"
    trust_path.write_text(TEST_TRUST_STORE.model_dump_json(indent=2), encoding="utf-8")
    observed: dict[str, Any] = {}

    def fake_run(application: Any, *, host: str, port: int, log_level: str) -> None:
        observed.update(application=application, host=host, port=port, log_level=log_level)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    result = runner.invoke(
        app,
        [
            "dashboard",
            "--database",
            str(tmp_path / "dashboard.db"),
            "--trust-store",
            str(trust_path),
            "--host",
            "localhost",
            "--port",
            "8123",
            "--session-ttl-seconds",
            "120",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "http://localhost:8123/app/" in result.output
    assert observed["host"] == "localhost"
    assert observed["port"] == 8123
    assert observed["log_level"] == "info"
    assert observed["application"].state.dashboard_session_manager is not None

    wrong_document = tmp_path / "identity.json"
    wrong_document.write_text(TEST_IDENTITY.model_dump_json(indent=2), encoding="utf-8")
    rejected = runner.invoke(
        app,
        [
            "dashboard",
            "--database",
            str(tmp_path / "wrong.db"),
            "--trust-store",
            str(wrong_document),
        ],
    )
    assert rejected.exit_code == 3
    assert "must contain forgegate.trust-store.v1" in rejected.output


def test_dashboard_cli_starts_and_stops_optional_read_only_msp430_monitor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trust_path = tmp_path / "trust-store.json"
    trust_path.write_text(TEST_TRUST_STORE.model_dump_json(indent=2), encoding="utf-8")
    observed: dict[str, Any] = {}

    class FakeMonitor:
        hardware_access = "READ_ONLY_TELEMETRY"

        def __init__(self, port: str, *, stale_after_seconds: float) -> None:
            observed.update(port=port, stale_after_seconds=stale_after_seconds)

        def start(self) -> None:
            observed["started"] = True

        def stop(self) -> None:
            observed["stopped"] = True

    def fake_run(application: Any, *, host: str, port: int, log_level: str) -> None:
        observed.update(application=application, host=host, http_port=port, log_level=log_level)

    monkeypatch.setattr(
        "forgegate.compatibility.msp430_live.Msp430SerialMonitor",
        FakeMonitor,
    )
    monkeypatch.setattr(uvicorn, "run", fake_run)
    result = runner.invoke(
        app,
        [
            "dashboard",
            "--database",
            str(tmp_path / "dashboard.db"),
            "--trust-store",
            str(trust_path),
            "--port",
            "8123",
            "--msp430-port",
            "COM4",
            "--msp430-stale-seconds",
            "4.5",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "read-only COM4 at 115200 baud; no bytes transmitted" in result.output
    assert observed["port"] == "COM4"
    assert observed["stale_after_seconds"] == 4.5
    assert observed["started"] is observed["stopped"] is True
    assert observed["application"].state.dashboard_live_status_provider.__class__ is FakeMonitor


def test_dashboard_activate_cli_loads_local_key_and_sanitizes_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_path = tmp_path / "identity.json"
    identity_path.write_text(TEST_IDENTITY.model_dump_json(indent=2), encoding="utf-8")
    private_key_path = tmp_path / "key.pem"
    private_key_path.write_bytes(
        TEST_PRIVATE_KEY.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    manager = DashboardSessionManager(ApiAuthenticator(TEST_TRUST_STORE))
    started, _ = manager.start_activation()
    challenge = manager.issue_challenge(
        started.activation_code,
        ApiChallengeRequest(
            identity_id=TEST_IDENTITY.identity_id,
            role=IdentityRole.OPERATOR,
            project_ids=("sample-api",),
        ),
    )
    completed = manager.complete_activation(
        started.activation_code,
        sign_api_challenge(
            challenge,
            identity=TEST_IDENTITY,
            private_key=TEST_PRIVATE_KEY,
        ),
    )
    observed: dict[str, Any] = {}

    def fake_activate(server: str, code: str, **kwargs: Any):
        observed.update(server=server, code=code, **kwargs)
        return completed

    monkeypatch.setattr("forgegate.dashboard.client.activate_dashboard", fake_activate)
    result = runner.invoke(
        app,
        [
            "dashboard-activate",
            "FG-ABCDE-FGHJK",
            "--identity",
            str(identity_path),
            "--private-key",
            str(private_key_path),
            "--role",
            "operator",
            "--project",
            "sample-api",
            "--server",
            "http://127.0.0.1:8123",
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"status": "AUTHENTICATED"' in result.output
    assert observed["project_ids"] == ("sample-api",)
    assert observed["identity"] == TEST_IDENTITY

    def fail_activate(*_args: Any, **_kwargs: Any):
        raise DashboardClientError("DASHBOARD_TEST_FAILURE", "safe local failure")

    monkeypatch.setattr("forgegate.dashboard.client.activate_dashboard", fail_activate)
    failed = runner.invoke(
        app,
        [
            "dashboard-activate",
            "FG-ABCDE-FGHJK",
            "--identity",
            str(identity_path),
            "--private-key",
            str(private_key_path),
            "--role",
            "operator",
            "--project",
            "sample-api",
        ],
    )
    assert failed.exit_code == 3
    assert "DASHBOARD_TEST_FAILURE: safe local failure" in failed.output
