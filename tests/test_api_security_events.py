from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from forgegate.api import (
    ApiAuthChallenge,
    ApiAuthenticator,
    ApiSessionResponse,
    create_api_app,
    sign_api_challenge,
)
from forgegate.application import CandidateApplication
from forgegate.audit import AuditActor
from forgegate.candidates import CandidateStoreError, SQLiteCandidateRepository
from forgegate.candidates.store import (
    POLICY_STORE_SCHEMA_NAME,
    POLICY_STORE_SCHEMA_VERSION,
    STORE_SCHEMA_VERSION,
)
from forgegate.security_events import (
    ApiSecurityEvent,
    ApiSecurityEventPage,
    ApiSecurityEventType,
    SecurityEventTargetType,
    create_api_security_event,
)
from tests.api_auth_support import TEST_IDENTITY, TEST_PRIVATE_KEY, TEST_TRUST_STORE

OCCURRED_AT = datetime(2026, 8, 31, 22, 0, tzinfo=UTC)


def _actor(session_id: str = "sess-" + "1" * 32) -> AuditActor:
    return AuditActor(
        identity_id=TEST_IDENTITY.identity_id,
        display_name=TEST_IDENTITY.display_name,
        role="operator",
        session_id=session_id,
        trust_store_id=TEST_TRUST_STORE.trust_store_id,
        authenticated_at=OCCURRED_AT,
    )


def _session(
    client: TestClient,
    *,
    project_ids: tuple[str, ...] = ("sample-api",),
) -> ApiSessionResponse:
    challenge_response = client.post(
        "/v1/auth/challenges",
        json={
            "identity_id": TEST_IDENTITY.identity_id,
            "role": "operator",
            "project_ids": list(project_ids),
        },
    )
    assert challenge_response.status_code == 201, challenge_response.text
    challenge = ApiAuthChallenge.model_validate(challenge_response.json())
    request = sign_api_challenge(
        challenge,
        identity=TEST_IDENTITY,
        private_key=TEST_PRIVATE_KEY,
    )
    response = client.post("/v1/auth/sessions", json=request.model_dump(mode="json"))
    assert response.status_code == 201, response.text
    return ApiSessionResponse.model_validate(response.json())


def test_security_event_contract_is_content_addressed_and_minimal() -> None:
    event = create_api_security_event(
        sequence=1,
        event_type=ApiSecurityEventType.SESSION_LOGGED_OUT,
        occurred_at=OCCURRED_AT,
        request_id="request-security-0001",
        outcome_code="API_SESSION_LOGGED_OUT",
        actor=_actor(),
        target_type=SecurityEventTargetType.SESSION,
        target_id="sess-" + "1" * 32,
    )
    assert ApiSecurityEvent.model_validate_json(event.model_dump_json()) == event
    assert "token" not in event.model_dump_json().lower()

    changed = event.model_dump(mode="json")
    changed["outcome_code"] = "API_SESSION_REVOKED"
    with pytest.raises(ValidationError, match="event_id does not match"):
        ApiSecurityEvent.model_validate(changed)
    with pytest.raises(ValidationError, match="session target"):
        create_api_security_event(
            sequence=2,
            event_type=ApiSecurityEventType.SESSION_REVOKED,
            occurred_at=OCCURRED_AT,
            request_id="request-security-0002",
            outcome_code="API_SESSION_REVOKED",
            actor=_actor(),
            target_type=SecurityEventTargetType.TRUST_STORE,
            target_id=TEST_TRUST_STORE.trust_store_id,
        )


def test_security_event_store_is_append_only_bounded_and_migrates_v7(tmp_path: Path) -> None:
    repository = SQLiteCandidateRepository(
        tmp_path / "events.db",
        security_event_capacity=2,
    )
    repository.initialize()
    first = repository.append_api_security_event(
        event_type=ApiSecurityEventType.AUTHENTICATION_REJECTED,
        occurred_at=OCCURRED_AT,
        request_id="request-security-0003",
        outcome_code="API_SESSION_INVALID",
    )
    second = repository.append_api_security_event(
        event_type=ApiSecurityEventType.SESSION_REVOKED,
        occurred_at=OCCURRED_AT,
        request_id="request-security-0004",
        outcome_code="API_SESSION_REVOKED",
        actor=_actor(),
        target_type=SecurityEventTargetType.SESSION,
        target_id="sess-" + "2" * 32,
    )
    page = repository.api_security_events(limit=1)
    filtered = repository.api_security_events(event_type=ApiSecurityEventType.SESSION_REVOKED)

    assert page.events == (first,)
    assert page.has_more is True
    assert page.recorded_count == page.capacity == 2
    assert page.saturated is True
    assert filtered.events == (second,)
    with pytest.raises(CandidateStoreError, match="STORE_SECURITY_EVENT_CAPACITY_REACHED"):
        repository.append_api_security_event(
            event_type=ApiSecurityEventType.AUTHENTICATION_REJECTED,
            occurred_at=OCCURRED_AT,
            request_id="request-security-0005",
            outcome_code="API_SESSION_INVALID",
        )
    with (
        sqlite3.connect(repository.database_path) as connection,
        pytest.raises(sqlite3.DatabaseError, match="append-only"),
    ):
        connection.execute("DELETE FROM api_security_events")

    migration = SQLiteCandidateRepository(tmp_path / "migration.db")
    migration.initialize()
    with sqlite3.connect(migration.database_path) as connection:
        connection.execute("DROP TABLE api_security_events")
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_name'",
            (POLICY_STORE_SCHEMA_NAME,),
        )
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_version'",
            (str(POLICY_STORE_SCHEMA_VERSION),),
        )
        connection.execute(f"PRAGMA user_version = {POLICY_STORE_SCHEMA_VERSION}")
    with pytest.raises(CandidateStoreError, match="STORE_MIGRATION_REQUIRED"):
        migration.initialize()
    migration.migrate()
    assert migration.api_security_events().events == ()
    with sqlite3.connect(migration.database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == STORE_SCHEMA_VERSION


def test_api_records_minimal_rejections_and_session_controls(tmp_path: Path) -> None:
    database = tmp_path / "api-events.db"
    authenticator = ApiAuthenticator(
        TEST_TRUST_STORE,
        trust_store_loader=lambda: TEST_TRUST_STORE,
    )
    with TestClient(
        create_api_app(database, authenticator=authenticator),
        base_url="http://127.0.0.1",
    ) as client:
        global_operator = _session(
            client,
            project_ids=TEST_TRUST_STORE.identities[0].project_ids,
        )
        target = _session(client)
        self_logout = _session(client)
        headers = {"Authorization": f"Bearer {global_operator.access_token}"}

        rejected = client.get(
            "/v1/projects/sample-api",
            headers={"Authorization": "Bearer " + "x" * 43},
        )
        revoked = client.delete(f"/v1/auth/sessions/{target.session_id}", headers=headers)
        reloaded = client.post("/v1/auth/trust-store/reload", headers=headers)
        logged_out = client.delete(
            "/v1/auth/session",
            headers={"Authorization": f"Bearer {self_logout.access_token}"},
        )
        response = client.get("/v1/security-events", headers=headers)

    assert rejected.status_code == 401
    assert revoked.status_code == reloaded.status_code == logged_out.status_code == 200
    page = ApiSecurityEventPage.model_validate(response.json())
    assert [event.event_type for event in page.events] == [
        ApiSecurityEventType.AUTHENTICATION_REJECTED,
        ApiSecurityEventType.SESSION_REVOKED,
        ApiSecurityEventType.TRUST_STORE_RELOADED,
        ApiSecurityEventType.SESSION_LOGGED_OUT,
    ]
    assert page.recorded_count == 4
    with sqlite3.connect(database) as connection:
        stored_json = "".join(
            str(row[0]) for row in connection.execute("SELECT event_json FROM api_security_events")
        )
    assert global_operator.access_token not in stored_json
    assert target.access_token not in stored_json


def test_security_event_access_is_global_operator_only_and_capacity_is_visible(
    tmp_path: Path,
) -> None:
    database = tmp_path / "bounded-events.db"
    application = CandidateApplication(
        SQLiteCandidateRepository(database, security_event_capacity=1)
    )
    with TestClient(
        create_api_app(
            database,
            application=application,
            authenticator=ApiAuthenticator(TEST_TRUST_STORE),
        ),
        base_url="http://127.0.0.1",
    ) as client:
        global_operator = _session(
            client,
            project_ids=TEST_TRUST_STORE.identities[0].project_ids,
        )
        scoped_operator = _session(client)
        disposable = _session(client)
        denied = client.get(
            "/v1/security-events",
            headers={"Authorization": f"Bearer {scoped_operator.access_token}"},
        )
        logout = client.delete(
            "/v1/auth/session",
            headers={"Authorization": f"Bearer {disposable.access_token}"},
        )
        page_response = client.get(
            "/v1/security-events",
            headers={"Authorization": f"Bearer {global_operator.access_token}"},
        )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "API_SECURITY_AUDIT_FORBIDDEN"
    assert logout.status_code == 200
    page = ApiSecurityEventPage.model_validate(page_response.json())
    assert page.capacity == page.recorded_count == 1
    assert page.saturated is True
    assert page.events[0].event_type is ApiSecurityEventType.AUTHENTICATION_REJECTED


def test_security_event_page_rejects_inconsistent_capacity() -> None:
    with pytest.raises(ValidationError, match="saturated"):
        ApiSecurityEventPage(
            events=(),
            next_after_sequence=None,
            has_more=False,
            capacity=1,
            recorded_count=1,
            saturated=False,
        )
