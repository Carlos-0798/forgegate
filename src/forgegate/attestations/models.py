from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from forgegate.candidates.models import (
    CANDIDATE_DOCUMENT_ADAPTER,
    EVALUATION_REQUIRED_STATUSES,
    TERMINAL_CANDIDATE_STATUSES,
    CandidateDocument,
    CandidateTransition,
    candidate_identity,
)
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.enums import Decision
from forgegate.domain.models import StrictModel
from forgegate.policy.models import PolicyEvaluation

FINGERPRINT_PATTERN = r"^sha256:[0-9a-f]{64}$"
_DECISION_RANK = {
    Decision.PASS: 0,
    Decision.REVIEW: 1,
    Decision.FAIL: 2,
    Decision.ERROR: 3,
}


class ReleaseAttestation(StrictModel):
    schema_version: Literal["forgegate.release-attestation.v1"] = "forgegate.release-attestation.v1"
    attestation_id: str = Field(pattern=FINGERPRINT_PATTERN)
    generator: Literal["forgegate"] = "forgegate"
    generator_version: str = Field(min_length=1, max_length=120)
    assurance: Literal["unsigned_local"] = "unsigned_local"
    issued_at: datetime
    candidate: CandidateDocument
    candidate_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    transitions: list[CandidateTransition] = Field(min_length=4, max_length=4)
    transition_chain_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    policy_evaluation: PolicyEvaluation | None = None
    evaluation_fingerprint: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)

    @field_validator("issued_at")
    @classmethod
    def issued_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("issued_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def attestation_must_be_self_consistent(self) -> ReleaseAttestation:
        candidate = self.candidate
        if candidate.status not in TERMINAL_CANDIDATE_STATUSES or candidate.revision != 4:
            raise ValueError("attestation requires a terminal revision-four candidate")
        if self.issued_at < candidate.updated_at:
            raise ValueError("issued_at cannot precede the terminal candidate timestamp")
        identity = candidate_identity(candidate)
        expected_candidate_id = "cand-" + sha256_fingerprint(identity).removeprefix("sha256:")[:24]
        if candidate.candidate_id != expected_candidate_id:
            raise ValueError("candidate_id does not match the candidate identity")
        candidate_fingerprint = sha256_fingerprint(candidate.model_dump(mode="json"))
        if self.candidate_fingerprint != candidate_fingerprint:
            raise ValueError("candidate_fingerprint does not match the candidate")
        self._validate_transition_chain(candidate_fingerprint)
        self._validate_evaluation()
        identity = self.model_dump(mode="json", exclude={"schema_version", "attestation_id"})
        if self.attestation_id != sha256_fingerprint(identity):
            raise ValueError("attestation_id does not match attestation content")
        return self

    def _validate_transition_chain(self, candidate_fingerprint: str) -> None:
        initial_values = self.candidate.model_dump(mode="python")
        initial_values.update(
            status="DRAFT",
            revision=0,
            updated_at=self.candidate.created_at,
            evaluated_at=None,
            evaluation_id=None,
        )
        current = CANDIDATE_DOCUMENT_ADAPTER.validate_python(initial_values)
        for index, transition in enumerate(self.transitions):
            if (
                transition.candidate_id != self.candidate.candidate_id
                or transition.from_revision != index
                or transition.to_revision != index + 1
            ):
                raise ValueError("attestation transition revisions or candidate ID are invalid")
            next_values = current.model_dump(mode="python")
            next_values.update(
                status=transition.to_status,
                revision=transition.to_revision,
                updated_at=transition.occurred_at,
                evaluated_at=(
                    transition.occurred_at
                    if transition.to_status in TERMINAL_CANDIDATE_STATUSES
                    else None
                ),
                evaluation_id=transition.evaluation_id,
            )
            next_candidate = CANDIDATE_DOCUMENT_ADAPTER.validate_python(next_values)
            if (
                transition.from_status is not current.status
                or transition.occurred_at < current.updated_at
                or transition.prior_candidate_fingerprint
                != sha256_fingerprint(current.model_dump(mode="json"))
                or transition.result_candidate_fingerprint
                != sha256_fingerprint(next_candidate.model_dump(mode="json"))
            ):
                raise ValueError(
                    "attestation transitions do not match reconstructed candidate snapshots"
                )
            current = next_candidate
        final = self.transitions[-1]
        if (
            current != self.candidate
            or final.to_status is not self.candidate.status
            or final.result_candidate_fingerprint != candidate_fingerprint
            or final.occurred_at != self.candidate.updated_at
            or final.evaluation_id != self.candidate.evaluation_id
        ):
            raise ValueError("attestation terminal transition does not match the candidate")
        chain_fingerprint = sha256_fingerprint(
            [transition.transition_id for transition in self.transitions]
        )
        if self.transition_chain_fingerprint != chain_fingerprint:
            raise ValueError("transition_chain_fingerprint does not match the transitions")

    def _validate_evaluation(self) -> None:
        candidate = self.candidate
        evaluation = self.policy_evaluation
        if evaluation is None:
            if (
                candidate.status in EVALUATION_REQUIRED_STATUSES
                or candidate.evaluation_id is not None
            ):
                raise ValueError("candidate decision requires its policy evaluation")
            if self.evaluation_fingerprint is not None:
                raise ValueError("evaluation_fingerprint requires a policy evaluation")
            return
        evaluation_fingerprint = sha256_fingerprint(evaluation.model_dump(mode="json"))
        if self.evaluation_fingerprint != evaluation_fingerprint:
            raise ValueError("evaluation_fingerprint does not match the policy evaluation")
        if (
            candidate.evaluation_id != evaluation.evaluation_id
            or candidate.commit_sha.lower() != evaluation.candidate_commit.lower()
            or candidate.status.value != evaluation.decision.value
            or candidate.updated_at != evaluation.evaluated_at
        ):
            raise ValueError("policy evaluation does not match the terminal candidate")
        evaluation_identity = {
            "policy_fingerprint": evaluation.policy_fingerprint,
            "evidence_fingerprint": evaluation.evidence_fingerprint,
            "evaluated_at": evaluation.evaluated_at.isoformat(),
        }
        if evaluation.evaluation_id != sha256_fingerprint(evaluation_identity):
            raise ValueError("policy evaluation ID does not match its declared inputs and time")
        rule_ids = [result.rule_id for result in evaluation.rule_results]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("policy evaluation rule IDs must be unique")
        expected_evidence_ids = sorted(
            {item for result in evaluation.rule_results for item in result.evidence_ids}
        )
        if evaluation.evaluated_evidence_ids != expected_evidence_ids:
            raise ValueError("policy evaluation evidence references are inconsistent")
        mandatory_decisions = [
            result.decision for result in evaluation.rule_results if result.mandatory
        ]
        expected_decision = max(
            mandatory_decisions,
            key=_DECISION_RANK.__getitem__,
            default=Decision.PASS,
        )
        if evaluation.decision is not expected_decision:
            raise ValueError("policy evaluation decision conflicts with mandatory rule results")


def _json_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
