from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from forgegate.domain.enums import Aggregation, Decision, Operator
from forgegate.domain.models import (
    COMMIT_PATTERN,
    EVIDENCE_KIND_PATTERN,
    RULE_ID_PATTERN,
    SLUG_PATTERN,
    StrictModel,
    ensure_json_compatible,
)


class RuleEvaluation(StrictModel):
    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    claim: str = Field(pattern=EVIDENCE_KIND_PATTERN)
    decision: Decision
    mandatory: bool
    evidence_kind: str = Field(pattern=EVIDENCE_KIND_PATTERN)
    aggregation: Aggregation
    operator: Operator
    expected: Any
    actual: Any
    evidence_ids: list[str]
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,127}$")
    explanation: str = Field(min_length=1, max_length=2048)
    remediation_hint: str | None = Field(default=None, max_length=2048)

    @field_validator("expected", "actual")
    @classmethod
    def values_must_be_json_compatible(cls, value: Any) -> Any:
        return ensure_json_compatible(value)


class PolicyEvaluation(StrictModel):
    schema_version: Literal["forgegate.policy-evaluation.v1"] = "forgegate.policy-evaluation.v1"
    evaluation_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    policy_name: str = Field(pattern=SLUG_PATTERN)
    policy_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evidence_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_commit: str = Field(pattern=COMMIT_PATTERN)
    evaluated_at: datetime
    decision: Decision
    rule_results: list[RuleEvaluation] = Field(min_length=1)
    evaluated_evidence_ids: list[str]

    @field_validator("evaluated_at")
    @classmethod
    def evaluated_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must include a UTC offset")
        return value
