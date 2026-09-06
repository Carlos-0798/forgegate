from __future__ import annotations

import http.client
import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from forgegate.api.models import HealthResponse
from forgegate.cli import app
from forgegate.dashboard import runtime

HTML = Path(runtime.__file__).with_name("static").joinpath("index.html").read_bytes()
HEALTH = HealthResponse(forgegate_version="0.1.0a1").model_dump_json().encode()


def _responses(monkeypatch: pytest.MonkeyPatch, values: list[Any]) -> list[str]:
    paths: list[str] = []

    def get(host: str, port: int, path: str, timeout: float) -> tuple[int, str, bytes]:
        assert host == "127.0.0.1"
        assert port == 8131
        assert timeout == 3.0
        paths.append(path)
        item = values.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(runtime, "_get", get)
    return paths


@pytest.mark.parametrize(
    ("responses", "expected"),
    [
        (
            [(200, "application/json", HEALTH), (200, "text/html; charset=utf-8", HTML)],
            "DASHBOARD_REACHABLE",
        ),
        ([(503, "text/plain", b"private upstream detail")], "HEALTH_HTTP_ERROR"),
        ([(302, "text/plain", b"redirect must not be followed")], "HEALTH_HTTP_ERROR"),
        ([(200, "text/html", HEALTH)], "HEALTH_INVALID"),
        ([(200, "application/json", b"x" * (runtime.MAX_PROBE_BYTES + 1))], "HEALTH_INVALID"),
        ([(200, "application/json", b"{}")], "HEALTH_INVALID"),
        ([(200, "application/json", b"invalid json")], "HEALTH_INVALID"),
        (
            [(200, "application/json", HEALTH), (404, "text/plain", b"no app")],
            "DASHBOARD_HTTP_ERROR",
        ),
        (
            [(200, "application/json", HEALTH), (200, "text/html", b"wrong HTML")],
            "DASHBOARD_HTML_MISMATCH",
        ),
        ([(200, "application/json", HEALTH), (200, "text/plain", HTML)], "DASHBOARD_HTML_MISMATCH"),
        ([ConnectionRefusedError("private detail")], "CONNECTION_REFUSED"),
        ([TimeoutError("private detail")], "CONNECTION_TIMEOUT"),
        ([OSError("private detail")], "PROBE_FAILED"),
        ([http.client.BadStatusLine("private detail")], "PROBE_FAILED"),
        ([(200, "application/json", HEALTH), ConnectionRefusedError()], "CONNECTION_REFUSED"),
    ],
)
def test_diagnostic_states_and_no_raw_response_leak(
    monkeypatch: pytest.MonkeyPatch, responses: list[Any], expected: str
) -> None:
    paths = _responses(monkeypatch, responses.copy())
    report = runtime.check_dashboard().to_dict()
    assert report["status"] == expected
    assert report["ready"] == (expected == "DASHBOARD_REACHABLE")
    assert paths[0] == "/healthz" and set(paths) <= {"/healthz", "/app/"}
    assert "private" not in json.dumps(report)
    assert report["instance_ownership"] == "NOT_VERIFIED"
    assert report["hardware_access"] == "NOT_PERFORMED"
    assert report["browser_interaction"] == "NOT_TESTED"


@pytest.mark.parametrize(
    "options",
    [
        {"host": "example.com"},
        {"host": "0.0.0.0"},
        {"port": 0},
        {"port": 65536},
        {"timeout_seconds": 0},
        {"timeout_seconds": 11},
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
    ],
)
def test_invalid_options_never_connect(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]
) -> None:
    monkeypatch.setattr(runtime, "_get", lambda *a: pytest.fail("must not connect"))
    with pytest.raises(ValueError):
        runtime.check_dashboard(**options)


def test_ipv6_and_cli_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "_get", lambda *a: (503, "text/plain", b""))
    assert runtime.check_dashboard("::1").origin == "http://[::1]:8131"
    runner = CliRunner()
    failed = runner.invoke(app, ["dashboard-check"])
    assert failed.exit_code == 3
    assert json.loads(failed.stdout)["health_http_status"] == 503
    assert runner.invoke(app, ["dashboard-check", "--host", "example.com"]).exit_code == 2
    assert runner.invoke(app, ["dashboard-check", "--port", "0"]).exit_code == 2
    _responses(monkeypatch, [(200, "application/json", HEALTH), (200, "text/html", HTML)])
    success = runner.invoke(app, ["dashboard-check"])
    assert success.exit_code == 0
    assert json.loads(success.stdout)["ready"] is True


def test_transport_bounds_and_close_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class Connection:
        closed = False
        failure = False

        def __init__(self, host: str, port: int, *, timeout: float) -> None:
            assert (host, port, timeout) == ("127.0.0.1", 8131, 2.0)

        def request(self, method: str, path: str, *, headers: dict[str, str]) -> None:
            assert (method, path) == ("GET", "/healthz")
            assert headers == {"Accept-Encoding": "identity"}
            if self.failure:
                raise TimeoutError

        def getresponse(self) -> Any:
            return self

        status = 200

        def read(self, count: int) -> bytes:
            assert count == runtime.MAX_PROBE_BYTES + 1
            return HEALTH

        def getheader(self, name: str, default: str) -> str:
            assert name == "Content-Type"
            return "application/json"

        def close(self) -> None:
            Connection.closed = True

    monkeypatch.setattr(runtime.http.client, "HTTPConnection", Connection)
    assert runtime._get("127.0.0.1", 8131, "/healthz", 2.0) == (200, "application/json", HEALTH)
    assert Connection.closed
    Connection.closed = False
    Connection.failure = True
    with pytest.raises(TimeoutError):
        runtime._get("127.0.0.1", 8131, "/healthz", 2.0)
    assert Connection.closed


@pytest.mark.skipif(sys.platform != "win32", reason="actual Windows PowerShell launcher")
def test_windows_launcher_missing_input_and_busy_port(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "tools/start_dashboard.ps1"
    command = [
        "powershell.exe",
        "-NoProfile",
        "-File",
        str(script),
        "-Database",
        str(tmp_path / "missing.db"),
        "-TrustStore",
        str(tmp_path / "trust.json"),
    ]
    missing = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert missing.returncode == 3
    assert "required database" in missing.stderr
    assert not (tmp_path / "missing.db").exists()
    # Busy-port rejection happens before any database initialization or trust parsing.
    database = tmp_path / "existing database.db"
    trust = tmp_path / "trust.json"
    database.write_bytes(b"unchanged sentinel")
    trust.write_bytes(b"unchanged sentinel")
    command[command.index("-Database") + 1] = str(database)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        result = subprocess.run(
            [*command, "-Port", str(listener.getsockname()[1])],
            capture_output=True,
            text=True,
            timeout=20,
        )
    assert result.returncode == 3
    assert "port cannot be reserved" in result.stderr
    assert database.read_bytes() == trust.read_bytes() == b"unchanged sentinel"


@pytest.mark.skipif(sys.platform != "win32", reason="actual Windows PowerShell launcher")
def test_windows_launcher_arguments_and_exit_code(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "tools/start_dashboard.ps1"
    shim = tmp_path / "python shim.cmd"
    shim.write_text("@echo off\necho %*\nexit /b 17\n", encoding="ascii")
    database = tmp_path / "database with spaces.db"
    trust = tmp_path / "trust with spaces.json"
    database.write_bytes(b"shim only; never opened as SQLite")
    trust.touch()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-File",
            str(script),
            "-Database",
            str(database),
            "-TrustStore",
            str(trust),
            "-Python",
            str(shim),
            "-Port",
            str(port),
            "-SessionTtlSeconds",
            "600",
            "-Msp430Port",
            "COM_TEST_ONLY",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 17
    assert '"' + str(database) + '"' in result.stdout
    assert "--msp430-port COM_TEST_ONLY" in result.stdout
    assert "--session-ttl-seconds 600" in result.stdout
    assert "No automatic restart or login" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="actual Windows PowerShell launcher")
def test_windows_launcher_rejects_empty_database(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "tools/start_dashboard.ps1"
    database = tmp_path / "empty.db"
    trust = tmp_path / "trust.json"
    database.touch()
    trust.write_text("not parsed", encoding="ascii")
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-File",
            str(script),
            "-Database",
            str(database),
            "-TrustStore",
            str(trust),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 3
    assert "database file is empty" in result.stderr
    assert database.stat().st_size == 0
