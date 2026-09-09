import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from forgegate.artifacts import ArtifactRegistry
from forgegate.collectors import CollectionStatus, JUnitCollectionRequest, JUnitCollector
from forgegate.collectors.junit import (
    JUnitParseError,
    _local_name,
    _nonnegative_decimal,
    _nonnegative_int,
)
from forgegate.domain.models import ExecutionContext

COMMIT = "a" * 40
COLLECTED_AT = datetime(2026, 8, 30, 20, 30, tzinfo=UTC)


def request(source_path: str = "junit.xml") -> JUnitCollectionRequest:
    return JUnitCollectionRequest(
        source_path=source_path,
        source_tool="pytest",
        source_version="8.4.2",
        execution_context=ExecutionContext(commit_sha=COMMIT),
        collected_at=COLLECTED_AT,
        trust="claimed_ci_metadata",
        verification_level="ci_validated",
    )


def collect(
    tmp_path: Path,
    xml: str | bytes,
    *,
    max_elements: int = 100_000,
    max_depth: int = 64,
):
    content = xml.encode("utf-8") if isinstance(xml, str) else xml
    (tmp_path / "junit.xml").write_bytes(content)
    collector = JUnitCollector(
        ArtifactRegistry(tmp_path),
        max_elements=max_elements,
        max_depth=max_depth,
    )
    return collector.collect(request())


def test_sample_report_normalizes_summary(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = JUnitCollector(ArtifactRegistry(root)).collect(request("artifacts/junit.xml"))

    assert result.status is CollectionStatus.COMPLETE
    assert result.warnings == []
    assert result.rejected_records == []
    assert len(result.artifacts) == 1
    assert len(result.evidence) == 1
    evidence = result.evidence[0]
    assert evidence.kind == "test.summary"
    assert evidence.status == "failed"
    assert evidence.value == {
        "total": 4,
        "passed": 2,
        "failures": 1,
        "errors": 0,
        "skipped": 1,
        "duration_seconds": 0.42,
    }
    assert evidence.evidence_id.startswith("test-summary-")
    assert evidence.artifact == result.artifacts[0]


def test_sample_report_matches_golden_output(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = JUnitCollector(ArtifactRegistry(root)).collect(request("artifacts/junit.xml"))
    golden_path = repository_root / "tests/golden/junit_summary.json"

    assert result.model_dump(mode="json") == json.loads(golden_path.read_text(encoding="utf-8"))


def test_namespaced_testsuites_are_supported(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        """<j:testsuites xmlns:j="urn:junit">
        <j:testsuite><j:testcase name="ok" time="0.2" /></j:testsuite>
        </j:testsuites>""",
    )
    assert result.status is CollectionStatus.COMPLETE
    assert result.evidence[0].value["passed"] == 1


def test_failure_error_and_skip_are_distinct(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        """<testsuite tests="4" failures="1" errors="1" skipped="1">
        <testcase name="pass" time="0.1" />
        <testcase name="fail" time="0.1"><failure /></testcase>
        <testcase name="error" time="0.1"><error /></testcase>
        <testcase name="skip" time="0.1"><skipped /></testcase>
        </testsuite>""",
    )
    assert result.evidence[0].value == {
        "total": 4,
        "passed": 1,
        "failures": 1,
        "errors": 1,
        "skipped": 1,
        "duration_seconds": 0.4,
    }
    assert result.evidence[0].status == "failed"


def test_summary_only_testsuite_is_supported(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        '<testsuite tests="10" failures="1" errors="2" skipped="3" time="1.5" />',
    )
    assert result.status is CollectionStatus.COMPLETE
    assert result.evidence[0].value["passed"] == 4
    assert result.evidence[0].value["duration_seconds"] == 1.5


def test_summary_only_testsuites_aggregate_direct_suites(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        """<testsuites>
        <testsuite tests="2" failures="1" time="0.3" />
        <testsuite tests="3" skipped="1" time="0.7" />
        </testsuites>""",
    )
    assert result.evidence[0].value == {
        "total": 5,
        "passed": 3,
        "failures": 1,
        "errors": 0,
        "skipped": 1,
        "duration_seconds": 1.0,
    }


def test_mixed_suites_retain_summary_only_failures(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        '<testsuites><testsuite><testcase time="0.1" /></testsuite>'
        '<testsuite tests="1" failures="1" time="0.2" /></testsuites>',
    )
    assert result.status is CollectionStatus.COMPLETE
    assert result.evidence[0].value == {
        "total": 2,
        "passed": 1,
        "failures": 1,
        "errors": 0,
        "skipped": 0,
        "duration_seconds": 0.3,
    }
    assert result.evidence[0].status == "failed"
    assert result.warnings == []


def test_nested_suite_mismatch_is_not_hidden_by_unannotated_root(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        '<testsuites><testsuite tests="9" failures="2">'
        '<testcase time="0.1" /></testsuite></testsuites>',
    )
    assert result.evidence[0].value["total"] == 1
    assert [(item.code, item.location) for item in result.warnings] == [
        ("JUNIT_DECLARED_COUNT_MISMATCH", "/0@tests"),
        ("JUNIT_DECLARED_COUNT_MISMATCH", "/0@failures"),
    ]


def test_deep_allowed_suite_mismatch_has_bounded_location(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        "<testsuites>" * 48
        + '<testsuite tests="9"><testcase time="0.1" /></testsuite>'
        + "</testsuites>" * 48,
    )
    assert result.status is CollectionStatus.COMPLETE
    assert len(result.warnings) == 1
    assert result.warnings[0].location == "/0" * 48 + "@tests"


def test_nested_aggregate_parents_do_not_double_count(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        '<testsuites tests="3" failures="1"><testsuite tests="3" failures="1">'
        '<testcase time="0.1" /><testsuite tests="2" failures="1" time="0.2" />'
        "</testsuite></testsuites>",
    )
    assert result.evidence[0].value["total"] == 3
    assert result.evidence[0].value["passed"] == 2
    assert result.evidence[0].value["failures"] == 1
    assert result.warnings == []


@pytest.mark.parametrize("attributes", ['tests="1" errors="1"', 'tests="1" skipped="1"'])
def test_summary_only_child_outcomes_are_retained(tmp_path: Path, attributes: str) -> None:
    result = collect(
        tmp_path,
        '<testsuites><testsuite><testcase time="0.1" /></testsuite>'
        f"<testsuite {attributes} /></testsuites>",
    )
    assert result.evidence[0].value["total"] == 2
    assert result.evidence[0].value["passed"] == 1
    assert result.evidence[0].value["duration_seconds"] is None
    assert result.warnings[0].code == "JUNIT_DURATION_INCOMPLETE"


@pytest.mark.parametrize(
    ("xml", "code"),
    [
        ("<testsuite><group><testcase /></group></testsuite>", "JUNIT_STRUCTURE_UNSUPPORTED"),
        ('<testsuites><testsuite tests="1"/><testsuite /></testsuites>', "JUNIT_SUMMARY_MISSING"),
        (
            '<testsuite tests="1" time="1e308"><testcase time="1e308" />'
            '<testcase time="1e308" /></testsuite>',
            "JUNIT_DURATION_INVALID",
        ),
    ],
)
def test_ambiguous_or_incomplete_suite_structures_fail_closed(
    tmp_path: Path, xml: str, code: str
) -> None:
    result = collect(tmp_path, xml)
    assert result.status is CollectionStatus.REJECTED
    assert result.rejected_records[0].code == code


def test_declared_count_mismatch_is_audited_but_observation_wins(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        '<testsuite tests="9" failures="2"><testcase name="ok" time="0.1" /></testsuite>',
    )
    assert result.status is CollectionStatus.COMPLETE
    assert result.evidence[0].value["total"] == 1
    assert [warning.code for warning in result.warnings] == [
        "JUNIT_DECLARED_COUNT_MISMATCH",
        "JUNIT_DECLARED_COUNT_MISMATCH",
    ]


def test_missing_case_duration_does_not_create_partial_total(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        '<testsuite><testcase name="a" time="0.1"/><testcase name="b"/></testsuite>',
    )
    assert result.evidence[0].value["duration_seconds"] is None
    assert [warning.code for warning in result.warnings] == ["JUNIT_DURATION_INCOMPLETE"]


@pytest.mark.parametrize(
    ("xml", "code"),
    [
        ("<testsuite>", "JUNIT_XML_INVALID"),
        ("<!DOCTYPE testsuite><testsuite tests='0'/>", "JUNIT_FORBIDDEN_DECLARATION"),
        ("<!ENTITY x 'value'><testsuite tests='0'/>", "JUNIT_FORBIDDEN_DECLARATION"),
        (b"<\x00testsuite />", "JUNIT_UNSUPPORTED_ENCODING"),
        ("<report />", "JUNIT_ROOT_UNSUPPORTED"),
        ("<testsuite />", "JUNIT_SUMMARY_MISSING"),
        ("<testsuite tests='-1' />", "JUNIT_COUNT_INVALID"),
        ("<testsuite tests='one' />", "JUNIT_COUNT_INVALID"),
        ("<testsuite tests='1' failures='2' />", "JUNIT_COUNTS_INCONSISTENT"),
        ("<testsuite tests='1' time='NaN' />", "JUNIT_DURATION_INVALID"),
        ("<testsuite tests='1' time='Infinity' />", "JUNIT_DURATION_INVALID"),
        ("<testsuite tests='1' time='-0.1' />", "JUNIT_DURATION_INVALID"),
        ("<testsuite tests='1' time='not-a-number' />", "JUNIT_DURATION_INVALID"),
    ],
)
def test_invalid_reports_are_rejected_with_audit(
    tmp_path: Path, xml: str | bytes, code: str
) -> None:
    result = collect(tmp_path, xml)
    assert result.status is CollectionStatus.REJECTED
    assert result.evidence == []
    assert result.rejected_records[0].code == code
    assert len(result.artifacts) == 1


def test_conflicting_case_outcomes_are_rejected(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        "<testsuite><testcase name='x'><failure/><skipped/></testcase></testsuite>",
    )
    assert result.rejected_records[0].code == "JUNIT_CASE_OUTCOME_CONFLICT"
    assert result.rejected_records[0].location == "testcase[0]"


def test_summary_without_time_keeps_duration_unknown(tmp_path: Path) -> None:
    result = collect(tmp_path, "<testsuite tests='0' />")
    assert result.status is CollectionStatus.COMPLETE
    assert result.evidence[0].value["duration_seconds"] is None


def test_element_limit_is_enforced(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        "<testsuite><testcase name='x'><failure/></testcase></testsuite>",
        max_elements=2,
    )
    assert result.rejected_records[0].code == "JUNIT_ELEMENT_LIMIT"


def test_depth_limit_is_enforced(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        "<testsuite><group><testcase name='x' time='0.1'/></group></testsuite>",
        max_depth=2,
    )
    assert result.rejected_records[0].code == "JUNIT_DEPTH_LIMIT"


def test_artifact_boundary_failure_is_returned_as_rejection(tmp_path: Path) -> None:
    collector = JUnitCollector(ArtifactRegistry(tmp_path))
    result = collector.collect(request("../outside.xml"))
    assert result.status is CollectionStatus.REJECTED
    assert result.artifacts == []
    assert result.rejected_records[0].code == "ARTIFACT_BOUNDARY"


def test_collector_limits_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="limits must be positive"):
        JUnitCollector(ArtifactRegistry(tmp_path), max_elements=0)


def test_collection_timestamp_requires_timezone() -> None:
    with pytest.raises(ValidationError, match="must include a UTC offset"):
        JUnitCollectionRequest(
            source_path="junit.xml",
            source_tool="pytest",
            source_version="8.4.2",
            execution_context=ExecutionContext(commit_sha=COMMIT),
            collected_at=datetime(2026, 8, 30, 20, 30),
            trust="unsigned_local",
            verification_level="host_tested",
        )


def test_defensive_parsing_helpers_fail_closed() -> None:
    assert _local_name(None) == ""
    with pytest.raises(JUnitParseError, match="missing integer field"):
        _nonnegative_int(None, field="tests")
    with pytest.raises(JUnitParseError, match="missing duration field"):
        _nonnegative_decimal(None, field="time")
    assert _nonnegative_decimal("0.25", field="time") == Decimal("0.25")
