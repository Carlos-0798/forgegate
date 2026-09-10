from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from forgegate.compatibility import msp430_live
from forgegate.compatibility.msp430_live import (
    MSP430_UART_MAX_LINE_BYTES,
    Msp430ProtocolError,
    Msp430SerialMonitor,
    crc16_ccitt_false,
    parse_msp430_uart_v1_line,
)


class _Clock:
    def __init__(self) -> None:
        self.monotonic_value = 100.0
        self.utc_value = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.monotonic_value

    def utc_now(self) -> datetime:
        return self.utc_value

    def advance(self, seconds: float) -> None:
        self.monotonic_value += seconds
        self.utc_value += timedelta(seconds=seconds)


def _tel_line(
    sequence: int = 1,
    *,
    uptime_ms: int = 1000,
    state: str = "FAULT",
    fault_flags: str = "0015",
) -> bytes:
    payload = (f"TEL,{sequence},{uptime_ms},-32768,-32768,0,0,0,0,{state},{fault_flags}").encode(
        "ascii"
    )
    return payload + f",{crc16_ccitt_false(payload):04X}\n".encode("ascii")


def test_crc_and_uart_v1_parser_accept_exact_valid_frame_and_ignores_legacy() -> None:
    assert crc16_ccitt_false(b"123456789") == 0x29B1
    parsed = parse_msp430_uart_v1_line(_tel_line())

    assert parsed is not None
    assert parsed.sequence == 1
    assert parsed.uptime_ms == 1000
    assert parsed.temp_ds_dC == parsed.temp_ntc_dC == -32768
    assert parsed.state == "FAULT"
    assert parsed.fault_flags == "0015"
    assert parse_msp430_uart_v1_line(b"HB,1\r\n") is None
    assert parse_msp430_uart_v1_line(b"READY\n") is None


@pytest.mark.parametrize(
    ("line", "code"),
    [
        (_tel_line()[:-1], "UART_FRAME_INCOMPLETE"),
        (_tel_line()[:-5] + b"0000\n", "UART_TEL_CRC_MISMATCH"),
        (b"TEL," + b"0" * MSP430_UART_MAX_LINE_BYTES + b"\n", "UART_FRAME_TOO_LONG"),
        (b"TEL,1,2,3\n", "UART_TEL_FIELD_COUNT"),
        (b"TEL,\xff\n", "UART_FRAME_NON_ASCII"),
    ],
)
def test_uart_v1_parser_rejects_malformed_frames(line: bytes, code: str) -> None:
    with pytest.raises(Msp430ProtocolError, match=code):
        parse_msp430_uart_v1_line(line)


def test_uart_v1_parser_rejects_valid_crc_but_invalid_ranges() -> None:
    payload = b"TEL,1,1000,-32768,-32768,0,0,0,1001,NORMAL,0000"
    line = payload + f",{crc16_ccitt_false(payload):04X}\n".encode("ascii")
    with pytest.raises(Msp430ProtocolError, match="UART_TEL_PWM_RANGE"):
        parse_msp430_uart_v1_line(line)


def test_uart_v1_parser_additional_format_and_state_boundaries() -> None:
    assert parse_msp430_uart_v1_line(b"") is None
    assert parse_msp430_uart_v1_line(_tel_line()[:-1] + b"\r\n") is not None

    with pytest.raises(Msp430ProtocolError, match="UART_TEL_CRC_FORMAT"):
        parse_msp430_uart_v1_line(_tel_line()[:-5] + b"ZZZZ\n")

    for payload, code in [
        (b"TEL,1,1000,-32768,-32768,0,0,0,0,BROKEN,0015", "UART_TEL_STATE"),
        (b"TEL,1,1000,-32768,-32768,0,0,0,0,NORMAL,XYZ1", "UART_TEL_FAULT_FORMAT"),
        (b"TEL,-1,1000,-32768,-32768,0,0,0,0,NORMAL,0000", "UART_TEL_SEQUENCE_FORMAT"),
    ]:
        line = payload + f",{crc16_ccitt_false(payload):04X}\n".encode("ascii")
        with pytest.raises(Msp430ProtocolError, match=code):
            parse_msp430_uart_v1_line(line)


def test_monitor_separates_connection_heartbeat_staleness_and_device_fault() -> None:
    clock = _Clock()
    monitor = Msp430SerialMonitor(
        "COM4",
        monotonic=clock.monotonic,
        utc_now=clock.utc_now,
        port_present=lambda _port: False,
    )
    monitor._set_connection("CONNECTED", "SERIAL_CONNECTED", "Connected for test.")
    monitor._process_line(_tel_line())

    current = monitor.snapshot().sources[0]
    assert current.connection == "CONNECTED"
    assert current.heartbeat == "NORMAL"
    assert current.device_health == "FAULT"
    assert current.device_state == "FAULT"
    assert current.fault_flags == "0015"
    assert [(issue.code, issue.mask) for issue in current.reported_issues] == [
        ("DS18B20_MISSING", "0x0001"),
        ("NTC_RANGE", "0x0004"),
        ("INA219_COMM", "0x0010"),
    ]
    assert current.frames_received == 1
    assert current.hardware_control == "NOT_PERFORMED"
    assert current.evidence_boundary == "LIVE_STATUS_ONLY_NOT_RELEASE_EVIDENCE"

    clock.advance(3.001)
    stale = monitor.snapshot().sources[0]
    assert stale.connection == "CONNECTED"
    assert stale.heartbeat == "STALE"
    assert stale.device_health == "FAULT"
    assert stale.detail_code == "TELEMETRY_STALE"


def test_monitor_counts_protocol_errors_and_sequence_gaps_then_recovers() -> None:
    clock = _Clock()
    monitor = Msp430SerialMonitor(
        "COM4",
        monotonic=clock.monotonic,
        utc_now=clock.utc_now,
        port_present=lambda _port: False,
    )
    monitor._process_line(_tel_line(sequence=10))
    monitor._process_line(_tel_line(sequence=10)[:-5] + b"0000\n")
    invalid = monitor.snapshot().sources[0]
    assert invalid.heartbeat == "INVALID"
    assert invalid.protocol_errors == 1

    clock.advance(1)
    monitor._process_line(
        _tel_line(sequence=13, uptime_ms=2000, state="NORMAL", fault_flags="0000")
    )
    recovered = monitor.snapshot().sources[0]
    assert recovered.heartbeat == "NORMAL"
    assert recovered.device_health == "NORMAL"
    assert recovered.reported_issues == ()
    assert recovered.frames_received == 2
    assert recovered.protocol_errors == 1
    assert recovered.sequence_gaps == 2

    clock.advance(1)
    monitor._process_line(_tel_line(sequence=1, uptime_ms=3000, state="WARNING"))
    warning = monitor.snapshot().sources[0]
    assert warning.device_health == "WARNING"
    assert warning.sequence_gaps == 3

    clock.advance(1)
    monitor._process_line(_tel_line(sequence=2, uptime_ms=4000, state="INIT"))
    assert monitor.snapshot().sources[0].device_health == "UNKNOWN"


def test_monitor_retains_unknown_fault_bits_without_inventing_meaning() -> None:
    monitor = Msp430SerialMonitor("COM4", port_present=lambda _port: False)
    monitor._process_line(_tel_line(fault_flags="9000"))

    issue = monitor.snapshot().sources[0].reported_issues[0]
    assert issue.code == "UNKNOWN_FAULT_BITS"
    assert issue.mask == "0x9000"


def test_monitor_validates_configuration() -> None:
    stopped = Msp430SerialMonitor("COM4", port_present=lambda _port: False)
    stopped.stop()
    assert stopped.snapshot().sources[0].detail_code == "MONITOR_STOPPED"
    with pytest.raises(ValueError, match="serial port"):
        Msp430SerialMonitor(" ")
    with pytest.raises(ValueError, match="stale threshold"):
        Msp430SerialMonitor("COM4", stale_after_seconds=1)
    with pytest.raises(ValueError, match="reconnect interval"):
        Msp430SerialMonitor("COM4", reconnect_after_seconds=31)


def test_monitor_thread_opens_reads_and_closes_without_a_write_surface() -> None:
    class ReadOnlyHandle:
        def __init__(self) -> None:
            self.port = "COM4"
            self.baudrate = 115200
            self.bytesize = 8
            self.parity = "N"
            self.stopbits = 1
            self.timeout = 0.25
            self.write_timeout = 0.0
            self.dtr = False
            self.rts = False
            self.is_open = False
            self.open_count = 0
            self.close_count = 0
            self.lines = [_tel_line(sequence=100)]

        def open(self) -> None:
            self.is_open = True
            self.open_count += 1

        def read_until(self, expected: bytes = b"\n", size: int | None = None) -> bytes:
            assert expected == b"\n"
            assert size == MSP430_UART_MAX_LINE_BYTES + 1
            if self.lines:
                return self.lines.pop(0)
            time.sleep(0.005)
            return b""

        def close(self) -> None:
            self.is_open = False
            self.close_count += 1

    handle = ReadOnlyHandle()
    monitor = Msp430SerialMonitor(
        "COM4",
        reconnect_after_seconds=0.05,
        serial_factory=lambda _port: handle,
        port_present=lambda _port: True,
    )
    monitor.start()
    monitor.start()
    deadline = time.monotonic() + 1
    while monitor.snapshot().sources[0].frames_received < 1 and time.monotonic() < deadline:
        time.sleep(0.005)
    observed = monitor.snapshot().sources[0]
    monitor.stop()

    assert observed.connection == "CONNECTED"
    assert observed.heartbeat == "NORMAL"
    assert observed.frames_received == 1
    assert handle.open_count == handle.close_count == 1
    assert not hasattr(handle, "write")


def test_monitor_thread_reports_absent_endpoint_without_opening_serial() -> None:
    checked = threading.Event()
    factory_called = False

    def absent(_port: str) -> bool:
        checked.set()
        return False

    def serial_factory(_port: str):
        nonlocal factory_called
        factory_called = True
        raise AssertionError("serial factory must not run for an absent endpoint")

    monitor = Msp430SerialMonitor(
        "COM255",
        reconnect_after_seconds=0.05,
        serial_factory=serial_factory,
        port_present=absent,
    )
    monitor.start()
    assert checked.wait(1)
    observed = monitor.snapshot().sources[0]
    monitor.stop()

    assert observed.connection == "DISCONNECTED"
    assert observed.heartbeat == "NOT_OBSERVED"
    assert observed.detail_code == "SERIAL_NOT_PRESENT"
    assert factory_called is False


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (msp430_live.Msp430MonitorError("missing"), "SERIAL_DEPENDENCY_UNAVAILABLE"),
        (OSError("unavailable"), "SERIAL_IO_ERROR"),
    ],
)
def test_monitor_thread_sanitizes_dependency_and_io_failures(
    error: Exception,
    expected_code: str,
) -> None:
    attempted = threading.Event()

    def fail(_port: str):
        attempted.set()
        raise error

    monitor = Msp430SerialMonitor(
        "COM4",
        reconnect_after_seconds=0.05,
        serial_factory=fail,
        port_present=lambda _port: True,
    )
    monitor.start()
    assert attempted.wait(1)
    deadline = time.monotonic() + 1
    observed = monitor.snapshot().sources[0]
    while observed.detail_code != expected_code and time.monotonic() < deadline:
        time.sleep(0.005)
        observed = monitor.snapshot().sources[0]
    monitor.stop()

    assert observed.connection == "ERROR"
    assert observed.detail_code == expected_code
    assert "unavailable" not in observed.detail_message


def test_default_serial_adapter_is_lazy_and_configures_read_only_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Handle:
        pass

    handle = Handle()
    serial_module = SimpleNamespace(Serial=lambda *, port: handle)
    ports_module = SimpleNamespace(
        comports=lambda: (SimpleNamespace(device="COM4"), SimpleNamespace(device="COM5"))
    )

    def import_module(name: str):
        return ports_module if name == "serial.tools.list_ports" else serial_module

    monkeypatch.setattr(msp430_live.importlib, "import_module", import_module)
    configured = msp430_live._default_serial_factory("COM4")

    assert configured is handle
    assert handle.port == "COM4"
    assert handle.baudrate == 115200
    assert handle.bytesize == 8
    assert handle.parity == "N"
    assert handle.stopbits == 1
    assert handle.timeout == 0.25
    assert handle.write_timeout == 0
    assert handle.dtr is handle.rts is False
    assert msp430_live._default_port_present("com4") is True
    assert msp430_live._default_port_present("COM9") is False


def test_default_serial_adapter_reports_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(_name: str):
        raise ModuleNotFoundError

    monkeypatch.setattr(msp430_live.importlib, "import_module", missing)
    with pytest.raises(msp430_live.Msp430MonitorError, match="pyserial"):
        msp430_live._default_serial_factory("COM4")
    with pytest.raises(msp430_live.Msp430MonitorError, match="pyserial"):
        msp430_live._default_port_present("COM4")


@pytest.mark.parametrize("stage", ["presence", "factory", "open", "read"])
def test_stop_timeout_retains_reader_and_blocks_replacement_until_exit(stage: str) -> None:
    entered = threading.Event()
    release = threading.Event()
    observed = {"factories": 0, "opens": 0, "closes": 0}

    def block_at(current: str) -> None:
        if stage == current:
            entered.set()
            assert release.wait(3), "test did not release simulated I/O"

    class BlockingHandle:
        is_open = False

        def open(self) -> None:
            block_at("open")
            self.is_open = True
            observed["opens"] += 1

        def read_until(self, expected: bytes = b"\n", size: int | None = None) -> bytes:
            block_at("read")
            return _tel_line()

        def close(self) -> None:
            self.is_open = False
            observed["closes"] += 1

    handle = BlockingHandle()

    def present(_port: str) -> bool:
        block_at("presence")
        return True

    def factory(_port: str):
        observed["factories"] += 1
        block_at("factory")
        return handle

    monitor = Msp430SerialMonitor("COM4", serial_factory=factory, port_present=present)
    try:
        monitor.start()
        assert entered.wait(1)
        reader = monitor._thread
        with pytest.raises(msp430_live.Msp430MonitorError, match="MONITOR_STOP_TIMEOUT"):
            monitor.stop(timeout=0)
        assert monitor._thread is reader and reader is not None and reader.is_alive()
        with pytest.raises(msp430_live.Msp430MonitorError, match="MONITOR_STOP_INCOMPLETE"):
            monitor.start()
        assert monitor._thread is reader
        assert monitor.snapshot().sources[0].detail_code == "MONITOR_STOP_TIMEOUT"
    finally:
        release.set()
        monitor.stop(timeout=1)
    assert monitor._thread is None
    assert monitor.snapshot().sources[0].detail_code == "MONITOR_STOPPED"
    assert monitor.snapshot().sources[0].frames_received == 0
    assert observed["opens"] == observed["closes"] == int(stage in {"open", "read"})
    assert observed["factories"] == int(stage != "presence")


@pytest.mark.parametrize("invalid", [False, True])
def test_stopped_lifecycle_detail_is_not_hidden_by_old_heartbeat(invalid: bool) -> None:
    clock = _Clock()
    monitor = Msp430SerialMonitor("COM4", monotonic=clock.monotonic, utc_now=clock.utc_now)
    monitor._process_line(_tel_line())
    clock.advance(10)
    if invalid:
        monitor._process_line(b"TEL,invalid\n")
    monitor.stop()
    source = monitor.snapshot().sources[0]
    assert source.heartbeat == ("INVALID" if invalid else "STALE")
    assert source.detail_code == "MONITOR_STOPPED"
    assert source.connection == "DISCONNECTED"
    assert source.data_origin == "LIVE_TELEMETRY"


def test_thread_start_failure_leaves_safe_stoppable_monitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_thread: threading.Thread) -> None:
        raise RuntimeError("private runtime detail")

    monitor = Msp430SerialMonitor("COM4", port_present=lambda _: pytest.fail("must not enumerate"))
    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread, "start", fail)
        with pytest.raises(msp430_live.Msp430MonitorError, match="MONITOR_START_FAILED"):
            monitor.start()
    assert monitor._thread is None
    assert monitor.snapshot().sources[0].detail_code == "MONITOR_START_FAILED"
    assert "private" not in monitor.snapshot().sources[0].detail_message
    monitor.stop()


@pytest.mark.parametrize("timeout", [-1, float("nan"), float("inf")])
def test_monitor_stop_rejects_unbounded_or_negative_timeout(timeout: float) -> None:
    monitor = Msp430SerialMonitor("COM4")
    with pytest.raises(ValueError, match="stop timeout"):
        monitor.stop(timeout=timeout)
