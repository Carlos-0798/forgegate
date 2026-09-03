from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import Field, field_validator

from forgegate.artifacts import ArtifactError, ArtifactRegistry, RegisteredArtifact
from forgegate.bounded_parsing import StructureLimitError, enforce_xml_structure_limits
from forgegate.collectors.base import (
    CollectionIssue,
    CollectionResult,
    CollectionStatus,
    IssueSeverity,
)
from forgegate.domain.enums import EvidenceTrust, VerificationLevel
from forgegate.domain.models import EvidenceRecord, ExecutionContext, StrictModel

JUNIT_MEDIA_TYPE = "application/junit+xml"
JUNIT_COLLECTOR_NAME = "junit"
JUNIT_COLLECTOR_VERSION = "forgegate-junit.v1"
DEFAULT_MAX_XML_ELEMENTS = 100_000
DEFAULT_MAX_XML_DEPTH = 64


class JUnitCollectionRequest(StrictModel):
    source_path: str = Field(min_length=1, max_length=512)
    source_tool: str = Field(min_length=1, max_length=120)
    source_version: str = Field(min_length=1, max_length=120)
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


class JUnitParseError(ValueError):
    def __init__(self, code: str, message: str, *, location: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.location = location


@dataclass(frozen=True, slots=True)
class JUnitSummary:
    total: int
    passed: int
    failures: int
    errors: int
    skipped: int
    duration_seconds: float | None

    def as_value(self) -> dict[str, int | float | None]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failures": self.failures,
            "errors": self.errors,
            "skipped": self.skipped,
            "duration_seconds": self.duration_seconds,
        }


class JUnitCollector:
    def __init__(
        self,
        registry: ArtifactRegistry,
        *,
        max_elements: int = DEFAULT_MAX_XML_ELEMENTS,
        max_depth: int = DEFAULT_MAX_XML_DEPTH,
    ) -> None:
        if max_elements <= 0 or max_depth <= 0:
            raise ValueError("XML element and depth limits must be positive")
        self._registry = registry
        self._max_elements = max_elements
        self._max_depth = max_depth

    def collect(self, request: JUnitCollectionRequest) -> CollectionResult:
        try:
            artifact = self._registry.register(
                request.source_path,
                media_type=JUNIT_MEDIA_TYPE,
            )
        except ArtifactError as exc:
            return self._rejected(exc.code, str(exc), location=request.source_path)

        try:
            summary, warnings = self._parse(artifact)
        except JUnitParseError as exc:
            return self._rejected(
                exc.code,
                str(exc),
                location=exc.location or request.source_path,
                artifact=artifact,
            )

        evidence = EvidenceRecord(
            evidence_id=f"test-summary-{artifact.reference.sha256[:16]}",
            kind="test.summary",
            scope=request.scope,
            value=summary.as_value(),
            unit=None,
            status="passed" if summary.failures + summary.errors == 0 else "failed",
            source_tool=request.source_tool,
            source_version=request.source_version,
            execution_context=request.execution_context,
            artifact=artifact.reference,
            collected_at=request.collected_at,
            trust=request.trust,
            verification_level=request.verification_level,
            tags={"collector": JUNIT_COLLECTOR_VERSION},
        )
        return CollectionResult(
            collector_name=JUNIT_COLLECTOR_NAME,
            collector_version=JUNIT_COLLECTOR_VERSION,
            status=CollectionStatus.COMPLETE,
            artifacts=[artifact.reference],
            evidence=[evidence],
            warnings=warnings,
            rejected_records=[],
        )

    def _parse(self, artifact: RegisteredArtifact) -> tuple[JUnitSummary, list[CollectionIssue]]:
        content = artifact.content
        upper = content.upper()
        if b"\x00" in content:
            raise JUnitParseError(
                "JUNIT_UNSUPPORTED_ENCODING",
                "JUnit XML must be UTF-8 compatible and cannot contain NUL bytes",
            )
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise JUnitParseError(
                "JUNIT_FORBIDDEN_DECLARATION",
                "DOCTYPE and ENTITY declarations are forbidden",
            )
        try:
            enforce_xml_structure_limits(
                content,
                max_elements=self._max_elements,
                max_depth=self._max_depth,
            )
        except StructureLimitError as exc:
            if exc.kind == "element":
                raise JUnitParseError(
                    "JUNIT_ELEMENT_LIMIT",
                    f"JUnit XML exceeds {self._max_elements} element limit",
                ) from exc
            raise JUnitParseError(
                "JUNIT_DEPTH_LIMIT",
                f"JUnit XML exceeds {self._max_depth} depth limit",
            ) from exc
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise JUnitParseError("JUNIT_XML_INVALID", f"invalid JUnit XML: {exc}") from exc

        root_name = _local_name(root.tag)
        if root_name not in {"testsuite", "testsuites"}:
            raise JUnitParseError(
                "JUNIT_ROOT_UNSUPPORTED",
                f"unsupported JUnit root element: {root_name}",
            )
        self._enforce_tree_limits(root)

        cases = [element for element in root.iter() if _local_name(element.tag) == "testcase"]
        if cases:
            summary = self._summary_from_cases(cases)
            warnings = self._declared_mismatch_warnings(root, summary)
            if summary.duration_seconds is None:
                warnings.append(
                    _warning(
                        "JUNIT_DURATION_INCOMPLETE",
                        "one or more test cases omitted duration; "
                        "aggregate duration is unavailable",
                    )
                )
            return summary, warnings
        return self._summary_from_attributes(root), []

    def _enforce_tree_limits(self, root: ET.Element) -> None:
        observed = 0
        stack = [(root, 1)]
        while stack:
            element, depth = stack.pop()
            observed += 1
            if observed > self._max_elements:
                raise JUnitParseError(
                    "JUNIT_ELEMENT_LIMIT",
                    f"JUnit XML exceeds {self._max_elements} element limit",
                )
            if depth > self._max_depth:
                raise JUnitParseError(
                    "JUNIT_DEPTH_LIMIT",
                    f"JUnit XML exceeds {self._max_depth} depth limit",
                )
            stack.extend((child, depth + 1) for child in element)

    def _summary_from_cases(self, cases: list[ET.Element]) -> JUnitSummary:
        failures = 0
        errors = 0
        skipped = 0
        durations: list[Decimal] = []
        complete_duration = True

        for index, case in enumerate(cases):
            outcomes = {
                _local_name(child.tag)
                for child in case
                if _local_name(child.tag) in {"failure", "error", "skipped"}
            }
            if len(outcomes) > 1:
                raise JUnitParseError(
                    "JUNIT_CASE_OUTCOME_CONFLICT",
                    "test case contains conflicting outcome elements",
                    location=f"testcase[{index}]",
                )
            failures += int("failure" in outcomes)
            errors += int("error" in outcomes)
            skipped += int("skipped" in outcomes)

            raw_time = case.get("time")
            if raw_time is None:
                complete_duration = False
            else:
                durations.append(_nonnegative_decimal(raw_time, field="testcase.time"))

        total = len(cases)
        passed = total - failures - errors - skipped
        duration = float(sum(durations, start=Decimal(0))) if complete_duration else None
        return JUnitSummary(
            total=total,
            passed=passed,
            failures=failures,
            errors=errors,
            skipped=skipped,
            duration_seconds=duration,
        )

    def _summary_from_attributes(self, root: ET.Element) -> JUnitSummary:
        sources = [root]
        if root.get("tests") is None and _local_name(root.tag) == "testsuites":
            sources = [child for child in root if _local_name(child.tag) == "testsuite"]
        if not sources or any(source.get("tests") is None for source in sources):
            raise JUnitParseError(
                "JUNIT_SUMMARY_MISSING",
                "JUnit report without test cases must declare test counts",
            )

        total = sum(_nonnegative_int(source.get("tests"), field="tests") for source in sources)
        failures = sum(
            _nonnegative_int(source.get("failures", "0"), field="failures") for source in sources
        )
        errors = sum(
            _nonnegative_int(source.get("errors", "0"), field="errors") for source in sources
        )
        skipped = sum(
            _nonnegative_int(source.get("skipped", "0"), field="skipped") for source in sources
        )
        passed = total - failures - errors - skipped
        if passed < 0:
            raise JUnitParseError(
                "JUNIT_COUNTS_INCONSISTENT",
                "failures, errors, and skipped exceed total tests",
            )

        raw_times = [source.get("time") for source in sources]
        duration = None
        if all(raw_time is not None for raw_time in raw_times):
            duration = float(
                sum(
                    (_nonnegative_decimal(raw_time, field="time") for raw_time in raw_times),
                    start=Decimal(0),
                )
            )
        return JUnitSummary(total, passed, failures, errors, skipped, duration)

    def _declared_mismatch_warnings(
        self, root: ET.Element, summary: JUnitSummary
    ) -> list[CollectionIssue]:
        if root.get("tests") is None:
            return []
        declared = {
            "tests": _nonnegative_int(root.get("tests"), field="tests"),
            "failures": _nonnegative_int(root.get("failures", "0"), field="failures"),
            "errors": _nonnegative_int(root.get("errors", "0"), field="errors"),
            "skipped": _nonnegative_int(root.get("skipped", "0"), field="skipped"),
        }
        actual = {
            "tests": summary.total,
            "failures": summary.failures,
            "errors": summary.errors,
            "skipped": summary.skipped,
        }
        return [
            _warning(
                "JUNIT_DECLARED_COUNT_MISMATCH",
                f"declared {name}={declared[name]} but observed {actual[name]}",
                location=f"@{name}",
            )
            for name in ("tests", "failures", "errors", "skipped")
            if declared[name] != actual[name]
        ]

    def _rejected(
        self,
        code: str,
        message: str,
        *,
        location: str,
        artifact: RegisteredArtifact | None = None,
    ) -> CollectionResult:
        return CollectionResult(
            collector_name=JUNIT_COLLECTOR_NAME,
            collector_version=JUNIT_COLLECTOR_VERSION,
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


def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", maxsplit=1)[-1]


def _nonnegative_int(value: str | None, *, field: str) -> int:
    if value is None:
        raise JUnitParseError("JUNIT_COUNT_INVALID", f"missing integer field: {field}")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise JUnitParseError(
            "JUNIT_COUNT_INVALID", f"invalid integer for {field}: {value}"
        ) from exc
    if parsed < 0:
        raise JUnitParseError("JUNIT_COUNT_INVALID", f"negative integer for {field}")
    return parsed


def _nonnegative_decimal(value: str | None, *, field: str) -> Decimal:
    if value is None:
        raise JUnitParseError("JUNIT_DURATION_INVALID", f"missing duration field: {field}")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise JUnitParseError(
            "JUNIT_DURATION_INVALID", f"invalid duration for {field}: {value}"
        ) from exc
    if not parsed.is_finite() or parsed < 0 or not math.isfinite(float(parsed)):
        raise JUnitParseError(
            "JUNIT_DURATION_INVALID", f"duration for {field} must be finite and nonnegative"
        )
    return parsed


def _warning(code: str, message: str, *, location: str | None = None) -> CollectionIssue:
    return CollectionIssue(
        code=code,
        severity=IssueSeverity.WARNING,
        message=message,
        location=location,
    )
