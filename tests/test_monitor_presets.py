from __future__ import annotations

import builtins
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from forgegate.live_status import LiveStatusPage
from forgegate.monitor_presets import (
    MonitorControlView,
    MonitorPreset,
    MonitorPresetCatalog,
    MonitorPresetController,
    MonitorPresetError,
    MonitorStartRequest,
    MonitorStopRequest,
)


def catalog() -> MonitorPresetCatalog:
    return MonitorPresetCatalog(
        project_id="monitor-project",
        presets=(
            MonitorPreset(
                preset_id="demo", name="Practice monitor", adapter="forgegate.simulated-demo.v1"
            ),
            MonitorPreset(
                preset_id="board", name="Lab monitor", adapter="msp430.uart.v1", port="COM4"
            ),
        ),
    )


class Clock:
    elapsed = 0.0

    def monotonic(self) -> float:
        return self.elapsed

    def utc_now(self) -> datetime:
        return datetime(2026, 9, 9, tzinfo=UTC) + timedelta(seconds=self.elapsed)


class FakeMonitor:
    def __init__(self) -> None:
        self.starts = 0
        self.stops = 0
        self.fail_start = False
        self.fail_stop = False

    def start(self) -> None:
        self.starts += 1
        if self.fail_start:
            raise OSError("private device path in exception")

    def stop(self) -> None:
        self.stops += 1
        if self.fail_stop:
            raise TimeoutError("private device path in exception")

    def snapshot(self) -> LiveStatusPage:
        return LiveStatusPage(observed_at=datetime(2026, 9, 9, tzinfo=UTC), sources=())


@pytest.mark.parametrize(
    "changes",
    [
        {"adapter": "unknown.adapter.v1"},
        {"adapter": "msp430.uart.v1"},
        {"port": "COM4"},
        {"stale_after_seconds": 1.49},
        {"stale_after_seconds": 60.01},
        {"stale_after_seconds": float("nan")},
        {"stale_after_seconds": float("inf")},
        {"stale_after_seconds": True},
        {"stale_after_seconds": "3"},
        {"preset_id": "../demo"},
        {"name": " "},
        {"command": "STOP"},
    ],
)
def test_preset_rejects_unsupported_or_unsafe_configuration(changes: dict[str, Any]) -> None:
    document = catalog().presets[0].model_dump()
    document.update(changes)
    with pytest.raises(ValidationError):
        MonitorPreset.model_validate(document)


@pytest.mark.parametrize("port", ["COM0", "COM01", "COM10000", "com4", "COM4/other", "tcp://host"])
def test_hardware_preset_only_accepts_explicit_windows_com_endpoint(port: str) -> None:
    with pytest.raises(ValidationError):
        MonitorPreset(preset_id="board", name="Board", adapter="msp430.uart.v1", port=port)


def test_catalog_is_versioned_bounded_unique_and_immutable() -> None:
    original = catalog()
    assert MonitorPresetCatalog.model_validate_json(original.model_dump_json()) == original
    invalid = [
        {"schema_version": "forgegate.monitor-presets.v2"},
        {"presets": []},
        {"presets": [original.presets[0]] * 2},
        {"presets": [original.presets[0]] * 21},
        {"project_id": "../project"},
        {"auto_start": True},
    ]
    for changes in invalid:
        with pytest.raises(ValidationError):
            MonitorPresetCatalog.model_validate({**original.model_dump(), **changes})
    with pytest.raises(ValidationError):
        original.project_id = "another-project"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        original.presets[0].name = "changed"  # type: ignore[misc]


def test_control_requests_reject_missing_revision_and_unbound_stop() -> None:
    for changes in ({}, {"expected_revision": -1}, {"expected_revision": True}):
        with pytest.raises(ValidationError):
            MonitorStartRequest.model_validate({"preset_id": "demo", **changes})
    for document in ({}, {"run_id": ""}, {"run_id": "a" * 32, "command": "STOP"}):
        with pytest.raises(ValidationError):
            MonitorStopRequest.model_validate(document)


def test_saved_catalog_and_reads_do_not_construct_or_start_any_monitor() -> None:
    controller = MonitorPresetController(
        catalog(), monitor_factory=lambda _: pytest.fail("no start")
    )
    assert controller.catalog == catalog()
    initial = controller.view()
    assert initial.schema_version == "forgegate.monitor-control.v1"
    assert initial.session.state == "STOPPED"
    assert initial.session.revision == 0
    assert initial.session.run_id is initial.session.active_preset_id is None
    assert controller.snapshot().sources == ()
    assert controller.hardware_access == "NOT_PERFORMED"
    controller.close()
    controller.close()
    with pytest.raises(MonitorPresetError, match="shutting down") as closed:
        controller.start("demo", 0)
    assert closed.value.code == "MONITOR_CONTROLLER_CLOSED"


def test_demo_cycles_all_states_without_optional_imports_or_factory_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        assert not name.startswith("serial") and "msp430" not in name
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    clock = Clock()
    controller = MonitorPresetController(
        catalog(),
        monitor_factory=lambda _: pytest.fail("demo must not create a real monitor"),
        monotonic=clock.monotonic,
        utc_now=clock.utc_now,
    )
    run = controller.start("demo", 0)
    assert run.session.revision == 1 and run.session.state == "RUNNING"
    assert "Simulated" in run.session.detail_message
    expected = [
        (0, "CONNECTED", "NORMAL", "NORMAL", "SIMULATED_NORMAL"),
        (5, "CONNECTED", "STALE", "UNKNOWN", "SIMULATED_STALE"),
        (10, "CONNECTED", "INVALID", "UNKNOWN", "SIMULATED_INVALID"),
        (15, "DISCONNECTED", "STALE", "UNKNOWN", "SIMULATED_DISCONNECTED"),
        (20, "CONNECTED", "NORMAL", "FAULT", "SIMULATED_FAULT"),
        (25, "CONNECTED", "NORMAL", "NORMAL", "SIMULATED_RECOVERY"),
        (30, "CONNECTED", "NORMAL", "NORMAL", "SIMULATED_NORMAL"),
    ]
    accepted = []
    for elapsed, connection, heartbeat, health, detail in expected:
        clock.elapsed = elapsed
        source = controller.snapshot().sources[0]
        assert (source.connection, source.heartbeat, source.device_health) == (
            connection,
            heartbeat,
            health,
        )
        assert source.detail_code == detail
        assert source.data_origin == "SIMULATED"
        assert source.hardware_control == "NOT_PERFORMED"
        assert source.evidence_boundary == "LIVE_STATUS_ONLY_NOT_RELEASE_EVIDENCE"
        assert "Simulated" in source.detail_message
        assert controller.hardware_access == "NOT_PERFORMED"
        if health == "FAULT":
            assert source.reported_issues[0].code == "SIMULATED_FAULT"
        if heartbeat == "STALE":
            assert source.heartbeat_age_seconds > source.stale_after_seconds
        accepted.append(source.frames_received)
    assert accepted[1] == accepted[2] == accepted[3]
    assert accepted[-1] > accepted[-2]
    assert run.session.run_id is not None
    stopped = controller.stop(run.session.run_id)
    assert stopped.session.state == "STOPPED" and stopped.session.revision == 2
    assert controller.snapshot().sources == ()


def test_revision_and_run_binding_block_stale_or_conflicting_actions() -> None:
    controller = MonitorPresetController(catalog())
    with pytest.raises(MonitorPresetError) as missing:
        controller.start("absent", 0)
    assert (missing.value.code, missing.value.status_code) == ("MONITOR_PRESET_NOT_FOUND", 404)
    started = controller.start("demo", 0)
    assert controller.start("demo", 1) == started
    for preset_id, revision, code in [
        ("demo", 0, "MONITOR_REVISION_CONFLICT"),
        ("board", 1, "MONITOR_ALREADY_ACTIVE"),
    ]:
        with pytest.raises(MonitorPresetError) as conflict:
            controller.start(preset_id, revision)
        assert (conflict.value.code, conflict.value.status_code) == (code, 409)
    with pytest.raises(MonitorPresetError) as wrong_run:
        controller.stop("0" * 32)
    assert wrong_run.value.code == "MONITOR_RUN_CONFLICT"
    assert controller.view() == started
    assert started.session.run_id is not None
    controller.stop(started.session.run_id)
    restarted = controller.start("demo", 2)
    assert restarted.session.run_id != started.session.run_id
    with pytest.raises(MonitorPresetError):
        controller.stop(started.session.run_id)
    assert controller.view() == restarted
    controller.close()


def test_concurrent_start_requests_create_only_one_reader() -> None:
    handle = FakeMonitor()
    selected = []

    def factory(preset: MonitorPreset) -> FakeMonitor:
        selected.append(preset)
        return handle

    controller = MonitorPresetController(catalog(), monitor_factory=factory)
    barrier = threading.Barrier(2)

    def start() -> MonitorControlView | MonitorPresetError:
        barrier.wait(timeout=2)
        try:
            return controller.start("board", 0)
        except MonitorPresetError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(start), executor.submit(start)]
        results = [future.result(timeout=3) for future in futures]
    assert sum(isinstance(result, MonitorControlView) for result in results) == 1
    assert handle.starts == len(selected) == 1
    assert selected[0].port == "COM4"
    assert controller.hardware_access == "READ_ONLY_TELEMETRY"
    assert controller.snapshot() == handle.snapshot()
    controller.close()
    assert handle.stops == 1 and controller.hardware_access == "NOT_PERFORMED"


def test_failed_factory_is_sanitized_and_can_be_retried_with_fresh_revision() -> None:
    def fail(_preset: MonitorPreset) -> FakeMonitor:
        raise OSError("private path and device failure")

    controller = MonitorPresetController(catalog(), monitor_factory=fail)
    with pytest.raises(MonitorPresetError) as error:
        controller.start("board", 0)
    assert (error.value.code, error.value.status_code) == ("MONITOR_START_FAILED", 503)
    failed = controller.view().session
    assert failed.state == "ERROR" and failed.revision == 1
    assert failed.run_id is failed.active_preset_id is None
    assert "private" not in failed.detail_message
    assert controller.hardware_access == "NOT_PERFORMED"
    assert controller.start("demo", 1).session.state == "RUNNING"
    controller.close()


def test_failed_start_retains_handle_until_explicit_stop() -> None:
    handle = FakeMonitor()
    handle.fail_start = True
    controller = MonitorPresetController(catalog(), monitor_factory=lambda _: handle)
    with pytest.raises(MonitorPresetError):
        controller.start("board", 0)
    failed = controller.view().session
    assert failed.state == "ERROR" and failed.run_id is not None
    assert failed.active_preset_id == "board"
    assert controller.hardware_access == "READ_ONLY_TELEMETRY"
    with pytest.raises(MonitorPresetError) as active:
        controller.start("demo", 1)
    assert active.value.code == "MONITOR_ALREADY_ACTIVE"
    controller.stop(failed.run_id)
    assert handle.stops == 1
    assert controller.hardware_access == "NOT_PERFORMED"


def test_incomplete_stop_retains_reader_and_allows_only_bound_stop_retry() -> None:
    handle = FakeMonitor()
    controller = MonitorPresetController(catalog(), monitor_factory=lambda _: handle)
    started = controller.start("board", 0).session
    assert started.run_id is not None
    handle.fail_stop = True
    with pytest.raises(MonitorPresetError) as incomplete:
        controller.stop(started.run_id)
    assert incomplete.value.code == "MONITOR_STOP_INCOMPLETE"
    stopped = controller.view().session
    assert stopped.state == "STOPPING" and stopped.run_id == started.run_id
    assert stopped.active_preset_id == "board" and stopped.revision == 2
    assert "private" not in stopped.detail_message
    assert controller.hardware_access == "READ_ONLY_TELEMETRY"
    with pytest.raises(MonitorPresetError) as active:
        controller.start("board", 2)
    assert active.value.code == "MONITOR_ALREADY_ACTIVE"
    handle.fail_stop = False
    assert controller.stop(started.run_id).session.state == "STOPPED"
    controller.start("demo", 3)
    controller.close()


def test_shutdown_blocks_start_but_preserves_incomplete_reader_for_cleanup_retry() -> None:
    handle = FakeMonitor()
    handle.fail_stop = True
    controller = MonitorPresetController(catalog(), monitor_factory=lambda _: handle)
    controller.start("board", 0)
    with pytest.raises(MonitorPresetError):
        controller.close()
    assert controller.view().session.state == "STOPPING"
    assert controller.hardware_access == "READ_ONLY_TELEMETRY"
    with pytest.raises(MonitorPresetError) as closed:
        controller.start("demo", 2)
    assert closed.value.code == "MONITOR_CONTROLLER_CLOSED"
    handle.fail_stop = False
    controller.close()
    assert controller.view().session.state == "STOPPED"


def test_real_adapter_import_occurs_only_on_explicit_selected_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle = FakeMonitor()
    selected = {}

    def factory(port: str, *, stale_after_seconds: float) -> FakeMonitor:
        selected.update(port=port, stale_after_seconds=stale_after_seconds)
        return handle

    monkeypatch.setattr("forgegate.compatibility.msp430_live.Msp430SerialMonitor", factory)
    controller = MonitorPresetController(catalog())
    assert not selected
    controller.start("board", 0)
    assert selected == {"port": "COM4", "stale_after_seconds": 3.0}
    assert handle.starts == 1
    controller.close()
