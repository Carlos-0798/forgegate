"""Real collection receipts -> reusable policy -> database-independent replay."""

import base64
import hashlib
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from forgegate.api import ApiAuthenticator, create_api_app
from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    CandidateEvaluateCommand,
    ProjectRegisterCommand,
)
from forgegate.config import load_config
from forgegate.dashboard.collection import DashboardCollectionPreviewRequest, preview_collection
from forgegate.evidence_replay import render_evidence_replay, verify_evidence_replay
from forgegate.policy import PolicyMaterial
from tests.api_auth_support import TEST_TRUST_STORE
from tests.test_dashboard import ORIGIN, ORIGIN_HEADER, _activate, _producer_trust_store
from tests.test_dashboard_standard_ci import standard_payload


def new_candidate(app, label, track="pull-request", project="sample-api"):
    return app.create_candidate(
        CandidateCreateCommand(
            project_id=project,
            version=label,
            commit_sha="a" * 40,
            source_branch="main",
            release_track=track,
            created_at=datetime.now(UTC),
        ),
        idempotency_key=f"new:{label}",
    )


def setup(tmp_path, root, decision="PASS"):
    app = CandidateApplication.for_database(tmp_path / "forgegate.db")
    app.initialize()
    app.register_project(
        ProjectRegisterCommand(
            config=load_config(root / "examples/dashboard-standard-ci/forgegate.yaml"),
            registered_at=datetime.now(UTC),
        ),
        idempotency_key="register",
    )
    candidate = new_candidate(app, "seed")
    payload = standard_payload(root, scan="finding.sarif" if decision == "FAIL" else "clean.sarif")
    if decision == "REVIEW":
        payload["reports"].pop()
    result = preview_collection(
        candidate.candidate_id, DashboardCollectionPreviewRequest.model_validate(payload)
    )
    app.advance_candidate(
        candidate.candidate_id,
        CandidateAdvanceCommand(
            to_status="COLLECTING", expected_revision=0, occurred_at=datetime.now(UTC)
        ),
        idempotency_key="quick:collect",
    )
    app.bind_evidence(
        candidate.candidate_id,
        CandidateBindEvidenceCommand(assembly=result.assembly, bound_at=datetime.now(UTC)),
        idempotency_key="quick:bind",
    )
    for revision, state in [(1, "READY"), (2, "EVALUATING")]:
        app.advance_candidate(
            candidate.candidate_id,
            CandidateAdvanceCommand(
                to_status=state, expected_revision=revision, occurred_at=datetime.now(UTC)
            ),
            idempotency_key=f"quick:{state}",
        )
    material = app.materialize_policy(
        candidate.candidate_id, root / "examples/dashboard-standard-ci"
    )
    app.evaluate_candidate(
        candidate.candidate_id,
        CandidateEvaluateCommand(
            policy_material=material, expected_revision=3, evaluated_at=datetime.now(UTC)
        ),
        idempotency_key="evaluate",
    )
    app.attest_candidate(
        candidate.candidate_id, CandidateAttestCommand(issued_at=datetime.now(UTC))
    )
    return app, candidate, result, payload


@pytest.mark.parametrize("decision", ["PASS", "FAIL", "REVIEW"])
def test_exact_preview_receipts_replay_and_policy_reuse(tmp_path, repository_root, decision):
    app, seed, result, payload = setup(tmp_path, repository_root, decision)
    sources = [base64.b64decode(report["content_base64"]) for report in payload["reports"]]
    sources += [text.encode() for text in result.collection_json]
    files = {hashlib.sha256(raw).hexdigest(): raw for raw in sources}
    for receipt in result.assembly.collections:
        assert (
            files[receipt.source.sha256]
            and len(files[receipt.source.sha256]) == receipt.source.size_bytes
        )
    name, archive = render_evidence_replay(app.get_assurance_bundle(seed.candidate_id), files)
    replay = verify_evidence_replay(archive, expected_commit="a" * 40)
    assert name.endswith(".zip") and replay.decision == decision
    assert replay.source_files == len(sources)
    target = new_candidate(app, "target")
    before = app.get_history(target.candidate_id)
    materials = app.reusable_policy_materials(target.candidate_id)
    assert materials == (app.get_policy_material(seed.candidate_id),)
    assert app.get_history(target.candidate_id) == before


def test_choices_endpoint_exact_json_and_authorization(tmp_path, repository_root):
    app, seed, _, _ = setup(tmp_path, repository_root)
    target = new_candidate(app, "target")
    endpoint = f"/app/api/candidates/{target.candidate_id}/policy-choices"
    with TestClient(
        create_api_app(
            tmp_path / "forgegate.db",
            application=app,
            authenticator=ApiAuthenticator(TEST_TRUST_STORE),
            dashboard=True,
        ),
        base_url=ORIGIN,
    ) as client:
        assert client.get(endpoint).status_code == 401
        _activate(client)
        response = client.get(endpoint, headers=ORIGIN_HEADER)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["candidate_id"] == target.candidate_id and body["truncated"] is False
        assert PolicyMaterial.model_validate_json(
            body["choices"][0]["material_json"]
        ) == app.get_policy_material(seed.candidate_id)
        assert json.loads(body["choices"][0]["material_json"]) == body["choices"][0]["material"]
        assert (
            client.get(endpoint, headers={"Origin": "https://example.invalid"}).status_code == 403
        )
    with TestClient(
        create_api_app(
            tmp_path / "forgegate.db",
            application=app,
            authenticator=ApiAuthenticator(_producer_trust_store()),
            dashboard=True,
        ),
        base_url=ORIGIN,
    ) as client:
        _activate(client, role="producer")
        assert client.get(endpoint).status_code == 403


def test_profile_version_and_project_are_not_crossed(tmp_path, repository_root):
    app, seed, _, _ = setup(tmp_path, repository_root)
    config = load_config(repository_root / "examples/dashboard-standard-ci/forgegate.yaml")
    app.repository.revise_project(
        "sample-api",
        config,
        expected_profile_version=1,
        effective_at=datetime.now(UTC),
        idempotency_key="quick:revise",
    )
    target = new_candidate(app, "new-profile")
    assert target.project_profile_version == 2
    assert app.reusable_policy_materials(target.candidate_id) == ()
    assert app.reusable_policy_materials(seed.candidate_id)
    alternate = config.model_dump(mode="json", by_alias=True)
    alternate["project"]["id"] = "other-project"
    app.register_project(
        ProjectRegisterCommand(config=alternate, registered_at=datetime.now(UTC)),
        idempotency_key="quick:other",
    )
    other = new_candidate(app, "other", project="other-project")
    assert app.reusable_policy_materials(other.candidate_id) == ()
    with TestClient(
        create_api_app(
            tmp_path / "forgegate.db",
            application=app,
            authenticator=ApiAuthenticator(TEST_TRUST_STORE),
            dashboard=True,
        ),
        base_url=ORIGIN,
    ) as client:
        _activate(client)
        assert (
            client.get(f"/app/api/candidates/{other.candidate_id}/policy-choices").status_code
            == 403
        )
