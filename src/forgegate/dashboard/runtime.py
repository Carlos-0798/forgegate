"""Unauthenticated loopback diagnostics, not process or database ownership checks."""

from __future__ import annotations

import http.client
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from forgegate.api.models import HealthResponse
from forgegate.network import validated_loopback_host

MAX_PROBE_BYTES = 64 * 1024


@dataclass(frozen=True)
class DashboardRuntimeCheck:
    origin: str
    status: str
    next_step: str
    health_http_status: int | None = None
    dashboard_http_status: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "ready": self.status == "DASHBOARD_REACHABLE",
            "scope": "unauthenticated_http_and_exact_installed_html_only",
            "instance_ownership": "NOT_VERIFIED",
            "database_integrity": "NOT_CHECKED",
            "browser_interaction": "NOT_TESTED",
            "hardware_access": "NOT_PERFORMED",
        }


def _get(host: str, port: int, path: str, timeout: float) -> tuple[int, str, bytes]:
    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        # Direct connection: no environment proxy, credentials, cookies or redirects.
        connection.request("GET", path, headers={"Accept-Encoding": "identity"})
        response = connection.getresponse()
        body = response.read(MAX_PROBE_BYTES + 1)
        return response.status, response.getheader("Content-Type", ""), body
    finally:
        connection.close()


def check_dashboard(
    host: str = "127.0.0.1", port: int = 8131, *, timeout_seconds: float = 3.0
) -> DashboardRuntimeCheck:
    """Probe only health and HTML; timeout is per socket operation, not a total deadline."""
    host = validated_loopback_host(host)
    if (
        not 1 <= port <= 65535
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 10
    ):
        raise ValueError("port must be 1-65535 and timeout must be finite, greater than 0 and <=10")
    authority = f"[{host}]" if ":" in host else host
    origin = f"http://{authority}:{port}"
    health_status: int | None = None
    app_status: int | None = None

    def result(status: str, step: str) -> DashboardRuntimeCheck:
        return DashboardRuntimeCheck(origin, status, step, health_status, app_status)

    try:
        health_status, content_type, body = _get(host, port, "/healthz", timeout_seconds)
        if health_status != 200:
            return result(
                "HEALTH_HTTP_ERROR",
                "Inspect the listener and its local logs; do not kill an unknown process.",
            )
        if (
            len(body) > MAX_PROBE_BYTES
            or content_type.split(";")[0].strip().lower() != "application/json"
        ):
            return result(
                "HEALTH_INVALID",
                "Check the port and server version; "
                "the response is not accepted ForgeGate health JSON.",
            )
        try:
            HealthResponse.model_validate_json(body)
        except ValidationError:
            return result(
                "HEALTH_INVALID",
                "Check the port and server version; "
                "the health contract does not match this installation.",
            )
        app_status, content_type, body = _get(host, port, "/app/", timeout_seconds)
        if app_status != 200:
            return result(
                "DASHBOARD_HTTP_ERROR",
                "Check that the service was started with dashboard, not serve-api; "
                "inspect local logs.",
            )
        expected = Path(__file__).with_name("static").joinpath("index.html").read_bytes()
        if content_type.split(";")[0].strip().lower() != "text/html" or body != expected:
            return result(
                "DASHBOARD_HTML_MISMATCH",
                "Check the installed/server versions and packaged assets; "
                "HTML does not match this installation.",
            )
        return result(
            "DASHBOARD_REACHABLE",
            "Open /app/ and approve a fresh CLI activation; "
            "HTTP reachability does not prove login, data or hardware health.",
        )
    except ConnectionRefusedError:
        return result(
            "CONNECTION_REFUSED",
            "No connection accepted at this instant. "
            "Start the intended service, then repeat this check.",
        )
    except TimeoutError:
        return result(
            "CONNECTION_TIMEOUT",
            "Inspect service responsiveness and local networking; "
            "do not assume the process has stopped.",
        )
    except (OSError, http.client.HTTPException):
        return result(
            "PROBE_FAILED",
            "Inspect local service logs and networking; "
            "no response body or exception detail is exported.",
        )


__all__ = ["DashboardRuntimeCheck", "check_dashboard"]
