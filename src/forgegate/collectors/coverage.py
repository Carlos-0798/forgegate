from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from pydantic import Field, field_validator

from forgegate.artifacts import ArtifactError, ArtifactRegistry, RegisteredArtifact
from forgegate.collectors.base import (
    CollectionIssue,
    CollectionResult,
    CollectionStatus,
    IssueSeverity,
)
from forgegate.domain.enums import EvidenceTrust, VerificationLevel
from forgegate.domain.models import EvidenceRecord, ExecutionContext, StrictModel

COVERAGE_XML_MEDIA_TYPE = "application/cobertura+xml"
LCOV_MEDIA_TYPE = "text/x-lcov"
COVERAGE_XML_COLLECTOR_VERSION = "forgegate-coverage-xml.v1"
LCOV_COLLECTOR_VERSION = "forgegate-lcov.v1"
DEFAULT_MAX_XML_ELEMENTS = 250_000
DEFAULT_MAX_XML_DEPTH = 64
DEFAULT_MAX_LCOV_LINES = 500_000
CONDITION_COVERAGE_PATTERN = re.compile(
    r"^\s*(?P<percent>\d+(?:\.\d+)?)%\s*"
    r"\(\s*(?P<covered>\d+)\s*/\s*(?P<total>\d+)\s*\)\s*$"
)


class CoverageCollectionRequest(StrictModel):
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


class CoverageParseError(ValueError):
    def __init__(self, code: str, message: str, *, location: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.location = location


@dataclass(frozen=True, slots=True)
class CoverageCounts:
    line_covered: int
    line_total: int
    branch_covered: int | None = None
    branch_total: int | None = None

    def merge(self, other: CoverageCounts) -> CoverageCounts:
        branch_known = self.branch_total is not None or other.branch_total is not None
        return CoverageCounts(
            line_covered=self.line_covered + other.line_covered,
            line_total=self.line_total + other.line_total,
            branch_covered=(self.branch_covered or 0) + (other.branch_covered or 0)
            if branch_known
            else None,
            branch_total=(self.branch_total or 0) + (other.branch_total or 0)
            if branch_known
            else None,
        )


@dataclass(frozen=True, slots=True)
class CoverageScope:
    name: str
    scope_type: str
    counts: CoverageCounts


class _CoverageCollectorBase:
    collector_name: ClassVar[str]
    collector_version: ClassVar[str]
    media_type: ClassVar[str]

    def __init__(self, registry: ArtifactRegistry) -> None:
        self._registry = registry

    def _register(self, request: CoverageCollectionRequest) -> RegisteredArtifact:
        return self._registry.register(request.source_path, media_type=self.media_type)

    def _complete(
        self,
        artifact: RegisteredArtifact,
        request: CoverageCollectionRequest,
        scopes: list[CoverageScope],
        warnings: list[CollectionIssue],
    ) -> CollectionResult:
        evidence: list[EvidenceRecord] = []
        for coverage_scope in scopes:
            for metric, covered, total in (
                (
                    "line",
                    coverage_scope.counts.line_covered,
                    coverage_scope.counts.line_total,
                ),
                (
                    "branch",
                    coverage_scope.counts.branch_covered,
                    coverage_scope.counts.branch_total,
                ),
            ):
                if covered is None or total is None:
                    continue
                scope_name = (
                    request.scope
                    if coverage_scope.scope_type == "repository"
                    else coverage_scope.name
                )
                evidence.append(
                    EvidenceRecord(
                        evidence_id=_evidence_id(
                            metric,
                            artifact.reference.sha256,
                            scope_name,
                        ),
                        kind=f"coverage.{metric}",
                        scope=scope_name,
                        value={
                            "covered": covered,
                            "total": total,
                            "percent": _percent(covered, total),
                        },
                        unit="percent",
                        status="not_applicable" if total == 0 else "observed",
                        source_tool=request.source_tool,
                        source_version=request.source_version,
                        execution_context=request.execution_context,
                        artifact=artifact.reference,
                        collected_at=request.collected_at,
                        trust=request.trust,
                        verification_level=request.verification_level,
                        tags={
                            "collector": self.collector_version,
                            "scope_type": coverage_scope.scope_type,
                        },
                    )
                )
        return CollectionResult(
            collector_name=self.collector_name,
            collector_version=self.collector_version,
            status=CollectionStatus.COMPLETE,
            artifacts=[artifact.reference],
            evidence=evidence,
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
            collector_name=self.collector_name,
            collector_version=self.collector_version,
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


class CoverageXmlCollector(_CoverageCollectorBase):
    collector_name = "coverage_xml"
    collector_version = COVERAGE_XML_COLLECTOR_VERSION
    media_type = COVERAGE_XML_MEDIA_TYPE

    def __init__(
        self,
        registry: ArtifactRegistry,
        *,
        max_elements: int = DEFAULT_MAX_XML_ELEMENTS,
        max_depth: int = DEFAULT_MAX_XML_DEPTH,
    ) -> None:
        super().__init__(registry)
        if max_elements <= 0 or max_depth <= 0:
            raise ValueError("XML element and depth limits must be positive")
        self._max_elements = max_elements
        self._max_depth = max_depth

    def collect(self, request: CoverageCollectionRequest) -> CollectionResult:
        try:
            artifact = self._register(request)
        except ArtifactError as exc:
            return self._rejected(exc.code, str(exc), location=request.source_path)
        try:
            scopes, warnings = self._parse(artifact)
        except CoverageParseError as exc:
            return self._rejected(
                exc.code,
                str(exc),
                location=exc.location or request.source_path,
                artifact=artifact,
            )
        return self._complete(artifact, request, scopes, warnings)

    def _parse(
        self, artifact: RegisteredArtifact
    ) -> tuple[list[CoverageScope], list[CollectionIssue]]:
        root = self._parse_xml(artifact.content)
        if _local_name(root.tag) != "coverage":
            raise CoverageParseError(
                "COVERAGE_ROOT_UNSUPPORTED",
                f"unsupported coverage root element: {_local_name(root.tag)}",
            )
        self._enforce_tree_limits(root)

        warnings: list[CollectionIssue] = []
        line_elements = [element for element in root.iter() if _local_name(element.tag) == "line"]
        classes = [element for element in root.iter() if _local_name(element.tag) == "class"]
        class_entries: list[tuple[ET.Element, str, CoverageCounts]] = []
        parsed_line_ids: set[int] = set()
        for index, class_element in enumerate(classes):
            class_lines = [
                element for element in class_element.iter() if _local_name(element.tag) == "line"
            ]
            if not class_lines:
                continue
            filename = class_element.get("filename")
            if filename is None or not filename.strip():
                raise CoverageParseError(
                    "COVERAGE_SCOPE_INVALID",
                    "coverage class with line data must declare filename",
                    location=f"class[{index}]",
                )
            module_scope = _scope_name("module", filename)
            counts, line_warnings = _counts_from_xml_lines(
                class_lines,
                location=module_scope,
                require_unique_numbers=True,
            )
            warnings.extend(line_warnings)
            class_entries.append((class_element, module_scope, counts))
            parsed_line_ids.update(id(element) for element in class_lines)

        if class_entries and any(id(element) not in parsed_line_ids for element in line_elements):
            raise CoverageParseError(
                "COVERAGE_LINE_SCOPE_AMBIGUOUS",
                "line data outside class scopes cannot be combined with class-scoped data",
            )

        module_counts: dict[str, CoverageCounts] = {}
        for _, module_scope, counts in class_entries:
            module_counts[module_scope] = _merge_optional(module_counts.get(module_scope), counts)

        package_counts: dict[str, CoverageCounts] = {}
        packages = [element for element in root.iter() if _local_name(element.tag) == "package"]
        for index, package in enumerate(packages):
            package_name = package.get("name")
            package_class_ids = {
                id(element) for element in package.iter() if _local_name(element.tag) == "class"
            }
            members = [
                counts
                for class_element, _, counts in class_entries
                if id(class_element) in package_class_ids
            ]
            if not members:
                continue
            if package_name is None or not package_name.strip():
                raise CoverageParseError(
                    "COVERAGE_SCOPE_INVALID",
                    "coverage package with line data must declare name",
                    location=f"package[{index}]",
                )
            package_scope = _scope_name("package", package_name)
            package_counts[package_scope] = _merge_optional(
                package_counts.get(package_scope), _merge_many(members)
            )

        observed: CoverageCounts | None = None
        if class_entries:
            observed = _merge_many(counts for _, _, counts in class_entries)
        elif line_elements:
            observed, line_warnings = _counts_from_xml_lines(
                line_elements,
                location="repository",
                require_unique_numbers=False,
            )
            warnings.extend(line_warnings)

        declared_line = _xml_declared_counts(
            root,
            covered_field="lines-covered",
            total_field="lines-valid",
            metric="line",
        )
        declared_branch = _xml_declared_counts(
            root,
            covered_field="branches-covered",
            total_field="branches-valid",
            metric="branch",
        )
        repository = _repository_counts(observed, declared_line, declared_branch)
        warnings.extend(_xml_declared_warnings(root, repository))
        if observed is None:
            warnings.append(
                _warning(
                    "COVERAGE_SUMMARY_ONLY",
                    "coverage XML uses root summary counts without detailed line records",
                )
            )
        elif observed.branch_total is None and declared_branch is not None:
            warnings.append(
                _warning(
                    "COVERAGE_BRANCH_SUMMARY_ONLY",
                    "branch coverage uses root summary counts without detailed branch records",
                )
            )
        if repository.branch_total is None:
            warnings.append(
                _warning(
                    "COVERAGE_BRANCH_UNAVAILABLE",
                    "coverage artifact contains no countable branch data",
                )
            )

        scopes = [CoverageScope("repository", "repository", repository)]
        scopes.extend(
            CoverageScope(name, "package", counts)
            for name, counts in sorted(package_counts.items())
        )
        scopes.extend(
            CoverageScope(name, "module", counts) for name, counts in sorted(module_counts.items())
        )
        return scopes, warnings

    def _parse_xml(self, content: bytes) -> ET.Element:
        upper = content.upper()
        if b"\x00" in content:
            raise CoverageParseError(
                "COVERAGE_UNSUPPORTED_ENCODING",
                "coverage XML must be UTF-8 compatible and cannot contain NUL bytes",
            )
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise CoverageParseError(
                "COVERAGE_FORBIDDEN_DECLARATION",
                "DOCTYPE and ENTITY declarations are forbidden",
            )
        try:
            return ET.fromstring(content)
        except ET.ParseError as exc:
            raise CoverageParseError(
                "COVERAGE_XML_INVALID", f"invalid coverage XML: {exc}"
            ) from exc

    def _enforce_tree_limits(self, root: ET.Element) -> None:
        observed = 0
        stack = [(root, 1)]
        while stack:
            element, depth = stack.pop()
            observed += 1
            if observed > self._max_elements:
                raise CoverageParseError(
                    "COVERAGE_ELEMENT_LIMIT",
                    f"coverage XML exceeds {self._max_elements} element limit",
                )
            if depth > self._max_depth:
                raise CoverageParseError(
                    "COVERAGE_DEPTH_LIMIT",
                    f"coverage XML exceeds {self._max_depth} depth limit",
                )
            stack.extend((child, depth + 1) for child in element)


@dataclass(slots=True)
class _LcovRecord:
    source: str
    start_line: int
    lines: dict[int, int] = field(default_factory=dict)
    branches: dict[tuple[int, str, str], int] = field(default_factory=dict)
    declared: dict[str, int] = field(default_factory=dict)
    function_data_seen: bool = False

    def counts(self) -> CoverageCounts:
        branch_covered: int | None
        branch_total: int | None
        if self.branches:
            branch_covered = sum(taken > 0 for taken in self.branches.values())
            branch_total = len(self.branches)
        elif "BRF" in self.declared and "BRH" in self.declared:
            branch_covered = self.declared["BRH"]
            branch_total = self.declared["BRF"]
        else:
            branch_covered = None
            branch_total = None
        return CoverageCounts(
            line_covered=sum(hits > 0 for hits in self.lines.values()),
            line_total=len(self.lines),
            branch_covered=branch_covered,
            branch_total=branch_total,
        )


class LcovCollector(_CoverageCollectorBase):
    collector_name = "lcov"
    collector_version = LCOV_COLLECTOR_VERSION
    media_type = LCOV_MEDIA_TYPE

    def __init__(
        self,
        registry: ArtifactRegistry,
        *,
        max_lines: int = DEFAULT_MAX_LCOV_LINES,
    ) -> None:
        super().__init__(registry)
        if max_lines <= 0:
            raise ValueError("LCOV line limit must be positive")
        self._max_lines = max_lines

    def collect(self, request: CoverageCollectionRequest) -> CollectionResult:
        try:
            artifact = self._register(request)
        except ArtifactError as exc:
            return self._rejected(exc.code, str(exc), location=request.source_path)
        try:
            scopes, warnings = self._parse(artifact.content)
        except CoverageParseError as exc:
            return self._rejected(
                exc.code,
                str(exc),
                location=exc.location or request.source_path,
                artifact=artifact,
            )
        return self._complete(artifact, request, scopes, warnings)

    def _parse(self, content: bytes) -> tuple[list[CoverageScope], list[CollectionIssue]]:
        if b"\x00" in content:
            raise CoverageParseError(
                "LCOV_UNSUPPORTED_ENCODING",
                "LCOV must be UTF-8 and cannot contain NUL bytes",
            )
        try:
            text = content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise CoverageParseError("LCOV_UNSUPPORTED_ENCODING", "LCOV must be UTF-8") from exc

        physical_lines = text.splitlines()
        if len(physical_lines) > self._max_lines:
            raise CoverageParseError(
                "LCOV_LINE_LIMIT",
                f"LCOV exceeds {self._max_lines} line limit",
            )

        records: list[_LcovRecord] = []
        current: _LcovRecord | None = None
        for line_number, raw_line in enumerate(physical_lines, start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line == "end_of_record":
                if current is None:
                    raise CoverageParseError(
                        "LCOV_RECORD_STATE_INVALID",
                        "end_of_record appears without an active source file",
                        location=f"line:{line_number}",
                    )
                _validate_lcov_record(current)
                records.append(current)
                current = None
                continue

            tag, separator, value = line.partition(":")
            if not separator:
                raise CoverageParseError(
                    "LCOV_RECORD_INVALID",
                    "LCOV record must use TAG:value syntax",
                    location=f"line:{line_number}",
                )
            if tag == "TN":
                continue
            if tag == "SF":
                if current is not None:
                    raise CoverageParseError(
                        "LCOV_RECORD_STATE_INVALID",
                        "new SF record started before end_of_record",
                        location=f"line:{line_number}",
                    )
                current = _LcovRecord(
                    source=_lcov_source(value, line_number=line_number),
                    start_line=line_number,
                )
                continue
            if current is None:
                raise CoverageParseError(
                    "LCOV_RECORD_STATE_INVALID",
                    f"{tag} appears before SF",
                    location=f"line:{line_number}",
                )
            _consume_lcov_field(current, tag, value, line_number=line_number)

        if current is not None:
            raise CoverageParseError(
                "LCOV_RECORD_UNTERMINATED",
                "LCOV source record is missing end_of_record",
                location=f"line:{current.start_line}",
            )
        if not records:
            raise CoverageParseError("LCOV_EMPTY", "LCOV contains no source records")

        warnings: list[CollectionIssue] = []
        module_counts: dict[str, CoverageCounts] = {}
        function_data_seen = False
        for record in records:
            counts = record.counts()
            module_scope = _scope_name("module", record.source)
            module_counts[module_scope] = _merge_optional(module_counts.get(module_scope), counts)
            warnings.extend(_lcov_declared_warnings(record, counts))
            if not record.branches and "BRF" in record.declared:
                warnings.append(
                    _warning(
                        "LCOV_BRANCH_SUMMARY_ONLY",
                        "branch coverage is based on BRF/BRH summary counts without BRDA records",
                        location=f"line:{record.start_line}",
                    )
                )
            function_data_seen = function_data_seen or record.function_data_seen

        repository = _merge_many(module_counts.values())
        if repository.branch_total is None:
            warnings.append(
                _warning(
                    "COVERAGE_BRANCH_UNAVAILABLE",
                    "LCOV artifact contains no BRDA branch data",
                )
            )
        if function_data_seen:
            warnings.append(
                _warning(
                    "LCOV_FUNCTION_DATA_NOT_NORMALIZED",
                    "LCOV function records were validated but are not normalized by collector v1",
                )
            )

        scopes = [CoverageScope("repository", "repository", repository)]
        scopes.extend(
            CoverageScope(name, "module", counts) for name, counts in sorted(module_counts.items())
        )
        return scopes, warnings


def _counts_from_xml_lines(
    lines: list[ET.Element],
    *,
    location: str,
    require_unique_numbers: bool,
) -> tuple[CoverageCounts, list[CollectionIssue]]:
    line_total = 0
    line_covered = 0
    branch_total: int | None = None
    branch_covered: int | None = None
    seen_numbers: set[int] = set()
    warnings: list[CollectionIssue] = []
    for index, line in enumerate(lines):
        line_number = _positive_int(
            line.get("number"),
            code="COVERAGE_LINE_INVALID",
            field="line.number",
            location=f"{location}/line[{index}]",
        )
        if require_unique_numbers and line_number in seen_numbers:
            raise CoverageParseError(
                "COVERAGE_LINE_DUPLICATE",
                f"duplicate line number {line_number}",
                location=location,
            )
        seen_numbers.add(line_number)
        hits = _nonnegative_int(
            line.get("hits"),
            code="COVERAGE_HITS_INVALID",
            field="line.hits",
            location=f"{location}/line[{index}]",
        )
        line_total += 1
        line_covered += int(hits > 0)

        branch = line.get("branch", "false").lower()
        if branch not in {"true", "false"}:
            raise CoverageParseError(
                "COVERAGE_BRANCH_INVALID",
                f"invalid branch flag: {branch}",
                location=f"{location}/line[{index}]",
            )
        if branch == "true":
            covered, total, condition_warning = _condition_counts(
                line.get("condition-coverage"),
                location=f"{location}/line[{index}]",
            )
            branch_covered = (branch_covered or 0) + covered
            branch_total = (branch_total or 0) + total
            if condition_warning is not None:
                warnings.append(condition_warning)
    return CoverageCounts(line_covered, line_total, branch_covered, branch_total), warnings


def _condition_counts(
    value: str | None, *, location: str
) -> tuple[int, int, CollectionIssue | None]:
    if value is None:
        raise CoverageParseError(
            "COVERAGE_BRANCH_INVALID",
            "branch line must include condition-coverage counts",
            location=location,
        )
    match = CONDITION_COVERAGE_PATTERN.fullmatch(value)
    if match is None:
        raise CoverageParseError(
            "COVERAGE_BRANCH_INVALID",
            f"invalid condition-coverage value: {value}",
            location=location,
        )
    covered = int(match.group("covered"))
    total = int(match.group("total"))
    if covered > total:
        raise CoverageParseError(
            "COVERAGE_COUNTS_INCONSISTENT",
            "covered branches exceed total branches",
            location=location,
        )
    declared_percent = _bounded_decimal(
        match.group("percent"),
        minimum=Decimal(0),
        maximum=Decimal(100),
        code="COVERAGE_RATE_INVALID",
        field="condition-coverage percent",
        location=location,
    )
    actual_percent = _percent_decimal(covered, total)
    warning = None
    if actual_percent is not None and abs(declared_percent - actual_percent) > Decimal("0.01"):
        warning = _warning(
            "COVERAGE_DECLARED_RATE_MISMATCH",
            f"declared branch percent={declared_percent} but counts imply {actual_percent}",
            location=location,
        )
    return covered, total, warning


def _xml_declared_counts(
    root: ET.Element,
    *,
    covered_field: str,
    total_field: str,
    metric: str,
) -> tuple[int, int] | None:
    raw_covered = root.get(covered_field)
    raw_total = root.get(total_field)
    if raw_covered is None and raw_total is None:
        return None
    if raw_covered is None or raw_total is None:
        raise CoverageParseError(
            "COVERAGE_SUMMARY_INVALID",
            f"declared {metric} coverage requires both {covered_field} and {total_field}",
        )
    covered = _nonnegative_int(
        raw_covered,
        code="COVERAGE_SUMMARY_INVALID",
        field=covered_field,
        location=f"@{covered_field}",
    )
    total = _nonnegative_int(
        raw_total,
        code="COVERAGE_SUMMARY_INVALID",
        field=total_field,
        location=f"@{total_field}",
    )
    if covered > total:
        raise CoverageParseError(
            "COVERAGE_COUNTS_INCONSISTENT",
            f"{covered_field} exceeds {total_field}",
        )
    return covered, total


def _repository_counts(
    observed: CoverageCounts | None,
    declared_line: tuple[int, int] | None,
    declared_branch: tuple[int, int] | None,
) -> CoverageCounts:
    if observed is None and declared_line is None:
        raise CoverageParseError(
            "COVERAGE_SUMMARY_MISSING",
            "coverage XML contains neither countable lines nor declared line counts",
        )
    line_covered, line_total = (
        (observed.line_covered, observed.line_total)
        if observed is not None
        else declared_line or (0, 0)
    )
    if observed is not None and observed.branch_total is not None:
        branch_covered = observed.branch_covered
        branch_total = observed.branch_total
    elif declared_branch is not None:
        branch_covered, branch_total = declared_branch
    else:
        branch_covered = None
        branch_total = None
    return CoverageCounts(line_covered, line_total, branch_covered, branch_total)


def _xml_declared_warnings(root: ET.Element, repository: CoverageCounts) -> list[CollectionIssue]:
    warnings: list[CollectionIssue] = []
    comparisons = (
        ("lines-covered", repository.line_covered),
        ("lines-valid", repository.line_total),
        ("branches-covered", repository.branch_covered),
        ("branches-valid", repository.branch_total),
    )
    for field_name, actual in comparisons:
        raw = root.get(field_name)
        if raw is None or actual is None:
            continue
        declared = _nonnegative_int(
            raw,
            code="COVERAGE_SUMMARY_INVALID",
            field=field_name,
            location=f"@{field_name}",
        )
        if declared != actual:
            warnings.append(
                _warning(
                    "COVERAGE_DECLARED_COUNT_MISMATCH",
                    f"declared {field_name}={declared} but observed {actual}",
                    location=f"@{field_name}",
                )
            )

    for field_name, covered, total in (
        ("line-rate", repository.line_covered, repository.line_total),
        ("branch-rate", repository.branch_covered, repository.branch_total),
    ):
        raw = root.get(field_name)
        if raw is None:
            continue
        declared_rate = _bounded_decimal(
            raw,
            minimum=Decimal(0),
            maximum=Decimal(1),
            code="COVERAGE_RATE_INVALID",
            field=field_name,
            location=f"@{field_name}",
        )
        if covered is None or total is None:
            continue
        actual_rate = None if total == 0 else Decimal(covered) / Decimal(total)
        if actual_rate is not None and abs(declared_rate - actual_rate) > Decimal("0.0001"):
            warnings.append(
                _warning(
                    "COVERAGE_DECLARED_RATE_MISMATCH",
                    f"declared {field_name}={declared_rate} but counts imply {actual_rate}",
                    location=f"@{field_name}",
                )
            )
    return warnings


def _lcov_source(value: str, *, line_number: int) -> str:
    source = value.strip().replace("\\", "/")
    if not source or len(source) > 240 or any(ord(character) < 32 for character in source):
        raise CoverageParseError(
            "LCOV_SOURCE_INVALID",
            "LCOV SF path must contain 1-240 printable characters",
            location=f"line:{line_number}",
        )
    return source


def _consume_lcov_field(record: _LcovRecord, tag: str, value: str, *, line_number: int) -> None:
    location = f"line:{line_number}"
    if tag == "DA":
        parts = value.split(",")
        if len(parts) not in {2, 3}:
            raise CoverageParseError(
                "LCOV_DA_INVALID", "DA requires line,hits[,checksum]", location=location
            )
        number = _positive_int(parts[0], code="LCOV_DA_INVALID", field="DA line", location=location)
        hits = _nonnegative_int(
            parts[1], code="LCOV_DA_INVALID", field="DA hits", location=location
        )
        if number in record.lines:
            raise CoverageParseError(
                "LCOV_DA_DUPLICATE", f"duplicate DA line {number}", location=location
            )
        if len(parts) == 3 and not parts[2]:
            raise CoverageParseError(
                "LCOV_DA_INVALID", "DA checksum cannot be empty", location=location
            )
        record.lines[number] = hits
        return
    if tag == "BRDA":
        parts = value.split(",")
        if len(parts) != 4 or not parts[1] or not parts[2]:
            raise CoverageParseError(
                "LCOV_BRDA_INVALID",
                "BRDA requires line,block,branch,taken",
                location=location,
            )
        number = _positive_int(
            parts[0], code="LCOV_BRDA_INVALID", field="BRDA line", location=location
        )
        taken = (
            0
            if parts[3] == "-"
            else _nonnegative_int(
                parts[3], code="LCOV_BRDA_INVALID", field="BRDA taken", location=location
            )
        )
        key = (number, parts[1], parts[2])
        if key in record.branches:
            raise CoverageParseError(
                "LCOV_BRDA_DUPLICATE", "duplicate BRDA branch", location=location
            )
        record.branches[key] = taken
        return
    if tag in {"LF", "LH", "BRF", "BRH", "FNF", "FNH"}:
        parsed = _nonnegative_int(value, code="LCOV_SUMMARY_INVALID", field=tag, location=location)
        if tag in record.declared:
            raise CoverageParseError(
                "LCOV_SUMMARY_DUPLICATE", f"duplicate {tag} summary", location=location
            )
        record.declared[tag] = parsed
        if tag in {"FNF", "FNH"}:
            record.function_data_seen = True
        return
    if tag == "FN":
        parts = value.split(",", maxsplit=1)
        if len(parts) != 2 or not parts[1]:
            raise CoverageParseError(
                "LCOV_FUNCTION_INVALID", "FN requires line,name", location=location
            )
        _positive_int(parts[0], code="LCOV_FUNCTION_INVALID", field="FN line", location=location)
        record.function_data_seen = True
        return
    if tag == "FNDA":
        parts = value.split(",", maxsplit=1)
        if len(parts) != 2 or not parts[1]:
            raise CoverageParseError(
                "LCOV_FUNCTION_INVALID", "FNDA requires count,name", location=location
            )
        _nonnegative_int(
            parts[0], code="LCOV_FUNCTION_INVALID", field="FNDA count", location=location
        )
        record.function_data_seen = True
        return
    raise CoverageParseError(
        "LCOV_TAG_UNSUPPORTED", f"unsupported LCOV tag: {tag}", location=location
    )


def _validate_lcov_record(record: _LcovRecord) -> None:
    if not record.lines:
        raise CoverageParseError(
            "LCOV_LINE_DATA_MISSING",
            "LCOV source record contains no DA line data",
            location=f"line:{record.start_line}",
        )
    for total_name, covered_name in (("LF", "LH"), ("BRF", "BRH"), ("FNF", "FNH")):
        if (total_name in record.declared) != (covered_name in record.declared):
            raise CoverageParseError(
                "LCOV_SUMMARY_INVALID",
                f"{total_name} and {covered_name} must be declared together",
                location=f"line:{record.start_line}",
            )
    if record.declared.get("LH", 0) > record.declared.get("LF", 0):
        raise CoverageParseError(
            "LCOV_COUNTS_INCONSISTENT",
            "declared LH exceeds LF",
            location=f"line:{record.start_line}",
        )
    if record.declared.get("BRH", 0) > record.declared.get("BRF", 0):
        raise CoverageParseError(
            "LCOV_COUNTS_INCONSISTENT",
            "declared BRH exceeds BRF",
            location=f"line:{record.start_line}",
        )
    if record.declared.get("FNH", 0) > record.declared.get("FNF", 0):
        raise CoverageParseError(
            "LCOV_COUNTS_INCONSISTENT",
            "declared FNH exceeds FNF",
            location=f"line:{record.start_line}",
        )


def _lcov_declared_warnings(record: _LcovRecord, counts: CoverageCounts) -> list[CollectionIssue]:
    actual = {
        "LF": counts.line_total,
        "LH": counts.line_covered,
        "BRF": counts.branch_total,
        "BRH": counts.branch_covered,
    }
    return [
        _warning(
            "LCOV_DECLARED_COUNT_MISMATCH",
            f"declared {name}={record.declared[name]} but observed {actual[name]}",
            location=f"line:{record.start_line}",
        )
        for name in ("LF", "LH", "BRF", "BRH")
        if name in record.declared
        and actual[name] is not None
        and record.declared[name] != actual[name]
    ]


def _scope_name(scope_type: str, value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    scope = f"{scope_type}:{normalized}"
    if len(scope) > 255:
        raise CoverageParseError(
            "COVERAGE_SCOPE_INVALID",
            f"{scope_type} scope exceeds 255 characters",
        )
    return scope


def _merge_optional(current: CoverageCounts | None, added: CoverageCounts) -> CoverageCounts:
    return added if current is None else current.merge(added)


def _merge_many(counts: Iterable[CoverageCounts]) -> CoverageCounts:
    result: CoverageCounts | None = None
    for item in counts:
        result = _merge_optional(result, item)
    if result is None:
        raise CoverageParseError("COVERAGE_SUMMARY_MISSING", "no coverage counts available")
    return result


def _positive_int(
    value: str | None,
    *,
    code: str,
    field: str,
    location: str,
) -> int:
    parsed = _nonnegative_int(value, code=code, field=field, location=location)
    if parsed == 0:
        raise CoverageParseError(code, f"{field} must be positive", location=location)
    return parsed


def _nonnegative_int(
    value: str | None,
    *,
    code: str,
    field: str,
    location: str,
) -> int:
    if value is None:
        raise CoverageParseError(code, f"missing integer field: {field}", location=location)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise CoverageParseError(
            code, f"invalid integer for {field}: {value}", location=location
        ) from exc
    if parsed < 0:
        raise CoverageParseError(code, f"negative integer for {field}", location=location)
    return parsed


def _bounded_decimal(
    value: str,
    *,
    minimum: Decimal,
    maximum: Decimal,
    code: str,
    field: str,
    location: str,
) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise CoverageParseError(
            code, f"invalid decimal for {field}: {value}", location=location
        ) from exc
    if not parsed.is_finite() or parsed < minimum or parsed > maximum:
        raise CoverageParseError(
            code,
            f"{field} must be finite and between {minimum} and {maximum}",
            location=location,
        )
    return parsed


def _percent(covered: int, total: int) -> float | None:
    percent = _percent_decimal(covered, total)
    return None if percent is None else float(round(percent, 6))


def _percent_decimal(covered: int, total: int) -> Decimal | None:
    return None if total == 0 else Decimal(covered) * Decimal(100) / Decimal(total)


def _evidence_id(metric: str, artifact_hash: str, scope: str) -> str:
    scope_digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()[:10]
    return f"coverage-{metric}-{artifact_hash[:12]}-{scope_digest}"


def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", maxsplit=1)[-1]


def _warning(code: str, message: str, *, location: str | None = None) -> CollectionIssue:
    return CollectionIssue(
        code=code,
        severity=IssueSeverity.WARNING,
        message=message,
        location=location,
    )
