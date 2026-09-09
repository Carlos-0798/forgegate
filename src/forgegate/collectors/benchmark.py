from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator

from forgegate.artifacts import ArtifactError, ArtifactSource, RegisteredArtifact
from forgegate.bounded_parsing import StructureLimitError, enforce_json_structure_limits
from forgegate.collectors.base import (
    CollectionIssue,
    CollectionResult,
    CollectionStatus,
    IssueSeverity,
)
from forgegate.domain.enums import EvidenceTrust, VerificationLevel
from forgegate.domain.models import EvidenceRecord, ExecutionContext, StrictModel

BENCHMARK_MEDIA_TYPE = "application/vnd.forgegate.benchmark+json"
BENCHMARK_COLLECTOR_NAME = "benchmark_json"
BENCHMARK_COLLECTOR_VERSION = "forgegate-benchmark-json.v1"
BENCHMARK_SCHEMA_VERSION = "forgegate.benchmark.v1"
DEFAULT_MAX_JSON_NODES = 250_000
DEFAULT_MAX_JSON_DEPTH = 32
DEFAULT_MAX_METRICS = 100_000
MAX_NUMBER_MAGNITUDE = Decimal("1e308")
METRIC_NAME_PATTERN = r"^[A-Za-z][A-Za-z0-9._/-]{0,254}$"
TOLERANCE_MODES = {"absolute", "percent"}

BENCHMARK_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:forgegate:schema:benchmark:v1",
    "title": "ForgeGate Benchmark Artifact v1",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "tool", "metrics"],
    "properties": {
        "schema_version": {"const": BENCHMARK_SCHEMA_VERSION},
        "tool": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "version"],
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 120},
                "version": {"type": "string", "minLength": 1, "maxLength": 120},
            },
        },
        "metrics": {
            "type": "array",
            "minItems": 1,
            "maxItems": DEFAULT_MAX_METRICS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "dependentRequired": {"tolerance": ["baseline"]},
                "required": ["name", "value", "unit"],
                "properties": {
                    "name": {
                        "type": "string",
                        "pattern": METRIC_NAME_PATTERN,
                        "maxLength": 255,
                    },
                    "value": {"type": "number"},
                    "unit": {"type": "string", "minLength": 1, "maxLength": 64},
                    "scope": {"type": "string", "minLength": 1, "maxLength": 255},
                    "baseline": {"type": "number"},
                    "tolerance": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["value", "mode"],
                        "properties": {
                            "value": {"type": "number", "minimum": 0},
                            "mode": {"enum": sorted(TOLERANCE_MODES)},
                        },
                    },
                },
            },
        },
    },
}


class BenchmarkCollectionRequest(StrictModel):
    source_path: str = Field(min_length=1, max_length=512)
    execution_context: ExecutionContext
    collected_at: datetime
    trust: EvidenceTrust
    verification_level: VerificationLevel
    scope: str = Field(default="repository", min_length=1, max_length=255)

    @field_validator("collected_at")
    @classmethod
    def collected_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collected_at must include a UTC offset")
        return value


class BenchmarkParseError(ValueError):
    def __init__(self, code: str, message: str, *, location: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.location = location


@dataclass(frozen=True, slots=True)
class BenchmarkTool:
    name: str
    version: str


@dataclass(frozen=True, slots=True)
class BenchmarkTolerance:
    value: int | float
    mode: str

    def as_value(self) -> dict[str, int | float | str]:
        return {"value": self.value, "mode": self.mode}


@dataclass(frozen=True, slots=True)
class BenchmarkMetric:
    name: str
    value: int | float
    unit: str
    scope: str
    baseline: int | float | None
    tolerance: BenchmarkTolerance | None

    def as_value(self) -> dict[str, Any]:
        return {
            "metric": self.name,
            "value": self.value,
            "baseline": self.baseline,
            "tolerance": None if self.tolerance is None else self.tolerance.as_value(),
        }


class BenchmarkJsonCollector:
    def __init__(
        self,
        registry: ArtifactSource,
        *,
        max_nodes: int = DEFAULT_MAX_JSON_NODES,
        max_depth: int = DEFAULT_MAX_JSON_DEPTH,
        max_metrics: int = DEFAULT_MAX_METRICS,
    ) -> None:
        if min(max_nodes, max_depth, max_metrics) <= 0:
            raise ValueError("benchmark parser limits must be positive")
        self._registry = registry
        self._max_nodes = max_nodes
        self._max_depth = max_depth
        self._max_metrics = max_metrics

    def collect(self, request: BenchmarkCollectionRequest) -> CollectionResult:
        try:
            artifact = self._registry.register(
                request.source_path,
                media_type=BENCHMARK_MEDIA_TYPE,
            )
        except ArtifactError as exc:
            return self._rejected(exc.code, str(exc), location=request.source_path)

        try:
            tool, metrics = self._parse(artifact.content, default_scope=request.scope)
        except BenchmarkParseError as exc:
            return self._rejected(
                exc.code,
                str(exc),
                location=exc.location or request.source_path,
                artifact=artifact,
            )
        return self._complete(artifact, request, tool, metrics)

    def _parse(
        self, content: bytes, *, default_scope: str
    ) -> tuple[BenchmarkTool, list[BenchmarkMetric]]:
        try:
            enforce_json_structure_limits(
                content,
                max_nodes=self._max_nodes,
                max_depth=self._max_depth,
            )
        except StructureLimitError as exc:
            code = "BENCHMARK_NODE_LIMIT" if exc.kind == "node" else "BENCHMARK_DEPTH_LIMIT"
            raise BenchmarkParseError(code, str(exc)) from exc
        root = _load_json(content)
        self._enforce_tree_limits(root)
        document = _mapping(root, code="BENCHMARK_ROOT_INVALID", location="$")
        _reject_unknown_fields(
            document,
            allowed={"schema_version", "tool", "metrics"},
            code="BENCHMARK_ROOT_INVALID",
            location="$",
        )
        schema_version = _required_string(
            document,
            "schema_version",
            code="BENCHMARK_SCHEMA_VERSION_INVALID",
            location="$.schema_version",
            maximum=64,
        )
        if schema_version != BENCHMARK_SCHEMA_VERSION:
            raise BenchmarkParseError(
                "BENCHMARK_SCHEMA_VERSION_UNSUPPORTED",
                "supported schema version is "
                f"{BENCHMARK_SCHEMA_VERSION}, received {schema_version}",
                location="$.schema_version",
            )
        tool = _parse_tool(document.get("tool"), location="$.tool")
        raw_metrics = _required_list(
            document,
            "metrics",
            code="BENCHMARK_METRICS_INVALID",
            location="$.metrics",
        )
        if not raw_metrics:
            raise BenchmarkParseError(
                "BENCHMARK_METRICS_EMPTY",
                "benchmark artifact must contain at least one metric",
                location="$.metrics",
            )
        if len(raw_metrics) > self._max_metrics:
            raise BenchmarkParseError(
                "BENCHMARK_METRIC_LIMIT",
                f"benchmark artifact exceeds {self._max_metrics} metric limit",
                location="$.metrics",
            )

        metrics: list[BenchmarkMetric] = []
        seen: set[tuple[str, str]] = set()
        for index, raw_metric in enumerate(raw_metrics):
            location = f"$.metrics[{index}]"
            metric = _parse_metric(raw_metric, default_scope=default_scope, location=location)
            identity = (metric.scope, metric.name)
            if identity in seen:
                raise BenchmarkParseError(
                    "BENCHMARK_METRIC_DUPLICATE",
                    f"duplicate benchmark metric {metric.name} in scope {metric.scope}",
                    location=location,
                )
            seen.add(identity)
            metrics.append(metric)
        return tool, metrics

    def _enforce_tree_limits(self, root: Any) -> None:
        observed = 0
        stack: list[tuple[Any, int]] = [(root, 1)]
        while stack:
            value, depth = stack.pop()
            observed += 1
            if observed > self._max_nodes:
                raise BenchmarkParseError(
                    "BENCHMARK_NODE_LIMIT",
                    f"benchmark artifact exceeds {self._max_nodes} JSON node limit",
                )
            if depth > self._max_depth:
                raise BenchmarkParseError(
                    "BENCHMARK_DEPTH_LIMIT",
                    f"benchmark artifact exceeds {self._max_depth} JSON depth limit",
                )
            if isinstance(value, dict):
                stack.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list):
                stack.extend((item, depth + 1) for item in value)

    def _complete(
        self,
        artifact: RegisteredArtifact,
        request: BenchmarkCollectionRequest,
        tool: BenchmarkTool,
        metrics: list[BenchmarkMetric],
    ) -> CollectionResult:
        evidence = [
            EvidenceRecord(
                evidence_id=_evidence_id(
                    artifact.reference.sha256,
                    metric.scope,
                    metric.name,
                ),
                kind="benchmark.metric",
                scope=metric.scope,
                value=metric.as_value(),
                unit=metric.unit,
                status="observed",
                source_tool=tool.name,
                source_version=tool.version,
                execution_context=request.execution_context,
                artifact=artifact.reference,
                collected_at=request.collected_at,
                trust=request.trust,
                verification_level=request.verification_level,
                tags={"collector": BENCHMARK_COLLECTOR_VERSION},
            )
            for metric in metrics
        ]
        return CollectionResult(
            collector_name=BENCHMARK_COLLECTOR_NAME,
            collector_version=BENCHMARK_COLLECTOR_VERSION,
            status=CollectionStatus.COMPLETE,
            artifacts=[artifact.reference],
            evidence=evidence,
            warnings=[],
            rejected_records=[],
        )

    def _rejected(
        self,
        code: str,
        message: str,
        *,
        location: str,
        artifact: RegisteredArtifact | None = None,
    ) -> CollectionResult:
        return CollectionResult(
            collector_name=BENCHMARK_COLLECTOR_NAME,
            collector_version=BENCHMARK_COLLECTOR_VERSION,
            status=CollectionStatus.REJECTED,
            artifacts=[] if artifact is None else [artifact.reference],
            evidence=[],
            warnings=[],
            rejected_records=[
                CollectionIssue(
                    code=code,
                    severity=IssueSeverity.REJECTION,
                    message=message,
                    location=location,
                )
            ],
        )


def _load_json(content: bytes) -> Any:
    if b"\x00" in content:
        raise BenchmarkParseError(
            "BENCHMARK_UNSUPPORTED_ENCODING",
            "benchmark JSON must be UTF-8 and cannot contain NUL bytes",
        )
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise BenchmarkParseError(
            "BENCHMARK_UNSUPPORTED_ENCODING", "benchmark JSON must be UTF-8"
        ) from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_float=Decimal,
            parse_constant=_reject_json_constant,
        )
    except BenchmarkParseError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise BenchmarkParseError(
            "BENCHMARK_JSON_INVALID", f"invalid benchmark JSON: {exc}"
        ) from exc


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise BenchmarkParseError(
                "BENCHMARK_DUPLICATE_KEY",
                f"duplicate JSON object key: {key}",
            )
        value[key] = item
    return value


def _reject_json_constant(value: str) -> Any:
    raise BenchmarkParseError("BENCHMARK_NUMBER_INVALID", f"non-finite JSON number: {value}")


def _parse_tool(value: Any, *, location: str) -> BenchmarkTool:
    tool = _mapping(value, code="BENCHMARK_TOOL_INVALID", location=location)
    _reject_unknown_fields(
        tool,
        allowed={"name", "version"},
        code="BENCHMARK_TOOL_INVALID",
        location=location,
    )
    name = _required_string(
        tool,
        "name",
        code="BENCHMARK_TOOL_INVALID",
        location=f"{location}.name",
        maximum=120,
    )
    version = _required_string(
        tool,
        "version",
        code="BENCHMARK_TOOL_INVALID",
        location=f"{location}.version",
        maximum=120,
    )
    return BenchmarkTool(name=name, version=version)


def _parse_metric(value: Any, *, default_scope: str, location: str) -> BenchmarkMetric:
    metric = _mapping(value, code="BENCHMARK_METRIC_INVALID", location=location)
    _reject_unknown_fields(
        metric,
        allowed={"name", "value", "unit", "scope", "baseline", "tolerance"},
        code="BENCHMARK_METRIC_INVALID",
        location=location,
    )
    name = _required_string(
        metric,
        "name",
        code="BENCHMARK_METRIC_INVALID",
        location=f"{location}.name",
        maximum=255,
    )
    if not _metric_name_is_valid(name):
        raise BenchmarkParseError(
            "BENCHMARK_METRIC_INVALID",
            "metric name must begin with a letter and contain only letters, numbers, ., _, /, or -",
            location=f"{location}.name",
        )
    observed = _required_number(
        metric,
        "value",
        code="BENCHMARK_VALUE_INVALID",
        location=f"{location}.value",
    )
    unit = _required_string(
        metric,
        "unit",
        code="BENCHMARK_UNIT_INVALID",
        location=f"{location}.unit",
        maximum=64,
    )
    scope = (
        default_scope
        if "scope" not in metric
        else _string(
            metric["scope"],
            code="BENCHMARK_SCOPE_INVALID",
            location=f"{location}.scope",
            maximum=255,
        )
    )
    baseline = (
        None
        if "baseline" not in metric
        else _number(
            metric["baseline"],
            code="BENCHMARK_BASELINE_INVALID",
            location=f"{location}.baseline",
        )
    )
    tolerance = (
        None
        if "tolerance" not in metric
        else _parse_tolerance(metric["tolerance"], location=f"{location}.tolerance")
    )
    if tolerance is not None and baseline is None:
        raise BenchmarkParseError(
            "BENCHMARK_TOLERANCE_WITHOUT_BASELINE",
            "benchmark tolerance requires a baseline",
            location=f"{location}.tolerance",
        )
    return BenchmarkMetric(name, observed, unit, scope, baseline, tolerance)


def _parse_tolerance(value: Any, *, location: str) -> BenchmarkTolerance:
    tolerance = _mapping(value, code="BENCHMARK_TOLERANCE_INVALID", location=location)
    _reject_unknown_fields(
        tolerance,
        allowed={"value", "mode"},
        code="BENCHMARK_TOLERANCE_INVALID",
        location=location,
    )
    tolerance_value = _required_number(
        tolerance,
        "value",
        code="BENCHMARK_TOLERANCE_INVALID",
        location=f"{location}.value",
    )
    if tolerance_value < 0:
        raise BenchmarkParseError(
            "BENCHMARK_TOLERANCE_INVALID",
            "benchmark tolerance cannot be negative",
            location=f"{location}.value",
        )
    mode = _required_string(
        tolerance,
        "mode",
        code="BENCHMARK_TOLERANCE_INVALID",
        location=f"{location}.mode",
        maximum=32,
    )
    if mode not in TOLERANCE_MODES:
        raise BenchmarkParseError(
            "BENCHMARK_TOLERANCE_INVALID",
            f"unsupported tolerance mode {mode}; expected absolute or percent",
            location=f"{location}.mode",
        )
    return BenchmarkTolerance(tolerance_value, mode)


def _required_number(mapping: dict[str, Any], key: str, *, code: str, location: str) -> int | float:
    if key not in mapping:
        raise BenchmarkParseError(code, f"missing required field: {key}", location=location)
    return _number(mapping[key], code=code, location=location)


def _number(value: Any, *, code: str, location: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise BenchmarkParseError(code, "expected a JSON number", location=location)
    decimal_value = Decimal(str(value))
    if not decimal_value.is_finite() or abs(decimal_value) > MAX_NUMBER_MAGNITUDE:
        raise BenchmarkParseError(
            code, "number is outside the supported finite range", location=location
        )
    if isinstance(value, int):
        return value
    normalized = float(decimal_value)
    if not math.isfinite(normalized) or (not decimal_value.is_zero() and normalized == 0.0):
        raise BenchmarkParseError(
            code, "number is outside the supported finite range", location=location
        )
    return normalized


def _required_string(
    mapping: dict[str, Any],
    key: str,
    *,
    code: str,
    location: str,
    maximum: int,
) -> str:
    if key not in mapping:
        raise BenchmarkParseError(code, f"missing required field: {key}", location=location)
    return _string(mapping[key], code=code, location=location, maximum=maximum)


def _string(value: Any, *, code: str, location: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise BenchmarkParseError(
            code,
            f"expected a non-empty string no longer than {maximum} characters",
            location=location,
        )
    if any(ord(character) < 32 and character not in "\t\r\n" for character in value):
        raise BenchmarkParseError(
            code, "string contains forbidden control characters", location=location
        )
    return value


def _required_list(mapping: dict[str, Any], key: str, *, code: str, location: str) -> list[Any]:
    if key not in mapping:
        raise BenchmarkParseError(code, f"missing required field: {key}", location=location)
    value = mapping[key]
    if not isinstance(value, list):
        raise BenchmarkParseError(code, "expected JSON array", location=location)
    return value


def _mapping(value: Any, *, code: str, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BenchmarkParseError(code, "expected JSON object", location=location)
    return value


def _reject_unknown_fields(
    value: dict[str, Any], *, allowed: set[str], code: str, location: str
) -> None:
    unknown = sorted(set(value).difference(allowed))
    if unknown:
        raise BenchmarkParseError(
            code,
            f"unknown field(s): {', '.join(unknown)}",
            location=location,
        )


def _metric_name_is_valid(value: str) -> bool:
    first = value[0]
    return (
        first.isascii()
        and first.isalpha()
        and all(
            character.isascii() and (character.isalnum() or character in "._/-")
            for character in value[1:]
        )
    )


def _evidence_id(artifact_sha256: str, scope: str, metric_name: str) -> str:
    identity = hashlib.sha256(f"{scope}\0{metric_name}".encode()).hexdigest()[:12]
    return f"benchmark-metric-{artifact_sha256[:12]}-{identity}"
