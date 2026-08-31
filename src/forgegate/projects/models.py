from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, field_serializer, field_validator, model_validator

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


class ProjectProfileRevision(StrictModel):
    """Append-only replacement profile linked to the preceding profile identity."""

    schema_version: Literal["forgegate.project-profile-revision.v1"] = (
        "forgegate.project-profile-revision.v1"
    )
    revision_id: str = Field(pattern=FINGERPRINT_PATTERN)
    project_id: str = Field(pattern=SLUG_PATTERN)
    profile_version: int = Field(ge=2)
    previous_profile_id: str = Field(pattern=FINGERPRINT_PATTERN)
    config: ProjectConfig
    config_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    effective_at: datetime

    @field_serializer("config")
    def serialize_config(self, value: ProjectConfig) -> dict[str, object]:
        return value.model_dump(mode="json", by_alias=True)

    @field_validator("effective_at")
    @classmethod
    def effective_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("effective_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def revision_must_match_config(self) -> ProjectProfileRevision:
        if self.project_id != self.config.project.id:
            raise ValueError("project_id must match the revised project config")
        expected_config_fingerprint = sha256_fingerprint(self.config.model_dump(mode="json"))
        if self.config_fingerprint != expected_config_fingerprint:
            raise ValueError("config_fingerprint does not match the revised project config")
        identity = self.model_dump(mode="json", exclude={"schema_version", "revision_id"})
        if self.revision_id != sha256_fingerprint(identity):
            raise ValueError("revision_id does not match revision content")
        return self


type ProjectProfileDocument = Annotated[
    RegisteredProject | ProjectProfileRevision,
    Field(discriminator="schema_version"),
]
PROJECT_PROFILE_ADAPTER: TypeAdapter[ProjectProfileDocument] = TypeAdapter(ProjectProfileDocument)


class ProjectProfilePage(StrictModel):
    """Bounded version-ordered history for one project's immutable profiles."""

    schema_version: Literal["forgegate.project-profile-page.v1"] = (
        "forgegate.project-profile-page.v1"
    )
    project_id: str = Field(pattern=SLUG_PATTERN)
    profiles: tuple[ProjectProfileDocument, ...] = Field(max_length=200)
    next_after_profile_version: int | None = Field(default=None, ge=1)
    has_more: bool

    @model_validator(mode="after")
    def cursor_scope_and_order_must_match(self) -> ProjectProfilePage:
        versions = [profile.profile_version for profile in self.profiles]
        if versions != sorted(set(versions)):
            raise ValueError("project profiles must have unique increasing versions")
        if any(profile.project_id != self.project_id for profile in self.profiles):
            raise ValueError("profile page contains a profile from another project")
        expected_cursor = versions[-1] if versions else None
        if self.next_after_profile_version != expected_cursor:
            raise ValueError("next_after_profile_version must identify the final profile")
        if not versions and self.has_more:
            raise ValueError("an empty profile page cannot report more results")
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


def create_project_profile_revision(
    config: ProjectConfig,
    *,
    profile_version: int,
    previous_profile_id: str,
    effective_at: datetime,
) -> ProjectProfileRevision:
    if profile_version < 2:
        raise ValueError("project profile revision version must be at least two")
    if effective_at.tzinfo is None or effective_at.utcoffset() is None:
        raise ValueError("effective_at must include a UTC offset")
    timestamp = effective_at.astimezone(UTC)
    config_fingerprint = sha256_fingerprint(config.model_dump(mode="json"))
    values = {
        "project_id": config.project.id,
        "profile_version": profile_version,
        "previous_profile_id": previous_profile_id,
        "config": config.model_dump(mode="json", by_alias=True),
        "config_fingerprint": config_fingerprint,
        "effective_at": timestamp.isoformat().replace("+00:00", "Z"),
    }
    return ProjectProfileRevision(
        revision_id=sha256_fingerprint(values),
        project_id=config.project.id,
        profile_version=profile_version,
        previous_profile_id=previous_profile_id,
        config=config,
        config_fingerprint=config_fingerprint,
        effective_at=timestamp,
    )


def profile_id(profile: ProjectProfileDocument) -> str:
    if isinstance(profile, ProjectProfileRevision):
        return profile.revision_id
    return profile.registration_id


def profile_effective_at(profile: ProjectProfileDocument) -> datetime:
    if isinstance(profile, ProjectProfileRevision):
        return profile.effective_at
    return profile.registered_at
