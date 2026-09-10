from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from forgegate.api import ApiAuthenticator, create_api_app
from forgegate.collection_jobs import CollectionJobStore
from forgegate.dashboard.startup import DashboardStartupError
from forgegate.live_status import DisabledLiveStatusProvider
from forgegate.monitor_presets import MonitorPreset, MonitorPresetCatalog, MonitorPresetController
from tests.api_auth_support import TEST_TRUST_STORE
from tests.test_dashboard import (
    ORIGIN,
    ORIGIN_HEADER,
    _activate,
    _application_with_project,
    _producer_trust_store,
)

PRESETS = "/app/api/monitor-presets"
START = "/app/api/monitor-session/start"
STOP = "/app/api/monitor-session/stop"


@pytest.fixture(autouse=True)
def forbid_hardware_monitor(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("preset Dashboard tests must never construct a physical monitor")

    monkeypatch.setattr("forgegate.compatibility.msp430_live.Msp430SerialMonitor", forbidden)


def _catalog(*, hardware: bool = False) -> MonitorPresetCatalog:
    presets = [
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
    return MonitorPresetCatalog.model_validate(
        {
            "schema_version": "forgegate.monitor-presets.v1",
            "project_id": "sample-api",
            "presets": presets,
        }
    )


def _client(
    tmp_path: Path,
    repository_root: Path,
    controller: MonitorPresetController | None,
    *,
    producer: bool = False,
) -> TestClient:
    return TestClient(
        create_api_app(
            tmp_path / "forgegate.db",
            application=_application_with_project(tmp_path, repository_root),
            authenticator=ApiAuthenticator(
                _producer_trust_store() if producer else TEST_TRUST_STORE
            ),
            dashboard=True,
            dashboard_monitor_controller=controller,
        ),
        base_url=ORIGIN,
    )


def _headers(activated: dict[str, Any]) -> dict[str, str]:
    return {**ORIGIN_HEADER, "X-ForgeGate-CSRF": activated["csrf_token"]}


def test_unconfigured_presets_require_login_and_explain_unavailable_controls(
    tmp_path: Path, repository_root: Path
) -> None:
    with _client(tmp_path, repository_root, None) as client:
        assert client.get(PRESETS).status_code == 401
        activated = _activate(client)
        response = client.get(PRESETS)
        assert response.status_code == 200
        assert response.json() is None
        for route, payload in (
            (START, {"preset_id": "simulated-demo", "expected_revision": 0}),
            (STOP, {"run_id": "a" * 32}),
        ):
            refused = client.post(route, headers=_headers(activated), json=payload)
            assert refused.status_code == 503, refused.text


def test_demo_session_round_trip_rejects_stale_actions_and_retains_evidence_boundary(
    tmp_path: Path, repository_root: Path
) -> None:
    controller = MonitorPresetController(_catalog())
    with _client(tmp_path, repository_root, controller) as client:
        activated = _activate(client)
        initial = client.get(PRESETS).json()
        assert initial["project_id"] == "sample-api"
        assert initial["presets"][0]["preset_id"] == "simulated-demo"
        assert initial["session"]["state"] == "STOPPED"
        assert initial["session"]["revision"] == 0
        assert initial["session"]["run_id"] is None
        assert client.get("/app/api/live-status").json()["sources"] == []

        started = client.post(
            START,
            headers=_headers(activated),
            json={"preset_id": "simulated-demo", "expected_revision": 0},
        )
        assert started.status_code == 200, started.text
        running = started.json()["session"]
        assert running["state"] == "RUNNING"
        assert running["revision"] == 1
        assert running["active_preset_id"] == "simulated-demo"
        assert running["run_id"]
        live = client.get("/app/api/live-status").json()
        assert live["sources"]
        assert all(source["hardware_control"] == "NOT_PERFORMED" for source in live["sources"])
        assert all(
            source["evidence_boundary"] == "LIVE_STATUS_ONLY_NOT_RELEASE_EVIDENCE"
            for source in live["sources"]
        )
        assert client.get("/app/api/overview").json()["hardware_access"] == "NOT_PERFORMED"

        stale_start = client.post(
            START,
            headers=_headers(activated),
            json={"preset_id": "simulated-demo", "expected_revision": 0},
        )
        assert stale_start.status_code == 409, stale_start.text
        stale_stop = client.post(STOP, headers=_headers(activated), json={"run_id": "0" * 32})
        assert stale_stop.status_code == 409, stale_stop.text
        assert client.get(PRESETS).json()["session"] == running

        stopped = client.post(STOP, headers=_headers(activated), json={"run_id": running["run_id"]})
        assert stopped.status_code == 200, stopped.text
        stopped_session = stopped.json()["session"]
        assert stopped_session["state"] == "STOPPED"
        assert stopped_session["revision"] > running["revision"]
        assert stopped_session["run_id"] is None
        assert client.get("/app/api/live-status").json()["sources"] == []

        restarted = client.post(
            START,
            headers=_headers(activated),
            json={
                "preset_id": "simulated-demo",
                "expected_revision": stopped_session["revision"],
            },
        )
        assert restarted.status_code == 200, restarted.text
        new_run = restarted.json()["session"]
        assert new_run["run_id"] != running["run_id"]
        late_stop = client.post(
            STOP, headers=_headers(activated), json={"run_id": running["run_id"]}
        )
        assert late_stop.status_code == 409, late_stop.text
        assert client.get(PRESETS).json()["session"] == new_run
    assert controller.view().session.state == "STOPPED"


@pytest.mark.parametrize("route", [START, STOP])
@pytest.mark.parametrize(
    "missing_or_wrong", ["cookie", "origin", "wrong-origin", "csrf", "wrong-csrf"]
)
def test_monitor_writes_require_cookie_exact_origin_and_csrf(
    tmp_path: Path, repository_root: Path, route: str, missing_or_wrong: str
) -> None:
    controller = MonitorPresetController(_catalog())
    with _client(tmp_path, repository_root, controller) as client:
        activated = _activate(client)
        before = client.get(PRESETS).json()["session"]
        headers = _headers(activated)
        if missing_or_wrong == "cookie":
            client.cookies.clear()
        elif missing_or_wrong == "origin":
            headers.pop("Origin")
        elif missing_or_wrong == "wrong-origin":
            headers["Origin"] = "http://localhost"
        elif missing_or_wrong == "csrf":
            headers.pop("X-ForgeGate-CSRF")
        else:
            headers["X-ForgeGate-CSRF"] = "forged-token"
        payload = (
            {"preset_id": "simulated-demo", "expected_revision": 0}
            if route == START
            else {"run_id": "a" * 32}
        )
        response = client.post(route, headers=headers, json=payload)
        assert response.status_code == (401 if missing_or_wrong == "cookie" else 403)
        assert controller.view().session.model_dump(mode="json") == before


@pytest.mark.parametrize("producer", [False, True])
def test_monitor_control_requires_operator_and_project_scope(
    tmp_path: Path, repository_root: Path, producer: bool
) -> None:
    controller = MonitorPresetController(_catalog(hardware=True))
    with _client(tmp_path, repository_root, controller, producer=producer) as client:
        activated = _activate(
            client,
            role="producer" if producer else "operator",
            project_ids=["sample-api"] if producer else ["another-project"],
        )
        expected_read_status = 200 if producer else 403
        assert client.get(PRESETS).status_code == expected_read_status
        assert client.get("/app/api/live-status").status_code == expected_read_status
        before = controller.view()
        for route, payload in (
            (START, {"preset_id": "msp430-uart", "expected_revision": 0}),
            (STOP, {"run_id": "a" * 32}),
        ):
            response = client.post(route, headers=_headers(activated), json=payload)
            assert response.status_code == 403, response.text
        assert controller.view() == before


@pytest.mark.parametrize("route", [PRESETS, "/app/api/live-status"])
def test_monitor_reads_reject_foreign_origin_and_anonymous_access(
    tmp_path: Path, repository_root: Path, route: str
) -> None:
    controller = MonitorPresetController(_catalog())
    with _client(tmp_path, repository_root, controller) as client:
        assert client.get(route).status_code == 401
        _activate(client)
        assert client.get(route, headers={"Origin": "http://localhost"}).status_code == 403


@pytest.mark.parametrize(
    ("route", "payload"),
    [
        (START, {}),
        (START, {"preset_id": "simulated-demo"}),
        (START, {"preset_id": "simulated-demo", "expected_revision": -1}),
        (START, {"preset_id": "simulated-demo", "expected_revision": True}),
        (START, {"preset_id": "simulated-demo", "expected_revision": "0"}),
        (START, {"preset_id": "../other", "expected_revision": 0}),
        (START, {"preset_id": "simulated-demo", "expected_revision": 0, "port": "COM4"}),
        (STOP, {}),
        (STOP, {"run_id": "../other"}),
        (STOP, {"run_id": "a" * 32, "preset_id": "simulated-demo"}),
    ],
)
def test_monitor_commands_reject_invalid_or_additional_fields_without_state_change(
    tmp_path: Path, repository_root: Path, route: str, payload: dict[str, Any]
) -> None:
    controller = MonitorPresetController(_catalog())
    with _client(tmp_path, repository_root, controller) as client:
        activated = _activate(client)
        before = controller.view()
        response = client.post(route, headers=_headers(activated), json=payload)
        assert response.status_code == 422, response.text
        assert controller.view() == before


def test_unknown_preset_is_not_found_without_session_mutation(
    tmp_path: Path, repository_root: Path
) -> None:
    controller = MonitorPresetController(_catalog())
    with _client(tmp_path, repository_root, controller) as client:
        activated = _activate(client)
        before = controller.view()
        response = client.post(
            START,
            headers=_headers(activated),
            json={"preset_id": "unconfigured", "expected_revision": 0},
        )
        assert response.status_code == 404, response.text
        assert controller.view() == before


def test_monitor_preparation_failure_is_sanitized_and_visible_for_retry(
    tmp_path: Path, repository_root: Path
) -> None:
    private_detail = "injected private device or filesystem detail"

    def fail_prepare(_preset: MonitorPreset) -> Any:
        raise OSError(private_detail)

    controller = MonitorPresetController(_catalog(hardware=True), monitor_factory=fail_prepare)
    with _client(tmp_path, repository_root, controller) as client:
        activated = _activate(client)
        response = client.post(
            START,
            headers=_headers(activated),
            json={"preset_id": "msp430-uart", "expected_revision": 0},
        )
        assert response.status_code == 503, response.text
        assert private_detail not in response.text
        view = client.get(PRESETS)
        assert view.status_code == 200
        assert view.json()["session"]["state"] == "ERROR"
        assert view.json()["session"]["revision"] == 1
        assert private_detail not in view.text
        assert client.get("/app/api/live-status").json()["sources"] == []


@pytest.mark.parametrize("dashboard_enabled", [False, True])
def test_api_rejects_controller_without_dashboard_or_with_competing_provider(
    tmp_path: Path, dashboard_enabled: bool
) -> None:
    database = tmp_path / "must-not-exist.db"
    with pytest.raises(ValueError):
        create_api_app(
            database,
            authenticator=ApiAuthenticator(TEST_TRUST_STORE),
            dashboard=dashboard_enabled,
            dashboard_monitor_controller=MonitorPresetController(_catalog()),
            dashboard_live_status_provider=(
                DisabledLiveStatusProvider() if dashboard_enabled else None
            ),
        )
    assert not database.exists()


def test_existing_pair_allows_demo_controller_and_closes_it(
    tmp_path: Path, repository_root: Path
) -> None:
    candidate_application = _application_with_project(tmp_path, repository_root)
    jobs = tmp_path / "jobs.db"
    CollectionJobStore(jobs).initialize()
    controller = MonitorPresetController(_catalog())
    with TestClient(
        create_api_app(
            tmp_path / "forgegate.db",
            application=candidate_application,
            authenticator=ApiAuthenticator(TEST_TRUST_STORE),
            dashboard=True,
            dashboard_job_store_path=jobs,
            dashboard_existing_pair=True,
            dashboard_monitor_controller=controller,
        ),
        base_url=ORIGIN,
    ) as client:
        activated = _activate(client)
        response = client.post(
            START,
            headers=_headers(activated),
            json={"preset_id": "simulated-demo", "expected_revision": 0},
        )
        assert response.status_code == 200, response.text
        assert controller.view().session.state == "RUNNING"
    assert controller.view().session.state == "STOPPED"


def test_existing_pair_rejects_hardware_catalog_before_opening_stores(tmp_path: Path) -> None:
    with pytest.raises(DashboardStartupError, match="NO_HARDWARE"):
        create_api_app(
            tmp_path / "must-not-exist.db",
            authenticator=ApiAuthenticator(TEST_TRUST_STORE),
            dashboard=True,
            dashboard_job_store_path=tmp_path / "jobs-must-not-exist.db",
            dashboard_existing_pair=True,
            dashboard_monitor_controller=MonitorPresetController(_catalog(hardware=True)),
        )
    assert list(tmp_path.iterdir()) == []
