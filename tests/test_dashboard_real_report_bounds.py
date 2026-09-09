"""Bounded host-report compatibility; generated data is not an AVS test run."""

import pytest

from forgegate.dashboard.collection import DashboardCollectionPreviewRequest, preview_collection
from tests.test_dashboard_multi_collection import payload


@pytest.mark.parametrize("lines,complete", [(24994, True), (24995, False)])
def test_coverage_xml_exact_browser_element_boundary(lines, complete):
    content = (
        b'<coverage><packages><package name="demo"><classes><class filename="demo.py"><lines>'
        + b"".join(f'<line number="{i}" hits="1"/>'.encode() for i in range(1, lines + 1))
        + b"</lines></class></classes></package></packages></coverage>"
    )
    assert len(content) < 1048576
    result = preview_collection(
        "fixture", DashboardCollectionPreviewRequest.model_validate(payload(content=content))
    )
    coverage = result.collections[1]
    assert (coverage.status == "COMPLETE") is complete
    if complete:
        assert coverage.evidence[0].value["covered"] == lines
    else:
        assert coverage.rejected_records[0].code == "COVERAGE_ELEMENT_LIMIT"
        assert result.assembly is None


def test_warning_repreview_keeps_receipts_and_distinct_tool_metadata():
    data = payload(
        content=b'<coverage lines-covered="1" lines-valid="1" line-rate="1"><packages/></coverage>'
    )
    data["reports"][0].update(source_tool="pytest", source_version="8.4.2")
    data["reports"][1].update(
        source_tool="coverage.py", source_version="7.16.0", collected_at="2026-09-04T11:58:00Z"
    )
    first = preview_collection("fixture", DashboardCollectionPreviewRequest.model_validate(data))
    assert first.assembly is None
    assert first.collections[1].warnings
    data["retain_warnings"] = True
    reviewed = preview_collection("fixture", DashboardCollectionPreviewRequest.model_validate(data))
    assert reviewed.assembly is not None
    assert reviewed.collection_json == first.collection_json
    assert reviewed.collections == first.collections
    assert reviewed.collections[0].evidence[0].source_tool == "pytest"
    assert reviewed.collections[1].evidence[0].source_tool == "coverage.py"
    assert (
        reviewed.collections[1].evidence[0].collected_at
        != reviewed.collections[0].evidence[0].collected_at
    )
