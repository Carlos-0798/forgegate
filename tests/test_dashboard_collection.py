import base64
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from forgegate.application import ProjectRegisterCommand
from forgegate.artifacts import ArtifactBoundaryError, RegisteredArtifact
from forgegate.canonical import canonical_json
from forgegate.config import load_config
from forgegate.dashboard.collection import (
    DashboardJUnitPreviewRequest,
    _UploadedSource,
    preview_junit,
)
from forgegate.domain.models import ArtifactReference
from forgegate.identity import IdentityRole
from forgegate.policy import evaluate_policy
from tests.test_dashboard import ORIGIN_HEADER, _activate, _candidate_payload, _dashboard_client

REPORT = b'<testsuite tests="4" failures="1" errors="0" skipped="1" time="0.5"/>'


def _payload(content: bytes = REPORT) -> dict:
    return {
        "expected_revision": 1,
        "reported_commit": _candidate_payload()["commit_sha"],
        "content_base64": base64.b64encode(content).decode("ascii"),
        "source_tool": "fixture-junit",
        "source_version": "1.0",
        "collected_at": "2026-09-04T13:00:00Z",
    }


def _create(client, headers, *, collecting=True, suffix="default"):
    created = client.post(
        "/app/api/candidates",
        json={**_candidate_payload(), "version": f"collection-{suffix}"},
        headers={**headers, "Idempotency-Key": f"collection:create:{suffix}"},
    )
    assert created.status_code == 201, created.text
    cid = created.json()["candidate_id"]
    if collecting:
        transitioned = client.post(
            f"/app/api/candidates/{cid}/transitions",
            headers={**headers, "Idempotency-Key": f"collection:advance:{suffix}"},
            json={
                "to_status": "COLLECTING",
                "expected_revision": 0,
                "occurred_at": "2026-09-04T13:00:00Z",
            },
        )
        assert transitioned.status_code == 200, transitioned.text
    return cid


def test_preview_exact_bytes_no_write_then_separate_binding(tmp_path, repository_root):
    with _dashboard_client(tmp_path, repository_root) as client:
        session = _activate(client)
        headers = {**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]}
        cid = _create(client, headers)
        audit_url = "/app/api/audit-events?project_id=sample-api"
        before = client.get(audit_url).json()
        response = client.post(
            f"/app/api/candidates/{cid}/junit-preview", headers=headers, json=_payload()
        )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        body = response.json()
        record = body["collection"]["evidence"][0]
        assert record["value"] == {
            "total": 4,
            "passed": 2,
            "failures": 1,
            "errors": 0,
            "skipped": 1,
            "duration_seconds": 0.5,
        }
        assert record["status"] == "failed"
        assert record["trust"] == "unsigned_local"
        assert record["verification_level"] == "declared"
        assert record["collected_at"] == "2026-09-04T13:00:00Z"
        assert record["execution_context"]["operating_system"] is None
        assert record["artifact"]["sha256"] == hashlib.sha256(REPORT).hexdigest()
        receipt = body["assembly"]["collections"][0]["source"]
        result_bytes = canonical_json(body["collection"]).encode()
        assert receipt["sha256"] == hashlib.sha256(result_bytes).hexdigest()
        assert receipt["size_bytes"] == len(result_bytes)
        assert body["persistence"] == "NOT_RETAINED"
        assert client.get(audit_url).json() == before
        assert (
            client.get(f"/app/api/candidates/{cid}/assurance-review").json()["evidence_binding"]
            is None
        )
        bound = client.post(
            f"/app/api/candidates/{cid}/evidence",
            headers={**headers, "Idempotency-Key": "collection:bind"},
            json={"assembly": body["assembly"], "bound_at": datetime.now(UTC).isoformat()},
        )
        assert bound.status_code == 200, bound.text
        assert bound.json()["assembly"] == body["assembly"]
        assert client.get(f"/app/api/candidates/{cid}").json()["status"] == "COLLECTING"
        assert len(client.get(audit_url).json()["events"]) == len(before["events"]) + 1
        assert (
            client.post(
                f"/app/api/candidates/{cid}/junit-preview", headers=headers, json=_payload()
            ).status_code
            == 409
        )


@pytest.mark.parametrize(
    "xml,code",
    [
        (b"<broken", "JUNIT_XML_INVALID"),
        (
            b'<!DOCTYPE test [<!ENTITY x SYSTEM "file:///secret">]><testsuite tests="0"/>',
            "JUNIT_FORBIDDEN_DECLARATION",
        ),
        (b"<testsuite>\x00</testsuite>", "JUNIT_UNSUPPORTED_ENCODING"),
        (b'<testsuite tests="1" failures="2"/>', "JUNIT_COUNTS_INCONSISTENT"),
        (b"<testsuite>" + b"<x>" * 33 + b"</x>" * 33 + b"</testsuite>", "JUNIT_DEPTH_LIMIT"),
        (b"<testsuite>" + b"<testcase/>" * 10001 + b"</testsuite>", "JUNIT_ELEMENT_LIMIT"),
    ],
    ids=["malformed", "doctype", "nul", "counts", "depth", "elements"],
)
def test_preview_rejected_reports(xml, code):
    result = preview_junit("fixture", DashboardJUnitPreviewRequest.model_validate(_payload(xml)))
    assert result.assembly is None
    assert result.collection.status == "REJECTED"
    assert result.collection.rejected_records[0].code == code


def test_preview_requires_explicit_warning_retention():
    command = _payload(b'<testsuite tests="2"><testcase/></testsuite>')
    result = preview_junit("fixture", DashboardJUnitPreviewRequest.model_validate(command))
    assert result.assembly is None
    assert len(result.collection.warnings) == 2
    command["retain_warnings"] = True
    retained = preview_junit("fixture", DashboardJUnitPreviewRequest.model_validate(command))
    assert retained.assembly.warning_disposition == "retained"
    assert retained.assembly.collections[0].warnings == result.collection.warnings


@pytest.mark.parametrize(
    "change",
    [
        {"content_base64": "not-base64!"},
        {"content_base64": "===="},
        {"content_base64": "YR=="},
        {"content_base64": "éééé"},
        {"content_base64": base64.b64encode(b"x" * (1048576 + 1)).decode()},
        {"collected_at": "2026-01-01T00:00:00"},
        {"collected_at": "2999-01-01T00:00:00Z"},
        {"source_tool": ""},
        {"expected_revision": -1},
        {"server_path": "secret.xml"},
        {"trust": "signed_attestation"},
        {"verification_level": "physically_verified"},
    ],
)
def test_preview_contract_rejects_invalid_or_privileged_input(change):
    with pytest.raises(ValidationError):
        DashboardJUnitPreviewRequest.model_validate({**_payload(), **change})


def test_uploaded_source_never_resolves_paths():
    source = _UploadedSource(
        RegisteredArtifact(
            ArtifactReference(
                path_or_uri="fixed.xml", media_type="application/xml", sha256="a" * 64, size_bytes=1
            ),
            b"x",
        )
    )
    for path, media in [("../secret", "application/xml"), (Path("fixed.xml"), "text/html")]:
        with pytest.raises(ArtifactBoundaryError):
            source.register(path, media_type=media)


def test_preview_auth_scope_revision_commit_and_body_limits(tmp_path, repository_root):
    with _dashboard_client(tmp_path, repository_root) as client:
        url = f"/app/api/candidates/cand-{'a' * 24}/junit-preview"
        assert client.post(url, json=_payload(), headers=ORIGIN_HEADER).status_code == 401
        session = _activate(client)
        headers = {**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]}
        cid = _create(client, headers, collecting=False)
        url = f"/app/api/candidates/{cid}/junit-preview"
        assert (
            client.post(
                url, json={**_payload(), "expected_revision": 0}, headers=headers
            ).status_code
            == 409
        )
        assert client.post(url, json=_payload(), headers=headers).status_code == 409
        assert client.post(url, json=_payload(), headers=ORIGIN_HEADER).status_code == 403
        assert (
            client.post(
                url, json=_payload(), headers={**headers, "Origin": "https://example.invalid"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                url, json=_payload(), headers={"X-ForgeGate-CSRF": session["csrf_token"]}
            ).status_code
            == 403
        )
        assert (
            client.post(url, json={**_payload(), "source_tool": ""}, headers=headers).status_code
            == 422
        )
        assert (
            client.post(
                url,
                content=b"x" * (4 * 1024 * 1024 + 1),
                headers={**headers, "Content-Type": "application/json"},
            ).status_code
            == 413
        )
        response = client.post(
            f"/app/api/candidates/{cid}/transitions",
            headers={**headers, "Idempotency-Key": "advance-for-mismatch"},
            json={
                "to_status": "COLLECTING",
                "expected_revision": 0,
                "occurred_at": "2026-09-04T13:00:00Z",
            },
        )
        assert response.status_code == 200
        assert (
            client.post(
                url, json={**_payload(), "reported_commit": "f" * 40}, headers=headers
            ).status_code
            == 409
        )


def test_producer_cannot_preview(tmp_path, repository_root):
    # Create using application services, then activate a read-only producer.
    with _dashboard_client(tmp_path, repository_root, role=IdentityRole.PRODUCER) as client:
        from forgegate.application import CandidateCreateCommand

        application = client.app.state.candidate_application
        candidate = application.create_candidate(
            CandidateCreateCommand.model_validate(_candidate_payload()),
            idempotency_key="producer-fixture",
        )
        session = _activate(client, role="producer")
        assert (
            client.post(
                f"/app/api/candidates/{candidate.candidate_id}/junit-preview",
                json=_payload(),
                headers={**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]},
            ).status_code
            == 403
        )


@pytest.mark.parametrize(
    "fixture,expected,multi",
    [
        ("pass.xml", "PASS", False),
        ("fail.xml", "FAIL", False),
        ("coverage.xml", "PASS", True),
        ("coverage-low.xml", "FAIL", True),
        ("coverage.info", "PASS", True),
    ],
)
def test_raw_preview_to_bound_policy_and_assurance(
    tmp_path, repository_root, fixture, expected, multi
):
    from forgegate.application import CandidateAttestCommand
    from forgegate.assurance import render_assurance_bundle_archive

    # Replace no user configuration: initialize an independent fixture database.
    with _dashboard_client(tmp_path, repository_root) as client:
        application = client.app.state.candidate_application
        from forgegate.application import ProjectReviseCommand

        root = repository_root / (
            "examples/dashboard-multi-report" if multi else "examples/dashboard-junit"
        )
        application.revise_project(
            "sample-api",
            ProjectReviseCommand(
                config=load_config(root / "forgegate.yaml"),
                expected_profile_version=1,
                effective_at=datetime(2026, 9, 4, 12, 1, tzinfo=UTC),
            ),
            idempotency_key="collection:fixture-profile",
        )
        session = _activate(client)
        headers = {**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]}
        # Two candidates must reuse the exact same profile-authorized material.
        for iteration in range(2):
            cid = _create(client, headers, suffix=f"{fixture}-{iteration}")
            if multi:
                from tests.test_dashboard_multi_collection import payload

                command = payload(
                    "lcov" if fixture.endswith(".info") else "coverage_xml",
                    (root / fixture).read_bytes(),
                )
                endpoint = "collection-preview"
            else:
                command = _payload((root / fixture).read_bytes())
                endpoint = "junit-preview"
            preview = client.post(
                f"/app/api/candidates/{cid}/{endpoint}",
                headers=headers,
                json=command,
            )
            assert preview.status_code == 200, preview.text
            assert (
                client.post(
                    f"/app/api/candidates/{cid}/evidence",
                    headers={**headers, "Idempotency-Key": f"chain:{iteration}:bind"},
                    json={
                        "assembly": preview.json()["assembly"],
                        "bound_at": datetime.now(UTC).isoformat(),
                    },
                ).status_code
                == 200
            )
            for revision, target in [(1, "READY"), (2, "EVALUATING")]:
                assert (
                    client.post(
                        f"/app/api/candidates/{cid}/transitions",
                        headers={**headers, "Idempotency-Key": f"chain:{iteration}:{target}"},
                        json={
                            "expected_revision": revision,
                            "to_status": target,
                            "occurred_at": datetime.now(UTC).isoformat(),
                        },
                    ).status_code
                    == 200
                )
            material = application.materialize_policy(cid, root)
            response = client.post(
                f"/app/api/candidates/{cid}/evaluate",
                headers={**headers, "Idempotency-Key": f"chain:{iteration}:evaluate"},
                json={
                    "policy_material": material.model_dump(mode="json"),
                    "expected_revision": 3,
                    "evaluated_at": datetime.now(UTC).isoformat(),
                },
            )
            assert response.status_code == 200, response.text
            assert response.json()["evaluation"]["decision"] == expected
            application.attest_candidate(cid, CandidateAttestCommand(issued_at=datetime.now(UTC)))
            bundle = application.get_assurance_bundle(cid)
            assert bundle is not None
            assert render_assurance_bundle_archive(bundle).startswith(b"PK")


def test_default_ci_policy_does_not_promote_uploaded_declarations(repository_root):
    result = preview_junit(
        "fixture", DashboardJUnitPreviewRequest.model_validate(_payload(b'<testsuite tests="1"/>'))
    )
    evaluation = evaluate_policy(
        load_config(repository_root / "examples/sample-python-api/policies/pull-request.yaml"),
        result.assembly.bundle,
        evaluated_at=datetime.now(UTC),
    )
    assert evaluation.decision == "REVIEW"


def test_preview_denies_another_project(tmp_path, repository_root):
    from forgegate.application import CandidateCreateCommand

    with _dashboard_client(tmp_path, repository_root) as client:
        application = client.app.state.candidate_application
        config = load_config(repository_root / "examples/sample-python-api/forgegate.yaml")
        config = config.model_copy(
            update={"project": config.project.model_copy(update={"id": "other-project"})}
        )
        application.register_project(
            ProjectRegisterCommand(config=config, registered_at=datetime.now(UTC)),
            idempotency_key="scope:register",
        )
        candidate = application.create_candidate(
            CandidateCreateCommand.model_validate(
                {
                    **_candidate_payload(),
                    "project_id": "other-project",
                    "created_at": datetime.now(UTC),
                }
            ),
            idempotency_key="scope:candidate",
        )
        session = _activate(client)
        response = client.post(
            f"/app/api/candidates/{candidate.candidate_id}/junit-preview",
            headers={**ORIGIN_HEADER, "X-ForgeGate-CSRF": session["csrf_token"]},
            json=_payload(),
        )
        assert response.status_code == 403
