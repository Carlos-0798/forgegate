from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from forgegate.candidates.models import FINGERPRINT_PATTERN
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.models import SLUG_PATTERN, ProjectConfig, StrictModel


class RegisteredProject(StrictModel):
    """Immutable first-version registration of one ForgeGate project profile."""

    schema_version: Literal["forgegate.registered-project.v1"] = "forgegate.registered-project.v1"
    registration_id: str = Field(pattern=FINGERPRINT_PATTERN)
    project_id: str = Field(pattern=SLUG_PATTERN)
    profile_version: Literal[1] = 1
    config: ProjectConfig
    config_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    registered_at: datetime

    @field_serializer("config")
    def serialize_config(self, value: ProjectConfig) -> dict[str, object]:
        return value.model_dump(mode="json", by_alias=True)

    @field_validator("registered_at")
    @classmethod
    def registered_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("registered_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def registration_must_match_config(self) -> RegisteredProject:
        if self.project_id != self.config.project.id:
            raise ValueError("project_id must match the registered project config")
        expected_config_fingerprint = sha256_fingerprint(self.config.model_dump(mode="json"))
        if self.config_fingerprint != expected_config_fingerprint:
            raise ValueError("config_fingerprint does not match the project config")
        identity = self.model_dump(
            mode="json",
            exclude={"schema_version", "registration_id"},
        )
        if self.registration_id != sha256_fingerprint(identity):
            raise ValueError("registration_id does not match registration content")
        return self


class RegisteredProjectPage(StrictModel):
    """Bounded lexicographic page of immutable registered projects."""

    schema_version: Literal["forgegate.registered-project-page.v1"] = (
        "forgegate.registered-project-page.v1"
    )
    projects: tuple[RegisteredProject, ...] = Field(max_length=200)
    next_after_project_id: str | None = Field(default=None, pattern=SLUG_PATTERN)
    has_more: bool

    @model_validator(mode="after")
    def cursor_must_match_ordered_projects(self) -> RegisteredProjectPage:
        project_ids = [project.project_id for project in self.projects]
        if project_ids != sorted(set(project_ids)):
            raise ValueError("registered projects must have unique increasing project IDs")
        expected_cursor = project_ids[-1] if project_ids else None
        if self.next_after_project_id != expected_cursor:
            raise ValueError("next_after_project_id must identify the final returned project")
        if not project_ids and self.has_more:
            raise ValueError("an empty project page cannot report more results")
        return self


def create_registered_project(
    config: ProjectConfig,
    *,
    registered_at: datetime,
) -> RegisteredProject:
    if registered_at.tzinfo is None or registered_at.utcoffset() is None:
        raise ValueError("registered_at must include a UTC offset")
    timestamp = registered_at.astimezone(UTC)
    config_fingerprint = sha256_fingerprint(config.model_dump(mode="json"))
    values = {
        "project_id": config.project.id,
        "profile_version": 1,
        "config": config.model_dump(mode="json", by_alias=True),
        "config_fingerprint": config_fingerprint,
        "registered_at": timestamp.isoformat().replace("+00:00", "Z"),
    }
    return RegisteredProject(
        registration_id=sha256_fingerprint(values),
        project_id=config.project.id,
        config=config,
        config_fingerprint=config_fingerprint,
        registered_at=timestamp,
    )
