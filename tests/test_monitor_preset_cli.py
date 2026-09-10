from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from rich.text import Text
from typer.testing import CliRunner

from forgegate.candidates import SQLiteCandidateRepository
from forgegate.cli import app
from forgegate.collection_jobs import CollectionJobStore
from forgegate.monitor_presets import MonitorPresetCatalog, MonitorPresetController
from forgegate.monitor_presets_io import load_monitor_presets
from tests.api_auth_support import TEST_TRUST_STORE

runner = CliRunner()


@pytest.fixture(autouse=True)
def forbid_hardware_monitor(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("preset CLI tests must never construct a physical monitor")

    monkeypatch.setattr("forgegate.compatibility.msp430_live.Msp430SerialMonitor", forbidden)


def _catalog_payload(*, hardware: bool = False) -> dict[str, Any]:
    presets: list[dict[str, Any]] = [
        {
            "preset_id": "simulated-demo",
            "name": "Simulated monitor",
            "adapter": "forgegate.simulated-demo.v1",
            "port": None,
            "stale_after_seconds": 3.0,
        }
    ]
    if hardware:
        presets.append(
            {
                "preset_id": "msp430-uart",
                "name": "MSP430 read-only telemetry",
                "adapter": "msp430.uart.v1",
                "port": "COM4",
                "stale_after_seconds": 3.0,
            }
        )
    return {
        "schema_version": "forgegate.monitor-presets.v1",
        "project_id": "sample-api",
        "presets": presets,
    }


def _dashboard_args(tmp_path: Path, presets: Path) -> list[str]:
    trust = tmp_path / "trust.json"
    trust.write_text(TEST_TRUST_STORE.model_dump_json(), encoding="utf-8")
    return [
        "dashboard",
        "--database",
        str(tmp_path / "dashboard.db"),
        "--trust-store",
        str(trust),
        "--monitor-presets",
        str(presets),
    ]


@pytest.mark.parametrize("hardware", [False, True])
def test_monitor_preset_init_writes_valid_catalog_without_starting_monitor(
    tmp_path: Path, hardware: bool
) -> None:
    output = tmp_path / "monitor-presets.json"
    args = ["monitor-preset-init", str(output), "--project", "sample-api"]
    if hardware:
        args.extend(["--msp430-port", "COM4"])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    catalog = MonitorPresetCatalog.model_validate_json(output.read_text(encoding="utf-8"))
    assert catalog.project_id == "sample-api"
    assert catalog.presets[0].preset_id == "simulated-demo"
    assert catalog.presets[0].adapter == "forgegate.simulated-demo.v1"
    assert catalog.presets[0].port is None
    assert len(catalog.presets) == (2 if hardware else 1)
    if hardware:
        assert catalog.presets[1].preset_id == "msp430-uart"
        assert catalog.presets[1].adapter == "msp430.uart.v1"
        assert catalog.presets[1].port == "COM4"
    assert list(tmp_path.iterdir()) == [output]
    validated = runner.invoke(app, ["validate-config", str(output)])
    assert validated.exit_code == 0, validated.output


def test_monitor_preset_init_refuses_to_overwrite_existing_bytes(tmp_path: Path) -> None:
    output = tmp_path / "monitor-presets.json"
    original = b"private configuration must survive\n"
    output.write_bytes(original)
    result = runner.invoke(app, ["monitor-preset-init", str(output), "--project", "sample-api"])
    assert result.exit_code != 0
    assert output.read_bytes() == original
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize(
    "options",
    [
        ["--project", "../outside"],
        ["--project", ""],
        ["--project", "sample-api", "--msp430-port", "COMabc"],
        ["--project", "sample-api", "--msp430-port", "COM4 --write"],
        ["--project", "sample-api", "--msp430-port", "\\\\.\\COM4"],
    ],
)
def test_monitor_preset_init_validates_before_creating_output(
    tmp_path: Path, options: list[str]
) -> None:
    output = tmp_path / "monitor-presets.json"
    result = runner.invoke(app, ["monitor-preset-init", str(output), *options])
    assert result.exit_code != 0
    assert list(tmp_path.iterdir()) == []


def test_monitor_preset_init_missing_parent_leaves_no_partial_output(tmp_path: Path) -> None:
    output = tmp_path / "new-directory" / "monitor-presets.json"
    result = runner.invoke(app, ["monitor-preset-init", str(output), "--project", "sample-api"])
    assert result.exit_code != 0
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("hardware", [False, True])
def test_dashboard_loads_preset_catalog_without_automatic_monitor_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hardware: bool
) -> None:
    presets = tmp_path / "presets.json"
    presets.write_text(json.dumps(_catalog_payload(hardware=hardware)), encoding="utf-8")
    observed: dict[str, Any] = {}

    def fake_run(application: Any, **kwargs: Any) -> None:
        controller = application.state.dashboard_monitor_controller
        observed.update(controller=controller, **kwargs)
        view = controller.view()
        assert view.project_id == "sample-api"
        assert view.session.state == "STOPPED"
        assert view.session.revision == 0
        assert controller.snapshot().sources == ()

    monkeypatch.setattr(uvicorn, "run", fake_run)
    result = runner.invoke(app, _dashboard_args(tmp_path, presets))
    assert result.exit_code == 0, result.output
    assert observed["host"] == "127.0.0.1"
    assert observed["controller"].view().session.state == "STOPPED"


@pytest.mark.parametrize("server_failure", [False, True])
def test_dashboard_always_closes_started_preset_controller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, server_failure: bool
) -> None:
    presets = tmp_path / "presets.json"
    presets.write_text(json.dumps(_catalog_payload()), encoding="utf-8")
    observed: dict[str, Any] = {"closed": 0}
    original_close = MonitorPresetController.close

    def observe_close(self: MonitorPresetController) -> None:
        observed["closed"] += 1
        original_close(self)

    def fake_run(application: Any, **_kwargs: Any) -> None:
        controller = application.state.dashboard_monitor_controller
        observed["controller"] = controller
        assert controller.view().session.state == "STOPPED"
        controller.start("simulated-demo", 0)
        assert controller.view().session.state == "RUNNING"
        if server_failure:
            raise RuntimeError("injected server failure")

    monkeypatch.setattr(MonitorPresetController, "close", observe_close)
    monkeypatch.setattr(uvicorn, "run", fake_run)
    result = runner.invoke(app, _dashboard_args(tmp_path, presets))
    assert (result.exit_code != 0) is server_failure, result.output
    assert observed["closed"] >= 1
    assert observed["controller"].view().session.state == "STOPPED"


@pytest.mark.parametrize(
    "failure",
    [
        "schema",
        "missing-version",
        "duplicates",
        "nested-duplicates",
        "oversize",
        "nonfinite",
        "deep",
        "root",
        "adapter",
        "alias",
        "utf8",
    ],
)
def test_dashboard_rejects_bad_catalog_before_database_or_monitor_activity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    presets = tmp_path / "presets.json"
    payload = _catalog_payload(hardware=True)
    if failure == "schema":
        payload["schema_version"] = "forgegate.monitor-presets.v99"
    elif failure == "missing-version":
        payload.pop("schema_version")
    elif failure == "adapter":
        payload["presets"][1]["adapter"] = "arbitrary.python.module"
    elif failure == "alias":
        payload["presets"][1]["port"] = "\\\\.\\COM4"
    raw = json.dumps(payload)
    if failure == "duplicates":
        raw = raw.replace(
            '"project_id": "sample-api"', '"project_id": "other", "project_id": "sample-api"'
        )
    elif failure == "nested-duplicates":
        raw = raw.replace('"port": "COM4"', '"port": "COM5", "port": "COM4"')
    elif failure == "oversize":
        raw += " " * (64 * 1024 + 1)
    elif failure == "nonfinite":
        raw = raw.replace('"stale_after_seconds": 3.0', '"stale_after_seconds": NaN')
    elif failure == "deep":
        raw = "[" * 2000 + "0" + "]" * 2000
    elif failure == "root":
        raw = "[]"
    presets.write_bytes(raw.encode("utf-8") if failure != "utf8" else b"\xff\xfe")
    monkeypatch.setattr(uvicorn, "run", lambda *_args, **_kwargs: pytest.fail("must not serve"))
    args = _dashboard_args(tmp_path, presets)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_dashboard_rejects_presets_and_legacy_port_before_store_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    presets = tmp_path / "presets.json"
    presets.write_text(json.dumps(_catalog_payload()), encoding="utf-8")
    monkeypatch.setattr(uvicorn, "run", lambda *_args, **_kwargs: pytest.fail("must not serve"))
    args = [*_dashboard_args(tmp_path, presets), "--msp430-port", "COM4"]
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert "DASHBOARD_MONITOR_PROVIDER_CONFLICT" in result.output
    assert not (tmp_path / "dashboard.db").exists()


@pytest.mark.parametrize("hardware", [False, True])
def test_dashboard_existing_pair_presets_preserve_stores_and_refuse_hardware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hardware: bool
) -> None:
    presets = tmp_path / "presets.json"
    presets.write_text(json.dumps(_catalog_payload(hardware=hardware)), encoding="utf-8")
    args = _dashboard_args(tmp_path, presets)
    database, jobs = tmp_path / "dashboard.db", tmp_path / "jobs.db"
    SQLiteCandidateRepository(database).initialize()
    CollectionJobStore(jobs).initialize()
    args.extend(["--job-store", str(jobs), "--existing-pair"])
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    served: list[Any] = []

    def fake_run(application: Any, **_kwargs: Any) -> None:
        served.append(application)
        assert application.state.dashboard_monitor_controller.view().session.state == "STOPPED"

    monkeypatch.setattr(uvicorn, "run", fake_run)
    result = runner.invoke(app, args)
    assert (result.exit_code != 0) is hardware, result.output
    assert bool(served) is not hardware
    if hardware:
        assert "DASHBOARD_EXISTING_PAIR_REQUIRES_JOBS_AND_NO_HARDWARE" in result.output
        assert {path.name for path in tmp_path.iterdir()} == set(before)
    assert {name: (tmp_path / name).read_bytes() for name in before} == before


def test_monitor_preset_loader_accepts_exact_byte_limit(tmp_path: Path) -> None:
    presets = tmp_path / "presets.json"
    raw = json.dumps(_catalog_payload()).encode("utf-8")
    presets.write_bytes(raw + b" " * (64 * 1024 - len(raw)))
    assert load_monitor_presets(presets).project_id == "sample-api"


@pytest.mark.parametrize("directory", [False, True])
def test_monitor_preset_loader_requires_existing_regular_file(
    tmp_path: Path, directory: bool
) -> None:
    presets = tmp_path / "presets.json"
    if directory:
        presets.mkdir()
    with pytest.raises(ValueError, match="MONITOR_PRESETS_FILE_REQUIRED"):
        load_monitor_presets(presets)


@pytest.mark.parametrize("force_color", [False, True], ids=["plain", "forced-color"])
def test_dashboard_help_exposes_preset_file_and_initializer(
    monkeypatch: pytest.MonkeyPatch, force_color: bool
) -> None:
    for variable in ("NO_COLOR", "FORCE_COLOR", "PY_COLORS"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    if force_color:
        monkeypatch.setenv("FORCE_COLOR", "1")
        monkeypatch.setenv("PY_COLORS", "1")
    # Typer caches terminal forcing at import; isolate both rendering modes.
    monkeypatch.setattr("typer.rich_utils.FORCE_TERMINAL", force_color)

    dashboard = runner.invoke(app, ["dashboard", "--help"])
    assert dashboard.exit_code == 0, dashboard.output
    assert ("\x1b[" in dashboard.output) is force_color
    assert "--monitor-presets" in Text.from_ansi(dashboard.output).plain
    initializer = runner.invoke(app, ["monitor-preset-init", "--help"])
    assert initializer.exit_code == 0, initializer.output
    assert ("\x1b[" in initializer.output) is force_color
    initializer_text = Text.from_ansi(initializer.output).plain
    assert "--project" in initializer_text
    assert "--msp430-port" in initializer_text
