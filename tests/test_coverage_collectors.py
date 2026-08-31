import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from forgegate.artifacts import ArtifactRegistry
from forgegate.collectors import (
    CollectionStatus,
    CoverageCollectionRequest,
    CoverageXmlCollector,
    LcovCollector,
)
from forgegate.collectors.coverage import (
    CoverageParseError,
    _condition_counts,
    _local_name,
    _merge_many,
    _nonnegative_int,
    _scope_name,
)
from forgegate.domain.models import ExecutionContext

COMMIT = "b" * 40
COLLECTED_AT = datetime(2026, 8, 30, 22, 0, tzinfo=UTC)


def request(source_path: str, *, source_tool: str) -> CoverageCollectionRequest:
    return CoverageCollectionRequest(
        source_path=source_path,
        source_tool=source_tool,
        source_version="7.10.0",
        execution_context=ExecutionContext(commit_sha=COMMIT),
        collected_at=COLLECTED_AT,
        trust="claimed_ci_metadata",
        verification_level="ci_validated",
    )


def collect_xml(
    tmp_path: Path,
    xml: str | bytes,
    *,
    max_elements: int = 250_000,
    max_depth: int = 64,
):
    content = xml.encode("utf-8") if isinstance(xml, str) else xml
    (tmp_path / "coverage.xml").write_bytes(content)
    collector = CoverageXmlCollector(
        ArtifactRegistry(tmp_path), max_elements=max_elements, max_depth=max_depth
    )
    return collector.collect(request("coverage.xml", source_tool="coverage.py"))


def collect_lcov(tmp_path: Path, content: str | bytes, *, max_lines: int = 500_000):
    encoded = content.encode("utf-8") if isinstance(content, str) else content
    (tmp_path / "coverage.info").write_bytes(encoded)
    collector = LcovCollector(ArtifactRegistry(tmp_path), max_lines=max_lines)
    return collector.collect(request("coverage.info", source_tool="lcov"))


def evidence_by_kind_and_scope(result):
    return {(record.kind, record.scope): record for record in result.evidence}


def golden_projection(result):
    return {
        "collector_name": result.collector_name,
        "collector_version": result.collector_version,
        "status": result.status,
        "artifact": result.artifacts[0].model_dump(mode="json"),
        "evidence": [
            {
                "evidence_id": record.evidence_id,
                "kind": record.kind,
                "scope": record.scope,
                "value": record.value,
                "unit": record.unit,
                "status": record.status,
                "tags": record.tags,
            }
            for record in result.evidence
        ],
        "warnings": [warning.model_dump(mode="json") for warning in result.warnings],
        "rejected_records": [
            rejection.model_dump(mode="json") for rejection in result.rejected_records
        ],
    }


def test_sample_coverage_xml_normalizes_repository_package_and_module(
    repository_root: Path,
) -> None:
    root = repository_root / "examples/sample-python-api"
    result = CoverageXmlCollector(ArtifactRegistry(root)).collect(
        request("artifacts/coverage.xml", source_tool="coverage.py")
    )

    assert result.status is CollectionStatus.COMPLETE
    assert result.warnings == []
    assert len(result.evidence) == 6
    evidence = evidence_by_kind_and_scope(result)
    assert evidence["coverage.line", "repository"].value == {
        "covered": 2,
        "total": 3,
        "percent": 66.666667,
    }
    assert evidence["coverage.branch", "repository"].value == {
        "covered": 1,
        "total": 2,
        "percent": 50.0,
    }
    assert evidence["coverage.line", "package:sample.api"].value["total"] == 3
    assert evidence["coverage.branch", "module:src/sample/api.py"].value["covered"] == 1
    assert all(record.status == "observed" for record in result.evidence)


def test_sample_coverage_xml_matches_golden_output(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = CoverageXmlCollector(ArtifactRegistry(root)).collect(
        request("artifacts/coverage.xml", source_tool="coverage.py")
    )
    golden = json.loads(
        (repository_root / "tests/golden/coverage_xml.json").read_text(encoding="utf-8")
    )
    assert golden_projection(result) == golden


def test_namespaced_coverage_xml_is_supported(tmp_path: Path) -> None:
    result = collect_xml(
        tmp_path,
        """<c:coverage xmlns:c="urn:coverage">
        <c:packages><c:package name="pkg"><c:classes>
        <c:class filename="src/a.py"><c:lines>
        <c:line number="1" hits="1" />
        </c:lines></c:class></c:classes></c:package></c:packages>
        </c:coverage>""",
    )
    assert result.status is CollectionStatus.COMPLETE
    assert result.evidence[0].value["percent"] == 100.0
    assert result.warnings[0].code == "COVERAGE_BRANCH_UNAVAILABLE"


def test_summary_only_coverage_supports_zero_branch_opportunities(tmp_path: Path) -> None:
    result = collect_xml(
        tmp_path,
        '<coverage lines-valid="4" lines-covered="3" line-rate="0.75" '
        'branches-valid="0" branches-covered="0" branch-rate="0" />',
    )
    evidence = evidence_by_kind_and_scope(result)
    assert evidence["coverage.line", "repository"].value["percent"] == 75.0
    branch = evidence["coverage.branch", "repository"]
    assert branch.value == {"covered": 0, "total": 0, "percent": None}
    assert branch.status == "not_applicable"
    assert result.warnings[0].code == "COVERAGE_SUMMARY_ONLY"


def test_classless_line_data_is_collected_at_repository_scope(tmp_path: Path) -> None:
    result = collect_xml(
        tmp_path,
        "<coverage><lines><line number='1' hits='1'/>"
        "<line number='1' hits='0'/></lines></coverage>",
    )
    assert len(result.evidence) == 1
    assert result.evidence[0].value == {"covered": 1, "total": 2, "percent": 50.0}


def test_empty_class_and_package_nodes_do_not_create_false_scopes(tmp_path: Path) -> None:
    result = collect_xml(
        tmp_path,
        "<coverage lines-valid='1' lines-covered='1'>"
        "<package name='empty'><class filename='empty.py'/></package></coverage>",
    )
    assert [record.scope for record in result.evidence] == ["repository"]


def test_duplicate_package_names_are_aggregated(tmp_path: Path) -> None:
    result = collect_xml(
        tmp_path,
        """<coverage><package name="pkg"><class filename="a.py">
        <line number="1" hits="1"/></class></package>
        <package name="pkg"><class filename="b.py">
        <line number="1" hits="0"/></class></package></coverage>""",
    )
    evidence = evidence_by_kind_and_scope(result)
    assert evidence["coverage.line", "package:pkg"].value == {
        "covered": 1,
        "total": 2,
        "percent": 50.0,
    }


def test_declared_branch_rate_without_branch_counts_remains_unavailable(tmp_path: Path) -> None:
    result = collect_xml(
        tmp_path,
        "<coverage branch-rate='0'><line number='1' hits='1'/></coverage>",
    )
    assert [record.kind for record in result.evidence] == ["coverage.line"]
    assert result.warnings[0].code == "COVERAGE_BRANCH_UNAVAILABLE"


def test_declared_branch_counts_without_details_are_explicitly_audited(
    tmp_path: Path,
) -> None:
    result = collect_xml(
        tmp_path,
        "<coverage branches-valid='2' branches-covered='1'><line number='1' hits='1'/></coverage>",
    )
    evidence = evidence_by_kind_and_scope(result)
    assert evidence["coverage.branch", "repository"].value["percent"] == 50.0
    assert result.warnings[0].code == "COVERAGE_BRANCH_SUMMARY_ONLY"


def test_observed_counts_win_and_declared_mismatches_are_audited(tmp_path: Path) -> None:
    result = collect_xml(
        tmp_path,
        """<coverage lines-valid="3" lines-covered="0" line-rate="0.5">
        <packages><package name="pkg"><classes><class filename="a.py"><lines>
        <line number="1" hits="1"/><line number="2" hits="1"/>
        </lines></class></classes></package></packages></coverage>""",
    )
    assert result.evidence[0].value["covered"] == 2
    assert [warning.code for warning in result.warnings] == [
        "COVERAGE_DECLARED_COUNT_MISMATCH",
        "COVERAGE_DECLARED_COUNT_MISMATCH",
        "COVERAGE_DECLARED_RATE_MISMATCH",
        "COVERAGE_BRANCH_UNAVAILABLE",
    ]


def test_condition_percent_mismatch_is_audited(tmp_path: Path) -> None:
    result = collect_xml(
        tmp_path,
        """<coverage><packages><package name="pkg"><classes>
        <class filename="a.py"><lines>
        <line number="1" hits="1" branch="true" condition-coverage="10% (1/2)"/>
        </lines></class></classes></package></packages></coverage>""",
    )
    assert [warning.code for warning in result.warnings] == ["COVERAGE_DECLARED_RATE_MISMATCH"]


@pytest.mark.parametrize(
    ("xml", "code"),
    [
        ("<coverage>", "COVERAGE_XML_INVALID"),
        ("<!DOCTYPE coverage><coverage/>", "COVERAGE_FORBIDDEN_DECLARATION"),
        ("<!ENTITY x 'v'><coverage/>", "COVERAGE_FORBIDDEN_DECLARATION"),
        (b"<\x00coverage/>", "COVERAGE_UNSUPPORTED_ENCODING"),
        ("<report/>", "COVERAGE_ROOT_UNSUPPORTED"),
        ("<coverage/>", "COVERAGE_SUMMARY_MISSING"),
        ("<coverage lines-valid='1'/>", "COVERAGE_SUMMARY_INVALID"),
        (
            "<coverage lines-valid='1' lines-covered='2'/>",
            "COVERAGE_COUNTS_INCONSISTENT",
        ),
        (
            "<coverage><class filename='a.py'><line number='0' hits='1'/></class></coverage>",
            "COVERAGE_LINE_INVALID",
        ),
        (
            "<coverage><class filename='a.py'><line number='1' hits='-1'/></class></coverage>",
            "COVERAGE_HITS_INVALID",
        ),
        (
            "<coverage><class filename='a.py'>"
            "<line number='1' hits='1' branch='yes'/></class></coverage>",
            "COVERAGE_BRANCH_INVALID",
        ),
        (
            "<coverage><class filename='a.py'>"
            "<line number='1' hits='1' branch='true'/></class></coverage>",
            "COVERAGE_BRANCH_INVALID",
        ),
        (
            "<coverage><class filename='a.py'><line number='1' hits='1' "
            "branch='true' condition-coverage='50%'/></class></coverage>",
            "COVERAGE_BRANCH_INVALID",
        ),
        (
            "<coverage><class filename='a.py'><line number='1' hits='1' "
            "branch='true' condition-coverage='50% (2/1)'/></class></coverage>",
            "COVERAGE_COUNTS_INCONSISTENT",
        ),
        (
            "<coverage lines-valid='1' lines-covered='1' line-rate='NaN'/>",
            "COVERAGE_RATE_INVALID",
        ),
        (
            "<coverage lines-valid='1' lines-covered='1' line-rate='text'/>",
            "COVERAGE_RATE_INVALID",
        ),
        (
            "<coverage><class><line number='1' hits='1'/></class></coverage>",
            "COVERAGE_SCOPE_INVALID",
        ),
        (
            "<coverage><package><class filename='a.py'>"
            "<line number='1' hits='1'/></class></package></coverage>",
            "COVERAGE_SCOPE_INVALID",
        ),
        (
            "<coverage><class filename='a.py'><line number='1' hits='1'/>"
            "<line number='1' hits='0'/></class></coverage>",
            "COVERAGE_LINE_DUPLICATE",
        ),
        (
            "<coverage><class filename='a.py'><line number='1' hits='1'/></class>"
            "<line number='2' hits='1'/></coverage>",
            "COVERAGE_LINE_SCOPE_AMBIGUOUS",
        ),
    ],
)
def test_invalid_coverage_xml_is_rejected(tmp_path: Path, xml: str | bytes, code: str) -> None:
    result = collect_xml(tmp_path, xml)
    assert result.status is CollectionStatus.REJECTED
    assert result.evidence == []
    assert result.rejected_records[0].code == code


def test_coverage_xml_limits_are_enforced(tmp_path: Path) -> None:
    element_result = collect_xml(
        tmp_path,
        "<coverage lines-valid='0' lines-covered='0'><a/></coverage>",
        max_elements=1,
    )
    assert element_result.rejected_records[0].code == "COVERAGE_ELEMENT_LIMIT"

    depth_result = collect_xml(
        tmp_path,
        "<coverage lines-valid='0' lines-covered='0'><a><b/></a></coverage>",
        max_depth=2,
    )
    assert depth_result.rejected_records[0].code == "COVERAGE_DEPTH_LIMIT"


def test_coverage_xml_collector_limits_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="limits must be positive"):
        CoverageXmlCollector(ArtifactRegistry(tmp_path), max_elements=0)


def test_coverage_xml_artifact_boundary_failure_is_a_rejection(tmp_path: Path) -> None:
    result = CoverageXmlCollector(ArtifactRegistry(tmp_path)).collect(
        request("../coverage.xml", source_tool="coverage.py")
    )
    assert result.rejected_records[0].code == "ARTIFACT_BOUNDARY"
    assert result.artifacts == []


def test_sample_lcov_normalizes_repository_and_modules(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = LcovCollector(ArtifactRegistry(root)).collect(
        request("artifacts/coverage.info", source_tool="lcov")
    )

    assert result.status is CollectionStatus.COMPLETE
    assert result.warnings == []
    assert len(result.evidence) == 4
    evidence = evidence_by_kind_and_scope(result)
    assert evidence["coverage.line", "repository"].value == {
        "covered": 2,
        "total": 3,
        "percent": 66.666667,
    }
    assert evidence["coverage.branch", "repository"].value["percent"] == 50.0
    assert evidence["coverage.line", "module:src/sample/api.py"].value["covered"] == 2


def test_sample_lcov_matches_golden_output(repository_root: Path) -> None:
    root = repository_root / "examples/sample-python-api"
    result = LcovCollector(ArtifactRegistry(root)).collect(
        request("artifacts/coverage.info", source_tool="lcov")
    )
    golden = json.loads(
        (repository_root / "tests/golden/lcov_summary.json").read_text(encoding="utf-8")
    )
    assert golden_projection(result) == golden


def test_lcov_declared_mismatch_and_function_data_are_audited(tmp_path: Path) -> None:
    result = collect_lcov(
        tmp_path,
        """TN:unit
SF:src/a.py
FN:1,work
FNDA:2,work
FNF:1
FNH:1
DA:1,1
LF:2
LH:0
end_of_record
""",
    )
    assert [warning.code for warning in result.warnings] == [
        "LCOV_DECLARED_COUNT_MISMATCH",
        "LCOV_DECLARED_COUNT_MISMATCH",
        "COVERAGE_BRANCH_UNAVAILABLE",
        "LCOV_FUNCTION_DATA_NOT_NORMALIZED",
    ]


def test_lcov_without_branch_records_emits_only_line_evidence(tmp_path: Path) -> None:
    result = collect_lcov(tmp_path, "SF:a.py\nDA:1,0\nend_of_record\n")
    assert [record.kind for record in result.evidence] == [
        "coverage.line",
        "coverage.line",
    ]
    assert result.warnings[0].code == "COVERAGE_BRANCH_UNAVAILABLE"


def test_lcov_branch_summary_without_brda_is_explicitly_audited(tmp_path: Path) -> None:
    result = collect_lcov(
        tmp_path,
        "SF:a.py\nDA:1,1\nLF:1\nLH:1\nBRF:4\nBRH:3\nend_of_record\n",
    )
    evidence = evidence_by_kind_and_scope(result)
    assert evidence["coverage.branch", "repository"].value == {
        "covered": 3,
        "total": 4,
        "percent": 75.0,
    }
    assert [warning.code for warning in result.warnings] == ["LCOV_BRANCH_SUMMARY_ONLY"]


def test_lcov_repeated_source_records_are_aggregated(tmp_path: Path) -> None:
    result = collect_lcov(
        tmp_path,
        "SF:a.py\nDA:1,1\nend_of_record\nSF:a.py\nDA:2,0\nend_of_record\n",
    )
    evidence = evidence_by_kind_and_scope(result)
    assert evidence["coverage.line", "module:a.py"].value == {
        "covered": 1,
        "total": 2,
        "percent": 50.0,
    }


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"\xff", "LCOV_UNSUPPORTED_ENCODING"),
        (b"SF:a.py\x00\n", "LCOV_UNSUPPORTED_ENCODING"),
        ("", "LCOV_EMPTY"),
        ("end_of_record\n", "LCOV_RECORD_STATE_INVALID"),
        ("not-a-record\n", "LCOV_RECORD_INVALID"),
        ("DA:1,1\n", "LCOV_RECORD_STATE_INVALID"),
        ("SF:a.py\nSF:b.py\n", "LCOV_RECORD_STATE_INVALID"),
        ("SF:a.py\nDA:1,1\n", "LCOV_RECORD_UNTERMINATED"),
        ("SF:a.py\nend_of_record\n", "LCOV_LINE_DATA_MISSING"),
        ("SF:\nDA:1,1\nend_of_record\n", "LCOV_SOURCE_INVALID"),
        ("SF:a.py\nDA:0,1\nend_of_record\n", "LCOV_DA_INVALID"),
        ("SF:a.py\nDA:1,-1\nend_of_record\n", "LCOV_DA_INVALID"),
        ("SF:a.py\nDA:1\nend_of_record\n", "LCOV_DA_INVALID"),
        ("SF:a.py\nDA:1,1\nDA:1,2\nend_of_record\n", "LCOV_DA_DUPLICATE"),
        ("SF:a.py\nDA:1,1,\nend_of_record\n", "LCOV_DA_INVALID"),
        ("SF:a.py\nDA:1,1\nBRDA:1,,,1\nend_of_record\n", "LCOV_BRDA_INVALID"),
        (
            "SF:a.py\nDA:1,1\nBRDA:1,0,0,1\nBRDA:1,0,0,0\nend_of_record\n",
            "LCOV_BRDA_DUPLICATE",
        ),
        ("SF:a.py\nDA:1,1\nLF:one\nend_of_record\n", "LCOV_SUMMARY_INVALID"),
        (
            "SF:a.py\nDA:1,1\nLF:1\nLF:1\nend_of_record\n",
            "LCOV_SUMMARY_DUPLICATE",
        ),
        (
            "SF:a.py\nDA:1,1\nLF:1\nLH:2\nend_of_record\n",
            "LCOV_COUNTS_INCONSISTENT",
        ),
        (
            "SF:a.py\nDA:1,1\nLF:1\nend_of_record\n",
            "LCOV_SUMMARY_INVALID",
        ),
        (
            "SF:a.py\nDA:1,1\nBRF:1\nend_of_record\n",
            "LCOV_SUMMARY_INVALID",
        ),
        (
            "SF:a.py\nDA:1,1\nBRDA:1,0,0,1\nBRF:1\nBRH:2\nend_of_record\n",
            "LCOV_COUNTS_INCONSISTENT",
        ),
        (
            "SF:a.py\nDA:1,1\nFNF:1\nFNH:2\nend_of_record\n",
            "LCOV_COUNTS_INCONSISTENT",
        ),
        ("SF:a.py\nDA:1,1\nFN:bad\nend_of_record\n", "LCOV_FUNCTION_INVALID"),
        ("SF:a.py\nDA:1,1\nFNDA:bad\nend_of_record\n", "LCOV_FUNCTION_INVALID"),
        ("SF:a.py\nDA:1,1\nXX:value\nend_of_record\n", "LCOV_TAG_UNSUPPORTED"),
    ],
)
def test_invalid_lcov_is_rejected(tmp_path: Path, content: str | bytes, code: str) -> None:
    result = collect_lcov(tmp_path, content)
    assert result.status is CollectionStatus.REJECTED
    assert result.evidence == []
    assert result.rejected_records[0].code == code


def test_lcov_line_limit_is_enforced(tmp_path: Path) -> None:
    result = collect_lcov(
        tmp_path,
        "SF:a.py\nDA:1,1\nend_of_record\n",
        max_lines=2,
    )
    assert result.rejected_records[0].code == "LCOV_LINE_LIMIT"


def test_lcov_blank_lines_are_ignored(tmp_path: Path) -> None:
    result = collect_lcov(tmp_path, "\nSF:a.py\n\nDA:1,1\nend_of_record\n")
    assert result.status is CollectionStatus.COMPLETE


def test_lcov_collector_line_limit_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        LcovCollector(ArtifactRegistry(tmp_path), max_lines=0)


def test_lcov_artifact_boundary_failure_is_a_rejection(tmp_path: Path) -> None:
    result = LcovCollector(ArtifactRegistry(tmp_path)).collect(
        request("../coverage.info", source_tool="lcov")
    )
    assert result.rejected_records[0].code == "ARTIFACT_BOUNDARY"


def test_coverage_request_requires_timezone() -> None:
    with pytest.raises(ValidationError, match="must include a UTC offset"):
        CoverageCollectionRequest(
            source_path="coverage.xml",
            source_tool="coverage.py",
            source_version="7.10.0",
            execution_context=ExecutionContext(commit_sha=COMMIT),
            collected_at=datetime(2026, 8, 30, 22, 0),
            trust="unsigned_local",
            verification_level="host_tested",
        )


def test_defensive_coverage_helpers_fail_closed() -> None:
    assert _local_name(None) == ""
    assert _condition_counts("100% (0/0)", location="line:1") == (0, 0, None)
    with pytest.raises(CoverageParseError, match="exceeds 255"):
        _scope_name("module", "x" * 250)
    with pytest.raises(CoverageParseError, match="no coverage counts"):
        _merge_many([])
    with pytest.raises(CoverageParseError, match="missing integer field"):
        _nonnegative_int(
            None,
            code="COVERAGE_TEST_INVALID",
            field="count",
            location="test",
        )
