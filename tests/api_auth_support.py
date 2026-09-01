from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from forgegate.api import (
    ApiAuthChallenge,
    ApiAuthenticator,
    ApiSessionResponse,
    create_api_app,
    sign_api_challenge,
)
from forgegate.application import CandidateApplication
from forgegate.identity import (
    IdentityRole,
    IdentityStatus,
    TrustedIdentity,
    create_trust_store,
    derive_signing_identity,
)

TEST_PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
TEST_IDENTITY = derive_signing_identity(TEST_PRIVATE_KEY, display_name="api-test-operator")
TEST_PROJECT_IDS = (
    "another-project",
    "missing-project",
    "registered-project",
    "sample-api",
    "test-project",
)
TEST_TRUST_STORE = create_trust_store(
    (
        TrustedIdentity(
            identity=TEST_IDENTITY,
            roles=(IdentityRole.OPERATOR,),
            project_ids=TEST_PROJECT_IDS,
            status=IdentityStatus.ACTIVE,
        ),
    )
)


def test_authenticator(*, role: IdentityRole = IdentityRole.OPERATOR) -> ApiAuthenticator:
    trust_store = (
        TEST_TRUST_STORE
        if role is IdentityRole.OPERATOR
        else create_trust_store(
            (
                TrustedIdentity(
                    identity=TEST_IDENTITY,
                    roles=(role,),
                    project_ids=TEST_PROJECT_IDS,
                    status=IdentityStatus.ACTIVE,
                ),
            )
        )
    )
    return ApiAuthenticator(trust_store)


def create_test_api_app(
    database: Path,
    *,
    application: CandidateApplication | None = None,
    role: IdentityRole = IdentityRole.OPERATOR,
) -> FastAPI:
    app = create_api_app(
        database,
        application=application,
        authenticator=test_authenticator(role=role),
    )
    app.state.test_private_key = TEST_PRIVATE_KEY
    app.state.test_identity = TEST_IDENTITY
    app.state.test_project_ids = TEST_PROJECT_IDS
    return app


class AuthenticatedTestClient(TestClient):
    def __enter__(self) -> AuthenticatedTestClient:
        client = super().__enter__()
        challenge_response = client.post(
            "/v1/auth/challenges",
            json={
                "identity_id": self.app.state.test_identity.identity_id,
                "role": "operator",
                "project_ids": list(self.app.state.test_project_ids),
            },
        )
        assert challenge_response.status_code == 201, challenge_response.text
        challenge = ApiAuthChallenge.model_validate(challenge_response.json())
        session_request = sign_api_challenge(
            challenge,
            identity=self.app.state.test_identity,
            private_key=self.app.state.test_private_key,
        )
        session_response = client.post(
            "/v1/auth/sessions",
            json=session_request.model_dump(mode="json"),
        )
        assert session_response.status_code == 201, session_response.text
        session = ApiSessionResponse.model_validate(session_response.json())
        self.headers["Authorization"] = f"Bearer {session.access_token}"
        return self


__all__ = [
    "TEST_IDENTITY",
    "TEST_PRIVATE_KEY",
    "TEST_PROJECT_IDS",
    "TEST_TRUST_STORE",
    "AuthenticatedTestClient",
    "create_test_api_app",
    "test_authenticator",
]
