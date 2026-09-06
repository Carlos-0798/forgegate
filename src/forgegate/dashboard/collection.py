from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from forgegate import __version__
from forgegate.artifacts import ArtifactBoundaryError, RegisteredArtifact
from forgegate.assembly.models import COLLECTION_RESULT_MEDIA_TYPE, EvidenceBundleAssembly
from forgegate.assembly.service import LoadedCollectionResult, assemble_evidence_bundle
from forgegate.canonical import canonical_json
from forgegate.collectors.base import CollectionResult, CollectionStatus
from forgegate.collectors.junit import JUNIT_MEDIA_TYPE, JUnitCollectionRequest, JUnitCollector
from forgegate.domain.enums import EvidenceTrust, VerificationLevel
from forgegate.domain.models import COMMIT_PATTERN, ArtifactReference, ExecutionContext, StrictModel

MAX_REPORT_BYTES = 1024 * 1024
MAX_REPORT_BASE64 = 4 * ((MAX_REPORT_BYTES + 2) // 3)


class DashboardJUnitPreviewRequest(StrictModel):
    expected_revision: int = Field(ge=0)
    reported_commit: str = Field(pattern=COMMIT_PATTERN)
    content_base64: str = Field(min_length=4, max_length=MAX_REPORT_BASE64)
    source_tool: str = Field(min_length=1, max_length=120)
    source_version: str = Field(min_length=1, max_length=120)
    collected_at: datetime
    retain_warnings: bool = False

    @field_validator("content_base64")
    @classmethod
    def exact_bounded_bytes(cls, value: str) -> str:
        try:
            content = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("report must use canonical base64") from exc
        if not content or len(content) > MAX_REPORT_BYTES:
            raise ValueError("report must contain 1 to 1048576 bytes")
        if base64.b64encode(content).decode("ascii") != value:
            raise ValueError("report must use canonical base64")
        return value

    @field_validator("collected_at")
    @classmethod
    def reported_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None or value > datetime.now(UTC):
            raise ValueError("reported collection time needs an offset and cannot be in the future")
        return value


class DashboardJUnitPreview(StrictModel):
    schema_version: Literal["forgegate.dashboard-junit-preview.v1"] = (
        "forgegate.dashboard-junit-preview.v1"
    )
    candidate_id: str
    expected_revision: int
    collection: CollectionResult
    assembly: EvidenceBundleAssembly | None
    persistence: Literal["NOT_RETAINED"] = "NOT_RETAINED"
    source_artifact_bytes: Literal["not_retained"] = "not_retained"


@dataclass(frozen=True)
class _UploadedSource:
    artifact: RegisteredArtifact

    def register(self, source_path: str | Path, *, media_type: str) -> RegisteredArtifact:
        if str(source_path) != self.artifact.reference.path_or_uri or (
            media_type != self.artifact.reference.media_type
        ):
            raise ArtifactBoundaryError("only the exact uploaded report is available")
        return self.artifact


def preview_junit(
    candidate_id: str, command: DashboardJUnitPreviewRequest
) -> DashboardJUnitPreview:
    content = base64.b64decode(command.content_base64, validate=True)
    digest = hashlib.sha256(content).hexdigest()
    source = _UploadedSource(
        RegisteredArtifact(
            reference=ArtifactReference(
                path_or_uri=f"uploads/{digest}.xml",
                media_type=JUNIT_MEDIA_TYPE,
                sha256=digest,
                size_bytes=len(content),
            ),
            content=content,
        )
    )
    result = JUnitCollector(source, max_elements=10_000, max_depth=32).collect(
        JUnitCollectionRequest(
            source_path=source.artifact.reference.path_or_uri,
            source_tool=command.source_tool,
            source_version=command.source_version,
            execution_context=ExecutionContext(commit_sha=command.reported_commit),
            collected_at=command.collected_at,
            trust=EvidenceTrust.UNSIGNED_LOCAL,
            verification_level=VerificationLevel.DECLARED,
        )
    )
    assembly = None
    if result.status is CollectionStatus.COMPLETE and (
        not result.warnings or command.retain_warnings
    ):
        result_bytes = canonical_json(result.model_dump(mode="json")).encode("utf-8")
        result_digest = hashlib.sha256(result_bytes).hexdigest()
        assembly = assemble_evidence_bundle(
            [
                LoadedCollectionResult(
                    source=ArtifactReference(
                        path_or_uri=f"collections/{result_digest}.json",
                        media_type=COLLECTION_RESULT_MEDIA_TYPE,
                        sha256=result_digest,
                        size_bytes=len(result_bytes),
                    ),
                    result=result,
                )
            ],
            candidate_commit=command.reported_commit,
            generated_at=datetime.now(UTC),
            producer="forgegate-dashboard-junit",
            producer_version=__version__,
            retain_warnings=command.retain_warnings,
        )
    return DashboardJUnitPreview(
        candidate_id=candidate_id,
        expected_revision=command.expected_revision,
        collection=result,
        assembly=assembly,
    )
