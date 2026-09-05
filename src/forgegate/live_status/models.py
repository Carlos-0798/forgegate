from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from forgegate.domain.models import StrictModel


class LiveSourceStatus(StrictModel):
    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    source_type: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]{0,63}$")
    display_name: str = Field(min_length=1, max_length=120)
    access_mode: Literal["READ_ONLY"] = "READ_ONLY"
    connection: Literal["CONNECTING", "CONNECTED", "DISCONNECTED", "ERROR"]
    heartbeat: Literal["NOT_OBSERVED", "NORMAL", "STALE", "INVALID"]
    device_health: Literal["UNKNOWN", "NORMAL", "WARNING", "FAULT"]
    detail_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    detail_message: str = Field(min_length=1, max_length=240)
    endpoint: str = Field(min_length=1, max_length=120)
    protocol: str = Field(min_length=1, max_length=120)
    baud_rate: int = Field(ge=1, le=10_000_000)
    expected_interval_seconds: float = Field(gt=0, le=3600)
    stale_after_seconds: float = Field(gt=0, le=3600)
    observed_at: datetime
    last_heartbeat_at: datetime | None = None
    heartbeat_age_seconds: float | None = Field(default=None, ge=0)
    sequence: int | None = Field(default=None, ge=0, le=4_294_967_295)
    uptime_ms: int | None = Field(default=None, ge=0, le=4_294_967_295)
    device_state: str | None = Field(default=None, max_length=32)
    fault_flags: str | None = Field(default=None, pattern=r"^[0-9A-F]{4}$")
    frames_received: int = Field(ge=0)
    protocol_errors: int = Field(ge=0)
    sequence_gaps: int = Field(ge=0)
    reconnects: int = Field(ge=0)
    evidence_boundary: Literal["LIVE_STATUS_ONLY_NOT_RELEASE_EVIDENCE"] = (
        "LIVE_STATUS_ONLY_NOT_RELEASE_EVIDENCE"
    )
    hardware_control: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"


class LiveStatusPage(StrictModel):
    schema_version: Literal["forgegate.live-status.v1"] = "forgegate.live-status.v1"
    observed_at: datetime
    refresh_after_seconds: int = Field(default=1, ge=1, le=30)
    sources: tuple[LiveSourceStatus, ...] = Field(max_length=20)


__all__ = ["LiveSourceStatus", "LiveStatusPage"]
