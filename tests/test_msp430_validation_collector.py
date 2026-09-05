import ast
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
from forgegate.assembly import CollectionResultLoader, assemble_evidence_bundle
from forgegate.cli import app
from forgegate.collectors import (
    CollectionStatus,
    Msp430ValidationCollectionRequest,
    Msp430ValidationReportCollector,
)
from forgegate.collectors.msp430_validation import (
    MAX_MSP430_REPORT_BYTES,
    MSP430_REPORT_JSON_SCHEMA,
    Msp430ValidationParseError,
    Msp430ValidationReportV1,
    _error_location,
    _finite_scalar,
    _load_json,
    _object_without_duplicates,
    _reject_json_constant,
    _timestamp,
)
from forgegate.domain.models import ExecutionContext

COMMIT = "0850241c1b2aa34704228146600501346ee81745"
COLLECTED_AT = datetime(2026, 9, 5, 18, 30, tzinfo=UTC)
runner = CliRunner()


def sample_document(repository_root: Path) -> dict[str, Any]:
    return json.loads(
        (
            repository_root / "examples/msp430-validation/artifacts/phase6-soak-report.json"
        ).read_text(encoding="utf-8")
    )


def request(source_path: str = "report.json", *, commit: str = COMMIT):
    return Msp430ValidationCollectionRequest(
        source_path=source_path,
        execution_context=ExecutionContext(commit_sha=commit),
        collected_at=COLLECTED_AT,
        trust="unsigned_local",
    )


def collect_payload(tmp_path: Path, payload: Any, **limits: int):
    if isinstance(payload, bytes):
        content = payload
    elif isinstance(payload, str):
        content = payload.encode("utf-8")
    else:
        content = json.dumps(payload).encode("utf-8")
    (tmp_path / "report.json").write_bytes(content)
    return Msp430ValidationReportCollector(ArtifactRegistry(tmp_path), **limits).collect(request())


def test_retained_phase6_fixture_normalizes_without_promoting_scope(
    repository_root: Path,
) -> None:
    root = repository_root / "examples/msp430-validation"
    result = Msp430ValidationReportCollector(ArtifactRegistry(root)).collect(
        request("artifacts/phase6-soak-report.json")
    )

    assert result.status is CollectionStatus.COMPLETE
    assert len(result.artifacts) == 1
    assert len(result.evidence) == 17
    run, *records = result.evidence
    assert run.kind == "msp430-validation.run"
    assert run.status == "PASS"
    assert run.verification_level == "system_observed"
    assert run.value["subject"]["commit_sha"] == COMMIT
    assert run.value["hardware"] == {
        "board_model": "MSP-EXP430FR6989",
        "board_connected": True,
        "access": "READ_ONLY_TELEMETRY",
        "connection_scope": "LAUNCHPAD_ONLY",
        "physical_measurements": False,
        "external_components": [],
        "instruments": [],
    }
    assert run.value["counts"] == {
        "checks": 7,
        "metrics": 9,
        "source_artifacts": 3,
        "corrections": 1,
    }
    assert {value.kind for value in records} == {
        "msp430-validation.check",
        "msp430-validation.metric",
    }
    assert all(value.artifact == result.artifacts[0] for value in result.evidence)
    assert all(value.execution_context.commit_sha == COMMIT for value in result.evidence)
    assert [value.code for value in result.warnings] == [
        "MSP430_HIL_SCOPE_RETAINED",
        "MSP430_REVIEW_CORRECTION_RETAINED",
    ]
    warning_message = result.warnings[0].message.lower()
    assert "physical" in warning_message or "bench" in warning_message


def test_collection_result_enters_retained_evidence_assembly(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    source = repository_root / "examples/msp430-validation/artifacts/phase6-soak-report.json"
    (artifacts / "phase6-soak-report.json").write_bytes(source.read_bytes())
    registry = ArtifactRegistry(tmp_path)
    result = Msp430ValidationReportCollector(registry).collect(
        request("artifacts/phase6-soak-report.json")
    )
    (tmp_path / "msp430.collection.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    loaded = CollectionResultLoader(registry).load("msp430.collection.json")
    assembly = assemble_evidence_bundle(
        [loaded],
        candidate_commit=COMMIT,
        generated_at=datetime(2026, 9, 5, 18, 31, tzinfo=UTC),
        producer="forgegate-test",
        producer_version="1",
        retain_warnings=True,
    )
    assert assembly.warning_disposition == "retained"
    assert assembly.bundle.candidate_commit == COMMIT
    assert len(assembly.bundle.evidence) == 17
    assert assembly.collections[0].collector_name == "msp430_validation_report"
    assert [value.code for value in assembly.collections[0].warnings] == [
        "MSP430_HIL_SCOPE_RETAINED",
        "MSP430_REVIEW_CORRECTION_RETAINED",
    ]


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (lambda value: value.update(extra=True), "MSP430_REPORT_CONTRACT_INVALID"),
        (
            lambda value: value["subject"].update(commit_sha="A" * 40),
            "MSP430_REPORT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["run"].update(ended_at="2026-08-30T00:00:00Z"),
            "MSP430_REPORT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["run"].update(duration_seconds=math.inf),
            "MSP430_REPORT_NUMBER_INVALID",
        ),
        (
            lambda value: value["checks"].append(deepcopy(value["checks"][0])),
            "MSP430_REPORT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["metrics"].append(deepcopy(value["metrics"][0])),
            "MSP430_REPORT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["source_artifacts"].append(deepcopy(value["source_artifacts"][0])),
            "MSP430_REPORT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["corrections"][0].update(original_artifact_sha256="0" * 64),
            "MSP430_REPORT_CONTRACT_INVALID",
        ),
        (
            lambda value: value.update(limitations=[]),
            "MSP430_REPORT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["hardware"].update(physical_measurements=True),
            "MSP430_REPORT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["hardware"].update(board_connected=False),
            "MSP430_REPORT_CONTRACT_INVALID",
        ),
        (
            lambda value: value["checks"][0].update(actual=[]),
            "MSP430_REPORT_CONTRACT_INVALID",
        ),
    ],
)
def test_contract_invariants_fail_closed(
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
    ("outcome", "status"),
    [
        ("PASS", "FAIL"),
        ("FAIL", "PASS"),
        ("INCOMPLETE", "PASS"),
        ("ERROR", "PASS"),
    ],
)
def test_outcome_requires_matching_check_status(
    tmp_path: Path,
    repository_root: Path,
    outcome: str,
    status: str,
) -> None:
    document = sample_document(repository_root)
    document["run"]["outcome"] = outcome
    document["checks"][0]["status"] = status
    result = collect_payload(tmp_path, document)
    assert result.status is CollectionStatus.REJECTED
    assert result.rejected_records[0].code == "MSP430_REPORT_CONTRACT_INVALID"


@pytest.mark.parametrize(
    ("evidence_level", "expected"),
    [("HOST_TEST", "host_tested"), ("TARGET_BUILD", "target_built")],
)
def test_non_hardware_levels_remain_non_hardware(
    tmp_path: Path,
    repository_root: Path,
    evidence_level: str,
    expected: str,
) -> None:
    document = sample_document(repository_root)
    document["run"]["evidence_level"] = evidence_level
    document["hardware"] = {
        "board_model": "MSP-EXP430FR6989",
        "board_connected": False,
        "access": "NOT_PERFORMED",
        "connection_scope": "NONE",
        "physical_measurements": False,
        "external_components": [],
        "instruments": [],
    }
    document["corrections"] = []
    result = collect_payload(tmp_path, document)
    assert result.status is CollectionStatus.COMPLETE
    assert {value.verification_level for value in result.evidence} == {expected}
    assert result.warnings == []


@pytest.mark.parametrize(
    ("calibration_status", "reference", "expected", "warning"),
    [
        ("CURRENT", "certificate-2026-01", "physically_verified", None),
        ("NOT_REQUIRED", None, "physically_verified", None),
        ("UNKNOWN", None, "system_observed", "MSP430_BENCH_EVIDENCE_CAPPED"),
    ],
)
def test_bench_measurement_requires_instrument_provenance_for_physical_level(
    tmp_path: Path,
    repository_root: Path,
    calibration_status: str,
    reference: str | None,
    expected: str,
    warning: str | None,
) -> None:
    document = sample_document(repository_root)
    document["run"]["evidence_level"] = "BENCH_MEASURED"
    document["hardware"] = {
        "board_model": "MSP-EXP430FR6989",
        "board_connected": True,
        "access": "READ_ONLY_TELEMETRY",
        "connection_scope": "EXTERNAL_BENCH",
        "physical_measurements": True,
        "external_components": ["INA219 test fixture"],
        "instruments": [
            {
                "instrument_id": "bench-dmm-01",
                "model": "traceable-dmm",
                "calibration_status": calibration_status,
                "calibration_reference": reference,
            }
        ],
    }
    document["corrections"] = []
    result = collect_payload(tmp_path, document)
    assert result.status is CollectionStatus.COMPLETE
    assert {value.verification_level for value in result.evidence} == {expected}
    assert ([value.code for value in result.warnings] or [None]) == [warning]


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"\xff", "MSP430_REPORT_UNSUPPORTED_ENCODING"),
        (
            b'{"schema_version":"forgegate.msp430-validation-report.v1"}\x00',
            "MSP430_REPORT_UNSUPPORTED_ENCODING",
        ),
        ("{", "MSP430_REPORT_JSON_INVALID"),
        (
            '{"schema_version":"forgegate.msp430-validation-report.v1","schema_version":"forgegate.msp430-validation-report.v1"}',
            "MSP430_REPORT_DUPLICATE_KEY",
        ),
        (
            '{"schema_version":"forgegate.msp430-validation-report.v1","value":NaN}',
            "MSP430_REPORT_NUMBER_INVALID",
        ),
        ([], "MSP430_REPORT_ROOT_INVALID"),
        ({"producer": {}}, "MSP430_REPORT_SCHEMA_VERSION_INVALID"),
        (
            {"schema_version": "forgegate.msp430-validation-report.v2"},
            "MSP430_REPORT_SCHEMA_VERSION_UNSUPPORTED",
        ),
    ],
)
def test_invalid_json_envelopes_fail_closed(tmp_path: Path, payload: Any, code: str) -> None:
    result = collect_payload(tmp_path, payload)
    assert result.status is CollectionStatus.REJECTED
    assert result.rejected_records[0].code == code


def test_limits_boundary_and_commit_mismatch_are_rejected(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    oversized = collect_payload(tmp_path, b" " * (MAX_MSP430_REPORT_BYTES + 1))
    assert oversized.rejected_records[0].code == "MSP430_REPORT_SIZE_LIMIT"
    nodes = collect_payload(tmp_path, sample_document(repository_root), max_nodes=3)
    assert nodes.rejected_records[0].code == "MSP430_REPORT_NODE_LIMIT"
    depth = collect_payload(tmp_path, sample_document(repository_root), max_depth=2)
    assert depth.rejected_records[0].code == "MSP430_REPORT_DEPTH_LIMIT"

    boundary = Msp430ValidationReportCollector(ArtifactRegistry(tmp_path)).collect(
        request("../report.json")
    )
    assert boundary.rejected_records[0].code == "ARTIFACT_BOUNDARY"
    (tmp_path / "report.json").write_text(
        json.dumps(sample_document(repository_root)), encoding="utf-8"
    )
    mismatch = Msp430ValidationReportCollector(ArtifactRegistry(tmp_path)).collect(
        request(commit="a" * 40)
    )
    assert mismatch.rejected_records[0].code == "MSP430_REPORT_COMMIT_MISMATCH"

    with pytest.raises(ValueError, match="limits must be positive"):
        Msp430ValidationReportCollector(ArtifactRegistry(tmp_path), max_depth=0)
    with pytest.raises(ValidationError, match="UTC offset"):
        Msp430ValidationCollectionRequest(
            source_path="report.json",
            execution_context=ExecutionContext(commit_sha=COMMIT),
            collected_at=datetime(2026, 9, 5, 18, 30),
            trust="unsigned_local",
        )


def test_low_level_guards_are_defensive() -> None:
    assert _timestamp("time", "2026-09-05T18:30:00Z").tzinfo is not None
    with pytest.raises(ValueError, match="UTC offset"):
        _timestamp("time", "2026-09-05T18:30:00")
    for value in (None, "text", True, 1, 1.5):
        assert _finite_scalar("value", value) == value
    for value in ([], math.inf):
        with pytest.raises(ValueError, match="finite JSON scalar"):
            _finite_scalar("value", value)
    with pytest.raises(Msp430ValidationParseError, match="duplicate"):
        _object_without_duplicates([("a", 1), ("a", 2)])
    with pytest.raises(Msp430ValidationParseError, match="Infinity"):
        _reject_json_constant("Infinity")
    assert _error_location(("checks", 1, "id")) == "$.checks[1].id"
    with pytest.raises(Msp430ValidationParseError, match="invalid MSP430 report JSON"):
        _load_json(b"{")


def test_schema_cli_and_no_hardware_io_contract(repository_root: Path, tmp_path: Path) -> None:
    expected = json.dumps(MSP430_REPORT_JSON_SCHEMA, indent=2, sort_keys=True) + "\n"
    schema_path = repository_root / "schemas/forgegate.msp430-validation-report.v1.schema.json"
    assert schema_path.read_text(encoding="utf-8") == expected

    valid = runner.invoke(
        app,
        [
            "collect-msp430-validation",
            "artifacts/phase6-soak-report.json",
            "--root",
            str(repository_root / "examples/msp430-validation"),
            "--commit",
            COMMIT,
            "--collected-at",
            "2026-09-05T18:30:00Z",
        ],
    )
    assert valid.exit_code == 0, valid.output
    assert json.loads(valid.stdout)["status"] == "COMPLETE"

    (tmp_path / "invalid.json").write_text(
        '{"schema_version":"forgegate.msp430-validation-report.v2"}',
        encoding="utf-8",
    )
    invalid = runner.invoke(
        app,
        [
            "collect-msp430-validation",
            "invalid.json",
            "--root",
            str(tmp_path),
            "--commit",
            COMMIT,
            "--collected-at",
            "2026-09-05T18:30:00Z",
        ],
    )
    assert invalid.exit_code == 3
    assert json.loads(invalid.stdout)["status"] == "REJECTED"

    source_path = repository_root / "src/forgegate/collectors/msp430_validation.py"
    imports = {
        node.names[0].name.split(".", 1)[0]
        for node in ast.walk(ast.parse(source_path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Import)
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(ast.parse(source_path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
    }
    assert "serial" not in imports
    assert "socket" not in imports
    assert Msp430ValidationReportV1.model_validate(sample_document(repository_root))
