import hashlib
import json

import pytest

from forgegate.canonical import sha256_fingerprint
from forgegate.identity import IdentityRole
from forgegate.recovery_models import (
    MAX_RECOVERY_REPORT_BYTES,
    RecoveryReadinessHandoff,
    build_recovery_handoff,
)
from tests.test_dashboard import ORIGIN_HEADER, _activate, _dashboard_client


def report(*, status="READY", dependency_status="VERIFIED"):
    dependencies = [
        {
            "backup_sha256": "b" * 64,
            "job_ids": ["job-" + "c" * 32],
            "status": dependency_status,
            "error_code": "WORKSPACE_HASH_MISMATCH" if dependency_status == "FAILED" else None,
            "result_payloads_verified": 1 if dependency_status == "VERIFIED" else 0,
            "jobs_without_result": 0,
        }
    ]
    return {
        "schema_version": "forgegate.workspace-recovery-readiness.v1",
        "backup_sha256": "a" * 64,
        "manifest_fingerprint": "sha256:" + "d" * 64,
        "checked_at": "2026-09-07T22:21:14Z",
        "status": status,
        "archived_job_count": 1,
        "dependencies": dependencies,
        "scope": "snapshot_and_exact_archived_job_payloads",
        "availability": "observed_during_check_only",
        "restore": "NOT_PERFORMED",
        "producer_authenticity": "NOT_VERIFIED",
        "external_identity_and_artifact_files": "NOT_CHECKED",
    }


def encoded(value):
    document = json.dumps(value, separators=(",", ":"))
    return document, hashlib.sha256(document.encode()).hexdigest()


@pytest.mark.parametrize(
    "status,dependency_status,disposition",
    [("READY", "VERIFIED", "READY_FOR_REHEARSAL"), ("INCOMPLETE", "FAILED", "BLOCKED")],
)
def test_dashboard_recovery_review_is_authenticated_read_only_and_exact(
    tmp_path, repository_root, status, dependency_status, disposition
):
    document, digest = encoded(report(status=status, dependency_status=dependency_status))
    with _dashboard_client(tmp_path, repository_root) as client:
        unauthenticated = client.post(
            "/app/api/recovery-review",
            headers={**ORIGIN_HEADER, "X-ForgeGate-CSRF": "x"},
            json={"document": document, "expected_sha256": digest},
        )
        activated = _activate(client)
        audit_before = client.get("/app/api/audit-events?project_id=sample-api").json()
        response = client.post(
            "/app/api/recovery-review",
            headers={**ORIGIN_HEADER, "X-ForgeGate-CSRF": activated["csrf_token"]},
            json={"document": document, "expected_sha256": digest},
        )
        audit_after = client.get("/app/api/audit-events?project_id=sample-api").json()
    assert unauthenticated.status_code == 401
    assert response.status_code == 200, response.text
    handoff = RecoveryReadinessHandoff.model_validate(response.json())
    assert handoff.disposition == disposition
    assert handoff.source_report_sha256 == digest
    assert handoff.report_fingerprint == sha256_fingerprint(
        report(status=status, dependency_status=dependency_status)
    )
    assert handoff.result_payloads_verified == (dependency_status == "VERIFIED")
    assert handoff.payload_transfer == "NOT_INCLUDED"
    assert handoff.live_availability == "NOT_CHECKED" and handoff.restore == "NOT_PERFORMED"
    assert audit_after == audit_before


def test_dashboard_recovery_requires_origin_csrf_and_operator(tmp_path, repository_root):
    document, digest = encoded(report())
    with _dashboard_client(tmp_path, repository_root) as client:
        activated = _activate(client)
        body = {"document": document, "expected_sha256": digest}
        assert client.post("/app/api/recovery-review", json=body).status_code == 403
        assert (
            client.post("/app/api/recovery-review", headers=ORIGIN_HEADER, json=body).status_code
            == 403
        )
    with _dashboard_client(tmp_path, repository_root, role=IdentityRole.PRODUCER) as client:
        activated = _activate(client, role="producer")
        response = client.post(
            "/app/api/recovery-review",
            headers={**ORIGIN_HEADER, "X-ForgeGate-CSRF": activated["csrf_token"]},
            json=body,
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "API_ROLE_FORBIDDEN"


@pytest.mark.parametrize(
    "kind",
    ["hash", "schema", "duplicate", "nonfinite", "coherence", "empty", "too_large"],
)
def test_dashboard_recovery_rejects_bad_reports_without_echoing_document(
    tmp_path, repository_root, kind
):
    value = report()
    document, digest = encoded(value)
    if kind == "hash":
        digest = "0" * 64
    elif kind == "schema":
        value["schema_version"] = "unknown"
        document, digest = encoded(value)
    elif kind == "duplicate":
        document = document[:-1] + ',"status":"READY"}'
        digest = hashlib.sha256(document.encode()).hexdigest()
    elif kind == "nonfinite":
        document = document[:-1] + ',"unknown":NaN}'
        digest = hashlib.sha256(document.encode()).hexdigest()
    elif kind == "coherence":
        value["status"] = "INCOMPLETE"
        document, digest = encoded(value)
    elif kind == "empty":
        document, digest = "", hashlib.sha256(b"").hexdigest()
    elif kind == "too_large":
        document = "x" * (MAX_RECOVERY_REPORT_BYTES + 1)
        digest = hashlib.sha256(document.encode()).hexdigest()
    with _dashboard_client(tmp_path, repository_root) as client:
        activated = _activate(client)
        response = client.post(
            "/app/api/recovery-review",
            headers={**ORIGIN_HEADER, "X-ForgeGate-CSRF": activated["csrf_token"]},
            json={"document": document, "expected_sha256": digest},
        )
    assert response.status_code in {400, 422}
    assert "job-" + "c" * 32 not in response.text


def test_recovery_handoff_identity_and_summary_cannot_be_forged():
    document, digest = encoded(report())
    handoff = build_recovery_handoff(document, digest)
    raw = handoff.model_dump(mode="json")
    for change in [
        {"handoff_id": "sha256:" + "0" * 64},
        {"report_fingerprint": "sha256:" + "0" * 64},
        {"disposition": "BLOCKED"},
        {"dependency_count": 0},
        {"verified_dependency_count": 0},
        {"result_payloads_verified": 0},
        {"jobs_without_result": 1},
    ]:
        with pytest.raises(ValueError):
            RecoveryReadinessHandoff.model_validate({**raw, **change})
