from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from forgegate.artifacts import ArtifactError, ArtifactRegistry, RegisteredArtifact
from forgegate.bounded_parsing import StructureLimitError, enforce_json_structure_limits
from forgegate.collectors.base import (
    CollectionIssue,
    CollectionResult,
    CollectionStatus,
    IssueSeverity,
)
from forgegate.domain.enums import EvidenceTrust, VerificationLevel
from forgegate.domain.models import COMMIT_PATTERN, EvidenceRecord, ExecutionContext, StrictModel

MSP430_REPORT_MEDIA_TYPE = "application/vnd.forgegate.msp430-validation-report+json"
MSP430_REPORT_SCHEMA_VERSION = "forgegate.msp430-validation-report.v1"
MSP430_COLLECTOR_NAME = "msp430_validation_report"
MSP430_COLLECTOR_VERSION = "forgegate-msp430-validation-report.v1"
MAX_MSP430_REPORT_BYTES = 2_000_000
DEFAULT_MAX_JSON_NODES = 100_000
DEFAULT_MAX_JSON_DEPTH = 32
SHA256_PATTERN = r"^[0-9a-f]{64}$"
IDENTIFIER_PATTERN = r"^[a-z][a-z0-9._-]{1,127}$"


class Msp430EvidenceLevel(StrEnum):
    HOST_TEST = "HOST_TEST"
    TARGET_BUILD = "TARGET_BUILD"
    LAUNCHPAD_HIL = "LAUNCHPAD_HIL"
    BENCH_MEASURED = "BENCH_MEASURED"


class Msp430Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"
    ERROR = "ERROR"


class Msp430CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    ERROR = "ERROR"


class Msp430HardwareAccess(StrEnum):
    NOT_PERFORMED = "NOT_PERFORMED"
    READ_ONLY_TELEMETRY = "READ_ONLY_TELEMETRY"
    CONTROLLED_TEST_COMMANDS = "CONTROLLED_TEST_COMMANDS"


class Msp430ConnectionScope(StrEnum):
    NONE = "NONE"
    LAUNCHPAD_ONLY = "LAUNCHPAD_ONLY"
    EXTERNAL_BENCH = "EXTERNAL_BENCH"


class CalibrationStatus(StrEnum):
    CURRENT = "CURRENT"
    NOT_REQUIRED = "NOT_REQUIRED"
    UNKNOWN = "UNKNOWN"


class Msp430ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _stripped(name: str, value: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty stripped string")
    return value


def _timestamp(name: str, value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a UTC offset")
    return parsed


def _finite_scalar(name: str, value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError(f"{name} must be a finite JSON scalar")


def _unique(name: str, values: list[str]) -> list[str]:
    for value in values:
        _stripped(name, value)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} cannot contain duplicates")
    return values


class Msp430Producer(Msp430ContractModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=120)

    @field_validator("name", "version")
    @classmethod
    def values_are_stripped(cls, value: str) -> str:
        return _stripped("producer field", value)


class Msp430Subject(Msp430ContractModel):
    commit_sha: str = Field(pattern=COMMIT_PATTERN)
    target: str = Field(min_length=1, max_length=120)
    firmware_version: str = Field(min_length=1, max_length=120)

    @field_validator("commit_sha")
    @classmethod
    def commit_is_full_lowercase(cls, value: str) -> str:
        if value.lower() != value or len(value) not in {40, 64}:
            raise ValueError(
                "subject commit_sha must be exactly 40 or 64 lowercase hexadecimal characters"
            )
        return value

    @field_validator("target", "firmware_version")
    @classmethod
    def identity_is_stripped(cls, value: str) -> str:
        return _stripped("subject field", value)


class Msp430Run(Msp430ContractModel):
    run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    evidence_level: Msp430EvidenceLevel
    started_at: str
    ended_at: str
    duration_seconds: int | float = Field(ge=0)
    outcome: Msp430Outcome

    @field_validator("evidence_level", mode="before")
    @classmethod
    def evidence_level_is_supported(cls, value: Any) -> Any:
        return Msp430EvidenceLevel(value) if isinstance(value, str) else value

    @field_validator("outcome", mode="before")
    @classmethod
    def outcome_is_supported(cls, value: Any) -> Any:
        return Msp430Outcome(value) if isinstance(value, str) else value

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def duration_is_finite(cls, value: Any) -> int | float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("duration_seconds must be numeric")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("duration_seconds must be finite")
        return cast(int | float, value)

    @model_validator(mode="after")
    def timestamps_match_duration(self) -> Msp430Run:
        started = _timestamp("run.started_at", self.started_at)
        ended = _timestamp("run.ended_at", self.ended_at)
        if ended < started:
            raise ValueError("run ended_at cannot be earlier than started_at")
        observed = (ended - started).total_seconds()
        if abs(observed - float(self.duration_seconds)) > 1.0:
            raise ValueError(
                "run duration_seconds must agree with its timestamps within one second"
            )
        return self


class Msp430Check(Msp430ContractModel):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    status: Msp430CheckStatus
    summary: str = Field(min_length=1, max_length=500)
    actual: str | int | float | bool | None
    expected: str | int | float | bool | None
    unit: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("status", mode="before")
    @classmethod
    def status_is_supported(cls, value: Any) -> Any:
        return Msp430CheckStatus(value) if isinstance(value, str) else value

    @field_validator("summary")
    @classmethod
    def summary_is_stripped(cls, value: str) -> str:
        return _stripped("check summary", value)

    @field_validator("actual", "expected", mode="before")
    @classmethod
    def values_are_finite_scalars(cls, value: Any, info: Any) -> Any:
        return _finite_scalar(info.field_name, value)


class Msp430Metric(Msp430ContractModel):
    name: str = Field(pattern=IDENTIFIER_PATTERN)
    value: str | int | float | bool | None
    unit: str = Field(min_length=1, max_length=64)

    @field_validator("value", mode="before")
    @classmethod
    def value_is_finite_scalar(cls, value: Any) -> Any:
        return _finite_scalar("metric value", value)


class Msp430SourceArtifact(Msp430ContractModel):
    name: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=SHA256_PATTERN)
    size_bytes: int = Field(ge=0)

    @field_validator("name", "media_type")
    @classmethod
    def values_are_stripped(cls, value: str) -> str:
        return _stripped("source artifact field", value)


class Msp430Instrument(Msp430ContractModel):
    instrument_id: str = Field(pattern=IDENTIFIER_PATTERN)
    model: str = Field(min_length=1, max_length=120)
    calibration_status: CalibrationStatus
    calibration_reference: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("calibration_status", mode="before")
    @classmethod
    def calibration_status_is_supported(cls, value: Any) -> Any:
        return CalibrationStatus(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def current_calibration_has_reference(self) -> Msp430Instrument:
        if (
            self.calibration_status is CalibrationStatus.CURRENT
            and self.calibration_reference is None
        ):
            raise ValueError("CURRENT calibration requires calibration_reference")
        return self


class Msp430HardwareBoundary(Msp430ContractModel):
    board_model: str = Field(min_length=1, max_length=120)
    board_connected: bool
    access: Msp430HardwareAccess
    connection_scope: Msp430ConnectionScope
    physical_measurements: bool
    external_components: list[str]
    instruments: list[Msp430Instrument]

    @field_validator("access", mode="before")
    @classmethod
    def access_is_supported(cls, value: Any) -> Any:
        return Msp430HardwareAccess(value) if isinstance(value, str) else value

    @field_validator("connection_scope", mode="before")
    @classmethod
    def connection_scope_is_supported(cls, value: Any) -> Any:
        return Msp430ConnectionScope(value) if isinstance(value, str) else value

    @field_validator("external_components")
    @classmethod
    def components_are_unique(cls, values: list[str]) -> list[str]:
        return _unique("external_components", values)

    @model_validator(mode="after")
    def access_scope_is_consistent(self) -> Msp430HardwareBoundary:
        if self.connection_scope is Msp430ConnectionScope.NONE:
            if self.board_connected or self.access is not Msp430HardwareAccess.NOT_PERFORMED:
                raise ValueError("NONE connection scope requires no board and no hardware access")
        elif not self.board_connected or self.access is Msp430HardwareAccess.NOT_PERFORMED:
            raise ValueError(
                "connected hardware scope requires board_connected and explicit access"
            )
        if self.connection_scope is not Msp430ConnectionScope.EXTERNAL_BENCH and (
            self.external_components or self.physical_measurements or self.instruments
        ):
            raise ValueError(
                "non-bench scope cannot claim external components, instruments, "
                "or physical measurements"
            )
        if self.physical_measurements and not self.instruments:
            raise ValueError("physical measurements require instrument provenance")
        return self


class Msp430ReviewCorrection(Msp430ContractModel):
    correction_id: str = Field(pattern=IDENTIFIER_PATTERN)
    original_outcome: Msp430Outcome
    original_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    rationale: str = Field(min_length=1, max_length=1000)

    @field_validator("original_outcome", mode="before")
    @classmethod
    def outcome_is_supported(cls, value: Any) -> Any:
        return Msp430Outcome(value) if isinstance(value, str) else value

    @field_validator("rationale")
    @classmethod
    def rationale_is_stripped(cls, value: str) -> str:
        return _stripped("correction rationale", value)


class Msp430ValidationReportV1(Msp430ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        title="MSP430 validation report v1 compatibility contract",
        json_schema_extra={"$id": "urn:forgegate:compatibility:msp430-validation-report:v1"},
    )

    schema_version: Literal["forgegate.msp430-validation-report.v1"]
    producer: Msp430Producer
    subject: Msp430Subject
    run: Msp430Run
    checks: list[Msp430Check] = Field(min_length=1)
    metrics: list[Msp430Metric]
    hardware: Msp430HardwareBoundary
    source_artifacts: list[Msp430SourceArtifact] = Field(min_length=1)
    corrections: list[Msp430ReviewCorrection]
    limitations: list[str] = Field(min_length=1)

    @field_validator("limitations")
    @classmethod
    def limitations_are_unique(cls, values: list[str]) -> list[str]:
        return _unique("limitations", values)

    @model_validator(mode="after")
    def report_is_self_consistent(self) -> Msp430ValidationReportV1:
        check_ids = [value.id for value in self.checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("check IDs must be unique")
        metric_names = [value.name for value in self.metrics]
        if len(metric_names) != len(set(metric_names)):
            raise ValueError("metric names must be unique")
        artifact_names = [value.name for value in self.source_artifacts]
        if len(artifact_names) != len(set(artifact_names)):
            raise ValueError("source artifact names must be unique")
        artifact_hashes = [value.sha256 for value in self.source_artifacts]
        if len(artifact_hashes) != len(set(artifact_hashes)):
            raise ValueError("source artifact hashes must be unique")
        correction_ids = [value.correction_id for value in self.corrections]
        if len(correction_ids) != len(set(correction_ids)):
            raise ValueError("correction IDs must be unique")
        if any(value.original_artifact_sha256 not in artifact_hashes for value in self.corrections):
            raise ValueError("corrections must reference a listed source artifact")

        statuses = {value.status for value in self.checks}
        if self.run.outcome is Msp430Outcome.PASS and statuses != {Msp430CheckStatus.PASS}:
            raise ValueError("PASS outcome requires every check to PASS")
        if self.run.outcome is Msp430Outcome.FAIL and Msp430CheckStatus.FAIL not in statuses:
            raise ValueError("FAIL outcome requires at least one failed check")
        if (
            self.run.outcome is Msp430Outcome.INCOMPLETE
            and Msp430CheckStatus.NOT_RUN not in statuses
        ):
            raise ValueError("INCOMPLETE outcome requires at least one NOT_RUN check")
        if self.run.outcome is Msp430Outcome.ERROR and Msp430CheckStatus.ERROR not in statuses:
            raise ValueError("ERROR outcome requires at least one ERROR check")

        if (
            self.run.evidence_level
            in {
                Msp430EvidenceLevel.HOST_TEST,
                Msp430EvidenceLevel.TARGET_BUILD,
            }
            and self.hardware.connection_scope is not Msp430ConnectionScope.NONE
        ):
            raise ValueError("host tests and target builds cannot claim connected hardware")
        if self.run.evidence_level is Msp430EvidenceLevel.LAUNCHPAD_HIL:
            if self.hardware.connection_scope is Msp430ConnectionScope.NONE:
                raise ValueError("LAUNCHPAD_HIL requires an attached LaunchPad")
            if self.hardware.physical_measurements:
                raise ValueError("LAUNCHPAD_HIL cannot claim physical measurements")
        if self.run.evidence_level is Msp430EvidenceLevel.BENCH_MEASURED and (
            self.hardware.connection_scope is not Msp430ConnectionScope.EXTERNAL_BENCH
            or not self.hardware.physical_measurements
        ):
            raise ValueError("BENCH_MEASURED requires external-bench physical measurements")
        return self


MSP430_REPORT_JSON_SCHEMA: dict[str, Any] = Msp430ValidationReportV1.model_json_schema()


class Msp430ValidationCollectionRequest(StrictModel):
    source_path: str = Field(min_length=1, max_length=512)
    execution_context: ExecutionContext
    collected_at: datetime
    trust: EvidenceTrust
    scope: str = Field(default="msp430-validation", min_length=1, max_length=255)

    @field_validator("collected_at")
    @classmethod
    def collected_at_has_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collected_at must include a UTC offset")
        return value


class Msp430ValidationParseError(ValueError):
    def __init__(self, code: str, message: str, *, location: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.location = location


class Msp430ValidationReportCollector:
    def __init__(
        self,
        registry: ArtifactRegistry,
        *,
        max_nodes: int = DEFAULT_MAX_JSON_NODES,
        max_depth: int = DEFAULT_MAX_JSON_DEPTH,
    ) -> None:
        if min(max_nodes, max_depth) <= 0:
            raise ValueError("MSP430 validation parser limits must be positive")
        self._registry = registry
        self._max_nodes = max_nodes
        self._max_depth = max_depth

    def collect(self, request: Msp430ValidationCollectionRequest) -> CollectionResult:
        try:
            artifact = self._registry.register(
                request.source_path,
                media_type=MSP430_REPORT_MEDIA_TYPE,
            )
        except ArtifactError as exc:
            return self._rejected(exc.code, str(exc), request.source_path)
        try:
            report = self._parse(artifact)
            if report.subject.commit_sha != request.execution_context.commit_sha.lower():
                raise Msp430ValidationParseError(
                    "MSP430_REPORT_COMMIT_MISMATCH",
                    "report subject commit does not match the requested execution context",
                    location="$.subject.commit_sha",
                )
            return self._complete(artifact, request, report)
        except Msp430ValidationParseError as exc:
            return self._rejected(
                exc.code,
                str(exc),
                exc.location or request.source_path,
                artifact,
            )
        except ValidationError as exc:
            return self._rejected(
                "MSP430_REPORT_NORMALIZATION_INVALID",
                _validation_message(exc),
                request.source_path,
                artifact,
            )

    def _parse(self, artifact: RegisteredArtifact) -> Msp430ValidationReportV1:
        if artifact.reference.size_bytes > MAX_MSP430_REPORT_BYTES:
            raise Msp430ValidationParseError(
                "MSP430_REPORT_SIZE_LIMIT",
                f"report exceeds the {MAX_MSP430_REPORT_BYTES} byte contract limit",
            )
        try:
            enforce_json_structure_limits(
                artifact.content,
                max_nodes=self._max_nodes,
                max_depth=self._max_depth,
            )
        except StructureLimitError as exc:
            code = "MSP430_REPORT_NODE_LIMIT" if exc.kind == "node" else "MSP430_REPORT_DEPTH_LIMIT"
            raise Msp430ValidationParseError(code, str(exc)) from exc
        root = _load_json(artifact.content)
        if not isinstance(root, dict):
            raise Msp430ValidationParseError(
                "MSP430_REPORT_ROOT_INVALID", "report root must be an object", location="$"
            )
        version = root.get("schema_version")
        if not isinstance(version, str):
            raise Msp430ValidationParseError(
                "MSP430_REPORT_SCHEMA_VERSION_INVALID",
                "schema_version must be a string",
                location="$.schema_version",
            )
        if version != MSP430_REPORT_SCHEMA_VERSION:
            raise Msp430ValidationParseError(
                "MSP430_REPORT_SCHEMA_VERSION_UNSUPPORTED",
                f"supported schema version is {MSP430_REPORT_SCHEMA_VERSION}, received {version}",
                location="$.schema_version",
            )
        try:
            return Msp430ValidationReportV1.model_validate(root)
        except ValidationError as exc:
            error = exc.errors(include_url=False, include_input=False)[0]
            raise Msp430ValidationParseError(
                "MSP430_REPORT_CONTRACT_INVALID",
                f"report violates {MSP430_REPORT_SCHEMA_VERSION}: {error['msg']}",
                location=_error_location(error.get("loc", ())),
            ) from exc

    def _complete(
        self,
        artifact: RegisteredArtifact,
        request: Msp430ValidationCollectionRequest,
        report: Msp430ValidationReportV1,
    ) -> CollectionResult:
        verification_level, warnings = _verification_level(report)
        tags = {
            "collector": MSP430_COLLECTOR_VERSION,
            "schema_version": MSP430_REPORT_SCHEMA_VERSION,
            "evidence_level": report.run.evidence_level.value,
            "target": report.subject.target,
        }
        summary = EvidenceRecord(
            evidence_id=f"msp430-validation-run-{artifact.reference.sha256[:12]}",
            kind="msp430-validation.run",
            value={
                "run_id": report.run.run_id,
                "outcome": report.run.outcome.value,
                "evidence_level": report.run.evidence_level.value,
                "started_at": report.run.started_at,
                "ended_at": report.run.ended_at,
                "duration_seconds": report.run.duration_seconds,
                "subject": report.subject.model_dump(mode="json"),
                "hardware": report.hardware.model_dump(mode="json"),
                "counts": {
                    "checks": len(report.checks),
                    "metrics": len(report.metrics),
                    "source_artifacts": len(report.source_artifacts),
                    "corrections": len(report.corrections),
                },
                "source_artifacts": [
                    value.model_dump(mode="json") for value in report.source_artifacts
                ],
                "corrections": [value.model_dump(mode="json") for value in report.corrections],
                "limitations": report.limitations,
            },
            unit=None,
            status=report.run.outcome.value,
            scope=request.scope,
            source_tool=report.producer.name,
            source_version=report.producer.version,
            execution_context=request.execution_context,
            artifact=artifact.reference,
            collected_at=request.collected_at,
            trust=request.trust,
            verification_level=verification_level,
            tags={**tags, "record_type": "run"},
        )
        checks = [
            EvidenceRecord(
                evidence_id=_evidence_id(
                    "check", artifact.reference.sha256, report.run.run_id, check.id
                ),
                kind="msp430-validation.check",
                value={
                    "run_id": report.run.run_id,
                    "check_id": check.id,
                    "actual": check.actual,
                    "expected": check.expected,
                    "summary": check.summary,
                },
                unit=check.unit,
                status=check.status.value,
                scope=request.scope,
                source_tool=report.producer.name,
                source_version=report.producer.version,
                execution_context=request.execution_context,
                artifact=artifact.reference,
                collected_at=request.collected_at,
                trust=request.trust,
                verification_level=verification_level,
                tags={**tags, "record_type": "check", "check_id": check.id},
            )
            for check in report.checks
        ]
        metrics = [
            EvidenceRecord(
                evidence_id=_evidence_id(
                    "metric", artifact.reference.sha256, report.run.run_id, metric.name
                ),
                kind="msp430-validation.metric",
                value={"run_id": report.run.run_id, "name": metric.name, "value": metric.value},
                unit=metric.unit,
                status="observed",
                scope=request.scope,
                source_tool=report.producer.name,
                source_version=report.producer.version,
                execution_context=request.execution_context,
                artifact=artifact.reference,
                collected_at=request.collected_at,
                trust=request.trust,
                verification_level=verification_level,
                tags={**tags, "record_type": "metric", "metric_name": metric.name},
            )
            for metric in report.metrics
        ]
        if report.corrections:
            warnings.append(
                CollectionIssue(
                    code="MSP430_REVIEW_CORRECTION_RETAINED",
                    severity=IssueSeverity.WARNING,
                    message=(
                        "the report discloses a reviewed correction and retains the "
                        "original artifact digest"
                    ),
                    location="$.corrections",
                )
            )
        return CollectionResult(
            collector_name=MSP430_COLLECTOR_NAME,
            collector_version=MSP430_COLLECTOR_VERSION,
            status=CollectionStatus.COMPLETE,
            artifacts=[artifact.reference],
            evidence=[summary, *checks, *metrics],
            warnings=warnings,
            rejected_records=[],
        )

    def _rejected(
        self,
        code: str,
        message: str,
        location: str,
        artifact: RegisteredArtifact | None = None,
    ) -> CollectionResult:
        return CollectionResult(
            collector_name=MSP430_COLLECTOR_NAME,
            collector_version=MSP430_COLLECTOR_VERSION,
            status=CollectionStatus.REJECTED,
            artifacts=[] if artifact is None else [artifact.reference],
            evidence=[],
            warnings=[],
            rejected_records=[
                CollectionIssue(
                    code=code,
                    severity=IssueSeverity.REJECTION,
                    message=message[:1024],
                    location=location,
                )
            ],
        )


def _verification_level(
    report: Msp430ValidationReportV1,
) -> tuple[VerificationLevel, list[CollectionIssue]]:
    level = report.run.evidence_level
    if level is Msp430EvidenceLevel.HOST_TEST:
        return VerificationLevel.HOST_TESTED, []
    if level is Msp430EvidenceLevel.TARGET_BUILD:
        return VerificationLevel.TARGET_BUILT, []
    if level is Msp430EvidenceLevel.LAUNCHPAD_HIL:
        return VerificationLevel.SYSTEM_OBSERVED, [
            CollectionIssue(
                code="MSP430_HIL_SCOPE_RETAINED",
                severity=IssueSeverity.WARNING,
                message=(
                    "LaunchPad HIL is system_observed and does not establish external "
                    "bench measurement"
                ),
                location="$.run.evidence_level",
            )
        ]
    calibrated = bool(report.hardware.instruments) and all(
        value.calibration_status in {CalibrationStatus.CURRENT, CalibrationStatus.NOT_REQUIRED}
        for value in report.hardware.instruments
    )
    if calibrated:
        return VerificationLevel.PHYSICALLY_VERIFIED, []
    return VerificationLevel.SYSTEM_OBSERVED, [
        CollectionIssue(
            code="MSP430_BENCH_EVIDENCE_CAPPED",
            severity=IssueSeverity.WARNING,
            message=(
                "bench evidence is capped at system_observed because calibration "
                "provenance is incomplete"
            ),
            location="$.hardware.instruments",
        )
    ]


def _load_json(content: bytes) -> Any:
    if b"\x00" in content:
        raise Msp430ValidationParseError(
            "MSP430_REPORT_UNSUPPORTED_ENCODING", "report must be UTF-8 without NUL bytes"
        )
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise Msp430ValidationParseError(
            "MSP430_REPORT_UNSUPPORTED_ENCODING", "report must be UTF-8"
        ) from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except Msp430ValidationParseError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise Msp430ValidationParseError(
            "MSP430_REPORT_JSON_INVALID", f"invalid MSP430 report JSON: {exc}"
        ) from exc


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Msp430ValidationParseError(
                "MSP430_REPORT_DUPLICATE_KEY", f"duplicate JSON object key: {key}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise Msp430ValidationParseError(
        "MSP430_REPORT_NUMBER_INVALID", f"non-finite JSON number: {value}"
    )


def _validation_message(exc: ValidationError) -> str:
    error = exc.errors(include_url=False, include_input=False)[0]
    return f"cannot normalize MSP430 validation report: {error['msg']}"[:1024]


def _error_location(parts: Any) -> str:
    location = "$"
    for part in parts:
        location += f"[{part}]" if isinstance(part, int) else f".{part}"
    return location


def _evidence_id(record_type: str, artifact_sha256: str, run_id: str, name: str) -> str:
    identity = hashlib.sha256(f"{run_id}\0{name}".encode()).hexdigest()[:12]
    return f"msp430-validation-{record_type}-{artifact_sha256[:12]}-{identity}"


__all__ = [
    "MAX_MSP430_REPORT_BYTES",
    "MSP430_COLLECTOR_NAME",
    "MSP430_COLLECTOR_VERSION",
    "MSP430_REPORT_JSON_SCHEMA",
    "MSP430_REPORT_MEDIA_TYPE",
    "MSP430_REPORT_SCHEMA_VERSION",
    "Msp430EvidenceLevel",
    "Msp430ValidationCollectionRequest",
    "Msp430ValidationParseError",
    "Msp430ValidationReportCollector",
    "Msp430ValidationReportV1",
]
