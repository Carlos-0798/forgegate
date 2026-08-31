import json
import math
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from forgegate.artifacts import ArtifactRegistry
from forgegate.cli import app
from forgegate.collectors import (
    AnalogValidationCollectionRequest,
    AnalogValidationResultCollector,
    CollectionStatus,
)
from forgegate.collectors.analog_validation import (
    AFE_RESULT_JSON_SCHEMA,
    MAX_AFE_RESULT_BYTES,
    AfeEvidenceSource,
    AfeExportValue,
    AfePointDisposition,
    AfeResultExportV1,
    AfeTestRunOutcome,
    AnalogValidationParseError,
    _error_location,
    _identifier,
    _load_json,
    _number,
    _object_without_duplicates,
    _reject_json_constant,
    _timestamp,
)
from forgegate.domain.models import ExecutionContext

COMMIT = "9ac23494b86212928185de9b0eef1c1a82a8c0ea"
COLLECTED_AT = datetime(2026, 8, 31, 13, 0, tzinfo=UTC)
runner = CliRunner()


def request(source_path: str = "result.json") -> AnalogValidationCollectionRequest:
    return AnalogValidationCollectionRequest(
        source_path=source_path,
        execution_context=ExecutionContext(commit_sha=COMMIT),
        collected_at=COLLECTED_AT,
        trust="unsigned_local",
    )


def sample_document(repository_root: Path) -> dict[str, Any]:
    path = repository_root / "examples/sample-python-api/artifacts/analog-validation-result.json"
    return json.loads(path.read_text(encoding="utf-8"))


def collect_payload(
    tmp_path: Path,
    payload: Any,
    **limits: int,
):
    if isinstance(payload, bytes):
        content = payload
    elif isinstance(payload, str):
        content = payload.encode("utf-8")
    else:
        content = json.dumps(payload).encode("utf-8")
    (tmp_path / "result.json").write_bytes(content)
    collector = AnalogValidationResultCollector(ArtifactRegistry(tmp_path), **limits)
    return collector.collect(request())


def add_mixed_source_reference(document: dict[str, Any]) -> None:
    reference = deepcopy(document["points"][0]["references"][0])
    reference.update(record_id="afe-demo-input-1", raw_record_id="afe-demo-raw-input-1")
    reference["source"] = "HOST_TEST"
    document["points"][0]["references"].append(reference)


def add_duplicate_record_point(document: dict[str, Any]) -> None:
    point = deepcopy(document["points"][0])
    point.update(index=1, label="dc-point-1")
    document["points"].append(point)


def leave_evidence_without_points(document: dict[str, Any]) -> None:
    document["test_run"]["outcome"] = "ABORTED"
    document["test_run"]["metadata"]["input_record_ids"] = []
    document["points"] = []


def make_incomplete_without_requirements(document: dict[str, Any]) -> None:
    document["test_run"].update(outcome="INCOMPLETE", missing_requirements=[])


def test_sample_result_normalizes_run_metric_and_criterion(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = AnalogValidationResultCollector(ArtifactRegistry(root)).collect(
        request("artifacts/analog-validation-result.json")
    )

    assert result.status is CollectionStatus.COMPLETE
    assert result.warnings == []
    assert result.rejected_records == []
    assert len(result.evidence) == 3
    run, metric, criterion = result.evidence
    assert run.kind == "analog-validation.run"
    assert run.status == "PASS"
    assert run.value["outcome"] == "PASS"
    assert run.value["limitations"] == [
        "SYNTHETIC compatibility fixture; no physical AFE was measured."
    ]
    assert run.value["counts"] == {
        "input_records": 1,
        "evidence_records": 1,
        "metrics": 1,
        "criteria": 1,
        "points": 1,
    }
    assert metric.kind == "analog-validation.metric"
    assert metric.value["name"] == "gain"
    assert metric.unit == "ratio"
    assert criterion.kind == "analog-validation.criterion"
    assert criterion.value["passed"] is True
    assert criterion.status == "passed"
    assert all(value.verification_level == "simulated" for value in result.evidence)
    assert all(value.source_tool == "analog-validation-studio" for value in result.evidence)
    assert all(value.artifact == result.artifacts[0] for value in result.evidence)


def test_sample_result_matches_golden_projection(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = AnalogValidationResultCollector(ArtifactRegistry(root)).collect(
        request("artifacts/analog-validation-result.json")
    )
    projection = {
        "collector_name": result.collector_name,
        "collector_version": result.collector_version,
        "status": result.status,
        "artifact": result.artifacts[0].model_dump(mode="json"),
        "evidence": [
            {
                "evidence_id": record.evidence_id,
                "kind": record.kind,
                "scope": record.scope,
                "value": record.value,
                "unit": record.unit,
                "status": record.status,
                "source_tool": record.source_tool,
                "source_version": record.source_version,
                "verification_level": record.verification_level,
                "tags": record.tags,
            }
            for record in result.evidence
        ],
        "warnings": result.warnings,
        "rejected_records": result.rejected_records,
    }
    golden = json.loads(
        (repository_root / "tests/golden/analog_validation_result.json").read_text(encoding="utf-8")
    )
    assert json.loads(json.dumps(projection, default=str)) == golden


@pytest.mark.parametrize(
    ("source", "level", "warned"),
    [
        ("THEORY", "declared", False),
        ("SYNTHETIC", "simulated", False),
        ("CSV_REPLAY", "replayed", False),
        ("SPICE_IDEAL", "simulated", False),
        ("SPICE_MODEL", "simulated", False),
        ("HOST_TEST", "host_tested", False),
        ("BENCH_DMM", "system_observed", True),
        ("BENCH_CONTROLLER", "system_observed", True),
        ("BENCH_SCOPE", "system_observed", True),
    ],
)
def test_source_mapping_is_fixed_and_bench_evidence_is_capped(
    tmp_path: Path,
    repository_root: Path,
    source: str,
    level: str,
    warned: bool,
) -> None:
    document = sample_document(repository_root)
    document["test_run"]["metadata"]["evidence_source"] = source
    document["points"][0]["references"][0]["source"] = source

    result = collect_payload(tmp_path, document)

    assert result.status is CollectionStatus.COMPLETE
    assert {record.verification_level for record in result.evidence} == {level}
    assert bool(result.warnings) is warned
    if warned:
        assert result.warnings[0].code == "AFE_BENCH_EVIDENCE_CAPPED"
        assert "system_observed" in result.warnings[0].message


def test_unsupported_export_still_emits_one_nonpassing_run_record(
    tmp_path: Path, repository_root: Path
) -> None:
    document = sample_document(repository_root)
    metadata = document["test_run"]["metadata"]
    metadata["evidence_source"] = "HOST_TEST"
    metadata["input_record_ids"] = []
    document["test_run"].update(
        outcome="UNSUPPORTED",
        summary="adapter lacks output capability",
        evidence_record_ids=[],
        missing_requirements=["command:SET_ANALOG_STIMULUS"],
    )
    document["criteria"] = None
    document["metrics"] = []
    document["points"] = []
    document["limitations"] = ["No acquisition occurred."]

    result = collect_payload(tmp_path, document)

    assert result.status is CollectionStatus.COMPLETE
    assert len(result.evidence) == 1
    assert result.evidence[0].status == "UNSUPPORTED"
    assert result.evidence[0].verification_level == "host_tested"
    assert result.evidence[0].value["missing_requirements"] == ["command:SET_ANALOG_STIMULUS"]


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda value: value.update(schema_version="result-export.v2"),
            "AFE_RESULT_SCHEMA_VERSION_UNSUPPORTED",
        ),
        (lambda value: value.update(extra=True), "AFE_RESULT_CONTRACT_INVALID"),
        (
            lambda value: value["test_run"]["metadata"].update(evidence_source="FAKE"),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["points"][0]["references"][0].update(source="HOST_TEST"),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["test_run"]["metadata"].update(input_record_ids=["wrong-raw-id"]),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (lambda value: value.update(limitations=[]), "AFE_RESULT_CONTRACT_INVALID"),
        (
            lambda value: value["criteria"]["results"][0].update(passed=False),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["metrics"][0].update(name=""),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["metrics"][0].update(value=[]),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["criteria"]["results"][0].update(actual_value=True),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["criteria"]["results"][0].update(
                lower_limit=None, upper_limit=None
            ),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["criteria"]["results"][0].update(lower_limit=3.0, upper_limit=2.0),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["points"][0].update(index=True),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["points"][0]["references"].append(
                deepcopy(value["points"][0]["references"][0])
            ),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (add_mixed_source_reference, "AFE_RESULT_CONTRACT_INVALID"),
        (
            lambda value: value["points"][0]["values"].append(
                deepcopy(value["points"][0]["values"][0])
            ),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["points"][0].update(exclusion_reasons=["unexpected"]),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["points"][0].update(disposition="EXCLUDED", exclusion_reasons=[]),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["test_run"]["metadata"].update(
                ended_at="2026-08-31T11:59:59.000000Z"
            ),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["test_run"].update(missing_requirements=["unexpected requirement"]),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["test_run"].update(evidence_record_ids=[]),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (make_incomplete_without_requirements, "AFE_RESULT_CONTRACT_INVALID"),
        (
            lambda value: value["criteria"]["results"].append(
                deepcopy(value["criteria"]["results"][0])
            ),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["source_schemas"].append(deepcopy(value["source_schemas"][0])),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["metrics"].append(deepcopy(value["metrics"][0])),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["points"][0].update(index=1),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (add_duplicate_record_point, "AFE_RESULT_CONTRACT_INVALID"),
        (
            lambda value: value["test_run"].update(evidence_record_ids=["other-record"]),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (leave_evidence_without_points, "AFE_RESULT_CONTRACT_INVALID"),
        (lambda value: value.update(criteria=None), "AFE_RESULT_CONTRACT_INVALID"),
        (
            lambda value: value["test_run"].update(outcome="FAIL"),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value.update(limitations=["same", "same"]),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["test_run"]["metadata"].update(started_at="not-utc"),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["test_run"]["metadata"].update(started_at="not-a-timeZ"),
            "AFE_RESULT_CONTRACT_INVALID",
        ),
    ],
)
def test_semantically_invalid_exports_fail_closed(
    tmp_path: Path,
    repository_root: Path,
    mutator: Any,
    code: str,
) -> None:
    document = sample_document(repository_root)
    mutator(document)
    result = collect_payload(tmp_path, document)
    assert result.status is CollectionStatus.REJECTED
    assert result.evidence == []
    assert result.rejected_records[0].code == code


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"\xff", "AFE_RESULT_UNSUPPORTED_ENCODING"),
        (b'{"schema_version":"result-export.v1"}\x00', "AFE_RESULT_UNSUPPORTED_ENCODING"),
        ("{", "AFE_RESULT_JSON_INVALID"),
        (
            '{"schema_version":"result-export.v1","schema_version":"result-export.v1"}',
            "AFE_RESULT_DUPLICATE_KEY",
        ),
        ('{"schema_version":"result-export.v1","value":NaN}', "AFE_RESULT_NUMBER_INVALID"),
        ([], "AFE_RESULT_ROOT_INVALID"),
        ({"test_run": {}}, "AFE_RESULT_SCHEMA_VERSION_INVALID"),
    ],
)
def test_invalid_json_envelopes_fail_closed(tmp_path: Path, payload: Any, code: str) -> None:
    result = collect_payload(tmp_path, payload)
    assert result.status is CollectionStatus.REJECTED
    assert result.rejected_records[0].code == code


def test_size_node_depth_and_normalization_limits_are_enforced(
    tmp_path: Path, repository_root: Path
) -> None:
    oversized = collect_payload(tmp_path, b" " * (MAX_AFE_RESULT_BYTES + 1))
    assert oversized.rejected_records[0].code == "AFE_RESULT_SIZE_LIMIT"

    document = sample_document(repository_root)
    nodes = collect_payload(tmp_path, document, max_nodes=3)
    assert nodes.rejected_records[0].code == "AFE_RESULT_NODE_LIMIT"
    depth = collect_payload(tmp_path, document, max_depth=2)
    assert depth.rejected_records[0].code == "AFE_RESULT_DEPTH_LIMIT"

    document["test_run"]["metadata"]["software_version"] = "v" * 121
    normalized = collect_payload(tmp_path, document)
    assert normalized.rejected_records[0].code == "AFE_RESULT_NORMALIZATION_INVALID"


def test_request_limits_and_artifact_boundary_validate_before_normalization(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError, match="UTC offset"):
        AnalogValidationCollectionRequest(
            source_path="result.json",
            execution_context=ExecutionContext(commit_sha=COMMIT),
            collected_at=datetime(2026, 8, 31, 13, 0),
            trust="unsigned_local",
        )
    with pytest.raises(ValueError, match="limits must be positive"):
        AnalogValidationResultCollector(ArtifactRegistry(tmp_path), max_nodes=0)

    result = AnalogValidationResultCollector(ArtifactRegistry(tmp_path)).collect(
        request("../result.json")
    )
    assert result.rejected_records[0].code == "ARTIFACT_BOUNDARY"
    assert result.artifacts == []


def test_low_level_json_guards_are_defensive(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(AnalogValidationParseError, match="duplicate"):
        _object_without_duplicates([("a", 1), ("a", 2)])
    with pytest.raises(AnalogValidationParseError, match="Infinity"):
        _reject_json_constant("Infinity")
    assert _error_location(("points", 1, "index")) == "$.points[1].index"

    monkeypatch.setattr(
        "forgegate.collectors.analog_validation.json.loads",
        lambda *args, **kwargs: (_ for _ in ()).throw(RecursionError("deep")),
    )
    with pytest.raises(AnalogValidationParseError, match="invalid result-export JSON"):
        _load_json(b"{}")


def test_contract_helpers_and_enum_instances_cover_strict_type_edges(
    repository_root: Path,
) -> None:
    assert _identifier("name", "value") == "value"
    with pytest.raises(ValueError, match="stripped"):
        _identifier("name", " value")

    assert _number("number", 2) == 2
    assert _number("number", 2.5) == 2.5
    for invalid in (True, math.inf, "2"):
        with pytest.raises(ValueError):
            _number("number", invalid)

    assert _timestamp("time", "2026-08-31T00:00:00Z").tzinfo is not None
    with pytest.raises(ValueError, match="Z suffix"):
        _timestamp("time", "2026-08-31T00:00:00+00:00")
    with pytest.raises(ValueError, match="valid timestamp"):
        _timestamp("time", "badZ")

    for scalar in (None, "text", True, 1, 1.5):
        assert (
            AfeExportValue.model_validate(
                {"name": "value", "value": scalar, "unit": "unitless"}
            ).value
            == scalar
        )
    with pytest.raises(ValidationError, match="finite JSON scalar"):
        AfeExportValue.model_validate({"name": "value", "value": math.inf, "unit": "unitless"})

    document = sample_document(repository_root)
    document["test_run"]["metadata"]["evidence_source"] = AfeEvidenceSource.SYNTHETIC
    document["test_run"]["outcome"] = AfeTestRunOutcome.PASS
    document["points"][0]["disposition"] = AfePointDisposition.INCLUDED
    document["points"][0]["references"][0]["source"] = AfeEvidenceSource.SYNTHETIC
    document["criteria"]["results"][0]["actual_value"] = 2
    document["criteria"]["results"][0]["lower_limit"] = None
    model = AfeResultExportV1.model_validate(document)
    assert model.test_run.outcome is AfeTestRunOutcome.PASS


def test_committed_compatibility_schema_matches_collector_contract(
    repository_root: Path,
) -> None:
    expected = json.dumps(AFE_RESULT_JSON_SCHEMA, indent=2, sort_keys=True) + "\n"
    path = repository_root / "schemas/analog-validation.result-export.v1.schema.json"
    assert path.read_text(encoding="utf-8") == expected


def test_cli_collects_valid_and_rejects_invalid_results(
    repository_root: Path, tmp_path: Path
) -> None:
    valid = runner.invoke(
        app,
        [
            "collect-analog-validation",
            "artifacts/analog-validation-result.json",
            "--root",
            str(repository_root / "examples/sample-python-api"),
            "--commit",
            COMMIT,
            "--collected-at",
            "2026-08-31T13:00:00Z",
        ],
    )
    assert valid.exit_code == 0
    assert json.loads(valid.stdout)["status"] == "COMPLETE"

    (tmp_path / "invalid.json").write_text(
        '{"schema_version":"result-export.v2"}', encoding="utf-8"
    )
    invalid = runner.invoke(
        app,
        [
            "collect-analog-validation",
            "invalid.json",
            "--root",
            str(tmp_path),
            "--commit",
            COMMIT,
            "--collected-at",
            "2026-08-31T13:00:00Z",
        ],
    )
    assert invalid.exit_code == 3
    assert json.loads(invalid.stdout)["status"] == "REJECTED"

    bad_timestamp = runner.invoke(
        app,
        [
            "collect-analog-validation",
            "invalid.json",
            "--root",
            str(tmp_path),
            "--commit",
            COMMIT,
            "--collected-at",
            "not-a-time",
        ],
    )
    assert bad_timestamp.exit_code == 3
    assert "Invalid isoformat string" in bad_timestamp.output
