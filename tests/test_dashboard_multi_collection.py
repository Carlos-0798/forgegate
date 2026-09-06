import base64
import hashlib
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forgegate.assembly.models import EvidenceBundleAssembly
from forgegate.dashboard.collection import DashboardCollectionPreviewRequest, preview_collection
from tests.test_dashboard import ORIGIN_HEADER, _activate, _dashboard_client
from tests.test_dashboard_collection import _create, _payload

XML = (
    b'<coverage><packages><package name="demo"><classes><class filename="src/demo.c"><lines>'
    b'<line number="1" hits="1" branch="true" condition-coverage="50% (1/2)"/>'
    b'<line number="2" hits="0"/></lines></class></classes></package></packages></coverage>'
)
LCOV = (
    b"SF:src/demo.c\nDA:1,1\nDA:2,0\nBRDA:1,0,0,1\nBRDA:1,0,1,0\n"
    b"LF:2\nLH:1\nBRF:2\nBRH:1\nend_of_record\n"
)


def payload(fmt="coverage_xml", content=XML):
    single = _payload(b'<testsuite tests="4" failures="0" errors="0" skipped="0"/>')
    report = {
        key: single[key]
        for key in ("content_base64", "source_tool", "source_version", "collected_at")
    }
    return {
        "expected_revision": 1,
        "reported_commit": single["reported_commit"],
        "reports": [
            {**report, "format": "junit"},
            {
                **report,
                "format": fmt,
                "source_tool": "coverage-fixture",
                "collected_at": "2026-09-04T12:00:00Z",
                "content_base64": base64.b64encode(content).decode(),
            },
        ],
    }


@pytest.mark.parametrize(
    "fmt,content,covered,total", [("coverage_xml", XML, 1, 2), ("lcov", LCOV, 1, 2)]
)
def test_combination_preserves_each_source_and_exact_counts(fmt, content, covered, total):
    command = DashboardCollectionPreviewRequest.model_validate(payload(fmt, content))
    result = preview_collection("fixture", command)
    assert result.assembly is not None
    assert len(result.assembly.collections) == 2
    assert result.persistence == "NOT_RETAINED"
    coverage = result.collections[1]
    assert coverage.artifacts[0].sha256 == hashlib.sha256(content).hexdigest()
    line = next(
        record
        for record in coverage.evidence
        if record.kind == "coverage.line" and record.scope == "repository"
    )
    assert line.value["covered"] == covered
    assert line.value["total"] == total
    assert line.value["percent"] == covered * 100 / total
    for collection, report in zip(result.collections, command.reports, strict=True):
        for record in collection.evidence:
            assert record.trust == "unsigned_local"
            assert record.verification_level == "declared"
            assert record.collected_at == report.collected_at
            assert record.source_tool == report.source_tool
            assert record.execution_context.commit_sha == command.reported_commit


@pytest.mark.parametrize(
    "fmt,content",
    [
        ("coverage_xml", b"<broken"),
        ("lcov", b"not lcov"),
        ("coverage_xml", b"<!DOCTYPE x><coverage/>"),
    ],
)
def test_one_rejection_blocks_entire_assembly_even_with_warning_consent(fmt, content):
    for retain in (False, True):
        result = preview_collection(
            "fixture",
            DashboardCollectionPreviewRequest.model_validate(
                {**payload(fmt, content), "retain_warnings": retain}
            ),
        )
        assert result.collections[0].status == "COMPLETE"
        assert result.collections[1].status == "REJECTED"
        assert result.assembly is None


def test_warnings_require_explicit_consent_for_whole_selection():
    command = payload()
    command["reports"][0]["content_base64"] = base64.b64encode(
        b'<testsuite tests="2"><testcase/></testsuite>'
    ).decode()
    blocked = preview_collection(
        "fixture", DashboardCollectionPreviewRequest.model_validate(command)
    )
    assert blocked.assembly is None
    assert blocked.collections[0].warnings
    retained = preview_collection(
        "fixture",
        DashboardCollectionPreviewRequest.model_validate({**command, "retain_warnings": True}),
    )
    assert retained.assembly.warning_disposition == "retained"
    assert len(retained.assembly.collections) == 2


def test_large_normalized_coverage_is_rejected_without_partial_evidence():
    classes = b"".join(
        (
            f'<class filename="file-{i}.c"><lines><line number="1" hits="1" '
            'branch="true" condition-coverage="50% (1/2)"/></lines></class>'
        ).encode()
        for i in range(257)
    )
    report = (
        b'<coverage><packages><package name="demo"><classes>'
        + classes
        + b"</classes></package></packages></coverage>"
    )
    result = preview_collection(
        "fixture", DashboardCollectionPreviewRequest.model_validate(payload("coverage_xml", report))
    )
    assert result.assembly is None
    assert result.collections[1].evidence == []
    assert result.collections[1].rejected_records[0].code == "DASHBOARD_REPORT_OUTPUT_LIMIT"


def test_unsafe_browser_integer_is_not_displayed_as_a_rounded_success():
    command = payload()
    command["reports"][0]["content_base64"] = base64.b64encode(
        b'<testsuite tests="9007199254740993"/>'
    ).decode()
    result = preview_collection(
        "fixture", DashboardCollectionPreviewRequest.model_validate(command)
    )
    assert result.assembly is None
    assert result.collections[0].rejected_records[0].code == "DASHBOARD_REPORT_OUTPUT_LIMIT"


@pytest.mark.parametrize(
    "change",
    [
        "empty",
        "three",
        "duplicate_junit",
        "duplicate_coverage",
        "duplicate_bytes",
        "format",
        "base64",
        "size",
        "time",
        "future",
        "trust",
        "path",
    ],
)
def test_bounded_contract_rejects_ambiguous_or_invalid_selection(change):
    command = payload()
    reports = command["reports"]
    if change == "empty":
        command["reports"] = []
    elif change == "three":
        reports.append(reports[0])
    elif change == "duplicate_junit":
        reports[1]["format"] = "junit"
    elif change == "duplicate_coverage":
        reports[0]["format"] = "lcov"
    elif change == "duplicate_bytes":
        reports[1]["content_base64"] = reports[0]["content_base64"]
    elif change == "format":
        reports[1]["format"] = "sarif"
    elif change == "base64":
        reports[1]["content_base64"] = "YR=="
    elif change == "size":
        reports[1]["content_base64"] = base64.b64encode(b"x" * 1048577).decode()
    elif change == "time":
        reports[1]["collected_at"] = "2026-01-01"
    elif change == "future":
        reports[1]["collected_at"] = "2999-01-01T00:00:00Z"
    elif change == "trust":
        reports[1]["trust"] = "signed_attestation"
    elif change == "path":
        reports[1]["server_path"] = "secret.xml"
    with pytest.raises(ValidationError):
        DashboardCollectionPreviewRequest.model_validate(command)


def test_single_coverage_is_supported_without_inventing_test_results():
    command = payload()
    command["reports"] = command["reports"][1:]
    result = preview_collection(
        "fixture", DashboardCollectionPreviewRequest.model_validate(command)
    )
    assert len(result.assembly.collections) == 1
    assert all(record.kind.startswith("coverage.") for record in result.assembly.bundle.evidence)


def test_exact_assembly_json_avoids_browser_number_roundtrip_fingerprint_failure():
    result = preview_collection(
        "fixture", DashboardCollectionPreviewRequest.model_validate(payload())
    )
    raw = result.model_dump(mode="json")["assembly_json"]
    assert '"percent":50.0' in raw
    assert EvidenceBundleAssembly.model_validate_json(raw) == result.assembly
    # JSON.parse + JSON.stringify converts integral floats to integers.
    with pytest.raises(ValidationError, match="assembly_id does not match"):
        EvidenceBundleAssembly.model_validate_json(raw.replace('"percent":50.0', '"percent":50'))
    assert json.loads(raw) == result.model_dump(mode="json")["assembly"]


def test_combined_preview_api_no_writes_auth_conflicts_and_separate_binding(
    tmp_path, repository_root
):
    with _dashboard_client(tmp_path, repository_root) as client:
        url = f"/app/api/candidates/cand-{'a' * 24}/collection-preview"
        assert client.post(url, headers=ORIGIN_HEADER, json=payload()).status_code == 401
        session = _activate(client)
        headers = {**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]}
        cid = _create(client, headers)
        url = f"/app/api/candidates/{cid}/collection-preview"
        assert client.post(url, headers=ORIGIN_HEADER, json=payload()).status_code == 403
        for change in ({"expected_revision": 0}, {"reported_commit": "f" * 40}):
            assert (
                client.post(url, headers=headers, json={**payload(), **change}).status_code == 409
            )
        audit_url = "/app/api/audit-events?project_id=sample-api"
        before = client.get(audit_url).json()
        response = client.post(url, headers=headers, json=payload())
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert client.get(audit_url).json() == before
        assembly = response.json()["assembly"]
        bound = client.post(
            f"/app/api/candidates/{cid}/evidence",
            headers={
                **headers,
                "Idempotency-Key": "combo:bind",
                "Content-Type": "application/json",
            },
            content='{"assembly":'
            + response.json()["assembly_json"]
            + ',"bound_at":'
            + json.dumps(datetime.now(UTC).isoformat())
            + "}",
        )
        assert bound.status_code == 200, bound.text
        assert bound.json()["assembly"] == assembly
        assert client.get(f"/app/api/candidates/{cid}").json()["status"] == "COLLECTING"
        assert client.post(url, headers=headers, json=payload()).status_code == 409
