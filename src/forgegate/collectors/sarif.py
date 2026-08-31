from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

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

SARIF_MEDIA_TYPE = "application/sarif+json"
SARIF_COLLECTOR_NAME = "sarif"
SARIF_COLLECTOR_VERSION = "forgegate-sarif.v1"
SARIF_VERSION = "2.1.0"
DEFAULT_MAX_JSON_NODES = 250_000
DEFAULT_MAX_JSON_DEPTH = 64
DEFAULT_MAX_RUNS = 100
DEFAULT_MAX_RESULTS = 100_000
DEFAULT_MAX_LOCATIONS = 32
DEFAULT_MAX_RULES = 100_000
SARIF_LEVELS = {"none", "note", "warning", "error"}
SARIF_KINDS = {"notApplicable", "pass", "fail", "review", "open", "informational"}
SARIF_BASELINE_STATES = {"new", "unchanged", "updated", "absent"}
SARIF_SUPPRESSION_KINDS = {"inSource", "external"}
SARIF_SUPPRESSION_STATUSES = {"accepted", "underReview", "rejected"}
MATERIAL_RESULT_DETAILS = {
    "attachments",
    "codeFlows",
    "fixes",
    "graphs",
    "hostedViewerUri",
    "relatedLocations",
    "stacks",
    "webRequest",
    "webResponse",
    "workItemUris",
}


class SarifCollectionRequest(StrictModel):
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


class SarifParseError(ValueError):
    def __init__(self, code: str, message: str, *, location: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.location = location


@dataclass(frozen=True, slots=True)
class SarifRule:
    rule_id: str
    name: str | None
    short_description: str | None
    help_uri: str | None
    default_level: str | None
    tags: tuple[str, ...]

    def as_value(self) -> dict[str, Any]:
        return {
            "id": self.rule_id,
            "name": self.name,
            "short_description": self.short_description,
            "help_uri": self.help_uri,
            "default_level": self.default_level,
            "tags": list(self.tags),
        }


@dataclass(frozen=True, slots=True)
class SarifTool:
    name: str
    version: str
    semantic_version: str | None
    information_uri: str | None
    rules: tuple[SarifRule, ...]

    def as_value(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "semantic_version": self.semantic_version,
            "information_uri": self.information_uri,
        }


@dataclass(frozen=True, slots=True)
class SarifFinding:
    run_index: int
    result_index: int
    rule_id: str
    level: str
    kind: str
    message: str
    locations: tuple[dict[str, Any], ...]
    fingerprint: dict[str, str]
    fingerprints: dict[str, str]
    partial_fingerprints: dict[str, str]
    suppression_states: tuple[dict[str, str | None], ...]
    baseline_state: str | None
    tool: SarifTool
    rule: SarifRule | None

    @property
    def is_suppressed(self) -> bool:
        return any(item["status"] == "accepted" for item in self.suppression_states)

    def as_value(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "level": self.level,
            "kind": self.kind,
            "message": self.message,
            "locations": list(self.locations),
            "fingerprint": self.fingerprint,
            "fingerprints": self.fingerprints,
            "partial_fingerprints": self.partial_fingerprints,
            "suppression_states": list(self.suppression_states),
            "baseline_state": self.baseline_state,
            "tool": self.tool.as_value(),
            "rule": None if self.rule is None else self.rule.as_value(),
        }


class SarifCollector:
    def __init__(
        self,
        registry: ArtifactRegistry,
        *,
        max_nodes: int = DEFAULT_MAX_JSON_NODES,
        max_depth: int = DEFAULT_MAX_JSON_DEPTH,
        max_runs: int = DEFAULT_MAX_RUNS,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> None:
        if min(max_nodes, max_depth, max_runs, max_results) <= 0:
            raise ValueError("SARIF parser limits must be positive")
        self._registry = registry
        self._max_nodes = max_nodes
        self._max_depth = max_depth
        self._max_runs = max_runs
        self._max_results = max_results

    def collect(self, request: SarifCollectionRequest) -> CollectionResult:
        try:
            artifact = self._registry.register(
                request.source_path,
                media_type=SARIF_MEDIA_TYPE,
            )
        except ArtifactError as exc:
            return self._rejected(exc.code, str(exc), location=request.source_path)

        try:
            findings, tools, warnings = self._parse(artifact.content)
        except SarifParseError as exc:
            return self._rejected(
                exc.code,
                str(exc),
                location=exc.location or request.source_path,
                artifact=artifact,
            )
        return self._complete(artifact, request, findings, tools, warnings)

    def _parse(
        self, content: bytes
    ) -> tuple[list[SarifFinding], list[SarifTool], list[CollectionIssue]]:
        root = _load_json(content)
        self._enforce_tree_limits(root)
        document = _mapping(root, code="SARIF_ROOT_INVALID", location="$")
        version = _required_string(
            document,
            "version",
            code="SARIF_VERSION_INVALID",
            location="$.version",
            maximum=32,
        )
        if version != SARIF_VERSION:
            raise SarifParseError(
                "SARIF_VERSION_UNSUPPORTED",
                f"supported SARIF version is {SARIF_VERSION}, received {version}",
                location="$.version",
            )

        warnings: list[CollectionIssue] = []
        schema_uri = document.get("$schema")
        if schema_uri is not None:
            schema_uri = _string(
                schema_uri,
                code="SARIF_SCHEMA_URI_INVALID",
                location="$.$schema",
                maximum=2048,
            )
            if not any(marker in schema_uri for marker in ("sarif-schema-2.1.0", "sarif-2.1.0")):
                warnings.append(
                    _warning(
                        "SARIF_SCHEMA_URI_UNRECOGNIZED",
                        "SARIF $schema URI does not identify the 2.1.0 schema",
                        location="$.$schema",
                    )
                )

        runs = _required_list(document, "runs", code="SARIF_RUNS_INVALID", location="$.runs")
        if not runs:
            raise SarifParseError(
                "SARIF_RUNS_INVALID", "SARIF runs cannot be empty", location="$.runs"
            )
        if len(runs) > self._max_runs:
            raise SarifParseError(
                "SARIF_RUN_LIMIT",
                f"SARIF exceeds {self._max_runs} run limit",
                location="$.runs",
            )

        findings: list[SarifFinding] = []
        tools: list[SarifTool] = []
        observed_results = 0
        for run_index, raw_run in enumerate(runs):
            run_location = f"$.runs[{run_index}]"
            run = _mapping(raw_run, code="SARIF_RUN_INVALID", location=run_location)
            tool = _parse_tool(run.get("tool"), location=f"{run_location}.tool")
            tools.append(tool)
            _validate_invocations(run.get("invocations"), location=f"{run_location}.invocations")

            raw_results = run.get("results", [])
            results = _list(
                raw_results, code="SARIF_RESULTS_INVALID", location=f"{run_location}.results"
            )
            observed_results += len(results)
            if observed_results > self._max_results:
                raise SarifParseError(
                    "SARIF_RESULT_LIMIT",
                    f"SARIF exceeds {self._max_results} result limit",
                    location=f"{run_location}.results",
                )
            for result_index, raw_result in enumerate(results):
                result_location = f"{run_location}.results[{result_index}]"
                finding, finding_warnings = _parse_result(
                    raw_result,
                    tool=tool,
                    run_index=run_index,
                    result_index=result_index,
                    location=result_location,
                )
                findings.append(finding)
                warnings.extend(finding_warnings)
        return findings, tools, warnings

    def _enforce_tree_limits(self, root: Any) -> None:
        observed = 0
        stack: list[tuple[Any, int]] = [(root, 1)]
        while stack:
            value, depth = stack.pop()
            observed += 1
            if observed > self._max_nodes:
                raise SarifParseError(
                    "SARIF_NODE_LIMIT",
                    f"SARIF exceeds {self._max_nodes} JSON node limit",
                )
            if depth > self._max_depth:
                raise SarifParseError(
                    "SARIF_DEPTH_LIMIT",
                    f"SARIF exceeds {self._max_depth} JSON depth limit",
                )
            if isinstance(value, dict):
                stack.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list):
                stack.extend((item, depth + 1) for item in value)

    def _complete(
        self,
        artifact: RegisteredArtifact,
        request: SarifCollectionRequest,
        findings: list[SarifFinding],
        tools: list[SarifTool],
        warnings: list[CollectionIssue],
    ) -> CollectionResult:
        by_level = {level: 0 for level in ("error", "warning", "note", "none")}
        by_kind = {kind: 0 for kind in sorted(SARIF_KINDS)}
        for finding in findings:
            by_level[finding.level] += 1
            by_kind[finding.kind] += 1

        evidence = [
            EvidenceRecord(
                evidence_id=f"static-analysis-summary-{artifact.reference.sha256[:16]}",
                kind="static_analysis.summary",
                scope=request.scope,
                value={
                    "total": len(findings),
                    "active": sum(not finding.is_suppressed for finding in findings),
                    "suppressed": sum(finding.is_suppressed for finding in findings),
                    "by_level": by_level,
                    "by_kind": by_kind,
                    "tools": [tool.as_value() for tool in tools],
                },
                unit=None,
                status="observed",
                source_tool="sarif",
                source_version=SARIF_VERSION,
                execution_context=request.execution_context,
                artifact=artifact.reference,
                collected_at=request.collected_at,
                trust=request.trust,
                verification_level=request.verification_level,
                tags={"collector": SARIF_COLLECTOR_VERSION},
            )
        ]
        evidence.extend(
            EvidenceRecord(
                evidence_id=(
                    f"static-analysis-finding-{artifact.reference.sha256[:12]}-"
                    f"r{finding.run_index}n{finding.result_index}"
                ),
                kind="static_analysis.finding",
                scope=request.scope,
                value=finding.as_value(),
                unit=None,
                status="suppressed" if finding.is_suppressed else finding.kind,
                source_tool=finding.tool.name,
                source_version=finding.tool.version,
                execution_context=request.execution_context,
                artifact=artifact.reference,
                collected_at=request.collected_at,
                trust=request.trust,
                verification_level=request.verification_level,
                tags={
                    "collector": SARIF_COLLECTOR_VERSION,
                    "run_index": str(finding.run_index),
                    "result_index": str(finding.result_index),
                },
            )
            for finding in findings
        )
        return CollectionResult(
            collector_name=SARIF_COLLECTOR_NAME,
            collector_version=SARIF_COLLECTOR_VERSION,
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
            collector_name=SARIF_COLLECTOR_NAME,
            collector_version=SARIF_COLLECTOR_VERSION,
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
        raise SarifParseError(
            "SARIF_UNSUPPORTED_ENCODING",
            "SARIF must be UTF-8 and cannot contain NUL bytes",
        )
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SarifParseError("SARIF_UNSUPPORTED_ENCODING", "SARIF must be UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except SarifParseError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise SarifParseError("SARIF_JSON_INVALID", f"invalid SARIF JSON: {exc}") from exc


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise SarifParseError(
                "SARIF_DUPLICATE_KEY",
                f"duplicate JSON object key: {key}",
            )
        value[key] = item
    return value


def _reject_json_constant(value: str) -> Any:
    raise SarifParseError("SARIF_NUMBER_INVALID", f"non-finite JSON number: {value}")


def _parse_tool(value: Any, *, location: str) -> SarifTool:
    tool_object = _mapping(value, code="SARIF_TOOL_INVALID", location=location)
    driver_location = f"{location}.driver"
    driver = _mapping(
        tool_object.get("driver"), code="SARIF_TOOL_INVALID", location=driver_location
    )
    name = _required_string(
        driver,
        "name",
        code="SARIF_TOOL_INVALID",
        location=f"{driver_location}.name",
        maximum=120,
    )
    version = _optional_string(
        driver.get("version"),
        code="SARIF_TOOL_INVALID",
        location=f"{driver_location}.version",
        maximum=120,
    )
    semantic_version = _optional_string(
        driver.get("semanticVersion"),
        code="SARIF_TOOL_INVALID",
        location=f"{driver_location}.semanticVersion",
        maximum=120,
    )
    information_uri = _optional_string(
        driver.get("informationUri"),
        code="SARIF_TOOL_INVALID",
        location=f"{driver_location}.informationUri",
        maximum=2048,
    )

    raw_rules = driver.get("rules", [])
    rules_list = _list(raw_rules, code="SARIF_RULES_INVALID", location=f"{driver_location}.rules")
    if len(rules_list) > DEFAULT_MAX_RULES:
        raise SarifParseError(
            "SARIF_RULE_LIMIT",
            f"SARIF tool exceeds {DEFAULT_MAX_RULES} rule limit",
            location=f"{driver_location}.rules",
        )
    rules: list[SarifRule] = []
    seen_ids: set[str] = set()
    for rule_index, raw_rule in enumerate(rules_list):
        rule = _parse_rule(raw_rule, location=f"{driver_location}.rules[{rule_index}]")
        if rule.rule_id in seen_ids:
            raise SarifParseError(
                "SARIF_RULE_DUPLICATE",
                f"duplicate SARIF rule id: {rule.rule_id}",
                location=f"{driver_location}.rules[{rule_index}].id",
            )
        seen_ids.add(rule.rule_id)
        rules.append(rule)
    return SarifTool(
        name=name,
        version=semantic_version or version or "unknown",
        semantic_version=semantic_version,
        information_uri=information_uri,
        rules=tuple(rules),
    )


def _parse_rule(value: Any, *, location: str) -> SarifRule:
    rule = _mapping(value, code="SARIF_RULE_INVALID", location=location)
    rule_id = _required_string(
        rule,
        "id",
        code="SARIF_RULE_INVALID",
        location=f"{location}.id",
        maximum=255,
    )
    name = _optional_string(
        rule.get("name"),
        code="SARIF_RULE_INVALID",
        location=f"{location}.name",
        maximum=255,
    )
    short_description = _optional_message(
        rule.get("shortDescription"), location=f"{location}.shortDescription"
    )
    help_uri = _optional_string(
        rule.get("helpUri"),
        code="SARIF_RULE_INVALID",
        location=f"{location}.helpUri",
        maximum=2048,
    )
    default_level = None
    if "defaultConfiguration" in rule:
        configuration = _mapping(
            rule["defaultConfiguration"],
            code="SARIF_RULE_INVALID",
            location=f"{location}.defaultConfiguration",
        )
        if "level" in configuration:
            default_level = _level(
                configuration["level"], location=f"{location}.defaultConfiguration.level"
            )

    tags: tuple[str, ...] = ()
    if "properties" in rule:
        properties = _mapping(
            rule["properties"], code="SARIF_RULE_INVALID", location=f"{location}.properties"
        )
        if "tags" in properties:
            raw_tags = _list(
                properties["tags"],
                code="SARIF_RULE_INVALID",
                location=f"{location}.properties.tags",
            )
            if len(raw_tags) > 64:
                raise SarifParseError(
                    "SARIF_RULE_INVALID",
                    "SARIF rule tags exceed 64 item limit",
                    location=f"{location}.properties.tags",
                )
            tags = tuple(
                _string(
                    item,
                    code="SARIF_RULE_INVALID",
                    location=f"{location}.properties.tags[{index}]",
                    maximum=255,
                )
                for index, item in enumerate(raw_tags)
            )
    return SarifRule(rule_id, name, short_description, help_uri, default_level, tags)


def _validate_invocations(value: Any, *, location: str) -> None:
    if value is None:
        return
    invocations = _list(value, code="SARIF_INVOCATIONS_INVALID", location=location)
    if len(invocations) > 32:
        raise SarifParseError(
            "SARIF_INVOCATION_LIMIT", "SARIF run exceeds 32 invocation limit", location=location
        )
    for index, raw_invocation in enumerate(invocations):
        item_location = f"{location}[{index}]"
        invocation = _mapping(
            raw_invocation, code="SARIF_INVOCATION_INVALID", location=item_location
        )
        successful = invocation.get("executionSuccessful")
        if not isinstance(successful, bool):
            raise SarifParseError(
                "SARIF_INVOCATION_INVALID",
                "SARIF invocation must declare boolean executionSuccessful",
                location=f"{item_location}.executionSuccessful",
            )
        if not successful:
            raise SarifParseError(
                "SARIF_INVOCATION_FAILED",
                "SARIF reports an unsuccessful analysis invocation",
                location=f"{item_location}.executionSuccessful",
            )


def _parse_result(
    value: Any,
    *,
    tool: SarifTool,
    run_index: int,
    result_index: int,
    location: str,
) -> tuple[SarifFinding, list[CollectionIssue]]:
    result = _mapping(value, code="SARIF_RESULT_INVALID", location=location)
    rule_id, rule = _resolve_rule(result, tool=tool, location=location)
    default_level = rule.default_level if rule is not None else None
    level = _level(result.get("level", default_level or "warning"), location=f"{location}.level")
    kind = _enum_string(
        result.get("kind", "fail"),
        allowed=SARIF_KINDS,
        code="SARIF_KIND_INVALID",
        location=f"{location}.kind",
    )
    message = _message(result.get("message"), location=f"{location}.message")
    raw_locations = result.get("locations", [])
    locations = _list(
        raw_locations, code="SARIF_LOCATIONS_INVALID", location=f"{location}.locations"
    )
    if len(locations) > DEFAULT_MAX_LOCATIONS:
        raise SarifParseError(
            "SARIF_LOCATION_LIMIT",
            f"SARIF result exceeds {DEFAULT_MAX_LOCATIONS} location limit",
            location=f"{location}.locations",
        )
    normalized_locations = tuple(
        _parse_location(item, location=f"{location}.locations[{index}]")
        for index, item in enumerate(locations)
    )

    fingerprints = _string_map(
        result.get("fingerprints", {}),
        code="SARIF_FINGERPRINT_INVALID",
        location=f"{location}.fingerprints",
    )
    partial_fingerprints = _string_map(
        result.get("partialFingerprints", {}),
        code="SARIF_FINGERPRINT_INVALID",
        location=f"{location}.partialFingerprints",
    )
    fingerprint = _select_fingerprint(
        fingerprints,
        partial_fingerprints,
        tool=tool,
        rule_id=rule_id,
        message=message,
        locations=normalized_locations,
    )
    suppression_states = _parse_suppressions(
        result.get("suppressions", []), location=f"{location}.suppressions"
    )
    baseline_state = None
    if "baselineState" in result:
        baseline_state = _enum_string(
            result["baselineState"],
            allowed=SARIF_BASELINE_STATES,
            code="SARIF_BASELINE_STATE_INVALID",
            location=f"{location}.baselineState",
        )

    warnings: list[CollectionIssue] = []
    ignored_details = sorted(MATERIAL_RESULT_DETAILS.intersection(result))
    if ignored_details:
        warnings.append(
            _warning(
                "SARIF_DETAIL_NOT_NORMALIZED",
                "validated result retains non-normalized detail in the artifact: "
                + ", ".join(ignored_details),
                location=location,
            )
        )
    return (
        SarifFinding(
            run_index=run_index,
            result_index=result_index,
            rule_id=rule_id,
            level=level,
            kind=kind,
            message=message,
            locations=normalized_locations,
            fingerprint=fingerprint,
            fingerprints=fingerprints,
            partial_fingerprints=partial_fingerprints,
            suppression_states=suppression_states,
            baseline_state=baseline_state,
            tool=tool,
            rule=rule,
        ),
        warnings,
    )


def _resolve_rule(
    result: dict[str, Any], *, tool: SarifTool, location: str
) -> tuple[str, SarifRule | None]:
    direct_id = None
    if "ruleId" in result:
        direct_id = _string(
            result["ruleId"],
            code="SARIF_RULE_REFERENCE_INVALID",
            location=f"{location}.ruleId",
            maximum=255,
        )
    indexed_rule = None
    if "ruleIndex" in result:
        index = _nonnegative_int(
            result["ruleIndex"],
            code="SARIF_RULE_REFERENCE_INVALID",
            location=f"{location}.ruleIndex",
        )
        if index >= len(tool.rules):
            raise SarifParseError(
                "SARIF_RULE_REFERENCE_INVALID",
                f"ruleIndex {index} is outside the driver rule table",
                location=f"{location}.ruleIndex",
            )
        indexed_rule = tool.rules[index]
    if direct_id is None and indexed_rule is None:
        raise SarifParseError(
            "SARIF_RULE_REFERENCE_INVALID",
            "SARIF result must declare ruleId or resolvable ruleIndex",
            location=location,
        )
    if direct_id is not None and indexed_rule is not None and direct_id != indexed_rule.rule_id:
        raise SarifParseError(
            "SARIF_RULE_REFERENCE_CONFLICT",
            "SARIF result ruleId conflicts with ruleIndex",
            location=location,
        )
    if direct_id is None:
        assert indexed_rule is not None
        rule_id = indexed_rule.rule_id
    else:
        rule_id = direct_id
    matching_rule = indexed_rule or next(
        (rule for rule in tool.rules if rule.rule_id == rule_id), None
    )
    return rule_id, matching_rule


def _parse_location(value: Any, *, location: str) -> dict[str, Any]:
    item = _mapping(value, code="SARIF_LOCATION_INVALID", location=location)
    physical = item.get("physicalLocation")
    logical = item.get("logicalLocations")
    if physical is None and logical is None:
        raise SarifParseError(
            "SARIF_LOCATION_INVALID",
            "SARIF location must contain physicalLocation or logicalLocations",
            location=location,
        )
    normalized: dict[str, Any] = {"physical": None, "logical": []}
    if physical is not None:
        physical_object = _mapping(
            physical,
            code="SARIF_LOCATION_INVALID",
            location=f"{location}.physicalLocation",
        )
        artifact_location = physical_object.get("artifactLocation")
        region_value = physical_object.get("region")
        if artifact_location is None and region_value is None:
            raise SarifParseError(
                "SARIF_LOCATION_INVALID",
                "physicalLocation must contain artifactLocation or region",
                location=f"{location}.physicalLocation",
            )
        uri = None
        uri_base_id = None
        if artifact_location is not None:
            artifact_object = _mapping(
                artifact_location,
                code="SARIF_LOCATION_INVALID",
                location=f"{location}.physicalLocation.artifactLocation",
            )
            uri = _optional_string(
                artifact_object.get("uri"),
                code="SARIF_LOCATION_INVALID",
                location=f"{location}.physicalLocation.artifactLocation.uri",
                maximum=2048,
            )
            uri_base_id = _optional_string(
                artifact_object.get("uriBaseId"),
                code="SARIF_LOCATION_INVALID",
                location=f"{location}.physicalLocation.artifactLocation.uriBaseId",
                maximum=255,
            )
            if uri is None and uri_base_id is None:
                raise SarifParseError(
                    "SARIF_LOCATION_INVALID",
                    "artifactLocation must contain uri or uriBaseId",
                    location=f"{location}.physicalLocation.artifactLocation",
                )
        region = (
            None
            if region_value is None
            else _parse_region(region_value, location=f"{location}.physicalLocation.region")
        )
        normalized["physical"] = {
            "uri": uri,
            "uri_base_id": uri_base_id,
            "region": region,
        }

    if logical is not None:
        logical_items = _list(
            logical, code="SARIF_LOCATION_INVALID", location=f"{location}.logicalLocations"
        )
        if not logical_items or len(logical_items) > 16:
            raise SarifParseError(
                "SARIF_LOCATION_INVALID",
                "logicalLocations must contain 1-16 items",
                location=f"{location}.logicalLocations",
            )
        normalized["logical"] = [
            _parse_logical_location(raw_logical, location=f"{location}.logicalLocations[{index}]")
            for index, raw_logical in enumerate(logical_items)
        ]
    return normalized


def _parse_region(value: Any, *, location: str) -> dict[str, int | None]:
    region = _mapping(value, code="SARIF_REGION_INVALID", location=location)
    normalized: dict[str, int | None] = {}
    for name in ("startLine", "startColumn", "endLine", "endColumn"):
        normalized[_snake_case(name)] = (
            None
            if name not in region
            else _positive_int(
                region[name], code="SARIF_REGION_INVALID", location=f"{location}.{name}"
            )
        )
    start_line = normalized["start_line"]
    end_line = normalized["end_line"]
    start_column = normalized["start_column"]
    end_column = normalized["end_column"]
    if start_line is None and start_column is None and end_line is None and end_column is None:
        raise SarifParseError(
            "SARIF_REGION_INVALID", "SARIF region contains no line/column bounds", location=location
        )
    if start_line is not None and end_line is not None and end_line < start_line:
        raise SarifParseError(
            "SARIF_REGION_INVALID", "endLine precedes startLine", location=location
        )
    if (
        start_line is not None
        and end_line == start_line
        and start_column is not None
        and end_column is not None
        and end_column < start_column
    ):
        raise SarifParseError(
            "SARIF_REGION_INVALID", "endColumn precedes startColumn", location=location
        )
    return normalized


def _parse_logical_location(value: Any, *, location: str) -> dict[str, str | None]:
    item = _mapping(value, code="SARIF_LOCATION_INVALID", location=location)
    name = _optional_string(
        item.get("name"),
        code="SARIF_LOCATION_INVALID",
        location=f"{location}.name",
        maximum=512,
    )
    fully_qualified_name = _optional_string(
        item.get("fullyQualifiedName"),
        code="SARIF_LOCATION_INVALID",
        location=f"{location}.fullyQualifiedName",
        maximum=1024,
    )
    kind = _optional_string(
        item.get("kind"),
        code="SARIF_LOCATION_INVALID",
        location=f"{location}.kind",
        maximum=120,
    )
    if name is None and fully_qualified_name is None:
        raise SarifParseError(
            "SARIF_LOCATION_INVALID",
            "logical location must contain name or fullyQualifiedName",
            location=location,
        )
    return {"name": name, "fully_qualified_name": fully_qualified_name, "kind": kind}


def _parse_suppressions(value: Any, *, location: str) -> tuple[dict[str, str | None], ...]:
    suppressions = _list(value, code="SARIF_SUPPRESSION_INVALID", location=location)
    if len(suppressions) > 16:
        raise SarifParseError(
            "SARIF_SUPPRESSION_LIMIT",
            "SARIF result exceeds 16 suppression limit",
            location=location,
        )
    normalized: list[dict[str, str | None]] = []
    for index, raw_suppression in enumerate(suppressions):
        item_location = f"{location}[{index}]"
        item = _mapping(raw_suppression, code="SARIF_SUPPRESSION_INVALID", location=item_location)
        kind = _enum_string(
            item.get("kind", "external"),
            allowed=SARIF_SUPPRESSION_KINDS,
            code="SARIF_SUPPRESSION_INVALID",
            location=f"{item_location}.kind",
        )
        status = _enum_string(
            item.get("status", "accepted"),
            allowed=SARIF_SUPPRESSION_STATUSES,
            code="SARIF_SUPPRESSION_INVALID",
            location=f"{item_location}.status",
        )
        justification = _optional_string(
            item.get("justification"),
            code="SARIF_SUPPRESSION_INVALID",
            location=f"{item_location}.justification",
            maximum=2048,
        )
        normalized.append({"kind": kind, "status": status, "justification": justification})
    return tuple(normalized)


def _select_fingerprint(
    fingerprints: dict[str, str],
    partial_fingerprints: dict[str, str],
    *,
    tool: SarifTool,
    rule_id: str,
    message: str,
    locations: tuple[dict[str, Any], ...],
) -> dict[str, str]:
    if fingerprints:
        key = sorted(fingerprints)[0]
        return {"source": f"fingerprints.{key}", "value": fingerprints[key]}
    if partial_fingerprints:
        key = sorted(partial_fingerprints)[0]
        return {"source": f"partialFingerprints.{key}", "value": partial_fingerprints[key]}
    canonical = json.dumps(
        {
            "tool": tool.name,
            "rule_id": rule_id,
            "message": message,
            "locations": locations,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "source": "forgegate-derived-sha256",
        "value": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def _message(value: Any, *, location: str) -> str:
    message = _mapping(value, code="SARIF_MESSAGE_INVALID", location=location)
    text = message.get("text")
    markdown = message.get("markdown")
    if text is not None:
        return _string(
            text, code="SARIF_MESSAGE_INVALID", location=f"{location}.text", maximum=4096
        )
    if markdown is not None:
        return _string(
            markdown,
            code="SARIF_MESSAGE_INVALID",
            location=f"{location}.markdown",
            maximum=4096,
        )
    raise SarifParseError(
        "SARIF_MESSAGE_INVALID",
        "SARIF message must contain text or markdown",
        location=location,
    )


def _optional_message(value: Any, *, location: str) -> str | None:
    return None if value is None else _message(value, location=location)


def _string_map(value: Any, *, code: str, location: str) -> dict[str, str]:
    mapping = _mapping(value, code=code, location=location)
    if len(mapping) > 64:
        raise SarifParseError(code, "fingerprint map exceeds 64 item limit", location=location)
    return {
        _string(key, code=code, location=location, maximum=255): _string(
            item, code=code, location=f"{location}.{key}", maximum=2048
        )
        for key, item in mapping.items()
    }


def _level(value: Any, *, location: str) -> str:
    return _enum_string(
        value,
        allowed=SARIF_LEVELS,
        code="SARIF_LEVEL_INVALID",
        location=location,
    )


def _enum_string(value: Any, *, allowed: set[str], code: str, location: str) -> str:
    parsed = _string(value, code=code, location=location, maximum=120)
    if parsed not in allowed:
        raise SarifParseError(
            code,
            f"unsupported value {parsed}; expected one of {', '.join(sorted(allowed))}",
            location=location,
        )
    return parsed


def _required_string(
    mapping: dict[str, Any],
    key: str,
    *,
    code: str,
    location: str,
    maximum: int,
) -> str:
    if key not in mapping:
        raise SarifParseError(code, f"missing required field: {key}", location=location)
    return _string(mapping[key], code=code, location=location, maximum=maximum)


def _optional_string(value: Any, *, code: str, location: str, maximum: int) -> str | None:
    return None if value is None else _string(value, code=code, location=location, maximum=maximum)


def _string(value: Any, *, code: str, location: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise SarifParseError(
            code,
            f"expected a non-empty string no longer than {maximum} characters",
            location=location,
        )
    if any(ord(character) < 32 and character not in "\t\r\n" for character in value):
        raise SarifParseError(
            code, "string contains forbidden control characters", location=location
        )
    return value


def _required_list(mapping: dict[str, Any], key: str, *, code: str, location: str) -> list[Any]:
    if key not in mapping:
        raise SarifParseError(code, f"missing required field: {key}", location=location)
    return _list(mapping[key], code=code, location=location)


def _list(value: Any, *, code: str, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise SarifParseError(code, "expected JSON array", location=location)
    return value


def _mapping(value: Any, *, code: str, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SarifParseError(code, "expected JSON object", location=location)
    return value


def _positive_int(value: Any, *, code: str, location: str) -> int:
    parsed = _nonnegative_int(value, code=code, location=location)
    if parsed == 0:
        raise SarifParseError(code, "expected positive integer", location=location)
    return parsed


def _nonnegative_int(value: Any, *, code: str, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SarifParseError(code, "expected nonnegative integer", location=location)
    return int(value)


def _snake_case(value: str) -> str:
    return "".join(
        f"_{character.lower()}" if character.isupper() else character for character in value
    )


def _warning(code: str, message: str, *, location: str | None = None) -> CollectionIssue:
    return CollectionIssue(
        code=code,
        severity=IssueSeverity.WARNING,
        message=message,
        location=location,
    )
