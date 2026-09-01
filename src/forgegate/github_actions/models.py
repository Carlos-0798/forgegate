from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from forgegate.candidates.models import CANDIDATE_ID_PATTERN
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.enums import Decision
from forgegate.domain.models import SLUG_PATTERN, StrictModel

FINGERPRINT_PATTERN = r"^sha256:[0-9a-f]{64}$"
FULL_COMMIT_PATTERN = r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"

type GitHubConclusion = Literal["success", "failure", "action_required"]

RECOMMENDED_CONCLUSIONS: dict[Decision, GitHubConclusion] = {
    Decision.PASS: "success",
    Decision.FAIL: "failure",
    Decision.REVIEW: "action_required",
    Decision.ERROR: "failure",
}


class GitHubActionReport(StrictModel):
    """Versioned result of binding one verified assurance bundle to a CI commit."""

    schema_version: Literal["forgegate.github-action-report.v1"] = (
        "forgegate.github-action-report.v1"
    )
    report_id: str = Field(pattern=FINGERPRINT_PATTERN)
    status: Literal["VALID"] = "VALID"
    integration: Literal["github-actions"] = "github-actions"
    bundle_id: str = Field(pattern=FINGERPRINT_PATTERN)
    manifest_id: str = Field(pattern=FINGERPRINT_PATTERN)
    project_id: str = Field(pattern=SLUG_PATTERN)
    candidate_id: str = Field(pattern=CANDIDATE_ID_PATTERN)
    candidate_commit: str = Field(pattern=FULL_COMMIT_PATTERN)
    expected_commit: str = Field(pattern=FULL_COMMIT_PATTERN)
    commit_binding: Literal["exact"] = "exact"
    decision: Decision
    recommended_conclusion: GitHubConclusion
    assurance: Literal["unsigned_local"] = "unsigned_local"
    verification_scope: Literal["retained_documents_and_embedded_policy_bytes"] = (
        "retained_documents_and_embedded_policy_bytes"
    )
    source_artifact_bytes: Literal["not_embedded"] = "not_embedded"

    @model_validator(mode="after")
    def identity_and_decision_must_match(self) -> GitHubActionReport:
        if self.candidate_commit != self.expected_commit:
            raise ValueError("candidate commit does not exactly match the expected CI commit")
        if self.recommended_conclusion != RECOMMENDED_CONCLUSIONS[self.decision]:
            raise ValueError("recommended conclusion does not match the ForgeGate decision")
        identity = self.model_dump(mode="json", exclude={"schema_version", "report_id"})
        if self.report_id != sha256_fingerprint(identity):
            raise ValueError("report_id does not match GitHub action report content")
        return self


__all__ = [
    "FULL_COMMIT_PATTERN",
    "RECOMMENDED_CONCLUSIONS",
    "GitHubActionReport",
    "GitHubConclusion",
]
