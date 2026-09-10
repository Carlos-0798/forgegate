from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from forgegate.live_status import LiveReportedIssue, LiveSourceStatus, LiveStatusPage
from forgegate.monitor_presets.models import (
    MonitorControlView,
    MonitorPreset,
    MonitorPresetCatalog,
    MonitorSessionView,
)


class MonitorPresetError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ManagedMonitor(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def snapshot(self) -> LiveStatusPage: ...


def _serial_monitor(preset: MonitorPreset) -> ManagedMonitor:
    # Importing the optional compatibility surface occurs only on explicit real start.
    from forgegate.compatibility.msp430_live import Msp430SerialMonitor

    assert preset.port is not None
    return Msp430SerialMonitor(preset.port, stale_after_seconds=preset.stale_after_seconds)


class MonitorPresetController:
    """One explicitly started, process-local monitor from an immutable startup catalog."""

    def __init__(
        self,
        catalog: MonitorPresetCatalog,
        *,
        monitor_factory: Callable[[MonitorPreset], ManagedMonitor] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] | None = None,
    ) -> None:
        self._catalog = catalog
        self._monitor_factory = monitor_factory or _serial_monitor
        self._monotonic = monotonic
        self._utc_now = utc_now or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()
        self._monitor: ManagedMonitor | None = None
        self._active: MonitorPreset | None = None
        self._run_id: str | None = None
        self._state: Literal["STOPPED", "RUNNING", "ERROR", "STOPPING"] = "STOPPED"
        self._revision = 0
        self._detail_code = "MONITOR_STOPPED"
        self._detail_message = "Choose a saved preset and start monitoring."
        self._closed = False

    @property
    def catalog(self) -> MonitorPresetCatalog:
        return self._catalog

    @property
    def hardware_access(self) -> Literal["NOT_PERFORMED", "READ_ONLY_TELEMETRY"]:
        with self._lock:
            if self._active is not None and self._active.adapter == "msp430.uart.v1":
                return "READ_ONLY_TELEMETRY"
            return "NOT_PERFORMED"

    def view(self) -> MonitorControlView:
        with self._lock:
            return MonitorControlView(
                project_id=self._catalog.project_id,
                presets=self._catalog.presets,
                session=MonitorSessionView(
                    state=self._state,
                    revision=self._revision,
                    run_id=self._run_id,
                    active_preset_id=None if self._active is None else self._active.preset_id,
                    detail_code=self._detail_code,
                    detail_message=self._detail_message,
                ),
            )

    def snapshot(self) -> LiveStatusPage:
        with self._lock:
            if self._monitor is None:
                return LiveStatusPage(observed_at=self._utc_now(), sources=())
            return self._monitor.snapshot()

    def start(self, preset_id: str, expected_revision: int) -> MonitorControlView:
        with self._lock:
            if self._closed:
                raise MonitorPresetError(
                    "MONITOR_CONTROLLER_CLOSED", "The monitor service is shutting down.", 503
                )
            if expected_revision != self._revision:
                raise MonitorPresetError(
                    "MONITOR_REVISION_CONFLICT",
                    "Reload the current monitor session and retry.",
                    409,
                )
            preset = next(
                (item for item in self._catalog.presets if item.preset_id == preset_id), None
            )
            if preset is None:
                raise MonitorPresetError("MONITOR_PRESET_NOT_FOUND", "Preset not found.", 404)
            if self._monitor is not None:
                if self._state == "RUNNING" and self._active == preset:
                    return self.view()
                raise MonitorPresetError(
                    "MONITOR_ALREADY_ACTIVE",
                    "Stop the active monitor before starting a preset.",
                    409,
                )
            try:
                monitor: ManagedMonitor = (
                    _SimulatedDemoMonitor(preset, self._monotonic, self._utc_now)
                    if preset.adapter == "forgegate.simulated-demo.v1"
                    else self._monitor_factory(preset)
                )
            except Exception as exc:
                self._state = "ERROR"
                self._revision += 1
                self._detail_code = "MONITOR_START_FAILED"
                self._detail_message = (
                    "The selected monitor could not be prepared. Check its setup."
                )
                raise MonitorPresetError(self._detail_code, self._detail_message, 503) from exc
            self._monitor = monitor
            self._active = preset
            self._run_id = uuid.uuid4().hex
            self._revision += 1
            try:
                monitor.start()
            except Exception as exc:
                self._state = "ERROR"
                self._detail_code = "MONITOR_START_FAILED"
                self._detail_message = "Monitor startup failed. Stop this session before retrying."
                raise MonitorPresetError(self._detail_code, self._detail_message, 503) from exc
            self._state = "RUNNING"
            self._detail_code = "MONITOR_RUNNING"
            self._detail_message = (
                "Simulated demonstration is running; no hardware is accessed."
                if preset.adapter == "forgegate.simulated-demo.v1"
                else "Read-only monitoring is running. Check live connection and heartbeat status."
            )
            return self.view()

    def stop(self, run_id: str) -> MonitorControlView:
        with self._lock:
            if self._run_id is None or run_id != self._run_id:
                raise MonitorPresetError(
                    "MONITOR_RUN_CONFLICT",
                    "Reload the current monitor session before stopping.",
                    409,
                )
            self._stop_monitor()
            return self.view()

    def _stop_monitor(self) -> None:
        assert self._monitor is not None
        self._revision += 1
        try:
            self._monitor.stop()
        except Exception as exc:
            self._state = "STOPPING"
            self._detail_code = "MONITOR_STOP_INCOMPLETE"
            self._detail_message = (
                "The monitor has not confirmed stopping. Retry Stop before starting another preset."
            )
            raise MonitorPresetError(self._detail_code, self._detail_message, 503) from exc
        self._monitor = None
        self._active = None
        self._run_id = None
        self._state = "STOPPED"
        self._detail_code = "MONITOR_STOPPED"
        self._detail_message = "The monitor is stopped. Saved presets remain available."

    def close(self) -> None:
        with self._lock:
            self._closed = True
            if self._monitor is not None:
                self._stop_monitor()


class _SimulatedDemoMonitor:
    """Generate a deterministic 30-second demonstration without I/O or worker threads."""

    def __init__(
        self,
        preset: MonitorPreset,
        monotonic: Callable[[], float],
        utc_now: Callable[[], datetime],
    ) -> None:
        self._preset = preset
        self._monotonic = monotonic
        self._utc_now = utc_now
        self._started_at = 0.0

    def start(self) -> None:
        self._started_at = self._monotonic()

    def stop(self) -> None:
        pass

    def snapshot(self) -> LiveStatusPage:
        elapsed = max(0.0, self._monotonic() - self._started_at)
        cycle, within = divmod(elapsed, 30.0)
        phase = int(within // 5)
        phase_elapsed = within % 5
        now = self._utc_now()
        connection: Literal["CONNECTED", "DISCONNECTED"] = "CONNECTED"
        heartbeat: Literal["NORMAL", "STALE", "INVALID"] = "NORMAL"
        health: Literal["NORMAL", "UNKNOWN", "FAULT"] = "NORMAL"
        age = phase_elapsed % 1
        accepted = int(cycle) * 15 + int(phase_elapsed) + 1
        detail_code, description = "SIMULATED_NORMAL", "normal heartbeat"
        if phase in (1, 2, 3):
            accepted = int(cycle) * 15 + 5
            age = self._preset.stale_after_seconds + 1 + within - 5
            health = "UNKNOWN"
            heartbeat = "INVALID" if phase == 2 else "STALE"
            if phase == 1:
                detail_code, description = "SIMULATED_STALE", "late heartbeat"
            elif phase == 2:
                detail_code, description = "SIMULATED_INVALID", "invalid telemetry frame"
            else:
                connection = "DISCONNECTED"
                detail_code, description = "SIMULATED_DISCONNECTED", "disconnected endpoint"
        elif phase == 4:
            accepted += 5
            health = "FAULT"
            detail_code, description = "SIMULATED_FAULT", "reported device fault"
        elif phase == 5:
            accepted += 10
            detail_code, description = "SIMULATED_RECOVERY", "recovered normal heartbeat"
        source = LiveSourceStatus(
            source_id=self._preset.preset_id,
            source_type="forgegate.simulated-demo.v1",
            display_name=self._preset.name,
            data_origin="SIMULATED",
            connection=connection,
            heartbeat=heartbeat,
            device_health=health,
            detail_code=detail_code,
            detail_message=f"Simulated {description}; generated demonstration data, no hardware.",
            endpoint="SIMULATED (no serial port)",
            protocol="forgegate.simulated-demo.v1",
            baud_rate=115200,
            expected_interval_seconds=1,
            stale_after_seconds=self._preset.stale_after_seconds,
            observed_at=now,
            last_heartbeat_at=now - timedelta(seconds=age),
            heartbeat_age_seconds=round(age, 3),
            sequence=accepted % (2**32),
            uptime_ms=int(elapsed * 1000) % (2**32),
            device_state=None if health == "UNKNOWN" else health,
            fault_flags="0001" if health == "FAULT" else "0000",
            reported_issues=(
                (
                    LiveReportedIssue(
                        code="SIMULATED_FAULT", label="Simulated sensor fault", mask="0x0001"
                    ),
                )
                if health == "FAULT"
                else ()
            ),
            frames_received=accepted,
            protocol_errors=int(cycle) + int(phase >= 2),
            sequence_gaps=int(cycle) + int(phase >= 4),
            reconnects=int(cycle) + int(phase >= 4),
        )
        return LiveStatusPage(observed_at=now, sources=(source,))


__all__ = ["MonitorPresetController", "MonitorPresetError"]
