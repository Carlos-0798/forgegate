import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from forgegate.artifacts import ArtifactRegistry
from forgegate.collectors import CollectionStatus, SarifCollectionRequest, SarifCollector
from forgegate.collectors.sarif import (
    SarifParseError,
    _load_json,
    _nonnegative_int,
    _object_without_duplicates,
    _positive_int,
    _reject_json_constant,
    _required_list,
    _required_string,
)
from forgegate.domain.models import ExecutionContext

COMMIT = "c" * 40
COLLECTED_AT = datetime(2026, 8, 30, 23, 0, tzinfo=UTC)


def request(source_path: str = "report.sarif") -> SarifCollectionRequest:
    return SarifCollectionRequest(
        source_path=source_path,
        execution_context=ExecutionContext(commit_sha=COMMIT),
        collected_at=COLLECTED_AT,
        trust="claimed_ci_metadata",
        verification_level="ci_validated",
    )


def base_document(*, results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if results is None:
        results = [
            {
                "ruleId": "R001",
                "message": {"text": "Review the finding."},
            }
        ]
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Scanner",
                        "version": "4.5.6",
                        "rules": [
                            {
                                "id": "R001",
                                "defaultConfiguration": {"level": "note"},
                            }
                        ],
                    }
                },
                "invocations": [{"executionSuccessful": True}],
                "results": results,
            }
        ],
    }


def collect_payload(
    tmp_path: Path,
    payload: Any,
    **limits: int,
):
    if isinstance(payload, str):
        content = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        content = payload
    else:
        content = json.dumps(payload).encode("utf-8")
    (tmp_path / "report.sarif").write_bytes(content)
    return SarifCollector(ArtifactRegistry(tmp_path), **limits).collect(request())


def rejection_code(tmp_path: Path, payload: Any) -> str:
    result = collect_payload(tmp_path, payload)
    assert result.status is CollectionStatus.REJECTED
    assert result.evidence == []
    assert len(result.artifacts) == 1
    return result.rejected_records[0].code


def golden_projection(result: Any) -> dict[str, Any]:
    payload = result.model_dump(mode="json")
    return {
        "collector_name": payload["collector_name"],
        "collector_version": payload["collector_version"],
        "status": payload["status"],
        "artifact": payload["artifacts"][0],
        "evidence": [
            {
                "evidence_id": record["evidence_id"],
                "kind": record["kind"],
                "scope": record["scope"],
                "value": record["value"],
                "status": record["status"],
                "source_tool": record["source_tool"],
                "source_version": record["source_version"],
                "tags": record["tags"],
            }
            for record in payload["evidence"]
        ],
        "warnings": payload["warnings"],
        "rejected_records": payload["rejected_records"],
    }


def test_sample_sarif_normalizes_summary_findings_and_tool(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = SarifCollector(ArtifactRegistry(root)).collect(request("artifacts/security.sarif"))

    assert result.status is CollectionStatus.COMPLETE
    assert result.warnings == []
    assert len(result.evidence) == 3
    summary, active, suppressed = result.evidence
    assert summary.kind == "static_analysis.summary"
    assert summary.value["total"] == 2
    assert summary.value["active"] == 1
    assert summary.value["suppressed"] == 1
    assert summary.value["by_level"] == {"error": 1, "warning": 1, "note": 0, "none": 0}
    assert summary.value["tools"][0]["name"] == "SampleScanner"
    assert active.status == "fail"
    assert active.value["rule"]["tags"] == ["security", "credential"]
    assert active.value["fingerprint"]["source"].startswith("fingerprints.")
    assert active.value["locations"][0]["physical"]["region"]["start_line"] == 2
    assert suppressed.status == "suppressed"
    assert suppressed.value["rule_id"] == "S002"
    assert suppressed.value["locations"][0]["logical"][0]["fully_qualified_name"].endswith(".DEBUG")
    assert result.artifacts[0].sha256 == summary.artifact.sha256


def test_sample_sarif_matches_golden_projection(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = SarifCollector(ArtifactRegistry(root)).collect(request("artifacts/security.sarif"))
    golden = json.loads(
        (repository_root / "tests/golden/sarif_summary.json").read_text(encoding="utf-8")
    )
    assert golden_projection(result) == golden


def test_zero_result_report_emits_explicit_summary_evidence(tmp_path: Path) -> None:
    result = collect_payload(tmp_path, base_document(results=[]))
    assert result.status is CollectionStatus.COMPLETE
    assert len(result.evidence) == 1
    assert result.evidence[0].value["total"] == 0
    assert result.evidence[0].value["active"] == 0
    assert result.evidence[0].status == "observed"


def test_defaults_rule_index_and_derived_fingerprint_are_deterministic(tmp_path: Path) -> None:
    document = base_document(
        results=[
            {
                "ruleIndex": 0,
                "message": {"markdown": "A **finding**"},
                "locations": [
                    {
                        "physicalLocation": {"region": {"startColumn": 3}},
                        "logicalLocations": [{"name": "entry", "kind": "function"}],
                    }
                ],
            }
        ]
    )
    first = collect_payload(tmp_path, document)
    second = collect_payload(tmp_path, document)
    finding = first.evidence[1]
    assert finding.value["rule_id"] == "R001"
    assert finding.value["level"] == "note"
    assert finding.value["kind"] == "fail"
    assert finding.value["tool"]["semantic_version"] is None
    assert finding.value["fingerprint"]["source"] == "forgegate-derived-sha256"
    assert finding.value["fingerprint"] == second.evidence[1].value["fingerprint"]


def test_direct_unregistered_rule_and_unknown_tool_version_are_preserved(tmp_path: Path) -> None:
    document = base_document()
    driver = document["runs"][0]["tool"]["driver"]
    driver.pop("version")
    document["runs"][0]["results"] = [
        {
            "ruleId": "OUTSIDE-TABLE",
            "level": "none",
            "kind": "informational",
            "message": {"text": "Informational result"},
            "fingerprints": {"z": "last", "a": "selected"},
        }
    ]
    result = collect_payload(tmp_path, document)
    finding = result.evidence[1]
    assert finding.source_version == "unknown"
    assert finding.value["rule"] is None
    assert finding.value["fingerprint"] == {"source": "fingerprints.a", "value": "selected"}


def test_non_normalized_details_and_unrecognized_schema_are_audited(tmp_path: Path) -> None:
    document = base_document()
    document["$schema"] = "https://example.invalid/different-schema.json"
    document["runs"][0]["results"][0]["fixes"] = []
    document["runs"][0]["results"][0]["codeFlows"] = []
    result = collect_payload(tmp_path, document)
    assert [warning.code for warning in result.warnings] == [
        "SARIF_SCHEMA_URI_UNRECOGNIZED",
        "SARIF_DETAIL_NOT_NORMALIZED",
    ]
    assert "codeFlows, fixes" in result.warnings[1].message


def test_optional_tool_and_rule_metadata_can_be_absent(tmp_path: Path) -> None:
    document = base_document()
    run = document["runs"][0]
    run.pop("invocations")
    rule = run["tool"]["driver"]["rules"][0]
    rule["defaultConfiguration"] = {}
    rule["properties"] = {}
    result = collect_payload(tmp_path, document)
    assert result.status is CollectionStatus.COMPLETE
    assert result.evidence[1].value["level"] == "warning"
    assert result.evidence[1].value["rule"]["tags"] == []


def test_suppressions_apply_only_when_accepted(tmp_path: Path) -> None:
    document = base_document()
    document["runs"][0]["results"][0]["suppressions"] = [
        {"kind": "inSource", "status": "underReview"},
        {"justification": "Default kind and status are accepted."},
    ]
    result = collect_payload(tmp_path, document)
    finding = result.evidence[1]
    assert finding.status == "suppressed"
    assert finding.value["suppression_states"][0]["status"] == "underReview"
    assert finding.value["suppression_states"][1]["kind"] == "external"


def test_request_and_collector_limits_validate_before_collection(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="UTC offset"):
        SarifCollectionRequest(
            source_path="report.sarif",
            execution_context=ExecutionContext(commit_sha=COMMIT),
            collected_at=datetime(2026, 8, 30, 23, 0),
            trust="unsigned_local",
            verification_level="declared",
        )
    with pytest.raises(ValueError, match="limits must be positive"):
        SarifCollector(ArtifactRegistry(tmp_path), max_nodes=0)


def test_artifact_boundary_failure_is_a_rejection(tmp_path: Path) -> None:
    result = SarifCollector(ArtifactRegistry(tmp_path)).collect(request("../report.sarif"))
    assert result.rejected_records[0].code == "ARTIFACT_BOUNDARY"
    assert result.artifacts == []


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"\xff", "SARIF_UNSUPPORTED_ENCODING"),
        (b'{"version":"2.1.0","runs":[]}\x00', "SARIF_UNSUPPORTED_ENCODING"),
        ("{", "SARIF_JSON_INVALID"),
        ('{"version":"2.1.0","version":"2.1.0","runs":[]}', "SARIF_DUPLICATE_KEY"),
        ('{"version":"2.1.0","runs":[],"number":NaN}', "SARIF_NUMBER_INVALID"),
        ([], "SARIF_ROOT_INVALID"),
        ({"runs": []}, "SARIF_VERSION_INVALID"),
        ({"version": "2.2.0", "runs": []}, "SARIF_VERSION_UNSUPPORTED"),
        ({"version": "2.1.0"}, "SARIF_RUNS_INVALID"),
        ({"version": "2.1.0", "runs": {}}, "SARIF_RUNS_INVALID"),
        ({"version": "2.1.0", "runs": []}, "SARIF_RUNS_INVALID"),
        ({"version": "2.1.0", "runs": [1]}, "SARIF_RUN_INVALID"),
    ],
)
def test_invalid_document_envelope_is_rejected(tmp_path: Path, payload: Any, code: str) -> None:
    assert rejection_code(tmp_path, payload) == code


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (lambda d: d["runs"][0].update(tool=None), "SARIF_TOOL_INVALID"),
        (lambda d: d["runs"][0]["tool"].update(driver=None), "SARIF_TOOL_INVALID"),
        (lambda d: d["runs"][0]["tool"]["driver"].pop("name"), "SARIF_TOOL_INVALID"),
        (lambda d: d["runs"][0]["tool"]["driver"].update(name=""), "SARIF_TOOL_INVALID"),
        (lambda d: d["runs"][0]["tool"]["driver"].update(rules={}), "SARIF_RULES_INVALID"),
        (
            lambda d: d["runs"][0]["tool"]["driver"]["rules"].append({"id": "R001"}),
            "SARIF_RULE_DUPLICATE",
        ),
        (
            lambda d: d["runs"][0]["tool"]["driver"]["rules"][0].update(shortDescription={}),
            "SARIF_MESSAGE_INVALID",
        ),
        (
            lambda d: d["runs"][0]["tool"]["driver"]["rules"][0].update(properties={"tags": [""]}),
            "SARIF_RULE_INVALID",
        ),
        (lambda d: d["runs"][0].update(invocations={}), "SARIF_INVOCATIONS_INVALID"),
        (
            lambda d: d["runs"][0].update(invocations=[{}]),
            "SARIF_INVOCATION_INVALID",
        ),
        (
            lambda d: d["runs"][0]["invocations"][0].update(executionSuccessful=False),
            "SARIF_INVOCATION_FAILED",
        ),
        (lambda d: d["runs"][0].update(results={}), "SARIF_RESULTS_INVALID"),
    ],
)
def test_invalid_tool_rule_invocation_and_result_tables_are_rejected(
    tmp_path: Path, mutator: Any, code: str
) -> None:
    document = base_document()
    mutator(document)
    assert rejection_code(tmp_path, document) == code


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (1, "SARIF_RESULT_INVALID"),
        ({"message": {"text": "x"}}, "SARIF_RULE_REFERENCE_INVALID"),
        (
            {"ruleId": "R001", "ruleIndex": 1, "message": {"text": "x"}},
            "SARIF_RULE_REFERENCE_INVALID",
        ),
        (
            {"ruleId": "OTHER", "ruleIndex": 0, "message": {"text": "x"}},
            "SARIF_RULE_REFERENCE_CONFLICT",
        ),
        ({"ruleId": "R001", "level": "fatal", "message": {"text": "x"}}, "SARIF_LEVEL_INVALID"),
        ({"ruleId": "R001", "kind": "unknown", "message": {"text": "x"}}, "SARIF_KIND_INVALID"),
        ({"ruleId": "R001"}, "SARIF_MESSAGE_INVALID"),
        ({"ruleId": "R001", "message": {"id": "m1"}}, "SARIF_MESSAGE_INVALID"),
        (
            {"ruleId": "R001", "message": {"text": "x"}, "locations": {}},
            "SARIF_LOCATIONS_INVALID",
        ),
        (
            {"ruleId": "R001", "message": {"text": "x"}, "locations": [{}]},
            "SARIF_LOCATION_INVALID",
        ),
        (
            {
                "ruleId": "R001",
                "message": {"text": "x"},
                "locations": [{"physicalLocation": {}}],
            },
            "SARIF_LOCATION_INVALID",
        ),
        (
            {
                "ruleId": "R001",
                "message": {"text": "x"},
                "locations": [
                    {"physicalLocation": {"artifactLocation": {}, "region": {"startLine": 1}}}
                ],
            },
            "SARIF_LOCATION_INVALID",
        ),
        (
            {
                "ruleId": "R001",
                "message": {"text": "x"},
                "locations": [{"physicalLocation": {"region": {}}}],
            },
            "SARIF_REGION_INVALID",
        ),
        (
            {
                "ruleId": "R001",
                "message": {"text": "x"},
                "locations": [{"physicalLocation": {"region": {"startLine": 3, "endLine": 2}}}],
            },
            "SARIF_REGION_INVALID",
        ),
        (
            {
                "ruleId": "R001",
                "message": {"text": "x"},
                "locations": [
                    {
                        "physicalLocation": {
                            "region": {
                                "startLine": 2,
                                "endLine": 2,
                                "startColumn": 8,
                                "endColumn": 4,
                            }
                        }
                    }
                ],
            },
            "SARIF_REGION_INVALID",
        ),
        (
            {
                "ruleId": "R001",
                "message": {"text": "x"},
                "locations": [{"logicalLocations": []}],
            },
            "SARIF_LOCATION_INVALID",
        ),
        (
            {
                "ruleId": "R001",
                "message": {"text": "x"},
                "locations": [{"logicalLocations": [{"kind": "function"}]}],
            },
            "SARIF_LOCATION_INVALID",
        ),
        (
            {"ruleId": "R001", "message": {"text": "x"}, "fingerprints": []},
            "SARIF_FINGERPRINT_INVALID",
        ),
        (
            {"ruleId": "R001", "message": {"text": "x"}, "fingerprints": {"k": 1}},
            "SARIF_FINGERPRINT_INVALID",
        ),
        (
            {"ruleId": "R001", "message": {"text": "x"}, "suppressions": {}},
            "SARIF_SUPPRESSION_INVALID",
        ),
        (
            {
                "ruleId": "R001",
                "message": {"text": "x"},
                "suppressions": [{"status": "invalid"}],
            },
            "SARIF_SUPPRESSION_INVALID",
        ),
        (
            {"ruleId": "R001", "message": {"text": "x"}, "baselineState": "old"},
            "SARIF_BASELINE_STATE_INVALID",
        ),
    ],
)
def test_invalid_result_shapes_are_rejected(tmp_path: Path, result: Any, code: str) -> None:
    assert rejection_code(tmp_path, base_document(results=[result])) == code


def test_collection_resource_limits_are_enforced(tmp_path: Path) -> None:
    run_limit = collect_payload(tmp_path, base_document(), max_runs=1)
    assert run_limit.status is CollectionStatus.COMPLETE
    two_runs = base_document()
    two_runs["runs"].append(deepcopy(two_runs["runs"][0]))
    assert (
        collect_payload(tmp_path, two_runs, max_runs=1).rejected_records[0].code
        == "SARIF_RUN_LIMIT"
    )

    two_results = base_document()
    two_results["runs"][0]["results"].append({"ruleId": "R001", "message": {"text": "second"}})
    assert (
        collect_payload(tmp_path, two_results, max_results=1).rejected_records[0].code
        == "SARIF_RESULT_LIMIT"
    )
    assert (
        collect_payload(tmp_path, base_document(), max_nodes=5).rejected_records[0].code
        == "SARIF_NODE_LIMIT"
    )
    assert (
        collect_payload(tmp_path, base_document(), max_depth=2).rejected_records[0].code
        == "SARIF_DEPTH_LIMIT"
    )


def test_per_result_and_invocation_limits_are_enforced(tmp_path: Path) -> None:
    locations = [{"logicalLocations": [{"name": f"n{index}"}]} for index in range(33)]
    document = base_document(
        results=[{"ruleId": "R001", "message": {"text": "x"}, "locations": locations}]
    )
    assert rejection_code(tmp_path, document) == "SARIF_LOCATION_LIMIT"

    document = base_document()
    document["runs"][0]["invocations"] = [{"executionSuccessful": True}] * 33
    assert rejection_code(tmp_path, document) == "SARIF_INVOCATION_LIMIT"

    document = base_document()
    document["runs"][0]["results"][0]["suppressions"] = [{}] * 17
    assert rejection_code(tmp_path, document) == "SARIF_SUPPRESSION_LIMIT"


def test_rule_fingerprint_and_tag_limits_are_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("forgegate.collectors.sarif.DEFAULT_MAX_RULES", 1)
    document = base_document()
    document["runs"][0]["tool"]["driver"]["rules"].append({"id": "R002"})
    assert rejection_code(tmp_path, document) == "SARIF_RULE_LIMIT"

    document = base_document()
    document["runs"][0]["tool"]["driver"]["rules"][0]["properties"] = {
        "tags": [f"tag-{index}" for index in range(65)]
    }
    assert rejection_code(tmp_path, document) == "SARIF_RULE_INVALID"

    document = base_document()
    document["runs"][0]["results"][0]["fingerprints"] = {
        f"key-{index}": "value" for index in range(65)
    }
    assert rejection_code(tmp_path, document) == "SARIF_FINGERPRINT_INVALID"


def test_low_level_json_guards_are_defensive() -> None:
    with pytest.raises(SarifParseError, match="duplicate"):
        _object_without_duplicates([("a", 1), ("a", 2)])
    with pytest.raises(SarifParseError, match="Infinity"):
        _reject_json_constant("Infinity")
    with pytest.raises(SarifParseError, match="missing required field"):
        _required_string({}, "value", code="CODE", location="$.value", maximum=5)
    with pytest.raises(SarifParseError, match="missing required field"):
        _required_list({}, "items", code="CODE", location="$.items")
    with pytest.raises(SarifParseError, match="nonnegative"):
        _nonnegative_int(True, code="CODE", location="$.index")
    with pytest.raises(SarifParseError, match="positive"):
        _positive_int(0, code="CODE", location="$.line")
    with pytest.raises(SarifParseError, match="control characters"):
        _required_string(
            {"value": "bad\u0001text"},
            "value",
            code="CODE",
            location="$.value",
            maximum=20,
        )
    with pytest.raises(SarifParseError, match="invalid SARIF JSON"):
        _load_json(b"[")
