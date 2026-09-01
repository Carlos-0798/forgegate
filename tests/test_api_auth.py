from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from pydantic import ValidationError
from typer.testing import CliRunner

from forgegate.api import (
    ApiAuthChallenge,
    ApiAuthenticationError,
    ApiAuthenticator,
    ApiChallengeRequest,
    ApiSessionCreateRequest,
    ApiSessionResponse,
    ApiSessionRevocationResponse,
    ApiTrustStoreReloadResponse,
    create_api_app,
    load_api_challenge,
    sign_api_challenge,
)
from forgegate.candidates import SQLiteCandidateRepository
from forgegate.cli import app as cli_app
from forgegate.config import load_config
from forgegate.identity import (
    IdentityRole,
    IdentityStatus,
    TrustedIdentity,
    create_trust_store,
    derive_signing_identity,
)
from tests.api_auth_support import TEST_IDENTITY, TEST_PRIVATE_KEY, TEST_TRUST_STORE

runner = CliRunner()


def _register_project(repository: SQLiteCandidateRepository, repository_root: Path) -> None:
    repository.register_project(
        load_config(repository_root / "examples/sample-python-api/forgegate.yaml"),
        registered_at=datetime(2026, 8, 31, 14, 0, tzinfo=UTC),
        idempotency_key="project:auth:setup",
    )


def _create_session(
    client: TestClient,
    *,
    identity=TEST_IDENTITY,
    private_key: Ed25519PrivateKey = TEST_PRIVATE_KEY,
    role: str = "operator",
    project_ids: tuple[str, ...] = ("sample-api",),
) -> ApiSessionResponse:
    challenge_response = client.post(
        "/v1/auth/challenges",
        json={
            "identity_id": identity.identity_id,
            "role": role,
            "project_ids": list(project_ids),
        },
    )
    assert challenge_response.status_code == 201, challenge_response.text
    challenge = ApiAuthChallenge.model_validate(challenge_response.json())
    request = sign_api_challenge(
        challenge,
        identity=identity,
        private_key=private_key,
    )
    response = client.post("/v1/auth/sessions", json=request.model_dump(mode="json"))
    assert response.status_code == 201, response.text
    return ApiSessionResponse.model_validate(response.json())


def test_api_requires_authenticator_and_bearer_session(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires an ApiAuthenticator"):
        create_api_app(tmp_path / "missing-auth.db")

    app = create_api_app(
        tmp_path / "forgegate.db",
        authenticator=ApiAuthenticator(TEST_TRUST_STORE),
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        missing = client.get("/v1/projects/sample-api")
        malformed = client.get(
            "/v1/projects/sample-api",
            headers={"Authorization": "Bearer malformed"},
        )
        session = _create_session(client)
        authorized = client.get(
            "/v1/projects/sample-api",
            headers={"Authorization": f"Bearer {session.access_token}"},
        )

    assert missing.status_code == malformed.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert missing.json()["error"]["code"] == "API_AUTHENTICATION_REQUIRED"
    assert malformed.json()["error"]["code"] == "API_SESSION_INVALID"
    assert authorized.status_code == 404


def test_operator_write_records_authenticated_actor_without_token(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    database = tmp_path / "forgegate.db"
    app = create_api_app(database, authenticator=ApiAuthenticator(TEST_TRUST_STORE))
    config = load_config(repository_root / "examples/sample-python-api/forgegate.yaml")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        session = _create_session(client)
        headers = {
            "Authorization": f"Bearer {session.access_token}",
            "Idempotency-Key": "project:auth:register",
        }
        registered = client.post(
            "/v1/projects",
            headers=headers,
            json={
                "config": config.model_dump(mode="json", by_alias=True),
                "registered_at": "2026-08-31T14:00:00Z",
            },
        )
        second_session = _create_session(client)
        replay = client.post(
            "/v1/projects",
            headers={
                "Authorization": f"Bearer {second_session.access_token}",
                "Idempotency-Key": "project:auth:register",
            },
            json={
                "config": config.model_dump(mode="json", by_alias=True),
                "registered_at": "2026-08-31T14:00:00Z",
            },
        )
        audit = client.get(
            "/v1/audit-events",
            headers={"Authorization": f"Bearer {session.access_token}"},
            params={"project_id": "sample-api"},
        )

    assert registered.status_code == replay.status_code == 201
    assert registered.json() == replay.json()
    assert audit.status_code == 200
    assert len(audit.json()["events"]) == 1
    actor = audit.json()["events"][0]["actor"]
    assert actor == {
        "schema_version": "forgegate.audit-actor.v1",
        "identity_id": TEST_IDENTITY.identity_id,
        "display_name": TEST_IDENTITY.display_name,
        "role": "operator",
        "session_id": session.session_id,
        "trust_store_id": TEST_TRUST_STORE.trust_store_id,
        "authenticated_at": session.authenticated_at.isoformat().replace("+00:00", "Z"),
    }
    assert session.access_token not in database.read_text(encoding="utf-8", errors="ignore")


def test_challenge_is_one_time_and_signature_fails_closed(tmp_path: Path) -> None:
    authenticator = ApiAuthenticator(TEST_TRUST_STORE)
    app = create_api_app(tmp_path / "forgegate.db", authenticator=authenticator)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        challenge_response = client.post(
            "/v1/auth/challenges",
            json={
                "identity_id": TEST_IDENTITY.identity_id,
                "role": "operator",
                "project_ids": ["sample-api"],
            },
        )
        challenge = ApiAuthChallenge.model_validate(challenge_response.json())
        request = sign_api_challenge(
            challenge,
            identity=TEST_IDENTITY,
            private_key=TEST_PRIVATE_KEY,
        )
        raw_signature = bytearray(base64.b64decode(request.signature_base64))
        raw_signature[0] ^= 1
        invalid = client.post(
            "/v1/auth/sessions",
            json={
                "challenge_id": request.challenge_id,
                "signature_base64": base64.b64encode(raw_signature).decode("ascii"),
            },
        )
        replay = client.post(
            "/v1/auth/sessions",
            json=request.model_dump(mode="json"),
        )

    assert invalid.status_code == replay.status_code == 401
    assert invalid.json()["error"]["code"] == "API_CHALLENGE_SIGNATURE_INVALID"
    assert replay.json()["error"]["code"] == "API_CHALLENGE_INVALID"


def test_role_project_revocation_and_expiry_authorization(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    producer_store = create_trust_store(
        (
            TrustedIdentity(
                identity=TEST_IDENTITY,
                roles=(IdentityRole.PRODUCER,),
                project_ids=("sample-api",),
            ),
        )
    )
    database = tmp_path / "producer.db"
    repository = SQLiteCandidateRepository(database)
    repository.initialize()
    _register_project(repository, repository_root)
    app = create_api_app(database, authenticator=ApiAuthenticator(producer_store))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        producer = _create_session(client, role="producer")
        auth = {"Authorization": f"Bearer {producer.access_token}"}
        readable = client.get("/v1/projects/sample-api", headers=auth)
        write = client.post(
            "/v1/candidates",
            headers={**auth, "Idempotency-Key": "candidate:producer:denied"},
            json={
                "project_id": "sample-api",
                "version": "1.2.0",
                "commit_sha": "a" * 40,
                "source_branch": "main",
                "release_track": "pull-request",
                "created_at": "2026-08-31T15:00:00Z",
            },
        )
        project_denied = client.get("/v1/projects/another-project", headers=auth)

    assert readable.status_code == 200
    assert write.status_code == project_denied.status_code == 403
    assert write.json()["error"]["code"] == "API_ROLE_FORBIDDEN"
    assert project_denied.json()["error"]["code"] == "API_PROJECT_FORBIDDEN"

    revoked = create_trust_store(
        (
            TrustedIdentity(
                identity=TEST_IDENTITY,
                roles=(IdentityRole.OPERATOR,),
                project_ids=("sample-api",),
                status=IdentityStatus.REVOKED,
            ),
        )
    )
    with pytest.raises(ApiAuthenticationError, match="API_CHALLENGE_AUTHORITY_DENIED"):
        ApiAuthenticator(revoked).issue_challenge(
            ApiChallengeRequest(
                identity_id=TEST_IDENTITY.identity_id,
                role=IdentityRole.OPERATOR,
                project_ids=("sample-api",),
            )
        )

    current = [datetime(2026, 8, 31, 20, 0, tzinfo=UTC)]
    expiring = ApiAuthenticator(
        TEST_TRUST_STORE,
        session_ttl=timedelta(minutes=1),
        clock=lambda: current[0],
    )
    challenge = expiring.issue_challenge(
        ApiChallengeRequest(
            identity_id=TEST_IDENTITY.identity_id,
            role=IdentityRole.OPERATOR,
            project_ids=("sample-api",),
        )
    )
    session = expiring.create_session(
        sign_api_challenge(
            challenge,
            identity=TEST_IDENTITY,
            private_key=TEST_PRIVATE_KEY,
        )
    )
    current[0] += timedelta(minutes=1)
    with pytest.raises(ApiAuthenticationError, match="API_SESSION_INVALID"):
        expiring.authenticate(f"Bearer {session.access_token}")


def test_challenge_model_loader_and_cli_signing_are_strict(tmp_path: Path) -> None:
    authenticator = ApiAuthenticator(TEST_TRUST_STORE)
    challenge = authenticator.issue_challenge(
        ApiChallengeRequest(
            identity_id=TEST_IDENTITY.identity_id,
            role=IdentityRole.OPERATOR,
            project_ids=("sample-api",),
        )
    )
    challenge_path = tmp_path / "challenge.json"
    challenge_path.write_text(challenge.model_dump_json(indent=2), encoding="utf-8")
    identity_path = tmp_path / "identity.json"
    identity_path.write_text(TEST_IDENTITY.model_dump_json(indent=2), encoding="utf-8")
    private_key_path = tmp_path / "key.pem"
    from cryptography.hazmat.primitives import serialization

    private_key_path.write_bytes(
        TEST_PRIVATE_KEY.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    loaded = load_api_challenge(challenge_path)
    result = runner.invoke(
        cli_app,
        [
            "identity",
            "sign-api-challenge",
            str(challenge_path),
            str(identity_path),
            str(private_key_path),
        ],
    )
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version":"x","schema_version":"y"}', encoding="utf-8")

    assert loaded == challenge
    assert result.exit_code == 0, result.output
    assert ApiSessionCreateRequest.model_validate_json(result.output).challenge_id == (
        challenge.challenge_id
    )
    with pytest.raises(ApiAuthenticationError, match="duplicate JSON key"):
        load_api_challenge(duplicate)
    with pytest.raises(ValidationError):
        ApiChallengeRequest(
            identity_id=TEST_IDENTITY.identity_id,
            role=IdentityRole.OPERATOR,
            project_ids=("z-project", "a-project"),
        )


def test_signing_rejects_a_different_private_key() -> None:
    challenge = ApiAuthenticator(TEST_TRUST_STORE).issue_challenge(
        ApiChallengeRequest(
            identity_id=TEST_IDENTITY.identity_id,
            role=IdentityRole.OPERATOR,
            project_ids=("sample-api",),
        )
    )
    wrong = Ed25519PrivateKey.from_private_bytes(bytes(range(33, 65)))
    with pytest.raises(ApiAuthenticationError, match="API_CHALLENGE_IDENTITY_MISMATCH"):
        sign_api_challenge(challenge, identity=TEST_IDENTITY, private_key=wrong)

    payload = json.loads(challenge.model_dump_json())
    payload["expires_at"] = payload["issued_at"]
    with pytest.raises(ValidationError, match="lifetime"):
        ApiAuthChallenge.model_validate(payload)


def test_authentication_cache_capacity_is_bounded() -> None:
    authenticator = ApiAuthenticator(TEST_TRUST_STORE, max_pending_challenges=1)
    request = ApiChallengeRequest(
        identity_id=TEST_IDENTITY.identity_id,
        role=IdentityRole.OPERATOR,
        project_ids=("sample-api",),
    )
    authenticator.issue_challenge(request)
    with pytest.raises(ApiAuthenticationError, match="API_CHALLENGE_CAPACITY_REACHED"):
        authenticator.issue_challenge(request)


@pytest.mark.parametrize(
    "overrides",
    [
        {"challenge_ttl": timedelta(0)},
        {"session_ttl": timedelta(hours=2)},
        {"max_pending_challenges": 0},
        {"max_active_sessions": 10_001},
        {"challenge_rate_limit": 0},
        {"session_rate_limit": 10_001},
        {"auth_failure_rate_limit": 0},
        {"rate_limit_window": timedelta(milliseconds=999)},
    ],
)
def test_authenticator_rejects_unsafe_bounds(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ApiAuthenticator(TEST_TRUST_STORE, **overrides)  # type: ignore[arg-type]


def test_identity_authority_and_session_capacity_fail_closed() -> None:
    authenticator = ApiAuthenticator(TEST_TRUST_STORE, max_active_sessions=1)
    assert authenticator.trust_store_id == TEST_TRUST_STORE.trust_store_id
    with pytest.raises(ApiAuthenticationError, match="API_CHALLENGE_AUTHORITY_DENIED"):
        authenticator.issue_challenge(
            ApiChallengeRequest(
                identity_id=TEST_IDENTITY.identity_id,
                role=IdentityRole.PRODUCER,
                project_ids=("sample-api",),
            )
        )
    with pytest.raises(ApiAuthenticationError, match="API_CHALLENGE_AUTHORITY_DENIED"):
        authenticator.issue_challenge(
            ApiChallengeRequest(
                identity_id=TEST_IDENTITY.identity_id,
                role=IdentityRole.OPERATOR,
                project_ids=("unauthorized-project",),
            )
        )
    request = ApiChallengeRequest(
        identity_id=TEST_IDENTITY.identity_id,
        role=IdentityRole.OPERATOR,
        project_ids=("sample-api",),
    )
    first = authenticator.issue_challenge(request)
    authenticator.create_session(
        sign_api_challenge(
            first,
            identity=TEST_IDENTITY,
            private_key=TEST_PRIVATE_KEY,
        )
    )
    second = authenticator.issue_challenge(request)
    with pytest.raises(ApiAuthenticationError, match="API_SESSION_CAPACITY_REACHED"):
        authenticator.create_session(
            sign_api_challenge(
                second,
                identity=TEST_IDENTITY,
                private_key=TEST_PRIVATE_KEY,
            )
        )


def test_clock_and_challenge_loader_error_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_clock = ApiAuthenticator(TEST_TRUST_STORE, clock=lambda: datetime(2026, 8, 31))
    with pytest.raises(ValueError, match="timezone-aware"):
        invalid_clock.issue_challenge(
            ApiChallengeRequest(
                identity_id=TEST_IDENTITY.identity_id,
                role=IdentityRole.OPERATOR,
                project_ids=("sample-api",),
            )
        )
    with pytest.raises(ApiAuthenticationError, match="must be a regular file"):
        load_api_challenge(tmp_path / "missing.json")
    empty = tmp_path / "empty.json"
    empty.write_bytes(b"")
    with pytest.raises(ApiAuthenticationError, match="invalid byte size"):
        load_api_challenge(empty)
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"value":NaN}', encoding="utf-8")
    with pytest.raises(ApiAuthenticationError, match="non-finite"):
        load_api_challenge(nonfinite)
    readable = tmp_path / "readable.json"
    readable.write_text("{}", encoding="utf-8")

    def fail_read(_path: Path) -> bytes:
        raise OSError("injected read failure")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    with pytest.raises(ApiAuthenticationError, match="API_CHALLENGE_DOCUMENT_IO"):
        load_api_challenge(readable)


def test_session_logout_revokes_the_presented_session(tmp_path: Path) -> None:
    app = create_api_app(
        tmp_path / "logout.db",
        authenticator=ApiAuthenticator(TEST_TRUST_STORE),
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        session = _create_session(client)
        authorization = {"Authorization": f"Bearer {session.access_token}"}
        logout = client.delete("/v1/auth/session", headers=authorization)
        reuse = client.get("/v1/projects/sample-api", headers=authorization)

    revoked = ApiSessionRevocationResponse.model_validate(logout.json())
    assert logout.status_code == 200
    assert revoked.session_id == session.session_id
    assert revoked.reason == "self_logout"
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "API_SESSION_INVALID"


def test_operator_revocation_is_exact_and_project_scoped(tmp_path: Path) -> None:
    app = create_api_app(
        tmp_path / "revocation.db",
        authenticator=ApiAuthenticator(TEST_TRUST_STORE),
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        operator = _create_session(client, project_ids=("sample-api",))
        target = _create_session(client, project_ids=("sample-api",))
        outside_scope = _create_session(client, project_ids=("another-project",))
        operator_headers = {"Authorization": f"Bearer {operator.access_token}"}

        revoked = client.delete(
            f"/v1/auth/sessions/{target.session_id}",
            headers=operator_headers,
        )
        hidden = client.delete(
            f"/v1/auth/sessions/{outside_scope.session_id}",
            headers=operator_headers,
        )
        target_reuse = client.get(
            "/v1/projects/sample-api",
            headers={"Authorization": f"Bearer {target.access_token}"},
        )
        operator_reuse = client.get("/v1/projects/sample-api", headers=operator_headers)

    result = ApiSessionRevocationResponse.model_validate(revoked.json())
    assert result.reason == "operator_revocation"
    assert result.session_id == target.session_id
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "API_SESSION_NOT_FOUND"
    assert target_reuse.status_code == 401
    assert operator_reuse.status_code == 404


def test_producer_cannot_revoke_another_session(tmp_path: Path) -> None:
    producer_store = create_trust_store(
        (
            TrustedIdentity(
                identity=TEST_IDENTITY,
                roles=(IdentityRole.PRODUCER,),
                project_ids=("sample-api",),
            ),
        )
    )
    app = create_api_app(
        tmp_path / "producer-revocation.db",
        authenticator=ApiAuthenticator(producer_store),
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        producer = _create_session(client, role="producer")
        target = _create_session(client, role="producer")
        denied = client.delete(
            f"/v1/auth/sessions/{target.session_id}",
            headers={"Authorization": f"Bearer {producer.access_token}"},
        )
        reload_denied = client.post(
            "/v1/auth/trust-store/reload",
            headers={"Authorization": f"Bearer {producer.access_token}"},
        )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "API_ROLE_FORBIDDEN"
    assert reload_denied.status_code == 403
    assert reload_denied.json()["error"]["code"] == "API_TRUST_STORE_RELOAD_FORBIDDEN"


def test_live_trust_store_reload_revokes_incompatible_sessions_and_challenges(
    tmp_path: Path,
) -> None:
    target_key = Ed25519PrivateKey.from_private_bytes(bytes(range(33, 65)))
    target_identity = derive_signing_identity(target_key, display_name="reload-target")
    initial_store = create_trust_store(
        (
            TrustedIdentity(
                identity=TEST_IDENTITY,
                roles=(IdentityRole.OPERATOR,),
                project_ids=TEST_TRUST_STORE.identities[0].project_ids,
            ),
            TrustedIdentity(
                identity=target_identity,
                roles=(IdentityRole.PRODUCER,),
                project_ids=("sample-api",),
            ),
        )
    )
    replacement_store = create_trust_store((TEST_TRUST_STORE.identities[0],))
    configured = [replacement_store]
    authenticator = ApiAuthenticator(initial_store, trust_store_loader=lambda: configured[0])
    app = create_api_app(tmp_path / "reload.db", authenticator=authenticator)

    with TestClient(app, base_url="http://127.0.0.1") as client:
        operator = _create_session(
            client,
            project_ids=TEST_TRUST_STORE.identities[0].project_ids,
        )
        target = _create_session(
            client,
            identity=target_identity,
            private_key=target_key,
            role="producer",
        )
        pending_response = client.post(
            "/v1/auth/challenges",
            json={
                "identity_id": target_identity.identity_id,
                "role": "producer",
                "project_ids": ["sample-api"],
            },
        )
        pending = ApiAuthChallenge.model_validate(pending_response.json())
        pending_request = sign_api_challenge(
            pending,
            identity=target_identity,
            private_key=target_key,
        )
        operator_headers = {"Authorization": f"Bearer {operator.access_token}"}
        reloaded = client.post("/v1/auth/trust-store/reload", headers=operator_headers)
        target_reuse = client.get(
            "/v1/projects/sample-api",
            headers={"Authorization": f"Bearer {target.access_token}"},
        )
        challenge_reuse = client.post(
            "/v1/auth/sessions",
            json=pending_request.model_dump(mode="json"),
        )
        operator_reuse = client.get("/v1/projects/sample-api", headers=operator_headers)

    result = ApiTrustStoreReloadResponse.model_validate(reloaded.json())
    assert reloaded.status_code == 200
    assert result.previous_trust_store_id == initial_store.trust_store_id
    assert result.trust_store_id == replacement_store.trust_store_id
    assert result.discarded_challenges == 1
    assert result.revoked_sessions == 1
    assert result.retained_sessions == 1
    assert target_reuse.status_code == challenge_reuse.status_code == 401
    assert operator_reuse.status_code == 404


def test_trust_store_reload_requires_global_operator_scope_and_valid_input(
    tmp_path: Path,
) -> None:
    invalid_loader = ApiAuthenticator(
        TEST_TRUST_STORE,
        trust_store_loader=lambda: (_ for _ in ()).throw(ValueError("invalid")),
    )
    invalid_app = create_api_app(tmp_path / "invalid-reload.db", authenticator=invalid_loader)
    with TestClient(invalid_app, base_url="http://127.0.0.1") as client:
        session = _create_session(client, project_ids=("sample-api",))
        failed = client.post(
            "/v1/auth/trust-store/reload",
            headers={"Authorization": f"Bearer {session.access_token}"},
        )
    assert failed.status_code == 503
    assert failed.json()["error"] == {
        "code": "API_TRUST_STORE_RELOAD_FAILED",
        "message": "configured trust store could not be loaded and validated",
        "request_id": failed.json()["error"]["request_id"],
    }

    scoped = ApiAuthenticator(TEST_TRUST_STORE, trust_store_loader=lambda: TEST_TRUST_STORE)
    scoped_app = create_api_app(tmp_path / "scoped-reload.db", authenticator=scoped)
    with TestClient(scoped_app, base_url="http://127.0.0.1") as client:
        session = _create_session(client, project_ids=("sample-api",))
        denied = client.post(
            "/v1/auth/trust-store/reload",
            headers={"Authorization": f"Bearer {session.access_token}"},
        )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "API_TRUST_STORE_RELOAD_FORBIDDEN"


def test_trust_store_reload_unavailable_noop_and_missing_session_boundaries(
    tmp_path: Path,
) -> None:
    unavailable = ApiAuthenticator(TEST_TRUST_STORE)
    unavailable_app = create_api_app(tmp_path / "unavailable.db", authenticator=unavailable)
    with TestClient(unavailable_app, base_url="http://127.0.0.1") as client:
        session = _create_session(
            client,
            project_ids=TEST_TRUST_STORE.identities[0].project_ids,
        )
        headers = {"Authorization": f"Bearer {session.access_token}"}
        reload_response = client.post("/v1/auth/trust-store/reload", headers=headers)
        missing = client.delete(
            "/v1/auth/sessions/sess-00000000000000000000000000000000",
            headers=headers,
        )
    assert reload_response.status_code == 503
    assert reload_response.json()["error"]["code"] == "API_TRUST_STORE_RELOAD_UNAVAILABLE"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "API_SESSION_NOT_FOUND"

    no_op = ApiAuthenticator(TEST_TRUST_STORE, trust_store_loader=lambda: TEST_TRUST_STORE)
    no_op_app = create_api_app(tmp_path / "no-op.db", authenticator=no_op)
    with TestClient(no_op_app, base_url="http://127.0.0.1") as client:
        session = _create_session(
            client,
            project_ids=TEST_TRUST_STORE.identities[0].project_ids,
        )
        response = client.post(
            "/v1/auth/trust-store/reload",
            headers={"Authorization": f"Bearer {session.access_token}"},
        )
    result = ApiTrustStoreReloadResponse.model_validate(response.json())
    assert result.previous_trust_store_id == result.trust_store_id
    assert result.discarded_challenges == result.revoked_sessions == 0
    assert result.retained_sessions == 1


def test_authentication_rate_limits_are_bounded_and_return_retry_after(tmp_path: Path) -> None:
    current = [datetime(2026, 8, 31, 21, 0, tzinfo=UTC)]
    authenticator = ApiAuthenticator(
        TEST_TRUST_STORE,
        challenge_rate_limit=1,
        auth_failure_rate_limit=1,
        rate_limit_window=timedelta(seconds=30),
        clock=lambda: current[0],
    )
    app = create_api_app(tmp_path / "rate-limit.db", authenticator=authenticator)
    payload = {
        "identity_id": TEST_IDENTITY.identity_id,
        "role": "operator",
        "project_ids": ["sample-api"],
    }
    with TestClient(app, base_url="http://127.0.0.1") as client:
        first = client.post("/v1/auth/challenges", json=payload)
        limited = client.post("/v1/auth/challenges", json=payload)
        first_failure = client.get("/v1/projects/sample-api")
        limited_failure = client.get("/v1/projects/sample-api")
        current[0] += timedelta(seconds=30)
        reset = client.post("/v1/auth/challenges", json=payload)

    assert first.status_code == reset.status_code == 201
    assert first_failure.status_code == 401
    assert limited.status_code == limited_failure.status_code == 429
    assert limited.headers["retry-after"] == limited_failure.headers["retry-after"] == "30"
    assert limited.json()["error"]["code"] == "API_AUTH_RATE_LIMITED"


def test_authentication_endpoint_limits_precede_body_validation(tmp_path: Path) -> None:
    authenticator = ApiAuthenticator(
        TEST_TRUST_STORE,
        challenge_rate_limit=1,
        session_rate_limit=1,
    )
    app = create_api_app(tmp_path / "malformed-rate.db", authenticator=authenticator)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        first_challenge = client.post(
            "/v1/auth/challenges",
            content=b"{",
            headers={"Content-Type": "application/json"},
        )
        limited_challenge = client.post(
            "/v1/auth/challenges",
            content=b"{",
            headers={"Content-Type": "application/json"},
        )
        first_session = client.post(
            "/v1/auth/sessions",
            content=b"{",
            headers={"Content-Type": "application/json"},
        )
        limited_session = client.post(
            "/v1/auth/sessions",
            content=b"{",
            headers={"Content-Type": "application/json"},
        )

    assert first_challenge.status_code == first_session.status_code == 422
    assert limited_challenge.status_code == limited_session.status_code == 429
    assert limited_challenge.json()["error"]["code"] == "API_AUTH_RATE_LIMITED"
    assert limited_session.headers["Retry-After"] == "60"


def test_session_exchange_rate_limit_precedes_signature_work() -> None:
    authenticator = ApiAuthenticator(TEST_TRUST_STORE, session_rate_limit=1)
    challenge = authenticator.issue_challenge(
        ApiChallengeRequest(
            identity_id=TEST_IDENTITY.identity_id,
            role=IdentityRole.OPERATOR,
            project_ids=("sample-api",),
        )
    )
    request = sign_api_challenge(
        challenge,
        identity=TEST_IDENTITY,
        private_key=TEST_PRIVATE_KEY,
    )
    session = authenticator.create_session(request)
    assert authenticator.authenticate(f"Bearer {session.access_token}").session_id == (
        session.session_id
    )
    with pytest.raises(ApiAuthenticationError, match="API_AUTH_RATE_LIMITED") as caught:
        authenticator.create_session(request)
    assert caught.value.status_code == 429
    assert caught.value.retry_after_seconds is not None
