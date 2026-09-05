from __future__ import annotations

import json
from typing import Any

import pytest

from forgegate.dashboard.client import (
    MAX_DASHBOARD_RESPONSE_BYTES,
    DashboardClientError,
    _parse_local_server,
    _post_json,
    activate_dashboard,
)
from forgegate.identity import IdentityRole
from tests.api_auth_support import TEST_IDENTITY, TEST_PRIVATE_KEY


@pytest.mark.parametrize(
    "value",
    [
        "https://127.0.0.1:8000",
        "http://example.com:8000",
        "http://user@127.0.0.1:8000",
        "http://127.0.0.1:8000/path",
        "http://127.0.0.1:8000?query=1",
        "http://127.0.0.1:99999",
    ],
)
def test_dashboard_client_rejects_nonlocal_or_ambiguous_server(value: str) -> None:
    with pytest.raises(DashboardClientError, match="DASHBOARD_SERVER_INVALID"):
        _parse_local_server(value)


def test_dashboard_client_accepts_loopback_origins() -> None:
    assert _parse_local_server("http://127.0.0.1:8123/").port == 8123
    assert _parse_local_server("http://localhost").hostname == "localhost"
    assert _parse_local_server("http://[::1]:9000").port == 9000


def test_activate_dashboard_rejects_code_and_empty_scope_before_network() -> None:
    with pytest.raises(DashboardClientError, match="ACTIVATION_CODE_INVALID"):
        activate_dashboard(
            "http://127.0.0.1:8000",
            "invalid",
            identity=TEST_IDENTITY,
            private_key=TEST_PRIVATE_KEY,
            role=IdentityRole.OPERATOR,
            project_ids=("sample-api",),
        )
    with pytest.raises(DashboardClientError, match="PROJECT_SCOPE_REQUIRED"):
        activate_dashboard(
            "http://127.0.0.1:8000",
            "FG-ABCDE-FGHJK",
            identity=TEST_IDENTITY,
            private_key=TEST_PRIVATE_KEY,
            role=IdentityRole.OPERATOR,
            project_ids=(),
        )


class _Response:
    def __init__(self, status: int, payload: bytes) -> None:
        self.status = status
        self._payload = payload

    def read(self, _: int) -> bytes:
        return self._payload


class _Connection:
    response = _Response(200, b"{}")
    request_values: tuple[str, str, bytes, dict[str, str]] | None = None
    fail: Exception | None = None

    def __init__(self, hostname: str, port: int, *, timeout: float) -> None:
        assert hostname == "127.0.0.1"
        assert port == 8000
        assert timeout == 5.0

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes,
        headers: dict[str, str],
    ) -> None:
        if self.fail is not None:
            raise self.fail
        type(self).request_values = (method, path, body, headers)

    def getresponse(self) -> _Response:
        return self.response

    def close(self) -> None:
        return None


def _patch_connection(monkeypatch: pytest.MonkeyPatch, response: _Response) -> None:
    _Connection.response = response
    _Connection.fail = None
    monkeypatch.setattr("forgegate.dashboard.client.http.client.HTTPConnection", _Connection)


def test_dashboard_post_json_success_and_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connection(monkeypatch, _Response(201, b'{"status":"ok"}'))
    server = _parse_local_server("http://127.0.0.1:8000")
    assert _post_json(server, "/endpoint", {"b": 2, "a": 1}, timeout_seconds=5.0) == {
        "status": "ok"
    }
    assert _Connection.request_values is not None
    method, path, body, headers = _Connection.request_values
    assert (method, path) == ("POST", "/endpoint")
    assert body == b'{"a":1,"b":2}'
    assert headers["Host"] == "127.0.0.1:8000"
    assert headers["X-Request-ID"] == "dashboard-cli-activation"


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (_Response(200, b"[1]"), "JSON object"),
        (_Response(200, b"{"), "invalid JSON"),
        (_Response(500, b'{"error":{"code":"SERVER_CODE"}}'), "SERVER_CODE"),
        (_Response(400, b'{"error":{}}'), "DASHBOARD_REQUEST_REJECTED"),
        (_Response(200, b"x" * (MAX_DASHBOARD_RESPONSE_BYTES + 1)), "RESPONSE_TOO_LARGE"),
    ],
)
def test_dashboard_post_json_rejects_invalid_responses(
    monkeypatch: pytest.MonkeyPatch,
    response: _Response,
    message: str,
) -> None:
    _patch_connection(monkeypatch, response)
    with pytest.raises(DashboardClientError, match=message):
        _post_json(
            _parse_local_server("http://127.0.0.1:8000"),
            "/endpoint",
            {},
            timeout_seconds=5.0,
        )


def test_dashboard_post_json_hides_connection_details(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connection(monkeypatch, _Response(200, b"{}"))
    _Connection.fail = OSError("private machine detail")
    with pytest.raises(DashboardClientError, match="DASHBOARD_CONNECTION_FAILED") as caught:
        _post_json(
            _parse_local_server("http://127.0.0.1:8000"),
            "/endpoint",
            {},
            timeout_seconds=5.0,
        )
    assert "private machine detail" not in str(caught.value)
    _Connection.fail = None


def test_activate_dashboard_validates_challenge_and_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: list[dict[str, Any]] = [
        {"not": "a challenge"},
        {"not": "a completion"},
    ]

    def fake_post(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return responses.pop(0)

    monkeypatch.setattr("forgegate.dashboard.client._post_json", fake_post)
    with pytest.raises(DashboardClientError, match="DASHBOARD_CHALLENGE_INVALID"):
        activate_dashboard(
            "http://127.0.0.1:8000",
            "FG-ABCDE-FGHJK",
            identity=TEST_IDENTITY,
            private_key=TEST_PRIVATE_KEY,
            role=IdentityRole.OPERATOR,
            project_ids=("sample-api",),
        )

    # A valid challenge reaches completion validation.
    from forgegate.api import ApiAuthenticator, ApiChallengeRequest
    from tests.api_auth_support import TEST_TRUST_STORE

    challenge = ApiAuthenticator(TEST_TRUST_STORE).issue_challenge(
        ApiChallengeRequest(
            identity_id=TEST_IDENTITY.identity_id,
            role=IdentityRole.OPERATOR,
            project_ids=("sample-api",),
        )
    )
    responses[:] = [challenge.model_dump(mode="json"), {"not": "a completion"}]
    with pytest.raises(DashboardClientError, match="DASHBOARD_COMPLETION_INVALID"):
        activate_dashboard(
            "http://127.0.0.1:8000",
            "FG-ABCDE-FGHJK",
            identity=TEST_IDENTITY,
            private_key=TEST_PRIVATE_KEY,
            role=IdentityRole.OPERATOR,
            project_ids=("sample-api",),
        )


def test_dashboard_post_json_serializes_only_supplied_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_connection(monkeypatch, _Response(200, json.dumps({"ok": True}).encode()))
    server = _parse_local_server("http://127.0.0.1:8000")
    result = _post_json(server, "/safe", {"value": "public"}, timeout_seconds=5.0)
    assert result == {"ok": True}
    assert _Connection.request_values is not None
    assert b"private" not in _Connection.request_values[2]
