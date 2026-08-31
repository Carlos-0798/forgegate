from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from forgegate.canonical import sha256_fingerprint
from forgegate.collectors.base import CollectionIssue, IssueSeverity
from forgegate.domain.models import (
    ArtifactReference,
    EvidenceBundle,
    EvidenceRecord,
    StrictModel,
)

COLLECTION_RESULT_MEDIA_TYPE = "application/vnd.forgegate.collection-result+json"
ASSEMBLY_SCHEMA_VERSION = "forgegate.evidence-bundle-assembly.v1"
FINGERPRINT_PATTERN = r"^sha256:[0-9a-f]{64}$"


def _artifact_identity(value: ArtifactReference) -> tuple[str, str, str, int]:
    return (value.path_or_uri, value.media_type, value.sha256, value.size_bytes)


class CollectionReceipt(StrictModel):
    source: ArtifactReference
    collector_name: str = Field(min_length=1, max_length=120)
    collector_version: str = Field(min_length=1, max_length=120)
    result_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    artifacts: list[ArtifactReference] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    warnings: list[CollectionIssue] = Field(default_factory=list)

    @field_validator("source")
    @classmethod
    def source_is_a_collection_result(cls, value: ArtifactReference) -> ArtifactReference:
        if value.media_type != COLLECTION_RESULT_MEDIA_TYPE:
            raise ValueError("receipt source must be a collection-result JSON artifact")
        return value

    @model_validator(mode="after")
    def receipt_is_self_consistent(self) -> CollectionReceipt:
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("receipt evidence IDs must be unique")
        identities = [_artifact_identity(value) for value in self.artifacts]
        if len(identities) != len(set(identities)):
            raise ValueError("receipt artifacts must be unique")
        if any(value.severity is not IssueSeverity.WARNING for value in self.warnings):
            raise ValueError("receipt warnings must use WARNING severity")
        return self


class EvidenceBundleAssembly(StrictModel):
    schema_version: Literal["forgegate.evidence-bundle-assembly.v1"] = (
        "forgegate.evidence-bundle-assembly.v1"
    )
    assembly_id: str = Field(pattern=FINGERPRINT_PATTERN)
    warning_disposition: Literal["none", "retained"]
    bundle: EvidenceBundle
    collections: list[CollectionReceipt] = Field(min_length=1)

    @model_validator(mode="after")
    def assembly_is_self_consistent(self) -> EvidenceBundleAssembly:
        source_paths = [value.source.path_or_uri for value in self.collections]
        if len(source_paths) != len(set(source_paths)):
            raise ValueError("collection receipt source paths must be unique")
        fingerprints = [value.result_fingerprint for value in self.collections]
        if len(fingerprints) != len(set(fingerprints)):
            raise ValueError("collection result fingerprints must be unique")

        expected_ids = [
            evidence_id for receipt in self.collections for evidence_id in receipt.evidence_ids
        ]
        actual_ids = [value.evidence_id for value in self.bundle.evidence]
        if expected_ids != actual_ids:
            raise ValueError("receipt evidence IDs must match bundle evidence order")

        has_warnings = any(receipt.warnings for receipt in self.collections)
        expected_disposition = "retained" if has_warnings else "none"
        if self.warning_disposition != expected_disposition:
            raise ValueError("warning disposition must match retained collection warnings")

        records = {value.evidence_id: value for value in self.bundle.evidence}
        artifact_paths: dict[str, tuple[str, str, str, int]] = {}
        for receipt in self.collections:
            allowed = {_artifact_identity(value) for value in receipt.artifacts}
            for evidence_id in receipt.evidence_ids:
                if _artifact_identity(records[evidence_id].artifact) not in allowed:
                    raise ValueError("evidence artifact must belong to its collection receipt")
            for artifact in receipt.artifacts:
                artifact_identity = _artifact_identity(artifact)
                previous = artifact_paths.setdefault(artifact.path_or_uri, artifact_identity)
                if previous != artifact_identity:
                    raise ValueError("artifact path cannot identify conflicting content")

        if any(value.collected_at > self.bundle.generated_at for value in self.bundle.evidence):
            raise ValueError("bundle generation cannot precede collected evidence")

        identity = assembly_identity(
            self.warning_disposition,
            self.bundle,
            self.collections,
        )
        if self.assembly_id != sha256_fingerprint(identity):
            raise ValueError("assembly_id does not match assembly content")
        return self


def assembly_identity(
    warning_disposition: str,
    bundle: EvidenceBundle,
    collections: list[CollectionReceipt],
) -> dict[str, object]:
    return {
        "warning_disposition": warning_disposition,
        "bundle": bundle.model_dump(mode="json"),
        "collections": [value.model_dump(mode="json") for value in collections],
    }


def evidence_artifact_is_listed(
    record: EvidenceRecord,
    artifacts: list[ArtifactReference],
) -> bool:
    identity = _artifact_identity(record.artifact)
    return any(_artifact_identity(value) == identity for value in artifacts)


__all__ = [
    "ASSEMBLY_SCHEMA_VERSION",
    "COLLECTION_RESULT_MEDIA_TYPE",
    "CollectionReceipt",
    "EvidenceBundleAssembly",
    "assembly_identity",
    "evidence_artifact_is_listed",
]
