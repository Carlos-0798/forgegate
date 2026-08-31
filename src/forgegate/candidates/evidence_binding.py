from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from forgegate.assembly import EvidenceBundleAssembly
from forgegate.candidates.models import FINGERPRINT_PATTERN, CandidateDocument
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import StrictModel


class CandidateEvidenceBinding(StrictModel):
    schema_version: Literal["forgegate.candidate-evidence-binding.v1"] = (
        "forgegate.candidate-evidence-binding.v1"
    )
    binding_id: str = Field(pattern=FINGERPRINT_PATTERN)
    bound_at: datetime
    candidate: CandidateDocument
    candidate_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    assembly: EvidenceBundleAssembly
    assembly_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)

    @field_validator("bound_at")
    @classmethod
    def bound_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("bound_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def binding_is_self_consistent(self) -> CandidateEvidenceBinding:
        if self.candidate.status is not CandidateStatus.COLLECTING or self.candidate.revision != 1:
            raise ValueError("evidence binding requires a revision-one COLLECTING candidate")
        if self.candidate.commit_sha.lower() != self.assembly.bundle.candidate_commit.lower():
            raise ValueError("assembly commit does not match candidate")
        if self.bound_at < self.candidate.updated_at:
            raise ValueError("bound_at cannot precede the candidate timestamp")
        if self.bound_at < self.assembly.bundle.generated_at:
            raise ValueError("bound_at cannot precede assembly generation")

        candidate_fingerprint = sha256_fingerprint(self.candidate.model_dump(mode="json"))
        if self.candidate_fingerprint != candidate_fingerprint:
            raise ValueError("candidate_fingerprint does not match candidate")
        assembly_fingerprint = sha256_fingerprint(self.assembly.model_dump(mode="json"))
        if self.assembly_fingerprint != assembly_fingerprint:
            raise ValueError("assembly_fingerprint does not match assembly")
        identity = binding_identity(
            self.bound_at,
            self.candidate,
            self.candidate_fingerprint,
            self.assembly,
            self.assembly_fingerprint,
        )
        if self.binding_id != sha256_fingerprint(identity):
            raise ValueError("binding_id does not match binding content")
        return self


def create_candidate_evidence_binding(
    candidate: CandidateDocument,
    assembly: EvidenceBundleAssembly,
    *,
    bound_at: datetime,
) -> CandidateEvidenceBinding:
    timestamp = _normalized_timestamp(bound_at)
    candidate_fingerprint = sha256_fingerprint(candidate.model_dump(mode="json"))
    assembly_fingerprint = sha256_fingerprint(assembly.model_dump(mode="json"))
    identity = binding_identity(
        timestamp,
        candidate,
        candidate_fingerprint,
        assembly,
        assembly_fingerprint,
    )
    return CandidateEvidenceBinding(
        binding_id=sha256_fingerprint(identity),
        bound_at=timestamp,
        candidate=candidate,
        candidate_fingerprint=candidate_fingerprint,
        assembly=assembly,
        assembly_fingerprint=assembly_fingerprint,
    )


def binding_identity(
    bound_at: datetime,
    candidate: CandidateDocument,
    candidate_fingerprint: str,
    assembly: EvidenceBundleAssembly,
    assembly_fingerprint: str,
) -> dict[str, object]:
    return {
        "bound_at": _json_timestamp(bound_at),
        "candidate": candidate.model_dump(mode="json"),
        "candidate_fingerprint": candidate_fingerprint,
        "assembly": assembly.model_dump(mode="json"),
        "assembly_fingerprint": assembly_fingerprint,
    }


def _normalized_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("bound_at must include a UTC offset")
    return value.astimezone(UTC)


def _json_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "CandidateEvidenceBinding",
    "binding_identity",
    "create_candidate_evidence_binding",
]
