from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from forgegate.domain.models import SLUG_PATTERN, StrictModel

PRESET_ID_PATTERN = r"^[a-z][a-z0-9-]{0,63}$"
RUN_ID_PATTERN = r"^[0-9a-f]{32}$"


class MonitorPreset(StrictModel):
    preset_id: str = Field(pattern=PRESET_ID_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    adapter: Literal["msp430.uart.v1", "forgegate.simulated-demo.v1"]
    port: str | None = Field(default=None, pattern=r"^COM[1-9][0-9]{0,3}$")
    stale_after_seconds: float = Field(default=3.0, ge=1.5, le=60, strict=True)

    @model_validator(mode="after")
    def validate_adapter_configuration(self) -> Self:
        if self.adapter == "msp430.uart.v1" and self.port is None:
            raise ValueError("MSP430 presets require an explicit COM port")
        if self.adapter == "forgegate.simulated-demo.v1" and self.port is not None:
            raise ValueError("simulated presets cannot select a serial port")
        return self


class MonitorPresetCatalog(StrictModel):
    schema_version: Literal["forgegate.monitor-presets.v1"] = "forgegate.monitor-presets.v1"
    project_id: str = Field(pattern=SLUG_PATTERN)
    presets: tuple[MonitorPreset, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def require_unique_ids(self) -> Self:
        if len({preset.preset_id for preset in self.presets}) != len(self.presets):
            raise ValueError("monitor preset IDs must be unique")
        return self


class MonitorSessionView(StrictModel):
    state: Literal["STOPPED", "RUNNING", "ERROR", "STOPPING"]
    revision: int = Field(ge=0, strict=True)
    run_id: str | None = Field(default=None, pattern=RUN_ID_PATTERN)
    active_preset_id: str | None = Field(default=None, pattern=PRESET_ID_PATTERN)
    detail_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    detail_message: str = Field(min_length=1, max_length=240)


class MonitorControlView(StrictModel):
    schema_version: Literal["forgegate.monitor-control.v1"] = "forgegate.monitor-control.v1"
    project_id: str = Field(pattern=SLUG_PATTERN)
    presets: tuple[MonitorPreset, ...] = Field(min_length=1, max_length=20)
    session: MonitorSessionView


class MonitorStartRequest(StrictModel):
    preset_id: str = Field(pattern=PRESET_ID_PATTERN)
    expected_revision: int = Field(ge=0, strict=True)


class MonitorStopRequest(StrictModel):
    run_id: str = Field(pattern=RUN_ID_PATTERN)


__all__ = [
    "MonitorControlView",
    "MonitorPreset",
    "MonitorPresetCatalog",
    "MonitorSessionView",
    "MonitorStartRequest",
    "MonitorStopRequest",
]
