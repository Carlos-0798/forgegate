from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import ValidationError

from forgegate.canonical import sha256_fingerprint
from forgegate.collectors.base import CollectionResult, CollectionStatus
from forgegate.domain.models import ArtifactReference, EvidenceBundle, EvidenceRecord

from .models import (
    CollectionReceipt,
    EvidenceBundleAssembly,
    assembly_identity,
    evidence_artifact_is_listed,
)


@dataclass(frozen=True, slots=True)
class LoadedCollectionResult:
    source: ArtifactReference
    result: CollectionResult


class EvidenceAssemblyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def assemble_evidence_bundle(
    inputs: Iterable[LoadedCollectionResult],
    *,
    candidate_commit: str,
    generated_at: datetime,
    producer: str,
    producer_version: str,
    retain_warnings: bool = False,
) -> EvidenceBundleAssembly:
    loaded = tuple(inputs)
    if not loaded:
        raise EvidenceAssemblyError(
            "ASSEMBLY_INPUTS_EMPTY", "at least one collection result is required"
        )

    receipts: list[CollectionReceipt] = []
    evidence: list[EvidenceRecord] = []
    for item in loaded:
        result = item.result
        if result.status is not CollectionStatus.COMPLETE:
            raise EvidenceAssemblyError(
                "ASSEMBLY_COLLECTION_REJECTED",
                f"collection result is not COMPLETE: {item.source.path_or_uri}",
            )
        if result.warnings and not retain_warnings:
            raise EvidenceAssemblyError(
                "ASSEMBLY_WARNINGS_PRESENT",
                "collection warnings require explicit --retain-warnings: "
                f"{item.source.path_or_uri}",
            )
        if not result.artifacts or any(
            not evidence_artifact_is_listed(record, result.artifacts) for record in result.evidence
        ):
            raise EvidenceAssemblyError(
                "ASSEMBLY_ARTIFACT_MISMATCH",
                f"collection evidence is not bound to its artifacts: {item.source.path_or_uri}",
            )
        receipt = CollectionReceipt(
            source=item.source,
            collector_name=result.collector_name,
            collector_version=result.collector_version,
            result_fingerprint=sha256_fingerprint(result.model_dump(mode="json")),
            artifacts=result.artifacts,
            evidence_ids=[record.evidence_id for record in result.evidence],
            warnings=result.warnings,
        )
        receipts.append(receipt)
        evidence.extend(result.evidence)

    source_paths = [receipt.source.path_or_uri for receipt in receipts]
    if len(source_paths) != len(set(source_paths)):
        raise EvidenceAssemblyError(
            "ASSEMBLY_SOURCE_DUPLICATE", "collection receipt source paths must be unique"
        )
    result_fingerprints = [receipt.result_fingerprint for receipt in receipts]
    if len(result_fingerprints) != len(set(result_fingerprints)):
        raise EvidenceAssemblyError(
            "ASSEMBLY_RESULT_DUPLICATE", "collection result fingerprints must be unique"
        )

    try:
        bundle = EvidenceBundle(
            schema_version="forgegate.evidence-bundle.v1",
            producer=producer,
            producer_version=producer_version,
            candidate_commit=candidate_commit,
            generated_at=generated_at,
            evidence=evidence,
        )
        warning_disposition: Literal["none", "retained"] = (
            "retained" if any(value.warnings for value in receipts) else "none"
        )
        identity = assembly_identity(warning_disposition, bundle, receipts)
        return EvidenceBundleAssembly(
            assembly_id=sha256_fingerprint(identity),
            warning_disposition=warning_disposition,
            bundle=bundle,
            collections=receipts,
        )
    except ValidationError as exc:
        raise EvidenceAssemblyError(
            "ASSEMBLY_MODEL_INVALID", f"cannot assemble evidence bundle: {exc}"
        ) from exc


__all__ = [
    "EvidenceAssemblyError",
    "LoadedCollectionResult",
    "assemble_evidence_bundle",
]
