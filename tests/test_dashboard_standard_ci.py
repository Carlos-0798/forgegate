"""Four-family software evidence: synthetic values are not hardware measurements."""

import base64
import hashlib
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forgegate.collection_jobs import CollectionJobRequest, CollectionJobStore
from forgegate.config import load_config
from forgegate.dashboard.collection import DashboardCollectionPreviewRequest, preview_collection
from forgegate.policy import evaluate_policy
from tests.test_collection_jobs import fixture  # noqa: F401
from tests.test_dashboard import ORIGIN_HEADER, _activate, _dashboard_client
from tests.test_dashboard_collection import _create


def standard_payload(root, *, scan="clean.sarif", benchmark="benchmark.json"):
    base = root / "examples/dashboard-standard-ci"
    return {
        "expected_revision": 1,
        "reported_commit": "a" * 40,
        "reports": [
            {
                "format": fmt,
                "content_base64": base64.b64encode((base / name).read_bytes()).decode(),
                "source_tool": "caller-declared-tool",
                "source_version": "1",
                "collected_at": "2026-09-04T12:00:00Z",
            }
            for fmt, name in [
                ("junit", "tests.xml"),
                ("coverage_xml", "coverage.xml"),
                ("sarif", scan),
                ("benchmark_json", benchmark),
            ]
        ],
    }


@pytest.mark.parametrize(
    "scan,benchmark,expected",
    [
        ("clean.sarif", "benchmark.json", "PASS"),
        ("finding.sarif", "benchmark.json", "FAIL"),
        ("clean.sarif", "benchmark-slow.json", "FAIL"),
    ],
)
def test_four_report_values_and_policy_decisions(repository_root, scan, benchmark, expected):
    command = DashboardCollectionPreviewRequest.model_validate(
        standard_payload(repository_root, scan=scan, benchmark=benchmark)
    )
    result = preview_collection("fixture", command)
    assert result.assembly is not None
    assert len(result.collections) == 4
    assert all(item.status == "COMPLETE" for item in result.collections)
    for collection, report in zip(result.collections, command.reports, strict=True):
        raw = base64.b64decode(report.content_base64)
        assert collection.artifacts[0].sha256 == hashlib.sha256(raw).hexdigest()
        assert collection.artifacts[0].size_bytes == len(raw)
        assert all(
            e.trust == "unsigned_local" and e.verification_level == "declared"
            for e in collection.evidence
        )
        assert all(e.collected_at == report.collected_at for e in collection.evidence)
    summary = result.collections[2].evidence[0]
    assert summary.value["active"] == (1 if scan == "finding.sarif" else 0)
    assert summary.value["tools"][0]["name"] == "SyntheticScanner"
    metric = result.collections[3].evidence[0]
    assert metric.source_tool == "synthetic-benchmark"
    assert metric.value["value"] == (75 if benchmark == "benchmark-slow.json" else 42.75)
    policy = load_config(
        repository_root / "examples/dashboard-standard-ci/policies/pull-request.yaml"
    )
    evaluation = evaluate_policy(policy, result.assembly.bundle, evaluated_at=datetime.now(UTC))
    assert evaluation.decision == expected


@pytest.mark.parametrize("missing", [2, 3])
def test_missing_required_family_is_review(repository_root, missing):
    data = standard_payload(repository_root)
    data["reports"].pop(missing)
    result = preview_collection("fixture", DashboardCollectionPreviewRequest.model_validate(data))
    policy = load_config(
        repository_root / "examples/dashboard-standard-ci/policies/pull-request.yaml"
    )
    assert (
        evaluate_policy(policy, result.assembly.bundle, evaluated_at=datetime.now(UTC)).decision
        == "REVIEW"
    )


@pytest.mark.parametrize("index", [2, 3])
@pytest.mark.parametrize("retain", [False, True])
def test_invalid_json_report_never_retains_partial_assembly(repository_root, index, retain):
    data = standard_payload(repository_root)
    data["reports"][index]["content_base64"] = base64.b64encode(b'{"invalid":true}').decode()
    data["retain_warnings"] = retain
    result = preview_collection("fixture", DashboardCollectionPreviewRequest.model_validate(data))
    assert result.collections[index].status == "REJECTED"
    assert result.assembly is None and result.assembly_json is None


def test_total_byte_limit_and_new_family_duplicates(repository_root):
    data = standard_payload(repository_root)
    for index, report in enumerate(data["reports"]):
        report["content_base64"] = base64.b64encode(bytes([65 + index]) * 524288).decode()
    assert DashboardCollectionPreviewRequest.model_validate(data)
    data["reports"][0]["content_base64"] = base64.b64encode(b"x" * 524289).decode()
    with pytest.raises(ValidationError, match="2 MiB"):
        DashboardCollectionPreviewRequest.model_validate(data)
    data = standard_payload(repository_root)
    data["reports"][3]["format"] = "sarif"
    with pytest.raises(ValidationError, match="one report"):
        DashboardCollectionPreviewRequest.model_validate(data)


def test_four_family_durable_job_replays_same_assembly(fixture, repository_root):  # noqa: F811
    app, store, old = fixture
    request = CollectionJobRequest(
        candidate_id=old.candidate_id, collection=standard_payload(repository_root)
    )
    before = app.get_history(old.candidate_id)
    job = store.submit(request, app, key="four-reports")
    assert store.show(job.job_id).state == "QUEUED"
    complete = store.run(job.job_id, 0, app)
    assert complete.state == "SUCCEEDED"
    assert complete.lease_renewal_count == 5
    result = CollectionJobStore(store.path).result(job.job_id)
    assert len(result.assembly.collections) == 4
    assert app.get_history(old.candidate_id) == before


def test_four_family_bff_exact_binding_and_tamper_rejection(tmp_path, repository_root):
    with _dashboard_client(tmp_path, repository_root) as client:
        session = _activate(client)
        headers = {**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]}
        cid = _create(client, headers)
        before = client.get("/app/api/audit-events?project_id=sample-api").json()
        response = client.post(
            f"/app/api/candidates/{cid}/collection-preview",
            headers=headers,
            json=standard_payload(repository_root),
        )
        assert response.status_code == 200, response.text
        assert client.get("/app/api/audit-events?project_id=sample-api").json() == before
        raw = response.json()["assembly_json"]
        for tampered in (True, False):
            document = raw.replace("42.75", "43.75") if tampered else raw
            bound = client.post(
                f"/app/api/candidates/{cid}/evidence",
                headers={
                    **headers,
                    "Idempotency-Key": f"four:bind:{tampered}",
                    "Content-Type": "application/json",
                },
                content='{"assembly":'
                + document
                + ',"bound_at":'
                + json.dumps(datetime.now(UTC).isoformat())
                + "}",
            )
            assert bound.status_code == (422 if tampered else 200), bound.text
        assert client.get(f"/app/api/candidates/{cid}").json()["status"] == "COLLECTING"
