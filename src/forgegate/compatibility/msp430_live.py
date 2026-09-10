from __future__ import annotations

import importlib
import math
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, cast

from forgegate.live_status.models import LiveReportedIssue, LiveSourceStatus, LiveStatusPage

MSP430_UART_PROTOCOL = "msp430.uart.v1"
MSP430_UART_BAUD_RATE = 115_200
MSP430_UART_MAX_LINE_BYTES = 128
MSP430_EXPECTED_INTERVAL_SECONDS = 1.0
_UINT32_MAX = 4_294_967_295
_UINT16_MAX = 65_535
_INT16_MIN = -32_768
_INT16_MAX = 32_767
_VALID_STATES = frozenset(
    {"BOOT", "INIT", "NORMAL", "COOLING_LOW", "COOLING_HIGH", "WARNING", "FAULT"}
)
_UNSIGNED_INTEGER = re.compile(r"^(?:0|[1-9][0-9]*)$")
_SIGNED_INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_HEX16 = re.compile(r"^[0-9A-Fa-f]{4}$")
_FAULT_DESCRIPTIONS = (
    (0x0001, "DS18B20_MISSING", "DS18B20 sensor not detected"),
    (0x0002, "DS18B20_CRC", "DS18B20 CRC validation failed"),
    (0x0004, "NTC_RANGE", "NTC input unavailable or outside its valid range"),
    (0x0008, "SENSOR_DISAGREE", "Temperature sensors disagree"),
    (0x0010, "INA219_COMM", "INA219 communication unavailable"),
    (0x0020, "FAN_NO_CURRENT", "Fan current was not detected"),
    (0x0040, "FAN_OVERCURRENT", "Fan overcurrent reported"),
    (0x0080, "OVERTEMP_WARNING", "Overtemperature warning reported"),
    (0x0100, "OVERTEMP_CRITICAL", "Critical overtemperature reported"),
    (0x0200, "CONFIG_CRC", "Configuration CRC validation failed"),
    (0x0400, "WATCHDOG_RESET", "Watchdog reset reported"),
    (0x0800, "UART_PROTOCOL", "UART protocol fault reported"),
)


class Msp430ProtocolError(ValueError):
    """A complete TEL frame violated the frozen MSP430 UART v1 contract."""


class Msp430MonitorError(RuntimeError):
    """The optional serial dependency or monitor configuration is unavailable."""


class SerialHandle(Protocol):
    port: str
    baudrate: int
    bytesize: int
    parity: str
    stopbits: int
    timeout: float
    write_timeout: float
    dtr: bool
    rts: bool

    @property
    def is_open(self) -> bool: ...

    def open(self) -> None: ...

    def read_until(self, expected: bytes = b"\n", size: int | None = None) -> bytes: ...

    def close(self) -> None: ...


SerialFactory = Callable[[str], SerialHandle]
PortPresence = Callable[[str], bool]


@dataclass(frozen=True, slots=True)
class Msp430TelemetryFrame:
    sequence: int
    uptime_ms: int
    temp_ds_dC: int
    temp_ntc_dC: int
    bus_mV: int
    current_mA: int
    power_mW: int
    pwm_permille: int
    state: str
    fault_flags: str


def crc16_ccitt_false(payload: bytes) -> int:
    crc = 0xFFFF
    for byte in payload:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def parse_msp430_uart_v1_line(line: bytes) -> Msp430TelemetryFrame | None:
    if not line:
        return None
    if len(line) > MSP430_UART_MAX_LINE_BYTES:
        raise Msp430ProtocolError("UART_FRAME_TOO_LONG")
    if not line.endswith(b"\n"):
        raise Msp430ProtocolError("UART_FRAME_INCOMPLETE")
    payload = line[:-1]
    if payload.endswith(b"\r"):
        payload = payload[:-1]
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise Msp430ProtocolError("UART_FRAME_NON_ASCII") from exc
    if not text.startswith("TEL,"):
        return None
    fields = text.split(",")
    if len(fields) != 12:
        raise Msp430ProtocolError("UART_TEL_FIELD_COUNT")
    crc_text = fields[-1]
    if _HEX16.fullmatch(crc_text) is None:
        raise Msp430ProtocolError("UART_TEL_CRC_FORMAT")
    crc_payload = text.rsplit(",", 1)[0].encode("ascii")
    if crc16_ccitt_false(crc_payload) != int(crc_text, 16):
        raise Msp430ProtocolError("UART_TEL_CRC_MISMATCH")
    sequence = _bounded_integer(fields[1], 0, _UINT32_MAX, "UART_TEL_SEQUENCE")
    uptime_ms = _bounded_integer(fields[2], 0, _UINT32_MAX, "UART_TEL_UPTIME")
    temp_ds = _bounded_integer(fields[3], _INT16_MIN, _INT16_MAX, "UART_TEL_TEMP_DS")
    temp_ntc = _bounded_integer(fields[4], _INT16_MIN, _INT16_MAX, "UART_TEL_TEMP_NTC")
    bus_mv = _bounded_integer(fields[5], 0, _UINT16_MAX, "UART_TEL_BUS")
    current_ma = _bounded_integer(fields[6], _INT16_MIN, _INT16_MAX, "UART_TEL_CURRENT")
    power_mw = _bounded_integer(fields[7], 0, _UINT32_MAX, "UART_TEL_POWER")
    pwm = _bounded_integer(fields[8], 0, 1000, "UART_TEL_PWM")
    state = fields[9]
    if state not in _VALID_STATES:
        raise Msp430ProtocolError("UART_TEL_STATE")
    fault_flags = fields[10]
    if _HEX16.fullmatch(fault_flags) is None:
        raise Msp430ProtocolError("UART_TEL_FAULT_FORMAT")
    return Msp430TelemetryFrame(
        sequence=sequence,
        uptime_ms=uptime_ms,
        temp_ds_dC=temp_ds,
        temp_ntc_dC=temp_ntc,
        bus_mV=bus_mv,
        current_mA=current_ma,
        power_mW=power_mw,
        pwm_permille=pwm,
        state=state,
        fault_flags=fault_flags.upper(),
    )


def _bounded_integer(value: str, minimum: int, maximum: int, code: str) -> int:
    pattern = _SIGNED_INTEGER if minimum < 0 else _UNSIGNED_INTEGER
    if pattern.fullmatch(value) is None:
        raise Msp430ProtocolError(f"{code}_FORMAT")
    parsed = int(value)
    if not minimum <= parsed <= maximum:
        raise Msp430ProtocolError(f"{code}_RANGE")
    return parsed


class Msp430SerialMonitor:
    """Continuously observe an MSP430 UART v1 stream without transmitting bytes."""

    def __init__(
        self,
        port: str,
        *,
        stale_after_seconds: float = 3.0,
        reconnect_after_seconds: float = 1.0,
        serial_factory: SerialFactory | None = None,
        port_present: PortPresence | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] | None = None,
    ) -> None:
        endpoint = port.strip()
        if not endpoint or len(endpoint) > 120:
            raise ValueError("MSP430 serial port must contain 1-120 characters")
        if not 1.5 <= stale_after_seconds <= 60:
            raise ValueError("MSP430 stale threshold must be between 1.5 and 60 seconds")
        if not 0.05 <= reconnect_after_seconds <= 30:
            raise ValueError("MSP430 reconnect interval must be between 0.05 and 30 seconds")
        self._port = endpoint
        self._stale_after_seconds = stale_after_seconds
        self._reconnect_after_seconds = reconnect_after_seconds
        self._serial_factory = serial_factory or _default_serial_factory
        self._port_present = port_present or _default_port_present
        self._monotonic = monotonic
        self._utc_now = utc_now or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._connection: Literal["CONNECTING", "CONNECTED", "DISCONNECTED", "ERROR"] = "CONNECTING"
        self._detail_code = "SERIAL_CONNECTING"
        self._detail_message = "Waiting to open the configured read-only serial endpoint."
        self._last_valid_monotonic: float | None = None
        self._last_heartbeat_at: datetime | None = None
        self._last_frame: Msp430TelemetryFrame | None = None
        self._last_frame_invalid = False
        self._frames_received = 0
        self._protocol_errors = 0
        self._sequence_gaps = 0
        self._successful_connections = 0

    @property
    def hardware_access(self) -> Literal["READ_ONLY_TELEMETRY"]:
        return "READ_ONLY_TELEMETRY"

    def start(self) -> None:
        # Serialize lifecycle changes separately from the lock needed by the reader.
        with self._lifecycle_lock:
            with self._lock:
                if self._thread is not None and self._thread.is_alive():
                    if self._stop_event.is_set():
                        raise Msp430MonitorError("MONITOR_STOP_INCOMPLETE")
                    return
                self._stop_event.clear()
                self._connection = "CONNECTING"
                self._detail_code = "SERIAL_CONNECTING"
                self._detail_message = "Waiting to open the configured read-only serial endpoint."
                self._thread = threading.Thread(
                    target=self._run,
                    name="forgegate-msp430-read-only",
                    daemon=True,
                )
                thread = self._thread
            try:
                thread.start()
            except Exception as exc:
                with self._lock:
                    self._thread = None
                    self._connection = "ERROR"
                    self._detail_code = "MONITOR_START_FAILED"
                    self._detail_message = "The read-only serial monitor could not start."
                raise Msp430MonitorError("MONITOR_START_FAILED") from exc

    def stop(self, timeout: float = 3.0) -> None:
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("monitor stop timeout must be finite and nonnegative")
        with self._lifecycle_lock:
            self._stop_event.set()
            with self._lock:
                thread = self._thread
            if thread is not None:
                thread.join(timeout)
                if thread.is_alive():
                    with self._lock:
                        self._connection = "ERROR"
                        self._detail_code = "MONITOR_STOP_TIMEOUT"
                        self._detail_message = "The serial reader has not yet confirmed stopping."
                    raise Msp430MonitorError("MONITOR_STOP_TIMEOUT")
            with self._lock:
                self._thread = None
                self._connection = "DISCONNECTED"
                self._detail_code = "MONITOR_STOPPED"
                self._detail_message = "The read-only serial monitor is stopped."

    def snapshot(self) -> LiveStatusPage:
        now_utc = self._utc_now()
        now_monotonic = self._monotonic()
        with self._lock:
            age = (
                None
                if self._last_valid_monotonic is None
                else max(0.0, now_monotonic - self._last_valid_monotonic)
            )
            heartbeat: Literal["NOT_OBSERVED", "NORMAL", "STALE", "INVALID"]
            detail_code = self._detail_code
            detail_message = self._detail_message
            lifecycle_detail = detail_code in {
                "MONITOR_STOPPED",
                "MONITOR_STOP_TIMEOUT",
                "MONITOR_START_FAILED",
            }
            if self._last_frame_invalid:
                heartbeat = "INVALID"
                if not lifecycle_detail:
                    detail_code = "PROTOCOL_ERROR"
                    detail_message = "The latest TEL frame failed the frozen UART v1 contract."
            elif age is None:
                heartbeat = "NOT_OBSERVED"
            elif age > self._stale_after_seconds:
                heartbeat = "STALE"
                if not lifecycle_detail:
                    detail_code = "TELEMETRY_STALE"
                    detail_message = (
                        "No valid TEL frame arrived within the configured stale threshold."
                    )
            else:
                heartbeat = "NORMAL"
                if self._connection == "CONNECTED":
                    detail_code = "HEARTBEAT_NORMAL"
                    detail_message = "The serial endpoint is open and valid TEL frames are current."
            frame = self._last_frame
            device_health = _device_health(frame.state if frame is not None else None)
            source = LiveSourceStatus(
                source_id="msp430-uart",
                source_type=MSP430_UART_PROTOCOL,
                display_name="MSP430 UART monitor",
                connection=self._connection,
                heartbeat=heartbeat,
                device_health=device_health,
                detail_code=detail_code,
                detail_message=detail_message,
                endpoint=self._port,
                protocol=MSP430_UART_PROTOCOL,
                baud_rate=MSP430_UART_BAUD_RATE,
                expected_interval_seconds=MSP430_EXPECTED_INTERVAL_SECONDS,
                stale_after_seconds=self._stale_after_seconds,
                observed_at=now_utc,
                last_heartbeat_at=self._last_heartbeat_at,
                heartbeat_age_seconds=None if age is None else round(age, 3),
                sequence=None if frame is None else frame.sequence,
                uptime_ms=None if frame is None else frame.uptime_ms,
                device_state=None if frame is None else frame.state,
                fault_flags=None if frame is None else frame.fault_flags,
                reported_issues=() if frame is None else _reported_issues(frame.fault_flags),
                frames_received=self._frames_received,
                protocol_errors=self._protocol_errors,
                sequence_gaps=self._sequence_gaps,
                reconnects=max(0, self._successful_connections - 1),
            )
        return LiveStatusPage(observed_at=now_utc, sources=(source,))

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                present = self._port_present(self._port)
                if self._stop_event.is_set():
                    return
                if not present:
                    self._set_connection(
                        "DISCONNECTED",
                        "SERIAL_NOT_PRESENT",
                        "The configured serial endpoint is not currently enumerated.",
                    )
                    self._stop_event.wait(self._reconnect_after_seconds)
                    continue
                handle = self._serial_factory(self._port)
                try:
                    if self._stop_event.is_set():
                        return
                    handle.open()
                    with self._lock:
                        self._successful_connections += 1
                    self._set_connection(
                        "CONNECTED",
                        "SERIAL_CONNECTED",
                        "The configured serial endpoint is open in read-only monitor mode.",
                    )
                    self._read_connected(handle)
                finally:
                    if handle.is_open:
                        handle.close()
            except Msp430MonitorError:
                self._set_connection(
                    "ERROR",
                    "SERIAL_DEPENDENCY_UNAVAILABLE",
                    "Install the ForgeGate msp430 optional dependency to use serial monitoring.",
                )
                self._stop_event.wait(self._reconnect_after_seconds)
            except Exception:
                self._set_connection(
                    "ERROR",
                    "SERIAL_IO_ERROR",
                    "The configured serial endpoint could not be opened or read.",
                )
                self._stop_event.wait(self._reconnect_after_seconds)

    def _read_connected(self, handle: SerialHandle) -> None:
        while not self._stop_event.is_set():
            line = handle.read_until(b"\n", MSP430_UART_MAX_LINE_BYTES + 1)
            if self._stop_event.is_set():
                return
            if not line:
                continue
            self._process_line(line)

    def _process_line(self, line: bytes) -> None:
        try:
            frame = parse_msp430_uart_v1_line(line)
        except Msp430ProtocolError:
            with self._lock:
                self._protocol_errors += 1
                self._last_frame_invalid = True
            return
        if frame is None:
            return
        observed_at = self._utc_now()
        observed_monotonic = self._monotonic()
        with self._lock:
            if self._last_frame is not None:
                expected = (self._last_frame.sequence + 1) & _UINT32_MAX
                if frame.sequence != expected:
                    distance = (frame.sequence - expected) & _UINT32_MAX
                    self._sequence_gaps += distance if 0 < distance < 2**31 else 1
            self._last_frame = frame
            self._last_heartbeat_at = observed_at
            self._last_valid_monotonic = observed_monotonic
            self._last_frame_invalid = False
            self._frames_received += 1

    def _set_connection(
        self,
        state: Literal["CONNECTING", "CONNECTED", "DISCONNECTED", "ERROR"],
        code: str,
        message: str,
    ) -> None:
        with self._lock:
            if self._stop_event.is_set():
                return
            self._connection = state
            self._detail_code = code
            self._detail_message = message


def _device_health(state: str | None) -> Literal["UNKNOWN", "NORMAL", "WARNING", "FAULT"]:
    if state == "FAULT":
        return "FAULT"
    if state == "WARNING":
        return "WARNING"
    if state in {"NORMAL", "COOLING_LOW", "COOLING_HIGH"}:
        return "NORMAL"
    return "UNKNOWN"


def _reported_issues(fault_flags: str) -> tuple[LiveReportedIssue, ...]:
    value = int(fault_flags, 16)
    issues = [
        LiveReportedIssue(code=code, label=label, mask=f"0x{mask:04X}")
        for mask, code, label in _FAULT_DESCRIPTIONS
        if value & mask
    ]
    known_mask = sum(mask for mask, _, _ in _FAULT_DESCRIPTIONS)
    unknown_mask = value & ~known_mask
    if unknown_mask:
        issues.append(
            LiveReportedIssue(
                code="UNKNOWN_FAULT_BITS",
                label="Firmware reported fault bits not defined by this adapter version",
                mask=f"0x{unknown_mask:04X}",
            )
        )
    return tuple(issues)


def _default_serial_factory(port: str) -> SerialHandle:
    try:
        serial_module = importlib.import_module("serial")
    except ModuleNotFoundError as exc:
        raise Msp430MonitorError("pyserial is unavailable") from exc
    handle = serial_module.Serial(port=None)
    handle.port = port
    handle.baudrate = MSP430_UART_BAUD_RATE
    handle.bytesize = 8
    handle.parity = "N"
    handle.stopbits = 1
    handle.timeout = 0.25
    handle.write_timeout = 0
    handle.dtr = False
    handle.rts = False
    return cast(SerialHandle, handle)


def _default_port_present(port: str) -> bool:
    try:
        list_ports_module = importlib.import_module("serial.tools.list_ports")
    except ModuleNotFoundError as exc:
        raise Msp430MonitorError("pyserial is unavailable") from exc
    return any(
        str(info.device).casefold() == port.casefold() for info in list_ports_module.comports()
    )


__all__ = [
    "MSP430_EXPECTED_INTERVAL_SECONDS",
    "MSP430_UART_BAUD_RATE",
    "MSP430_UART_MAX_LINE_BYTES",
    "MSP430_UART_PROTOCOL",
    "Msp430MonitorError",
    "Msp430ProtocolError",
    "Msp430SerialMonitor",
    "Msp430TelemetryFrame",
    "crc16_ccitt_false",
    "parse_msp430_uart_v1_line",
]
