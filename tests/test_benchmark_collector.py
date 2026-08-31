import json
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from forgegate.artifacts import ArtifactRegistry
from forgegate.collectors import (
    BenchmarkCollectionRequest,
    BenchmarkJsonCollector,
    CollectionStatus,
)
from forgegate.collectors.benchmark import (
    BENCHMARK_JSON_SCHEMA,
    BenchmarkParseError,
    _load_json,
    _mapping,
    _metric_name_is_valid,
    _number,
    _object_without_duplicates,
    _reject_json_constant,
    _required_list,
    _required_number,
    _required_string,
)
from forgegate.domain.models import ExecutionContext

COMMIT = "d" * 40
COLLECTED_AT = datetime(2026, 8, 31, 0, 0, tzinfo=UTC)


def request(
    source_path: str = "benchmark.json", *, scope: str = "repository"
) -> BenchmarkCollectionRequest:
    return BenchmarkCollectionRequest(
        source_path=source_path,
        execution_context=ExecutionContext(commit_sha=COMMIT),
        collected_at=COLLECTED_AT,
        trust="claimed_ci_metadata",
        verification_level="ci_validated",
        scope=scope,
    )


def base_document(*, metrics: list[Any] | None = None) -> dict[str, Any]:
    if metrics is None:
        metrics = [{"name": "latency.p95", "value": 12.5, "unit": "ms"}]
    return {
        "schema_version": "forgegate.benchmark.v1",
        "tool": {"name": "bench-tool", "version": "2.0.0"},
        "metrics": metrics,
    }


def collect_payload(
    tmp_path: Path,
    payload: Any,
    *,
    scope: str = "repository",
    **limits: int,
):
    if isinstance(payload, str):
        content = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        content = payload
    else:
        content = json.dumps(payload).encode("utf-8")
    (tmp_path / "benchmark.json").write_bytes(content)
    collector = BenchmarkJsonCollector(ArtifactRegistry(tmp_path), **limits)
    return collector.collect(request(scope=scope))


def rejection_code(tmp_path: Path, payload: Any, **limits: int) -> str:
    result = collect_payload(tmp_path, payload, **limits)
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
                "unit": record["unit"],
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


def test_sample_benchmark_normalizes_metrics_and_provenance(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = BenchmarkJsonCollector(ArtifactRegistry(root)).collect(
        request("artifacts/benchmark.json")
    )

    assert result.status is CollectionStatus.COMPLETE
    assert result.warnings == []
    assert result.rejected_records == []
    assert len(result.evidence) == 3
    latency, throughput, memory = result.evidence
    assert latency.kind == "benchmark.metric"
    assert latency.scope == "endpoint:GET /health"
    assert latency.unit == "ms"
    assert latency.value == {
        "metric": "api.request_latency.p95",
        "value": 42.75,
        "baseline": 40.0,
        "tolerance": {"value": 10.0, "mode": "percent"},
    }
    assert throughput.value["value"] == 1250
    assert throughput.value["tolerance"] == {"value": 100, "mode": "absolute"}
    assert memory.value["baseline"] is None
    assert memory.value["tolerance"] is None
    assert all(record.source_tool == "sample-benchmark" for record in result.evidence)
    assert all(record.artifact == result.artifacts[0] for record in result.evidence)


def test_sample_benchmark_matches_golden_projection(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = BenchmarkJsonCollector(ArtifactRegistry(root)).collect(
        request("artifacts/benchmark.json")
    )
    golden = json.loads(
        (repository_root / "tests/golden/benchmark_metrics.json").read_text(encoding="utf-8")
    )
    assert golden_projection(result) == golden


def test_committed_benchmark_schema_matches_collector_contract(repository_root: Path) -> None:
    expected = json.dumps(BENCHMARK_JSON_SCHEMA, indent=2, sort_keys=True) + "\n"
    path = repository_root / "schemas/forgegate.benchmark.v1.schema.json"
    assert path.read_text(encoding="utf-8") == expected


def test_default_scope_and_evidence_ids_are_deterministic(tmp_path: Path) -> None:
    document = base_document(
        metrics=[
            {"name": "signed.delta", "value": -2, "unit": "points"},
            {"name": "signed.delta", "value": 0, "unit": "points", "scope": "variant:b"},
        ]
    )
    first = collect_payload(tmp_path, document, scope="suite:default")
    second = collect_payload(tmp_path, document, scope="suite:default")
    assert [record.scope for record in first.evidence] == ["suite:default", "variant:b"]
    assert [record.evidence_id for record in first.evidence] == [
        record.evidence_id for record in second.evidence
    ]
    assert first.evidence[0].value["value"] == -2


def test_request_and_collector_limits_validate_before_collection(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="UTC offset"):
        BenchmarkCollectionRequest(
            source_path="benchmark.json",
            execution_context=ExecutionContext(commit_sha=COMMIT),
            collected_at=datetime(2026, 8, 31, 0, 0),
            trust="unsigned_local",
            verification_level="declared",
        )
    with pytest.raises(ValueError, match="limits must be positive"):
        BenchmarkJsonCollector(ArtifactRegistry(tmp_path), max_metrics=0)


def test_artifact_boundary_failure_is_a_rejection(tmp_path: Path) -> None:
    result = BenchmarkJsonCollector(ArtifactRegistry(tmp_path)).collect(
        request("../benchmark.json")
    )
    assert result.rejected_records[0].code == "ARTIFACT_BOUNDARY"
    assert result.artifacts == []


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"\xff", "BENCHMARK_UNSUPPORTED_ENCODING"),
        (b'{"schema_version":"forgegate.benchmark.v1"}\x00', "BENCHMARK_UNSUPPORTED_ENCODING"),
        ("{", "BENCHMARK_JSON_INVALID"),
        (
            '{"schema_version":"forgegate.benchmark.v1","schema_version":"forgegate.benchmark.v1"}',
            "BENCHMARK_DUPLICATE_KEY",
        ),
        (
            '{"schema_version":"forgegate.benchmark.v1","tool":{},"metrics":[],"x":NaN}',
            "BENCHMARK_NUMBER_INVALID",
        ),
        ([], "BENCHMARK_ROOT_INVALID"),
        ({"unknown": True}, "BENCHMARK_ROOT_INVALID"),
        ({"tool": {}, "metrics": []}, "BENCHMARK_SCHEMA_VERSION_INVALID"),
        (
            {"schema_version": "forgegate.benchmark.v2", "tool": {}, "metrics": []},
            "BENCHMARK_SCHEMA_VERSION_UNSUPPORTED",
        ),
        (
            {"schema_version": "forgegate.benchmark.v1", "tool": {}},
            "BENCHMARK_TOOL_INVALID",
        ),
        (
            {"schema_version": "forgegate.benchmark.v1", "tool": None, "metrics": []},
            "BENCHMARK_TOOL_INVALID",
        ),
        (
            {
                "schema_version": "forgegate.benchmark.v1",
                "tool": {"name": "tool", "version": "1", "extra": True},
                "metrics": [],
            },
            "BENCHMARK_TOOL_INVALID",
        ),
        (
            {
                "schema_version": "forgegate.benchmark.v1",
                "tool": {"name": "", "version": "1"},
                "metrics": [],
            },
            "BENCHMARK_TOOL_INVALID",
        ),
        (
            {
                "schema_version": "forgegate.benchmark.v1",
                "tool": {"name": "tool", "version": ""},
                "metrics": [],
            },
            "BENCHMARK_TOOL_INVALID",
        ),
        (
            {
                "schema_version": "forgegate.benchmark.v1",
                "tool": {"name": "tool", "version": "1"},
            },
            "BENCHMARK_METRICS_INVALID",
        ),
        (
            {
                "schema_version": "forgegate.benchmark.v1",
                "tool": {"name": "tool", "version": "1"},
                "metrics": {},
            },
            "BENCHMARK_METRICS_INVALID",
        ),
        (
            {
                "schema_version": "forgegate.benchmark.v1",
                "tool": {"name": "tool", "version": "1"},
                "metrics": [],
            },
            "BENCHMARK_METRICS_EMPTY",
        ),
    ],
)
def test_invalid_document_envelope_is_rejected(tmp_path: Path, payload: Any, code: str) -> None:
    assert rejection_code(tmp_path, payload) == code


@pytest.mark.parametrize(
    ("metric", "code"),
    [
        (1, "BENCHMARK_METRIC_INVALID"),
        (
            {"name": "latency", "value": 1, "unit": "ms", "unknown": True},
            "BENCHMARK_METRIC_INVALID",
        ),
        ({"value": 1, "unit": "ms"}, "BENCHMARK_METRIC_INVALID"),
        ({"name": "1latency", "value": 1, "unit": "ms"}, "BENCHMARK_METRIC_INVALID"),
        ({"name": "lätency", "value": 1, "unit": "ms"}, "BENCHMARK_METRIC_INVALID"),
        ({"name": "latency p95", "value": 1, "unit": "ms"}, "BENCHMARK_METRIC_INVALID"),
        ({"name": "latency", "unit": "ms"}, "BENCHMARK_VALUE_INVALID"),
        ({"name": "latency", "value": True, "unit": "ms"}, "BENCHMARK_VALUE_INVALID"),
        ({"name": "latency", "value": "1", "unit": "ms"}, "BENCHMARK_VALUE_INVALID"),
        ({"name": "latency", "value": 1, "unit": ""}, "BENCHMARK_UNIT_INVALID"),
        ({"name": "latency", "value": 1, "unit": "ms\u0001"}, "BENCHMARK_UNIT_INVALID"),
        (
            {"name": "latency", "value": 1, "unit": "ms", "scope": ""},
            "BENCHMARK_SCOPE_INVALID",
        ),
        (
            {"name": "latency", "value": 1, "unit": "ms", "baseline": False},
            "BENCHMARK_BASELINE_INVALID",
        ),
        (
            {"name": "latency", "value": 1, "unit": "ms", "tolerance": {}},
            "BENCHMARK_TOLERANCE_INVALID",
        ),
        (
            {
                "name": "latency",
                "value": 1,
                "unit": "ms",
                "baseline": 1,
                "tolerance": {"value": 1, "mode": "absolute", "extra": True},
            },
            "BENCHMARK_TOLERANCE_INVALID",
        ),
        (
            {
                "name": "latency",
                "value": 1,
                "unit": "ms",
                "baseline": 1,
                "tolerance": {"mode": "absolute"},
            },
            "BENCHMARK_TOLERANCE_INVALID",
        ),
        (
            {
                "name": "latency",
                "value": 1,
                "unit": "ms",
                "baseline": 1,
                "tolerance": {"value": -1, "mode": "absolute"},
            },
            "BENCHMARK_TOLERANCE_INVALID",
        ),
        (
            {
                "name": "latency",
                "value": 1,
                "unit": "ms",
                "baseline": 1,
                "tolerance": {"value": 1},
            },
            "BENCHMARK_TOLERANCE_INVALID",
        ),
        (
            {
                "name": "latency",
                "value": 1,
                "unit": "ms",
                "baseline": 1,
                "tolerance": {"value": 1, "mode": "relative"},
            },
            "BENCHMARK_TOLERANCE_INVALID",
        ),
        (
            {
                "name": "latency",
                "value": 1,
                "unit": "ms",
                "tolerance": {"value": 1, "mode": "absolute"},
            },
            "BENCHMARK_TOLERANCE_WITHOUT_BASELINE",
        ),
    ],
)
def test_invalid_metric_shapes_are_rejected(tmp_path: Path, metric: Any, code: str) -> None:
    assert rejection_code(tmp_path, base_document(metrics=[metric])) == code


@pytest.mark.parametrize(
    ("number", "code"),
    [
        ("1e309", "BENCHMARK_VALUE_INVALID"),
        ("1e-999", "BENCHMARK_VALUE_INVALID"),
        ("-1e309", "BENCHMARK_VALUE_INVALID"),
    ],
)
def test_extreme_decimal_values_are_rejected(tmp_path: Path, number: str, code: str) -> None:
    payload = (
        '{"schema_version":"forgegate.benchmark.v1",'
        '"tool":{"name":"tool","version":"1"},'
        f'"metrics":[{{"name":"latency","value":{number},"unit":"ms"}}]}}'
    )
    assert rejection_code(tmp_path, payload) == code


def test_excessive_integer_digits_are_rejected_as_invalid_json(tmp_path: Path) -> None:
    payload = (
        '{"schema_version":"forgegate.benchmark.v1",'
        '"tool":{"name":"tool","version":"1"},'
        f'"metrics":[{{"name":"latency","value":{"1" * 5000},"unit":"ms"}}]}}'
    )
    assert rejection_code(tmp_path, payload) == "BENCHMARK_JSON_INVALID"


def test_duplicate_metric_identity_is_rejected_but_distinct_scopes_are_allowed(
    tmp_path: Path,
) -> None:
    metric = {"name": "latency", "value": 1, "unit": "ms"}
    duplicate = base_document(metrics=[metric, deepcopy(metric)])
    assert rejection_code(tmp_path, duplicate) == "BENCHMARK_METRIC_DUPLICATE"

    scoped = base_document(metrics=[metric, {**metric, "scope": "variant:b"}])
    assert collect_payload(tmp_path, scoped).status is CollectionStatus.COMPLETE


def test_collection_resource_limits_are_enforced(tmp_path: Path) -> None:
    document = base_document(
        metrics=[
            {"name": "metric.a", "value": 1, "unit": "count"},
            {"name": "metric.b", "value": 2, "unit": "count"},
        ]
    )
    assert rejection_code(tmp_path, document, max_metrics=1) == "BENCHMARK_METRIC_LIMIT"
    assert rejection_code(tmp_path, document, max_nodes=5) == "BENCHMARK_NODE_LIMIT"
    assert rejection_code(tmp_path, document, max_depth=2) == "BENCHMARK_DEPTH_LIMIT"


def test_low_level_json_and_number_guards_are_defensive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(BenchmarkParseError, match="duplicate"):
        _object_without_duplicates([("a", 1), ("a", 2)])
    with pytest.raises(BenchmarkParseError, match="Infinity"):
        _reject_json_constant("Infinity")
    with pytest.raises(BenchmarkParseError, match="missing required field"):
        _required_string({}, "name", code="CODE", location="$.name", maximum=10)
    with pytest.raises(BenchmarkParseError, match="missing required field"):
        _required_number({}, "value", code="CODE", location="$.value")
    with pytest.raises(BenchmarkParseError, match="missing required field"):
        _required_list({}, "items", code="CODE", location="$.items")
    with pytest.raises(BenchmarkParseError, match="expected JSON object"):
        _mapping([], code="CODE", location="$")
    with pytest.raises(BenchmarkParseError, match="supported finite range"):
        _number(float("inf"), code="CODE", location="$.value")
    with pytest.raises(BenchmarkParseError, match="supported finite range"):
        _number(Decimal("1e-999"), code="CODE", location="$.value")
    assert _number(Decimal("0.0"), code="CODE", location="$.value") == 0.0
    assert _metric_name_is_valid("metric/path-1")
    assert not _metric_name_is_valid("_metric")

    monkeypatch.setattr(
        "forgegate.collectors.benchmark.json.loads",
        lambda *args, **kwargs: (_ for _ in ()).throw(RecursionError("deep")),
    )
    with pytest.raises(BenchmarkParseError, match="invalid benchmark JSON"):
        _load_json(b"{}")
