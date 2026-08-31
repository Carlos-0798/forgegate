from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from forgegate.candidates.models import CANDIDATE_ID_PATTERN, FINGERPRINT_PATTERN
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.models import SLUG_PATTERN, StrictModel


class AuditEventType(StrEnum):
    PROJECT_REGISTERED = "project.registered"
    CANDIDATE_CREATED = "candidate.created"
    CANDIDATE_TRANSITIONED = "candidate.transitioned"
    EVIDENCE_BOUND = "candidate.evidence-bound"
    EVALUATION_RECORDED = "candidate.evaluation-recorded"
    ATTESTATION_RECORDED = "candidate.attestation-recorded"


class AuditEvent(StrictModel):
    schema_version: Literal["forgegate.audit-event.v1"] = "forgegate.audit-event.v1"
    event_id: str = Field(pattern=FINGERPRINT_PATTERN)
    sequence: int = Field(ge=1)
    event_type: AuditEventType
    occurred_at: datetime
    project_id: str = Field(pattern=SLUG_PATTERN)
    candidate_id: str | None = Field(default=None, pattern=CANDIDATE_ID_PATTERN)
    subject_schema_version: str = Field(min_length=1, max_length=120)
    subject_id: str = Field(min_length=1, max_length=255)
    subject_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def identity_must_match_content(self) -> AuditEvent:
        if self.event_type is AuditEventType.PROJECT_REGISTERED:
            if self.candidate_id is not None:
                raise ValueError("project registration events cannot reference a candidate")
        elif self.candidate_id is None:
            raise ValueError("candidate audit events require candidate_id")
        identity = _audit_identity(
            event_type=self.event_type,
            occurred_at=self.occurred_at,
            project_id=self.project_id,
            candidate_id=self.candidate_id,
            subject_schema_version=self.subject_schema_version,
            subject_id=self.subject_id,
            subject_fingerprint=self.subject_fingerprint,
        )
        if self.event_id != sha256_fingerprint(identity):
            raise ValueError("event_id does not match audit-event content")
        return self


class AuditEventPage(StrictModel):
    schema_version: Literal["forgegate.audit-event-page.v1"] = "forgegate.audit-event-page.v1"
    events: tuple[AuditEvent, ...]
    next_after_sequence: int | None = Field(default=None, ge=1)
    has_more: bool

    @model_validator(mode="after")
    def cursor_must_match_events(self) -> AuditEventPage:
        sequences = [event.sequence for event in self.events]
        if sequences != sorted(set(sequences)):
            raise ValueError("audit events must have unique increasing sequences")
        expected_cursor = sequences[-1] if sequences else None
        if self.next_after_sequence != expected_cursor:
            raise ValueError("next_after_sequence must identify the last returned event")
        if not self.events and self.has_more:
            raise ValueError("an empty audit page cannot claim more events")
        return self


def create_audit_event(
    *,
    sequence: int,
    event_type: AuditEventType,
    occurred_at: datetime,
    project_id: str,
    candidate_id: str | None,
    subject_schema_version: str,
    subject_id: str,
    subject_fingerprint: str,
) -> AuditEvent:
    identity = _audit_identity(
        event_type=event_type,
        occurred_at=occurred_at,
        project_id=project_id,
        candidate_id=candidate_id,
        subject_schema_version=subject_schema_version,
        subject_id=subject_id,
        subject_fingerprint=subject_fingerprint,
    )
    return AuditEvent(
        event_id=sha256_fingerprint(identity),
        sequence=sequence,
        event_type=event_type,
        occurred_at=occurred_at,
        project_id=project_id,
        candidate_id=candidate_id,
        subject_schema_version=subject_schema_version,
        subject_id=subject_id,
        subject_fingerprint=subject_fingerprint,
    )


def _audit_identity(
    *,
    event_type: AuditEventType,
    occurred_at: datetime,
    project_id: str,
    candidate_id: str | None,
    subject_schema_version: str,
    subject_id: str,
    subject_fingerprint: str,
) -> dict[str, object]:
    return {
        "event_type": event_type.value,
        "occurred_at": occurred_at.isoformat().replace("+00:00", "Z"),
        "project_id": project_id,
        "candidate_id": candidate_id,
        "subject_schema_version": subject_schema_version,
        "subject_id": subject_id,
        "subject_fingerprint": subject_fingerprint,
    }
