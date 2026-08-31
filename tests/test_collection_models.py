from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forgegate.collectors.base import CollectionIssue, CollectionResult
from forgegate.domain.models import ArtifactReference, EvidenceRecord, ExecutionContext


def evidence() -> EvidenceRecord:
    artifact = ArtifactReference(
        path_or_uri="artifacts/junit.xml",
        media_type="application/junit+xml",
        sha256="b" * 64,
        size_bytes=100,
    )
    return EvidenceRecord(
        evidence_id="test-summary-12345678",
        kind="test.summary",
        scope="repository",
        value={"total": 1},
        status="passed",
        source_tool="pytest",
        source_version="8.4.2",
        execution_context=ExecutionContext(commit_sha="a" * 40),
        artifact=artifact,
        collected_at=datetime(2026, 8, 30, 20, 30, tzinfo=UTC),
        trust="unsigned_local",
        verification_level="host_tested",
    )


def warning() -> CollectionIssue:
    return CollectionIssue(code="JUNIT_WARNING", severity="WARNING", message="warning")


def rejection() -> CollectionIssue:
    return CollectionIssue(code="JUNIT_REJECTED", severity="REJECTION", message="rejected")


def test_complete_result_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="must contain evidence"):
        CollectionResult(collector_name="junit", collector_version="v1", status="COMPLETE")


def test_complete_result_cannot_contain_rejections() -> None:
    with pytest.raises(ValidationError, match="cannot contain rejected records"):
        CollectionResult(
            collector_name="junit",
            collector_version="v1",
            status="COMPLETE",
            evidence=[evidence()],
            rejected_records=[rejection()],
        )


def test_rejected_result_cannot_contain_evidence() -> None:
    with pytest.raises(ValidationError, match="cannot contain evidence"):
        CollectionResult(
            collector_name="junit",
            collector_version="v1",
            status="REJECTED",
            evidence=[evidence()],
            rejected_records=[rejection()],
        )


def test_rejected_result_requires_explanation() -> None:
    with pytest.raises(ValidationError, match="must explain"):
        CollectionResult(collector_name="junit", collector_version="v1", status="REJECTED")


def test_warning_list_requires_warning_severity() -> None:
    with pytest.raises(ValidationError, match="warnings must use WARNING"):
        CollectionResult(
            collector_name="junit",
            collector_version="v1",
            status="COMPLETE",
            evidence=[evidence()],
            warnings=[rejection()],
        )


def test_rejection_list_requires_rejection_severity() -> None:
    with pytest.raises(ValidationError, match="must use REJECTION"):
        CollectionResult(
            collector_name="junit",
            collector_version="v1",
            status="REJECTED",
            rejected_records=[warning()],
        )
