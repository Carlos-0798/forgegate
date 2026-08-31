from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from forgegate.artifacts import ArtifactError, ArtifactRegistry, RegisteredArtifact
from forgegate.collectors.base import (
    CollectionIssue,
    CollectionResult,
    CollectionStatus,
    IssueSeverity,
)
from forgegate.domain.enums import EvidenceTrust, VerificationLevel
from forgegate.domain.models import EvidenceRecord, ExecutionContext, StrictModel

AFE_RESULT_MEDIA_TYPE = "application/vnd.analog-validation.result+json"
AFE_RESULT_COLLECTOR_NAME = "analog_validation_result"
AFE_RESULT_COLLECTOR_VERSION = "forgegate-analog-validation-result.v1"
AFE_RESULT_SCHEMA_VERSION = "result-export.v1"
AFE_TEST_RUN_SCHEMA_VERSION = "test-run.v1"
MAX_AFE_RESULT_BYTES = 2_000_000
DEFAULT_MAX_JSON_NODES = 250_000
DEFAULT_MAX_JSON_DEPTH = 32


class AfeEvidenceSource(StrEnum):
    THEORY = "THEORY"
    SYNTHETIC = "SYNTHETIC"
    CSV_REPLAY = "CSV_REPLAY"
    SPICE_IDEAL = "SPICE_IDEAL"
    SPICE_MODEL = "SPICE_MODEL"
    HOST_TEST = "HOST_TEST"
    BENCH_DMM = "BENCH_DMM"
    BENCH_CONTROLLER = "BENCH_CONTROLLER"
    BENCH_SCOPE = "BENCH_SCOPE"

    @property
    def is_bench(self) -> bool:
        return self.value.startswith("BENCH_")


class AfeTestRunOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"
    UNSUPPORTED = "UNSUPPORTED"
    ABORTED = "ABORTED"
    ERROR = "ERROR"


class AfePointDisposition(StrEnum):
    INCLUDED = "INCLUDED"
    EXCLUDED = "EXCLUDED"
    INVALID = "INVALID"


class AfeContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _identifier(name: str, value: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty stripped string")
    return value


def _number(name: str, value: Any) -> int | float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        return value
    raise ValueError(f"{name} must be numeric")


def _timestamp(name: str, value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError(f"{name} must be UTC with Z suffix")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid timestamp") from exc


def _unique_strings(name: str, values: list[str]) -> list[str]:
    for value in values:
        _identifier(name, value)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} cannot contain duplicates")
    return values


class AfeExportValue(AfeContractModel):
    name: str
    value: str | int | float | bool | None
    unit: str

    @field_validator("name", "unit")
    @classmethod
    def identifiers_are_stripped(cls, value: str) -> str:
        return _identifier("value field", value)

    @field_validator("value", mode="before")
    @classmethod
    def scalar_is_supported(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float) and math.isfinite(value):
            return value
        raise ValueError("value must be a finite JSON scalar")


class AfeExportCriterion(AfeContractModel):
    name: str
    actual_value: int | float
    unit: str
    passed: bool
    lower_limit: int | float | None
    upper_limit: int | float | None

    @field_validator("name", "unit")
    @classmethod
    def identifiers_are_stripped(cls, value: str) -> str:
        return _identifier("criterion field", value)

    @field_validator("actual_value", "lower_limit", "upper_limit", mode="before")
    @classmethod
    def numbers_are_finite(cls, value: Any, info: Any) -> Any:
        if value is None and info.field_name != "actual_value":
            return None
        return _number(info.field_name, value)

    @model_validator(mode="after")
    def result_matches_inclusive_limits(self) -> AfeExportCriterion:
        if self.lower_limit is None and self.upper_limit is None:
            raise ValueError("at least one criterion limit is required")
        if (
            self.lower_limit is not None
            and self.upper_limit is not None
            and self.lower_limit > self.upper_limit
        ):
            raise ValueError("lower_limit cannot exceed upper_limit")
        expected = (self.lower_limit is None or self.actual_value >= self.lower_limit) and (
            self.upper_limit is None or self.actual_value <= self.upper_limit
        )
        if self.passed is not expected:
            raise ValueError("passed must agree with inclusive limits")
        return self


class AfeRecordReference(AfeContractModel):
    record_id: str
    raw_record_id: str
    timestamp: str
    channel: str
    source: AfeEvidenceSource

    @field_validator("source", mode="before")
    @classmethod
    def source_is_supported(cls, value: Any) -> Any:
        return AfeEvidenceSource(value) if isinstance(value, str) else value

    @field_validator("record_id", "raw_record_id", "channel")
    @classmethod
    def identifiers_are_stripped(cls, value: str) -> str:
        return _identifier("reference field", value)

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_utc(cls, value: str) -> str:
        _timestamp("reference.timestamp", value)
        return value


class AfeExportPoint(AfeContractModel):
    index: int = Field(ge=0)
    label: str
    disposition: AfePointDisposition
    references: list[AfeRecordReference] = Field(min_length=1)
    values: list[AfeExportValue] = Field(min_length=1)
    quality_flags: list[str]
    exclusion_reasons: list[str]

    @field_validator("disposition", mode="before")
    @classmethod
    def disposition_is_supported(cls, value: Any) -> Any:
        return AfePointDisposition(value) if isinstance(value, str) else value

    @field_validator("index", mode="before")
    @classmethod
    def index_is_integer(cls, value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("point index must be an integer")
        return value

    @field_validator("label")
    @classmethod
    def label_is_stripped(cls, value: str) -> str:
        return _identifier("point label", value)

    @field_validator("quality_flags", "exclusion_reasons")
    @classmethod
    def string_arrays_are_unique(cls, values: list[str], info: Any) -> list[str]:
        return _unique_strings(info.field_name, values)

    @model_validator(mode="after")
    def lineage_and_disposition_are_consistent(self) -> AfeExportPoint:
        record_ids = [reference.record_id for reference in self.references]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("point reference record IDs must be unique")
        if len({reference.source for reference in self.references}) != 1:
            raise ValueError("point references must use one evidence source")
        value_names = [value.name for value in self.values]
        if len(value_names) != len(set(value_names)):
            raise ValueError("point value names must be unique")
        if self.disposition is AfePointDisposition.INCLUDED and self.exclusion_reasons:
            raise ValueError("included points cannot have exclusion reasons")
        if self.disposition is not AfePointDisposition.INCLUDED and not self.exclusion_reasons:
            raise ValueError("excluded or invalid points require reasons")
        return self


class AfeSourceSchema(AfeContractModel):
    name: str
    version: str

    @field_validator("name", "version")
    @classmethod
    def identifiers_are_stripped(cls, value: str) -> str:
        return _identifier("source schema field", value)


class AfeRunMetadata(AfeContractModel):
    run_id: str
    test_type: str
    configuration_id: str
    configuration_version: str
    started_at: str
    ended_at: str
    software_version: str
    device_id: str
    profile_name: str
    profile_version: str
    evidence_source: AfeEvidenceSource
    input_record_ids: list[str]
    schema_version: Literal["test-run.v1"]

    @field_validator("evidence_source", mode="before")
    @classmethod
    def evidence_source_is_supported(cls, value: Any) -> Any:
        return AfeEvidenceSource(value) if isinstance(value, str) else value

    @field_validator(
        "run_id",
        "test_type",
        "configuration_id",
        "configuration_version",
        "software_version",
        "device_id",
        "profile_name",
        "profile_version",
    )
    @classmethod
    def identifiers_are_stripped(cls, value: str) -> str:
        return _identifier("metadata field", value)

    @field_validator("started_at", "ended_at")
    @classmethod
    def timestamps_are_utc(cls, value: str, info: Any) -> str:
        _timestamp(info.field_name, value)
        return value

    @field_validator("input_record_ids")
    @classmethod
    def input_ids_are_unique(cls, values: list[str]) -> list[str]:
        return _unique_strings("input_record_ids", values)

    @model_validator(mode="after")
    def end_is_not_before_start(self) -> AfeRunMetadata:
        if _timestamp("ended_at", self.ended_at) < _timestamp("started_at", self.started_at):
            raise ValueError("ended_at cannot be earlier than started_at")
        return self


class AfeTestRun(AfeContractModel):
    metadata: AfeRunMetadata
    outcome: AfeTestRunOutcome
    summary: str
    evidence_record_ids: list[str]
    missing_requirements: list[str]

    @field_validator("outcome", mode="before")
    @classmethod
    def outcome_is_supported(cls, value: Any) -> Any:
        return AfeTestRunOutcome(value) if isinstance(value, str) else value

    @field_validator("summary")
    @classmethod
    def summary_is_stripped(cls, value: str) -> str:
        return _identifier("summary", value)

    @field_validator("evidence_record_ids", "missing_requirements")
    @classmethod
    def identifiers_are_unique(cls, values: list[str], info: Any) -> list[str]:
        return _unique_strings(info.field_name, values)

    @model_validator(mode="after")
    def outcome_has_required_evidence(self) -> AfeTestRun:
        if self.outcome in {AfeTestRunOutcome.PASS, AfeTestRunOutcome.FAIL}:
            if self.missing_requirements:
                raise ValueError("complete PASS/FAIL cannot have missing requirements")
            if not self.evidence_record_ids:
                raise ValueError("complete PASS/FAIL requires evidence")
        if (
            self.outcome in {AfeTestRunOutcome.INCOMPLETE, AfeTestRunOutcome.UNSUPPORTED}
            and not self.missing_requirements
        ):
            raise ValueError(f"{self.outcome.value} requires missing requirements")
        return self


class AfeCriteria(AfeContractModel):
    id: str
    version: str
    results: list[AfeExportCriterion]

    @field_validator("id", "version")
    @classmethod
    def identity_is_stripped(cls, value: str) -> str:
        return _identifier("criteria identity", value)

    @field_validator("results")
    @classmethod
    def result_names_are_unique(cls, values: list[AfeExportCriterion]) -> list[AfeExportCriterion]:
        names = [value.name for value in values]
        if len(names) != len(set(names)):
            raise ValueError("criterion names must be unique")
        return values


class AfeResultExportV1(AfeContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        title="Analog Validation Studio result-export.v1 compatibility contract",
        json_schema_extra={"$id": "urn:forgegate:compatibility:analog-validation:result-export:v1"},
    )

    schema_version: Literal["result-export.v1"]
    test_run: AfeTestRun
    criteria: AfeCriteria | None
    source_schemas: list[AfeSourceSchema] = Field(min_length=1)
    metrics: list[AfeExportValue]
    points: list[AfeExportPoint]
    limitations: list[str] = Field(min_length=1)

    @field_validator("source_schemas")
    @classmethod
    def source_schema_names_are_unique(cls, values: list[AfeSourceSchema]) -> list[AfeSourceSchema]:
        names = [value.name for value in values]
        if len(names) != len(set(names)):
            raise ValueError("source schema names must be unique")
        return values

    @field_validator("metrics")
    @classmethod
    def metric_names_are_unique(cls, values: list[AfeExportValue]) -> list[AfeExportValue]:
        names = [value.name for value in values]
        if len(names) != len(set(names)):
            raise ValueError("metric names must be unique")
        return values

    @field_validator("limitations")
    @classmethod
    def limitations_are_unique(cls, values: list[str]) -> list[str]:
        return _unique_strings("limitations", values)

    @model_validator(mode="after")
    def export_preserves_lineage_and_outcome(self) -> AfeResultExportV1:
        if [point.index for point in self.points] != list(range(len(self.points))):
            raise ValueError("point indexes must be contiguous from zero")

        source = self.test_run.metadata.evidence_source
        if any(
            reference.source is not source
            for point in self.points
            for reference in point.references
        ):
            raise ValueError("point source must match TestRun evidence source")

        record_ids = [
            reference.record_id for point in self.points for reference in point.references
        ]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("point record IDs must be unique across the export")
        if self.points and record_ids != self.test_run.evidence_record_ids:
            raise ValueError("point record IDs must match TestRun evidence IDs")
        if self.test_run.evidence_record_ids and not self.points:
            raise ValueError("TestRun evidence IDs require exported points")

        raw_ids = list(
            dict.fromkeys(
                reference.raw_record_id for point in self.points for reference in point.references
            )
        )
        if self.points and raw_ids != self.test_run.metadata.input_record_ids:
            raise ValueError("point raw IDs must match TestRun input IDs")

        if self.test_run.outcome in {AfeTestRunOutcome.PASS, AfeTestRunOutcome.FAIL}:
            if self.criteria is None or not self.criteria.results or not self.points:
                raise ValueError("PASS/FAIL exports require criteria and point evidence")
            all_passed = all(result.passed for result in self.criteria.results)
            if (self.test_run.outcome is AfeTestRunOutcome.PASS) is not all_passed:
                raise ValueError("criterion results must match TestRun outcome")
        return self


AFE_RESULT_JSON_SCHEMA: dict[str, Any] = AfeResultExportV1.model_json_schema()

AFE_VERIFICATION_LEVELS: dict[AfeEvidenceSource, VerificationLevel] = {
    AfeEvidenceSource.THEORY: VerificationLevel.DECLARED,
    AfeEvidenceSource.SYNTHETIC: VerificationLevel.SIMULATED,
    AfeEvidenceSource.CSV_REPLAY: VerificationLevel.REPLAYED,
    AfeEvidenceSource.SPICE_IDEAL: VerificationLevel.SIMULATED,
    AfeEvidenceSource.SPICE_MODEL: VerificationLevel.SIMULATED,
    AfeEvidenceSource.HOST_TEST: VerificationLevel.HOST_TESTED,
    AfeEvidenceSource.BENCH_DMM: VerificationLevel.SYSTEM_OBSERVED,
    AfeEvidenceSource.BENCH_CONTROLLER: VerificationLevel.SYSTEM_OBSERVED,
    AfeEvidenceSource.BENCH_SCOPE: VerificationLevel.SYSTEM_OBSERVED,
}


class AnalogValidationCollectionRequest(StrictModel):
    source_path: str = Field(min_length=1, max_length=512)
    execution_context: ExecutionContext
    collected_at: datetime
    trust: EvidenceTrust
    scope: str = Field(default="analog-validation", min_length=1, max_length=255)

    @field_validator("collected_at")
    @classmethod
    def collected_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collected_at must include a UTC offset")
        return value


class AnalogValidationParseError(ValueError):
    def __init__(self, code: str, message: str, *, location: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.location = location


class AnalogValidationResultCollector:
    def __init__(
        self,
        registry: ArtifactRegistry,
        *,
        max_nodes: int = DEFAULT_MAX_JSON_NODES,
        max_depth: int = DEFAULT_MAX_JSON_DEPTH,
    ) -> None:
        if min(max_nodes, max_depth) <= 0:
            raise ValueError("analog validation parser limits must be positive")
        self._registry = registry
        self._max_nodes = max_nodes
        self._max_depth = max_depth

    def collect(self, request: AnalogValidationCollectionRequest) -> CollectionResult:
        try:
            artifact = self._registry.register(
                request.source_path,
                media_type=AFE_RESULT_MEDIA_TYPE,
            )
        except ArtifactError as exc:
            return self._rejected(exc.code, str(exc), location=request.source_path)

        try:
            document = self._parse(artifact)
            return self._complete(artifact, request, document)
        except AnalogValidationParseError as exc:
            return self._rejected(
                exc.code,
                str(exc),
                location=exc.location or request.source_path,
                artifact=artifact,
            )
        except ValidationError as exc:
            return self._rejected(
                "AFE_RESULT_NORMALIZATION_INVALID",
                _validation_message(exc),
                location=request.source_path,
                artifact=artifact,
            )

    def _parse(self, artifact: RegisteredArtifact) -> AfeResultExportV1:
        if artifact.reference.size_bytes > MAX_AFE_RESULT_BYTES:
            raise AnalogValidationParseError(
                "AFE_RESULT_SIZE_LIMIT",
                f"result export exceeds the {MAX_AFE_RESULT_BYTES} byte contract limit",
            )
        root = _load_json(artifact.content)
        self._enforce_tree_limits(root)
        if not isinstance(root, dict):
            raise AnalogValidationParseError(
                "AFE_RESULT_ROOT_INVALID", "result export root must be an object", location="$"
            )
        version = root.get("schema_version")
        if not isinstance(version, str):
            raise AnalogValidationParseError(
                "AFE_RESULT_SCHEMA_VERSION_INVALID",
                "schema_version must be a string",
                location="$.schema_version",
            )
        if version != AFE_RESULT_SCHEMA_VERSION:
            raise AnalogValidationParseError(
                "AFE_RESULT_SCHEMA_VERSION_UNSUPPORTED",
                f"supported schema version is {AFE_RESULT_SCHEMA_VERSION}, received {version}",
                location="$.schema_version",
            )
        try:
            return AfeResultExportV1.model_validate(root)
        except ValidationError as exc:
            error = exc.errors(include_url=False, include_input=False)[0]
            raise AnalogValidationParseError(
                "AFE_RESULT_CONTRACT_INVALID",
                f"result export violates result-export.v1: {error['msg']}",
                location=_error_location(error.get("loc", ())),
            ) from exc

    def _enforce_tree_limits(self, root: Any) -> None:
        observed = 0
        stack: list[tuple[Any, int]] = [(root, 1)]
        while stack:
            value, depth = stack.pop()
            observed += 1
            if observed > self._max_nodes:
                raise AnalogValidationParseError(
                    "AFE_RESULT_NODE_LIMIT",
                    f"result export exceeds the {self._max_nodes} JSON node limit",
                )
            if depth > self._max_depth:
                raise AnalogValidationParseError(
                    "AFE_RESULT_DEPTH_LIMIT",
                    f"result export exceeds the {self._max_depth} JSON depth limit",
                )
            if isinstance(value, dict):
                stack.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list):
                stack.extend((item, depth + 1) for item in value)

    def _complete(
        self,
        artifact: RegisteredArtifact,
        request: AnalogValidationCollectionRequest,
        document: AfeResultExportV1,
    ) -> CollectionResult:
        metadata = document.test_run.metadata
        source = metadata.evidence_source
        verification_level = AFE_VERIFICATION_LEVELS[source]
        tags = {
            "collector": AFE_RESULT_COLLECTOR_VERSION,
            "schema_version": AFE_RESULT_SCHEMA_VERSION,
            "evidence_source": source.value,
        }
        criteria_identity = (
            None
            if document.criteria is None
            else {"id": document.criteria.id, "version": document.criteria.version}
        )
        summary = EvidenceRecord(
            evidence_id=f"analog-validation-run-{artifact.reference.sha256[:12]}",
            kind="analog-validation.run",
            scope=request.scope,
            value={
                "run_id": metadata.run_id,
                "test_type": metadata.test_type,
                "outcome": document.test_run.outcome.value,
                "summary": document.test_run.summary,
                "configuration": {
                    "id": metadata.configuration_id,
                    "version": metadata.configuration_version,
                },
                "profile": {"name": metadata.profile_name, "version": metadata.profile_version},
                "device_id": metadata.device_id,
                "started_at": metadata.started_at,
                "ended_at": metadata.ended_at,
                "criteria": criteria_identity,
                "counts": {
                    "input_records": len(metadata.input_record_ids),
                    "evidence_records": len(document.test_run.evidence_record_ids),
                    "metrics": len(document.metrics),
                    "criteria": 0 if document.criteria is None else len(document.criteria.results),
                    "points": len(document.points),
                },
                "missing_requirements": document.test_run.missing_requirements,
                "limitations": document.limitations,
                "source_schemas": [
                    {"name": value.name, "version": value.version}
                    for value in document.source_schemas
                ],
            },
            unit=None,
            status=document.test_run.outcome.value,
            source_tool="analog-validation-studio",
            source_version=metadata.software_version,
            execution_context=request.execution_context,
            artifact=artifact.reference,
            collected_at=request.collected_at,
            trust=request.trust,
            verification_level=verification_level,
            tags={**tags, "record_type": "run"},
        )
        metrics = [
            EvidenceRecord(
                evidence_id=_evidence_id(
                    "metric", artifact.reference.sha256, metadata.run_id, value.name
                ),
                kind="analog-validation.metric",
                scope=request.scope,
                value={
                    "run_id": metadata.run_id,
                    "test_type": metadata.test_type,
                    "name": value.name,
                    "value": value.value,
                },
                unit=value.unit,
                status="observed",
                source_tool="analog-validation-studio",
                source_version=metadata.software_version,
                execution_context=request.execution_context,
                artifact=artifact.reference,
                collected_at=request.collected_at,
                trust=request.trust,
                verification_level=verification_level,
                tags={**tags, "record_type": "metric"},
            )
            for value in document.metrics
        ]
        criteria = (
            []
            if document.criteria is None
            else [
                EvidenceRecord(
                    evidence_id=_evidence_id(
                        "criterion", artifact.reference.sha256, metadata.run_id, value.name
                    ),
                    kind="analog-validation.criterion",
                    scope=request.scope,
                    value={
                        "run_id": metadata.run_id,
                        "test_type": metadata.test_type,
                        "criteria_id": document.criteria.id,
                        "criteria_version": document.criteria.version,
                        "name": value.name,
                        "actual_value": value.actual_value,
                        "lower_limit": value.lower_limit,
                        "upper_limit": value.upper_limit,
                        "passed": value.passed,
                    },
                    unit=value.unit,
                    status="passed" if value.passed else "failed",
                    source_tool="analog-validation-studio",
                    source_version=metadata.software_version,
                    execution_context=request.execution_context,
                    artifact=artifact.reference,
                    collected_at=request.collected_at,
                    trust=request.trust,
                    verification_level=verification_level,
                    tags={**tags, "record_type": "criterion"},
                )
                for value in document.criteria.results
            ]
        )
        warnings = []
        if source.is_bench:
            warnings.append(
                CollectionIssue(
                    code="AFE_BENCH_EVIDENCE_CAPPED",
                    severity=IssueSeverity.WARNING,
                    message=(
                        "result-export.v1 does not require instrument identity or calibration "
                        "provenance; BENCH_* is capped at system_observed"
                    ),
                    location="$.test_run.metadata.evidence_source",
                )
            )
        return CollectionResult(
            collector_name=AFE_RESULT_COLLECTOR_NAME,
            collector_version=AFE_RESULT_COLLECTOR_VERSION,
            status=CollectionStatus.COMPLETE,
            artifacts=[artifact.reference],
            evidence=[summary, *metrics, *criteria],
            warnings=warnings,
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
            collector_name=AFE_RESULT_COLLECTOR_NAME,
            collector_version=AFE_RESULT_COLLECTOR_VERSION,
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
        raise AnalogValidationParseError(
            "AFE_RESULT_UNSUPPORTED_ENCODING",
            "result export must be UTF-8 and cannot contain NUL bytes",
        )
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AnalogValidationParseError(
            "AFE_RESULT_UNSUPPORTED_ENCODING", "result export must be UTF-8"
        ) from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except AnalogValidationParseError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise AnalogValidationParseError(
            "AFE_RESULT_JSON_INVALID", f"invalid result-export JSON: {exc}"
        ) from exc


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AnalogValidationParseError(
                "AFE_RESULT_DUPLICATE_KEY", f"duplicate JSON object key: {key}"
            )
        value[key] = item
    return value


def _reject_json_constant(value: str) -> Any:
    raise AnalogValidationParseError(
        "AFE_RESULT_NUMBER_INVALID", f"non-finite JSON number: {value}"
    )


def _error_location(parts: Any) -> str:
    location = "$"
    for part in parts:
        location += f"[{part}]" if isinstance(part, int) else f".{part}"
    return location


def _validation_message(exc: ValidationError) -> str:
    error = exc.errors(include_url=False, include_input=False)[0]
    return f"cannot normalize result export: {error['msg']}"[:1024]


def _evidence_id(record_type: str, artifact_sha256: str, run_id: str, name: str) -> str:
    identity = hashlib.sha256(f"{run_id}\0{name}".encode()).hexdigest()[:12]
    return f"analog-validation-{record_type}-{artifact_sha256[:12]}-{identity}"


__all__ = [
    "AFE_RESULT_COLLECTOR_NAME",
    "AFE_RESULT_COLLECTOR_VERSION",
    "AFE_RESULT_JSON_SCHEMA",
    "AFE_RESULT_MEDIA_TYPE",
    "AFE_RESULT_SCHEMA_VERSION",
    "AFE_VERIFICATION_LEVELS",
    "AnalogValidationCollectionRequest",
    "AnalogValidationParseError",
    "AnalogValidationResultCollector",
]
