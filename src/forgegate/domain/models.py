from __future__ import annotations

import math
import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from forgegate.domain.enums import (
    Aggregation,
    CollectorType,
    Decision,
    EvidenceTrust,
    Operator,
    VerificationLevel,
)

SLUG_PATTERN = r"^[a-z][a-z0-9-]{1,62}$"
RULE_ID_PATTERN = r"^[a-z][a-z0-9._-]{1,127}$"
EVIDENCE_KIND_PATTERN = r"^[a-z][a-z0-9_-]*(\.[a-z0-9_-]+)+$"
COMMIT_PATTERN = r"^[0-9a-fA-F]{7,64}$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
TRACK_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ProjectIdentity(StrictModel):
    id: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    repository: str | None = Field(default=None, max_length=2048)
    default_branch: str = Field(default="main", min_length=1, max_length=255)


class ReleaseTrack(StrictModel):
    policy: str = Field(min_length=1, max_length=512)

    @field_validator("policy")
    @classmethod
    def policy_must_be_relative(cls, value: str) -> str:
        return _relative_path(value, "policy")


class CollectorConfig(StrictModel):
    type: CollectorType
    path: str = Field(min_length=1, max_length=512)
    optional: bool = False

    @field_validator("path")
    @classmethod
    def path_must_be_relative(cls, value: str) -> str:
        return _relative_path(value, "collector path")


class OutputConfig(StrictModel):
    json_output: str = Field(alias="json", min_length=1, max_length=512)
    markdown_output: str = Field(alias="markdown", min_length=1, max_length=512)

    @field_validator("json_output", "markdown_output")
    @classmethod
    def output_must_be_relative(cls, value: str) -> str:
        return _relative_path(value, "output path")


class ProjectConfig(StrictModel):
    schema_version: Literal["forgegate.project.v1"]
    project: ProjectIdentity
    release_tracks: dict[str, ReleaseTrack] = Field(min_length=1)
    collectors: list[CollectorConfig] = Field(min_length=1)
    outputs: OutputConfig

    @field_validator("release_tracks")
    @classmethod
    def validate_track_names(cls, value: dict[str, ReleaseTrack]) -> dict[str, ReleaseTrack]:
        invalid = sorted(name for name in value if not TRACK_PATTERN.fullmatch(name))
        if invalid:
            raise ValueError(f"invalid release track name(s): {', '.join(invalid)}")
        return value


class PolicyRule(StrictModel):
    id: str = Field(pattern=RULE_ID_PATTERN)
    claim: str = Field(pattern=EVIDENCE_KIND_PATTERN)
    evidence_kind: str = Field(pattern=EVIDENCE_KIND_PATTERN)
    aggregation: Aggregation = Aggregation.VALUE
    operator: Operator
    expected: Any
    where: dict[str, Any] = Field(default_factory=dict)
    mandatory: bool = True
    require_presence: bool = True
    on_missing: Decision = Decision.REVIEW
    minimum_trust: EvidenceTrust = EvidenceTrust.UNSIGNED_LOCAL
    minimum_verification: VerificationLevel = VerificationLevel.DECLARED
    maximum_age_seconds: int | None = Field(default=None, ge=0, le=315_576_000)

    @field_validator("expected", "where")
    @classmethod
    def expression_values_must_be_json_compatible(cls, value: Any) -> Any:
        return ensure_json_compatible(value)

    @model_validator(mode="after")
    def mandatory_rules_fail_closed(self) -> PolicyRule:
        if self.mandatory and not self.require_presence:
            raise ValueError("mandatory rules must require evidence presence")
        if self.on_missing is Decision.PASS:
            raise ValueError("missing evidence cannot produce PASS")
        return self


class PolicyConfig(StrictModel):
    schema_version: Literal["forgegate.policy.v1"]
    name: str = Field(pattern=SLUG_PATTERN)
    rules: list[PolicyRule] = Field(min_length=1)

    @field_validator("rules")
    @classmethod
    def unique_rule_ids(cls, value: list[PolicyRule]) -> list[PolicyRule]:
        ids = [rule.id for rule in value]
        if len(ids) != len(set(ids)):
            raise ValueError("policy rule IDs must be unique")
        return value


class ArtifactReference(StrictModel):
    path_or_uri: str = Field(min_length=1, max_length=2048)
    media_type: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=SHA256_PATTERN)
    size_bytes: int = Field(ge=0)


class ExecutionContext(StrictModel):
    commit_sha: str = Field(pattern=COMMIT_PATTERN)
    operating_system: str | None = Field(default=None, max_length=120)
    architecture: str | None = Field(default=None, max_length=120)
    runtime: str | None = Field(default=None, max_length=255)
    ci_provider: str | None = Field(default=None, max_length=120)
    ci_run_id: str | None = Field(default=None, max_length=255)
    tags: dict[str, str] = Field(default_factory=dict)


class EvidenceRecord(StrictModel):
    evidence_id: str = Field(pattern=RULE_ID_PATTERN)
    kind: str = Field(pattern=EVIDENCE_KIND_PATTERN)
    scope: str = Field(min_length=1, max_length=255)
    value: Any
    unit: str | None = Field(default=None, max_length=64)
    status: str = Field(min_length=1, max_length=64)
    source_tool: str = Field(min_length=1, max_length=120)
    source_version: str = Field(min_length=1, max_length=120)
    execution_context: ExecutionContext
    artifact: ArtifactReference
    collected_at: datetime
    trust: EvidenceTrust
    verification_level: VerificationLevel
    tags: dict[str, str] = Field(default_factory=dict)

    @field_validator("value")
    @classmethod
    def value_must_be_json_compatible(cls, value: Any) -> Any:
        return ensure_json_compatible(value)

    @field_validator("collected_at")
    @classmethod
    def timestamp_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collected_at must include a UTC offset")
        return value


class EvidenceBundle(StrictModel):
    schema_version: Literal["forgegate.evidence-bundle.v1"]
    producer: str = Field(min_length=1, max_length=120)
    producer_version: str = Field(min_length=1, max_length=120)
    candidate_commit: str = Field(pattern=COMMIT_PATTERN)
    generated_at: datetime
    evidence: list[EvidenceRecord] = Field(min_length=1)

    @field_validator("generated_at")
    @classmethod
    def generated_timestamp_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def evidence_matches_candidate(self) -> EvidenceBundle:
        ids = [record.evidence_id for record in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence IDs must be unique within a bundle")
        mismatches = [
            record.evidence_id
            for record in self.evidence
            if record.execution_context.commit_sha.lower() != self.candidate_commit.lower()
        ]
        if mismatches:
            raise ValueError(
                "evidence commit does not match candidate for: " + ", ".join(mismatches)
            )
        return self


def _relative_path(value: str, field_name: str) -> str:
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise ValueError(f"{field_name} must be relative")
    if any(part == ".." for part in normalized.split("/")):
        raise ValueError(f"{field_name} cannot contain parent traversal")
    return value


def ensure_json_compatible(value: Any) -> Any:
    """Reject values that cannot participate in canonical JSON identity."""
    try:
        _check_json_value(value, set())
    except RecursionError as exc:
        raise ValueError("value exceeds supported JSON nesting depth") from exc
    return value


def _check_json_value(value: Any, active_containers: set[int]) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("floating-point JSON values must be finite")
        return
    if isinstance(value, (dict, list)):
        identity = id(value)
        if identity in active_containers:
            raise ValueError("cyclic JSON values are not supported")
        active_containers.add(identity)
        children: Iterable[Any]
        if isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("JSON object keys must be strings")
            children = value.values()
        else:
            children = value
        for child in children:
            _check_json_value(child, active_containers)
        active_containers.remove(identity)
        return
    raise ValueError(f"value is not JSON-compatible: {type(value).__name__}")
