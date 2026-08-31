from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forgegate.domain.models import EvidenceBundle, PolicyConfig, ProjectConfig


def valid_project() -> dict[str, object]:
    return {
        "schema_version": "forgegate.project.v1",
        "project": {"id": "sample-api", "name": "Sample API"},
        "release_tracks": {"production": {"policy": "policies/production.yaml"}},
        "collectors": [{"type": "junit", "path": "artifacts/junit.xml"}],
        "outputs": {
            "json": "build/forgegate/attestation.json",
            "markdown": "build/forgegate/summary.md",
        },
    }


def valid_policy_rule() -> dict[str, object]:
    return {
        "id": "no-critical-findings",
        "claim": "security.no-critical",
        "evidence_kind": "security.finding",
        "aggregation": "count",
        "operator": "equals",
        "expected": 0,
        "mandatory": True,
        "require_presence": True,
        "on_missing": "REVIEW",
        "minimum_trust": "claimed_ci_metadata",
        "minimum_verification": "ci_validated",
    }


def valid_evidence_record() -> dict[str, object]:
    commit = "a" * 40
    return {
        "evidence_id": "tests-summary-1",
        "kind": "test.summary",
        "scope": "repository",
        "value": {"failed": 0, "total": 10},
        "status": "passed",
        "source_tool": "pytest",
        "source_version": "8.3.5",
        "execution_context": {"commit_sha": commit},
        "artifact": {
            "path_or_uri": "artifacts/junit.xml",
            "media_type": "application/xml",
            "sha256": "b" * 64,
            "size_bytes": 100,
        },
        "collected_at": datetime(2026, 8, 30, 20, 0, tzinfo=UTC),
        "trust": "claimed_ci_metadata",
        "verification_level": "ci_validated",
    }


def test_valid_project_model() -> None:
    model = ProjectConfig.model_validate(valid_project())
    assert model.project.id == "sample-api"


def test_unknown_project_field_is_rejected() -> None:
    payload = valid_project()
    payload["unknown"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProjectConfig.model_validate(payload)


def test_invalid_release_track_name_is_rejected() -> None:
    payload = valid_project()
    payload["release_tracks"] = {"Production Track": {"policy": "policies/production.yaml"}}
    with pytest.raises(ValidationError, match="invalid release track"):
        ProjectConfig.model_validate(payload)


@pytest.mark.parametrize(
    "path",
    ["../outside.xml", "/absolute/file.xml", "C:/absolute/file.xml", "C:\\absolute\\file.xml"],
)
def test_unsafe_collector_paths_are_rejected(path: str) -> None:
    payload = valid_project()
    payload["collectors"] = [{"type": "junit", "path": path}]
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate(payload)


def test_mandatory_policy_rule_requires_presence() -> None:
    rule = valid_policy_rule()
    rule["require_presence"] = False
    with pytest.raises(ValidationError, match="must require evidence presence"):
        PolicyConfig.model_validate(
            {"schema_version": "forgegate.policy.v1", "name": "production", "rules": [rule]}
        )


def test_missing_evidence_cannot_pass() -> None:
    rule = valid_policy_rule()
    rule["on_missing"] = "PASS"
    with pytest.raises(ValidationError, match="cannot produce PASS"):
        PolicyConfig.model_validate(
            {"schema_version": "forgegate.policy.v1", "name": "production", "rules": [rule]}
        )


def test_policy_rule_ids_are_unique() -> None:
    rule = valid_policy_rule()
    with pytest.raises(ValidationError, match="must be unique"):
        PolicyConfig.model_validate(
            {
                "schema_version": "forgegate.policy.v1",
                "name": "production",
                "rules": [rule, rule],
            }
        )


def test_evidence_ids_are_unique() -> None:
    record = valid_evidence_record()
    with pytest.raises(ValidationError, match="evidence IDs must be unique"):
        EvidenceBundle.model_validate(
            {
                "schema_version": "forgegate.evidence-bundle.v1",
                "producer": "sample-ci",
                "producer_version": "1.0.0",
                "candidate_commit": "a" * 40,
                "generated_at": datetime(2026, 8, 30, 20, 1, tzinfo=UTC),
                "evidence": [record, record],
            }
        )


def test_evidence_bundle_accepts_matching_commit() -> None:
    record = valid_evidence_record()
    bundle = EvidenceBundle.model_validate(
        {
            "schema_version": "forgegate.evidence-bundle.v1",
            "producer": "sample-ci",
            "producer_version": "1.0.0",
            "candidate_commit": "a" * 40,
            "generated_at": datetime(2026, 8, 30, 20, 1, tzinfo=UTC),
            "evidence": [record],
        }
    )
    assert bundle.evidence[0].execution_context.commit_sha == bundle.candidate_commit


def test_evidence_bundle_rejects_commit_mismatch() -> None:
    record = valid_evidence_record()
    record["execution_context"] = {"commit_sha": "c" * 40}
    with pytest.raises(ValidationError, match="commit does not match"):
        EvidenceBundle.model_validate(
            {
                "schema_version": "forgegate.evidence-bundle.v1",
                "producer": "sample-ci",
                "producer_version": "1.0.0",
                "candidate_commit": "a" * 40,
                "generated_at": datetime(2026, 8, 30, 20, 1, tzinfo=UTC),
                "evidence": [record],
            }
        )


def test_naive_evidence_timestamp_is_rejected() -> None:
    record = valid_evidence_record()
    record["collected_at"] = datetime(2026, 8, 30, 20, 0)
    with pytest.raises(ValidationError, match="must include a UTC offset"):
        EvidenceBundle.model_validate(
            {
                "schema_version": "forgegate.evidence-bundle.v1",
                "producer": "sample-ci",
                "producer_version": "1.0.0",
                "candidate_commit": "a" * 40,
                "generated_at": datetime(2026, 8, 30, 20, 1, tzinfo=UTC),
                "evidence": [record],
            }
        )


def test_naive_bundle_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError, match="generated_at must include a UTC offset"):
        EvidenceBundle.model_validate(
            {
                "schema_version": "forgegate.evidence-bundle.v1",
                "producer": "sample-ci",
                "producer_version": "1.0.0",
                "candidate_commit": "a" * 40,
                "generated_at": datetime(2026, 8, 30, 20, 1),
                "evidence": [valid_evidence_record()],
            }
        )


def test_invalid_sha256_is_rejected() -> None:
    record = valid_evidence_record()
    artifact = dict(record["artifact"])  # type: ignore[arg-type]
    artifact["sha256"] = "not-a-hash"
    record["artifact"] = artifact
    with pytest.raises(ValidationError):
        EvidenceBundle.model_validate(
            {
                "schema_version": "forgegate.evidence-bundle.v1",
                "producer": "sample-ci",
                "producer_version": "1.0.0",
                "candidate_commit": "a" * 40,
                "generated_at": datetime(2026, 8, 30, 20, 1, tzinfo=UTC),
                "evidence": [record],
            }
        )
