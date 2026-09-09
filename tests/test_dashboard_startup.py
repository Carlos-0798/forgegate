from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from forgegate.api import ApiAuthenticator, create_api_app
from forgegate.application import CandidateApplication
from forgegate.candidates import CandidateStoreError, SQLiteCandidateRepository
from forgegate.cli import app as cli_app
from forgegate.collection_jobs import CollectionJobStore
from forgegate.dashboard import runtime, startup
from forgegate.dashboard.startup import DashboardStartupError, ExistingDashboardPair
from tests.api_auth_support import TEST_TRUST_STORE
from tests.test_api_auth import _create_session


def pair_files(tmp_path: Path, version: int = 3) -> tuple[Path, Path]:
    candidate, jobs = tmp_path / "candidates.db", tmp_path / "jobs.db"
    SQLiteCandidateRepository(candidate).initialize()
    store = CollectionJobStore(jobs)
    store.initialize()
    if version == 4:
        store.enable_archiving()
    return candidate, jobs


def build(candidate: Path, jobs: Path, **kwargs):
    return create_api_app(
        candidate,
        authenticator=ApiAuthenticator(TEST_TRUST_STORE),
        dashboard=True,
        dashboard_job_store_path=jobs,
        dashboard_existing_pair=True,
        **kwargs,
    )


@pytest.mark.parametrize("version", [3, 4])
def test_pair_lifespan_never_initializes_and_auth_still_required(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    version: int,
) -> None:
    candidate, jobs = pair_files(tmp_path, version)
    original = [p.read_bytes() for p in (candidate, jobs)]
    monkeypatch.setattr(CandidateApplication, "initialize", lambda _: pytest.fail("no initialize"))
    api = build(candidate, jobs)
    assert [p.read_bytes() for p in (candidate, jobs)] == original
    identities = []
    for _ in range(2):
        with TestClient(api, base_url="http://127.0.0.1") as client:
            health = client.get("/healthz")
            assert health.status_code == 200
            receipt = json.loads(capsys.readouterr().out.split("ForgeGate runtime: ")[-1])
            assert health.headers["X-ForgeGate-Runtime-Id"] == receipt["runtime_id"]
            assert health.headers["X-ForgeGate-Store-Pair-Id"] == receipt["store_pair_id"]
            assert health.headers["Cache-Control"] == "no-store"
            assert str(tmp_path) not in json.dumps(receipt)
            assert receipt["process_ownership"] == "NOT_ESTABLISHED"
            assert client.get("/v1/projects").status_code == 401
            session = _create_session(client)
            assert (
                client.get(
                    "/v1/projects", headers={"Authorization": f"Bearer {session.access_token}"}
                ).status_code
                == 200
            )
            assert client.get("/app/").status_code == 200
            identities.append((receipt["runtime_id"], receipt["store_pair_id"]))
        with pytest.raises(DashboardStartupError, match="NOT_STARTED"):
            api.state.dashboard_pair.headers()
    assert identities[0][0] != identities[1][0] and identities[0][1] != identities[1][1]


@pytest.mark.parametrize("which", [0, 1])
@pytest.mark.parametrize("kind", ["missing", "empty", "foreign", "old", "directory", "trigger"])
def test_bad_pair_refused_without_repair(tmp_path: Path, which: int, kind: str) -> None:
    paths = pair_files(tmp_path)
    target = paths[which]
    if kind in {"missing", "empty", "directory"}:
        target.unlink()
        if kind == "empty":
            target.touch()
        elif kind == "directory":
            target.mkdir()
    elif kind == "foreign":
        target.write_bytes(b"not a database")
    else:
        with sqlite3.connect(target) as con:
            if kind == "old":
                con.execute("PRAGMA user_version=2")
            else:
                trigger = con.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger' LIMIT 1"
                ).fetchone()[0]
                con.execute(f'DROP TRIGGER "{trigger}"')
    original = target.read_bytes() if target.is_file() else None
    with pytest.raises(DashboardStartupError):
        build(*paths)
    if original is not None:
        assert target.read_bytes() == original
    elif kind == "missing":
        assert not target.exists()


def test_overlap_hardlink_and_reparse_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate, jobs = pair_files(tmp_path)
    with pytest.raises(DashboardStartupError, match="OVERLAP"):
        ExistingDashboardPair.prepare(candidate, candidate)
    alias = tmp_path / "alias.db"
    alias.hardlink_to(jobs)
    with pytest.raises(DashboardStartupError, match="ALIAS"):
        ExistingDashboardPair.prepare(candidate, alias)
    alias.unlink()
    original = Path.is_junction
    monkeypatch.setattr(Path, "is_junction", lambda p: p == tmp_path or original(p))
    with pytest.raises(DashboardStartupError, match="ALIAS"):
        ExistingDashboardPair.prepare(candidate, jobs)


@pytest.mark.parametrize("replace", [False, True])
def test_changed_between_construction_and_lifespan(tmp_path: Path, replace: bool) -> None:
    candidate, jobs = pair_files(tmp_path)
    api = build(candidate, jobs)
    jobs.rename(tmp_path / "retained.db")
    if replace:
        shutil.copyfile(tmp_path / "retained.db", jobs)
    with pytest.raises(DashboardStartupError), TestClient(api):
        pytest.fail("must not serve")
    assert jobs.exists() == replace


def test_replacement_during_runtime_refuses_health(tmp_path: Path) -> None:
    candidate, jobs = pair_files(tmp_path)
    with TestClient(build(candidate, jobs), base_url="http://127.0.0.1") as client:
        assert client.get("/healthz").status_code == 200
        jobs.rename(tmp_path / "retained.db")
        shutil.copyfile(tmp_path / "retained.db", jobs)
        response = client.get("/healthz")
        assert response.status_code == 503
        assert "x-forgegate-runtime-id" not in response.headers
        assert str(tmp_path) not in response.text


def test_application_mismatch_and_hardware_refused(tmp_path: Path) -> None:
    candidate, jobs = pair_files(tmp_path)
    with pytest.raises(DashboardStartupError, match="APPLICATION_MISMATCH"):
        build(candidate, jobs, application=CandidateApplication.for_database(tmp_path / "other.db"))
    with pytest.raises(DashboardStartupError, match="NO_HARDWARE"):
        build(candidate, jobs, dashboard_live_status_provider=object())
    with pytest.raises(DashboardStartupError, match="NO_HARDWARE"):
        create_api_app(
            candidate,
            authenticator=ApiAuthenticator(TEST_TRUST_STORE),
            dashboard=True,
            dashboard_existing_pair=True,
        )
    assert not (tmp_path / "other.db").exists()


def test_cli_existing_pair_does_not_initialize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate, jobs = pair_files(tmp_path)
    trust = tmp_path / "trust.json"
    trust.write_text(TEST_TRUST_STORE.model_dump_json(), encoding="utf-8")
    command = [
        "dashboard",
        "--database",
        str(candidate),
        "--trust-store",
        str(trust),
        "--job-store",
        str(jobs),
        "--existing-pair",
    ]
    monkeypatch.setattr(CandidateApplication, "initialize", lambda _: pytest.fail("no initialize"))

    def run(api, **kwargs):
        with TestClient(api, base_url="http://127.0.0.1") as client:
            assert client.get("/healthz").status_code == 200

    monkeypatch.setattr("uvicorn.run", run)
    assert CliRunner().invoke(cli_app, command).exit_code == 0
    assert CliRunner().invoke(cli_app, [*command, "--msp430-port", "FORBIDDEN"]).exit_code == 3
    candidate.unlink()
    result = CliRunner().invoke(cli_app, command)
    assert result.exit_code == 3 and "PAIR_FILE_UNAVAILABLE" in result.output
    assert not candidate.exists()


def test_candidate_require_exists_uri_prevents_creation_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, _ = pair_files(tmp_path)
    real = sqlite3.connect

    def removed_before_connect(path, **kwargs):
        candidate.unlink()
        return real(path, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", removed_before_connect)
    with pytest.raises(CandidateStoreError):
        SQLiteCandidateRepository(candidate)._open(require_exists=True)
    assert not candidate.exists()


@pytest.mark.parametrize("observed", [("a" * 32, "b" * 32), ("a" * 32, "c" * 32), ("", "")])
def test_correlated_probe_match_or_refusal(monkeypatch: pytest.MonkeyPatch, observed) -> None:
    from forgegate.api.models import HealthResponse

    monkeypatch.setattr(
        runtime,
        "_get_correlated",
        lambda *args: (
            200,
            "application/json",
            HealthResponse(forgegate_version="0.1.0a1").model_dump_json().encode(),
            observed,
        ),
    )
    html = Path(runtime.__file__).with_name("static").joinpath("index.html").read_bytes()
    monkeypatch.setattr(runtime, "_get", lambda *args: (200, "text/html", html))
    report = runtime.check_dashboard(
        expected_runtime_id="a" * 32, expected_store_pair_id="b" * 32
    ).to_dict()
    assert report["ready"] == (observed == ("a" * 32, "b" * 32))
    assert report["instance_ownership"] == "NOT_VERIFIED"
    assert report["runtime_correlation"] == (
        "MATCH_NOT_AUTHENTICATED" if report["ready"] else "MISMATCH"
    )


@pytest.mark.parametrize("ids", [("a" * 32, None), (None, "b" * 32), ("bad", "b" * 32)])
def test_partial_or_invalid_expectation_never_connects(
    monkeypatch: pytest.MonkeyPatch, ids
) -> None:
    monkeypatch.setattr(runtime, "_get", lambda *args: pytest.fail("no HTTP"))
    monkeypatch.setattr(runtime, "_get_correlated", lambda *args: pytest.fail("no HTTP"))
    with pytest.raises(ValueError, match="supply both"):
        runtime.check_dashboard(expected_runtime_id=ids[0], expected_store_pair_id=ids[1])


def test_timeout_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    candidate, jobs = pair_files(tmp_path)
    clock = iter([0, 10])
    monkeypatch.setattr(startup.time, "monotonic", lambda: next(clock, 10))
    with pytest.raises(DashboardStartupError):
        ExistingDashboardPair.prepare(candidate, jobs)


def test_committed_wal_is_not_ignored(tmp_path: Path) -> None:
    candidate, jobs = pair_files(tmp_path)
    original = candidate.read_bytes()
    con = sqlite3.connect(candidate)
    try:
        con.execute("PRAGMA wal_autocheckpoint=0")
        con.execute("PRAGMA user_version=8")
        con.commit()
        assert candidate.read_bytes() == original
        assert Path(str(candidate) + "-wal").stat().st_size > 0
        with pytest.raises(DashboardStartupError, match="VALIDATION_FAILED"):
            ExistingDashboardPair.prepare(candidate, jobs)
    finally:
        con.close()


def test_resolution_race_is_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    candidate, jobs = pair_files(tmp_path)
    original = Path.resolve

    def resolve(path, **kwargs):
        if path == candidate:
            raise FileNotFoundError("private path detail")
        return original(path, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(DashboardStartupError, match="PAIR_FILE_UNAVAILABLE"):
        ExistingDashboardPair.prepare(candidate, jobs)


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows junction")
def test_native_windows_junction_is_refused(tmp_path: Path) -> None:
    pair_files(tmp_path)
    alias = tmp_path / "linked-directory"
    # PowerShell receives paths as literal arguments, not interpolated script code.
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "& { param($link, $target) "
            "New-Item -ItemType Junction -Path $link -Target $target | Out-Null }",
            str(alias),
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert alias.is_junction()
    try:
        with pytest.raises(DashboardStartupError, match="ALIAS"):
            ExistingDashboardPair.prepare(alias / "candidates.db", tmp_path / "jobs.db")
    finally:
        # rmdir removes only this verified junction entry, never its target contents.
        assert alias.is_junction() and alias.parent == tmp_path
        alias.rmdir()


def test_sidecar_alias_and_reserved_pair_names(tmp_path: Path) -> None:
    candidate, jobs = pair_files(tmp_path)
    sidecar = Path(str(candidate) + "-wal")
    sidecar.hardlink_to(jobs)
    with pytest.raises(DashboardStartupError, match="ALIAS"):
        ExistingDashboardPair.prepare(candidate, jobs)
    sidecar.unlink()
    jobs.rename(sidecar)
    with pytest.raises(DashboardStartupError, match="OVERLAP"):
        ExistingDashboardPair.prepare(candidate, sidecar)


def test_job_foreign_key_corruption_refused(tmp_path: Path) -> None:
    candidate, jobs = pair_files(tmp_path)
    with sqlite3.connect(jobs) as con:
        con.execute("INSERT INTO events VALUES ('missing', 0, '{}', NULL)")
    with pytest.raises(DashboardStartupError, match="INTEGRITY_INVALID"):
        ExistingDashboardPair.prepare(candidate, jobs)


def test_legacy_health_has_no_pair_headers(tmp_path: Path) -> None:
    api = create_api_app(tmp_path / "legacy.db", authenticator=ApiAuthenticator(TEST_TRUST_STORE))
    with TestClient(api, base_url="http://127.0.0.1") as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert "x-forgegate-runtime-id" not in response.headers


def test_correlated_connection_closes_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class Connection:
        closed = False

        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            raise TimeoutError("private detail")

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(runtime.http.client, "HTTPConnection", lambda *a, **k: connection)
    report = runtime.check_dashboard(expected_runtime_id="a" * 32, expected_store_pair_id="b" * 32)
    assert report.status == "CONNECTION_TIMEOUT" and connection.closed
    assert "private detail" not in json.dumps(report.to_dict())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows launcher")
def test_windows_pair_arguments_and_refusal(tmp_path: Path) -> None:
    candidate, jobs = pair_files(tmp_path)
    trust = tmp_path / "trust.json"
    trust.touch()
    shim = tmp_path / "python shim.cmd"
    shim.write_text("@echo off\necho %*\nexit /b 17\n", encoding="ascii")
    script = Path(__file__).resolve().parents[1] / "tools/start_dashboard.ps1"
    command = [
        "powershell.exe",
        "-NoProfile",
        "-File",
        str(script),
        "-Database",
        str(candidate),
        "-TrustStore",
        str(trust),
        "-Python",
        str(shim),
        "-ExistingPair",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert result.returncode == 3 and "requires JobStore" in result.stderr
    # A real exclusive bind probe still runs; choose a temporary free port.
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    result = subprocess.run(
        [*command, "-JobStore", str(jobs), "-Port", str(port)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 17
    assert "--existing-pair" in result.stdout and "--job-store" in result.stdout
    result = subprocess.run(
        [*command, "-JobStore", str(jobs), "-Msp430Port", "NO_ACCESS"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 3 and "does not allow Msp430Port" in result.stderr
