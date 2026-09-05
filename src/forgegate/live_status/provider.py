from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Protocol

from forgegate.live_status.models import LiveStatusPage


class LiveStatusProvider(Protocol):
    @property
    def hardware_access(self) -> Literal["NOT_PERFORMED", "READ_ONLY_TELEMETRY"]: ...

    def snapshot(self) -> LiveStatusPage: ...


class DisabledLiveStatusProvider:
    @property
    def hardware_access(self) -> Literal["NOT_PERFORMED"]:
        return "NOT_PERFORMED"

    def snapshot(self) -> LiveStatusPage:
        return LiveStatusPage(observed_at=datetime.now(UTC), sources=())


__all__ = ["DisabledLiveStatusProvider", "LiveStatusProvider"]
