from __future__ import annotations

import http.client
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from forgegate.api.auth import ApiAuthChallenge, ApiChallengeRequest, sign_api_challenge
from forgegate.dashboard.models import DashboardActivationCompleted
from forgegate.identity import IdentityRole, SigningIdentity
from forgegate.network import is_loopback_host

ACTIVATION_CODE_PATTERN = re.compile(r"^FG-[A-Z2-7]{5}-[A-Z2-7]{5}$")
MAX_DASHBOARD_RESPONSE_BYTES = 256 * 1024


class DashboardClientError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class _LocalServer:
    hostname: str
    port: int
    origin: str


def activate_dashboard(
    server_url: str,
    activation_code: str,
    *,
    identity: SigningIdentity,
    private_key: Ed25519PrivateKey,
    role: IdentityRole,
    project_ids: tuple[str, ...],
    timeout_seconds: float = 5.0,
) -> DashboardActivationCompleted:
    if ACTIVATION_CODE_PATTERN.fullmatch(activation_code) is None:
        raise DashboardClientError(
            "DASHBOARD_ACTIVATION_CODE_INVALID",
            "activation code must use FG-XXXXX-XXXXX",
        )
    projects = tuple(sorted(set(project_ids)))
    if not projects:
        raise DashboardClientError(
            "DASHBOARD_PROJECT_SCOPE_REQUIRED",
            "at least one --project scope is required",
        )
    server = _parse_local_server(server_url)
    challenge_payload = ApiChallengeRequest(
        identity_id=identity.identity_id,
        role=role,
        project_ids=projects,
    ).model_dump(mode="json")
    challenge_document = _post_json(
        server,
        f"/app/api/activations/{activation_code}/challenge",
        challenge_payload,
        timeout_seconds=timeout_seconds,
    )
    try:
        challenge = ApiAuthChallenge.model_validate(challenge_document)
        signed = sign_api_challenge(challenge, identity=identity, private_key=private_key)
    except (ValidationError, ValueError) as exc:
        raise DashboardClientError(
            "DASHBOARD_CHALLENGE_INVALID",
            "local Dashboard returned an invalid authentication challenge",
        ) from exc
    completed_document = _post_json(
        server,
        f"/app/api/activations/{activation_code}/complete",
        signed.model_dump(mode="json"),
        timeout_seconds=timeout_seconds,
    )
    try:
        return DashboardActivationCompleted.model_validate(completed_document)
    except ValidationError as exc:
        raise DashboardClientError(
            "DASHBOARD_COMPLETION_INVALID",
            "local Dashboard returned an invalid completion response",
        ) from exc


def _parse_local_server(server_url: str) -> _LocalServer:
    parsed = urlsplit(server_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname is None
        or not is_loopback_host(parsed.hostname)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise DashboardClientError(
            "DASHBOARD_SERVER_INVALID",
            "server must be an http:// loopback origin without credentials or a path",
        )
    try:
        port = parsed.port or 80
    except ValueError as exc:
        raise DashboardClientError(
            "DASHBOARD_SERVER_INVALID",
            "server port is invalid",
        ) from exc
    return _LocalServer(
        hostname=parsed.hostname,
        port=port,
        origin=f"http://{parsed.netloc}",
    )


def _post_json(
    server: _LocalServer,
    path: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    connection = http.client.HTTPConnection(server.hostname, server.port, timeout=timeout_seconds)
    try:
        connection.request(
            "POST",
            path,
            body=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Host": urlsplit(server.origin).netloc,
                "X-Request-ID": "dashboard-cli-activation",
            },
        )
        response = connection.getresponse()
        raw = response.read(MAX_DASHBOARD_RESPONSE_BYTES + 1)
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        raise DashboardClientError(
            "DASHBOARD_CONNECTION_FAILED",
            "could not reach the local Dashboard service",
        ) from exc
    finally:
        connection.close()
    if len(raw) > MAX_DASHBOARD_RESPONSE_BYTES:
        raise DashboardClientError(
            "DASHBOARD_RESPONSE_TOO_LARGE",
            "local Dashboard response exceeds the client limit",
        )
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DashboardClientError(
            "DASHBOARD_RESPONSE_INVALID",
            "local Dashboard returned invalid JSON",
        ) from exc
    if not isinstance(document, dict):
        raise DashboardClientError(
            "DASHBOARD_RESPONSE_INVALID",
            "local Dashboard response must be a JSON object",
        )
    if not 200 <= response.status < 300:
        error = document.get("error")
        code = "DASHBOARD_REQUEST_REJECTED"
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            code = error["code"]
        raise DashboardClientError(
            code,
            f"local Dashboard rejected the request ({response.status})",
        )
    return document


__all__ = ["DashboardClientError", "activate_dashboard"]
