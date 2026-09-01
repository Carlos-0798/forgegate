from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from forgegate.audit import AuditActor
from forgegate.candidates.models import FINGERPRINT_PATTERN
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.models import StrictModel

REQUEST_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$"
SESSION_ID_PATTERN = re.compile(r"^sess-[0-9a-f]{32}$")
FINGERPRINT_RE = re.compile(FINGERPRINT_PATTERN)


class ApiSecurityEventType(StrEnum):
    AUTHENTICATION_REJECTED = "authentication.rejected"
    AUTHENTICATION_RATE_LIMITED = "authentication.rate-limited"
    SESSION_LOGGED_OUT = "session.logged-out"
    SESSION_REVOKED = "session.revoked"
    TRUST_STORE_RELOADED = "trust-store.reloaded"


class SecurityEventTargetType(StrEnum):
    SESSION = "session"
    TRUST_STORE = "trust_store"


class ApiSecurityEvent(StrictModel):
    """Minimal API-control event; intentionally separate from product-state audit."""

    schema_version: Literal["forgegate.api-security-event.v1"] = "forgegate.api-security-event.v1"
    event_id: str = Field(pattern=FINGERPRINT_PATTERN)
    sequence: int = Field(ge=1)
    event_type: ApiSecurityEventType
    occurred_at: datetime
    request_id: str = Field(pattern=REQUEST_ID_PATTERN)
    outcome_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,127}$")
    actor: AuditActor | None = None
    target_type: SecurityEventTargetType | None = None
    target_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def content_must_be_safe_and_self_identifying(self) -> ApiSecurityEvent:
        control_events = {
            ApiSecurityEventType.SESSION_LOGGED_OUT,
            ApiSecurityEventType.SESSION_REVOKED,
            ApiSecurityEventType.TRUST_STORE_RELOADED,
        }
        if self.event_type in control_events and self.actor is None:
            raise ValueError("successful security-control events require an actor")
        if (self.target_type is None) != (self.target_id is None):
            raise ValueError("security-event target type and ID must be present together")
        if self.target_type is SecurityEventTargetType.SESSION and (
            self.target_id is None or SESSION_ID_PATTERN.fullmatch(self.target_id) is None
        ):
            raise ValueError("session targets require a canonical session ID")
        if self.target_type is SecurityEventTargetType.TRUST_STORE and (
            self.target_id is None or FINGERPRINT_RE.fullmatch(self.target_id) is None
        ):
            raise ValueError("trust-store targets require a SHA-256 fingerprint")
        if (
            self.event_type
            in {
                ApiSecurityEventType.SESSION_LOGGED_OUT,
                ApiSecurityEventType.SESSION_REVOKED,
            }
            and self.target_type is not SecurityEventTargetType.SESSION
        ):
            raise ValueError("session-control events require a session target")
        if (
            self.event_type is ApiSecurityEventType.TRUST_STORE_RELOADED
            and self.target_type is not SecurityEventTargetType.TRUST_STORE
        ):
            raise ValueError("trust-store reload events require a trust-store target")
        if (
            self.event_type
            in {
                ApiSecurityEventType.AUTHENTICATION_REJECTED,
                ApiSecurityEventType.AUTHENTICATION_RATE_LIMITED,
            }
            and self.target_type is not None
        ):
            raise ValueError("authentication rejection events cannot retain a target")
        if self.event_id != sha256_fingerprint(_event_identity(self)):
            raise ValueError("event_id does not match API security-event content")
        return self


class ApiSecurityEventPage(StrictModel):
    schema_version: Literal["forgegate.api-security-event-page.v1"] = (
        "forgegate.api-security-event-page.v1"
    )
    events: tuple[ApiSecurityEvent, ...]
    next_after_sequence: int | None = Field(default=None, ge=1)
    has_more: bool
    capacity: int = Field(ge=1)
    recorded_count: int = Field(ge=0)
    saturated: bool

    @model_validator(mode="after")
    def cursor_and_capacity_must_match(self) -> ApiSecurityEventPage:
        sequences = [event.sequence for event in self.events]
        if sequences != sorted(set(sequences)):
            raise ValueError("API security events must have unique increasing sequences")
        if self.next_after_sequence != (sequences[-1] if sequences else None):
            raise ValueError("next_after_sequence must identify the last returned event")
        if not self.events and self.has_more:
            raise ValueError("an empty security-event page cannot claim more events")
        if self.recorded_count > self.capacity:
            raise ValueError("recorded_count cannot exceed security-event capacity")
        if self.saturated != (self.recorded_count >= self.capacity):
            raise ValueError("saturated must reflect security-event capacity")
        return self


def create_api_security_event(
    *,
    sequence: int,
    event_type: ApiSecurityEventType,
    occurred_at: datetime,
    request_id: str,
    outcome_code: str,
    actor: AuditActor | None = None,
    target_type: SecurityEventTargetType | None = None,
    target_id: str | None = None,
) -> ApiSecurityEvent:
    provisional = ApiSecurityEvent.model_construct(
        event_id="sha256:" + "0" * 64,
        sequence=sequence,
        event_type=event_type,
        occurred_at=occurred_at,
        request_id=request_id,
        outcome_code=outcome_code,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
    )
    return ApiSecurityEvent(
        event_id=sha256_fingerprint(_event_identity(provisional)),
        sequence=sequence,
        event_type=event_type,
        occurred_at=occurred_at,
        request_id=request_id,
        outcome_code=outcome_code,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
    )


def _event_identity(event: ApiSecurityEvent) -> dict[str, object]:
    identity: dict[str, object] = {
        "event_type": event.event_type.value,
        "occurred_at": event.occurred_at.isoformat().replace("+00:00", "Z"),
        "request_id": event.request_id,
        "outcome_code": event.outcome_code,
        "target_type": event.target_type.value if event.target_type is not None else None,
        "target_id": event.target_id,
    }
    if event.actor is not None:
        identity["actor"] = event.actor.model_dump(mode="json")
    return identity
