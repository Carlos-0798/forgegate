"""Synthetic fixtures exercise the file-only AVS handoff, not upstream hardware."""

import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateEvaluateCommand,
)
from forgegate.assurance import publish_assurance_bundle, verify_assurance_bundle
from forgegate.config import load_config
from tools.avs_host_acceptance import (
    QUALITY_CHECKS,
    _unique_object,
    prepare_handoff,
    quality_benchmark,
)


def quality_fixture():
    return {
        "schema_version": "phase5-product-quality-acceptance.v1",
        "scope": "HOST_SOFTWARE_ONLY",
        "hardware_validation": False,
        "passed": True,
        "checks": dict.fromkeys(QUALITY_CHECKS, True),
        "measurements": {
            "replay": [{"records": 10000, "elapsed_seconds": 0.6, "peak_memory_mib": 13.1}],
            "live_monitor": {
                "requested_points": 10000,
                "elapsed_seconds": 0.2,
                "peak_memory_mib": 1.3,
            },
            "event_volume": {"requested_progress_events": 10000, "elapsed_seconds": 0.04},
            "demo": {"elapsed_seconds": 0.03},
        },
    }


def test_quality_mapping_preserves_values_and_failed_checks():
    document = quality_fixture()
    document["checks"]["live_status_accounted"] = False
    document["passed"] = False
    metrics = {item["name"]: item for item in quality_benchmark(document)["metrics"]}
    assert len(metrics) == 7
    assert metrics["upstream.checks.failed"]["value"] == 1
    assert metrics["replay.10000.elapsed"] == {
        "name": "replay.10000.elapsed",
        "value": 0.6,
        "unit": "s",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "unknown"),
        ("scope", "BENCH"),
        ("hardware_validation", True),
        ("hardware_validation", 0),
        ("passed", False),
        ("checks", {}),
    ],
)
def test_rejects_incompatible_quality_contract(field, value):
    document = quality_fixture()
    document[field] = value
    with pytest.raises(ValueError):
        quality_benchmark(document)


@pytest.mark.parametrize("value", [True, "1", -1, float("nan"), float("inf")])
def test_rejects_invalid_measurement(value):
    document = quality_fixture()
    document["measurements"]["demo"]["elapsed_seconds"] = value
    with pytest.raises(ValueError, match="finite nonnegative"):
        quality_benchmark(document)


def test_rejects_ambiguous_checks_workload_and_duplicate_json():
    document = quality_fixture()
    document["checks"]["demo_time"] = 1
    with pytest.raises(ValueError, match="booleans"):
        quality_benchmark(document)
    document = quality_fixture()
    document["measurements"]["replay"] *= 2
    with pytest.raises(ValueError, match="exactly one"):
        quality_benchmark(document)
    document = quality_fixture()
    document["measurements"]["live_monitor"]["requested_points"] = 999
    with pytest.raises(ValueError, match="workload"):
        quality_benchmark(document)
    with pytest.raises(ValueError, match="duplicate"):
        json.loads('{"passed":true,"passed":false}', object_pairs_hook=_unique_object)


def test_handoff_preserves_failure_through_assurance(tmp_path, repository_root):
    reports = tmp_path / "reports"
    reports.mkdir()
    base = repository_root / "examples/dashboard-standard-ci"
    for source, target in [
        ("tests.xml", "junit.xml"),
        ("coverage.xml", "coverage.xml"),
        ("finding.sarif", "security.sarif"),
    ]:
        (reports / target).write_bytes((base / source).read_bytes())
    document = quality_fixture()
    document["checks"]["demo_pass"] = False
    document["passed"] = False
    (reports / "product-quality.json").write_text(json.dumps(document), encoding="utf-8")
    output = tmp_path / "handoff"
    arguments = dict(commit="a" * 40, pytest_version="fixture", coverage_version="fixture")
    manifest = prepare_handoff(reports, output, **arguments)
    assert manifest["candidate_status"] == "COLLECTING" and manifest["bound"] is False
    assert manifest["hardware_access"] == manifest["producer_authentication"] == "NOT_PERFORMED"
    for name in ["junit.xml", "coverage.xml", "security.sarif", "product-quality.json"]:
        assert (reports / name).read_bytes() == (output / "artifacts" / name).read_bytes()
    with pytest.raises(FileExistsError):
        prepare_handoff(reports, output, **arguments)
    application = CandidateApplication.for_database(output / "forgegate.db")
    candidate_id = manifest["candidate_id"]
    application.bind_evidence(
        candidate_id,
        CandidateBindEvidenceCommand(
            assembly=load_config(output / "assembly.json"),
            bound_at=datetime.now(UTC),
        ),
        idempotency_key="test:bind",
    )
    for revision, target in [(1, "READY"), (2, "EVALUATING")]:
        application.advance_candidate(
            candidate_id,
            CandidateAdvanceCommand.model_validate(
                {
                    "to_status": target,
                    "expected_revision": revision,
                    "occurred_at": datetime.now(UTC),
                }
            ),
            idempotency_key=f"test:{target}",
        )
    application.evaluate_candidate(
        candidate_id,
        CandidateEvaluateCommand(
            policy_material=load_config(output / "policy-material.json"),
            expected_revision=3,
            evaluated_at=datetime.now(UTC),
        ),
        idempotency_key="test:evaluate",
    )
    application.attest_candidate(candidate_id, CandidateAttestCommand(issued_at=datetime.now(UTC)))
    bundle = application.get_assurance_bundle(candidate_id)
    evaluation = bundle.attestation.policy_evaluation
    assert evaluation.decision == "FAIL"
    failed = {item.rule_id for item in evaluation.rule_results if item.decision == "FAIL"}
    assert {"static-review", "quality-checks"} <= failed
    published = publish_assurance_bundle(bundle, tmp_path / "portable")
    verified = verify_assurance_bundle(published.directory)
    assert verified is not None


def test_handoff_rejects_materially_future_dated_report(tmp_path, repository_root):
    reports = tmp_path / "reports"
    reports.mkdir()
    base = repository_root / "examples/dashboard-standard-ci"
    for source, target in [
        ("tests.xml", "junit.xml"),
        ("coverage.xml", "coverage.xml"),
        ("finding.sarif", "security.sarif"),
    ]:
        (reports / target).write_bytes((base / source).read_bytes())
    quality = reports / "product-quality.json"
    quality.write_text(json.dumps(quality_fixture()), encoding="utf-8")
    future = (datetime.now(UTC) + timedelta(seconds=5)).timestamp()
    os.utime(quality, (future, future))

    with pytest.raises(ValueError, match="file time cannot be in the future"):
        prepare_handoff(
            reports,
            tmp_path / "handoff",
            commit="a" * 40,
            pytest_version="fixture",
            coverage_version="fixture",
        )
