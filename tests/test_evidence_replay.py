import base64
import hashlib
import json
import os
import zipfile
from datetime import UTC, datetime
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from forgegate.api import ApiAuthenticator, create_api_app
from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateEvaluateCommand,
)
from forgegate.artifacts import ArtifactBoundaryError
from forgegate.assembly import CollectionResultLoader
from forgegate.cli import app
from forgegate.config import load_config
from forgegate.evidence_replay import (
    EvidenceReplayError,
    _archive,
    _collect,
    _ReplaySource,
    load_replay_sources,
    publish_evidence_replay,
    render_evidence_replay,
    required_replay_files,
    verify_evidence_replay,
)
from tests.test_avs_host_acceptance import quality_fixture
from tests.test_dashboard import ORIGIN, ORIGIN_HEADER, _activate
from tools.avs_host_acceptance import prepare_handoff


def replay_fixture(tmp_path, repository_root, *, fail=True):
    reports = tmp_path / "reports"
    reports.mkdir()
    base = repository_root / "examples/dashboard-standard-ci"
    for src, dst in [
        ("tests.xml", "junit.xml"),
        ("coverage.xml", "coverage.xml"),
        ("finding.sarif" if fail else "clean.sarif", "security.sarif"),
    ]:
        (reports / dst).write_bytes((base / src).read_bytes())
    (reports / "product-quality.json").write_text(json.dumps(quality_fixture()), encoding="utf-8")
    for path in reports.iterdir():
        os.utime(path, (1788825600, 1788825600))
    root = tmp_path / "handoff"
    manifest = prepare_handoff(
        reports, root, commit="a" * 40, pytest_version="fixture", coverage_version="fixture"
    )
    application = CandidateApplication.for_database(root / "forgegate.db")
    candidate_id = manifest["candidate_id"]
    application.bind_evidence(
        candidate_id,
        CandidateBindEvidenceCommand(
            assembly=load_config(root / "assembly.json"), bound_at=datetime.now(UTC)
        ),
        idempotency_key="replay:bind",
    )
    for rev, state in [(1, "READY"), (2, "EVALUATING")]:
        application.advance_candidate(
            candidate_id,
            CandidateAdvanceCommand.model_validate(
                {"to_status": state, "expected_revision": rev, "occurred_at": datetime.now(UTC)}
            ),
            idempotency_key=f"replay:{state}",
        )
    application.evaluate_candidate(
        candidate_id,
        CandidateEvaluateCommand(
            policy_material=load_config(root / "policy-material.json"),
            expected_revision=3,
            evaluated_at=datetime.now(UTC),
        ),
        idempotency_key="evaluate",
    )
    application.attest_candidate(candidate_id, CandidateAttestCommand(issued_at=datetime.now(UTC)))
    bundle = application.get_assurance_bundle(candidate_id)
    return application, root, bundle, load_replay_sources(bundle, root)


@pytest.mark.parametrize("fail", [True, False])
def test_actual_reports_roundtrip_decision_and_no_overwrite(tmp_path, repository_root, fail):
    application, root, bundle, files = replay_fixture(tmp_path, repository_root, fail=fail)
    name, raw = render_evidence_replay(bundle, files)
    verified = verify_evidence_replay(raw, expected_commit="a" * 40)
    assert verified.decision == ("FAIL" if fail else "PASS")
    assert verified.collections_replayed == 4 and verified.source_files == 8
    assert verified.producer_authentication == verified.hardware_access == "NOT_PERFORMED"
    assert (name, raw) == render_evidence_replay(bundle, dict(reversed(list(files.items()))))
    target = publish_evidence_replay(bundle, root, tmp_path / "export")
    assert target.name == name and target.read_bytes() == raw
    with pytest.raises(FileExistsError):
        publish_evidence_replay(bundle, root, tmp_path / "export")
    runner = CliRunner()
    result = runner.invoke(
        app, ["evidence-replay", "verify", str(target), "--expected-commit", "a" * 40]
    )
    assert result.exit_code == 0 and json.loads(result.stdout)["decision"] == verified.decision
    assert (
        runner.invoke(
            app, ["evidence-replay", "verify", str(target), "--expected-commit", "b" * 40]
        ).exit_code
        == 3
    )
    export_args = [
        "evidence-replay",
        "export",
        str(root / "forgegate.db"),
        bundle.attestation.candidate.candidate_id,
        "--source-root",
        str(root),
        "--destination",
        str(tmp_path / "cli-export"),
    ]
    assert runner.invoke(app, export_args).exit_code == 0
    assert runner.invoke(app, export_args).exit_code == 3
    assert application.get_assurance_bundle(bundle.attestation.candidate.candidate_id) == bundle


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "extra",
        "tampered",
        "wrong-commit",
        "trailing",
        "bad-zip",
        "compressed",
        "traversal",
        "manifest",
        "version",
    ],
)
def test_reject_corrupted_or_misassociated_export(tmp_path, repository_root, change):
    _, _, bundle, files = replay_fixture(tmp_path, repository_root)
    _, raw = render_evidence_replay(bundle, files)
    commit = "a" * 40
    if change in {"missing", "extra", "tampered"}:
        altered = dict(files)
        key = next(iter(altered))
        if change == "missing":
            del altered[key]
        elif change == "extra":
            altered["0" * 64] = b"extra"
        else:
            altered[key] += b"changed"
        with pytest.raises(EvidenceReplayError):
            render_evidence_replay(bundle, altered)
        return
    if change == "wrong-commit":
        commit = "b" * 40
    elif change == "trailing":
        raw += b"hidden trailing bytes"
    elif change == "bad-zip":
        raw = b"not zip"
    else:
        content = {
            i.filename: zipfile.ZipFile(BytesIO(raw)).read(i.filename)
            for i in zipfile.ZipFile(BytesIO(raw)).infolist()
        }
        if change == "traversal":
            content["../escape"] = b"x"
        if change in {"manifest", "version"}:
            doc = json.loads(content["manifest.json"])
            doc["replay_id" if change == "manifest" else "forgegate_version"] = (
                "sha256:" + "0" * 64 if change == "manifest" else "future"
            )
            content["manifest.json"] = json.dumps(doc).encode()
        output = BytesIO()
        with zipfile.ZipFile(
            output,
            "w",
            compression=zipfile.ZIP_DEFLATED if change == "compressed" else zipfile.ZIP_STORED,
        ) as z:
            for name, value in content.items():
                z.writestr(name, value)
        raw = output.getvalue()
    with pytest.raises(EvidenceReplayError):
        verify_evidence_replay(raw, expected_commit=commit)


def test_parser_and_policy_recomputation_detect_changes(tmp_path, repository_root, monkeypatch):
    import forgegate.evidence_replay as module

    _, _, bundle, files = replay_fixture(tmp_path, repository_root)
    source = _ReplaySource(bundle, files)
    with pytest.raises(ArtifactBoundaryError):
        source.register("unlisted", media_type="application/json")
    result = (
        CollectionResultLoader(source)
        .load(bundle.evidence_binding.assembly.collections[0].source.path_or_uri)
        .result
    )
    modified = result.model_copy(update={"collector_version": "changed"})
    with monkeypatch.context() as patch:
        patch.setattr(module, "_collect", lambda *_: modified)
        with pytest.raises(EvidenceReplayError, match="Current parser"):
            render_evidence_replay(bundle, files)
    with monkeypatch.context() as patch:
        patch.setattr(
            module,
            "evaluate_policy_material",
            lambda *a, **kw: bundle.attestation.policy_evaluation.model_copy(
                update={"policy_name": "changed"}
            ),
        )
        with pytest.raises(EvidenceReplayError, match="Recomputed policy"):
            render_evidence_replay(bundle, files)
    receipt = bundle.evidence_binding.assembly.collections[0]
    with monkeypatch.context() as patch:
        patch.setattr(module, "MAX_SOURCE_BYTES", 1)
        with pytest.raises(EvidenceReplayError, match="1 MiB"):
            required_replay_files(bundle)
    with monkeypatch.context() as patch:
        patch.setattr(module, "MAX_TOTAL_SOURCE_BYTES", 1)
        with pytest.raises(EvidenceReplayError, match="2 MiB"):
            required_replay_files(bundle)
    with monkeypatch.context() as patch:
        patch.setattr(module, "MAX_BUNDLE_BYTES", 1)
        with pytest.raises(EvidenceReplayError, match="16 MiB"):
            _archive(bundle, files)
    with monkeypatch.context() as patch:
        patch.setattr(module, "MAX_REPLAY_ARCHIVE_BYTES", 1)
        with pytest.raises(EvidenceReplayError, match="20 MiB"):
            verify_evidence_replay(b"xx", expected_commit="a" * 40)
    assert _collect(result, source) == result
    bundle.evidence_binding.assembly.collections[0] = receipt.model_copy(
        update={"collector_name": "external_plugin"}
    )
    with pytest.raises(EvidenceReplayError, match="outside software replay"):
        required_replay_files(bundle)


def test_dashboard_export_auth_scope_hashes_and_no_state_change(tmp_path, repository_root):
    from forgegate.identity import TrustedIdentity, create_trust_store
    from tests.api_auth_support import TEST_IDENTITY

    application, root, bundle, files = replay_fixture(tmp_path, repository_root)
    trust = create_trust_store(
        (
            TrustedIdentity(
                identity=TEST_IDENTITY,
                roles=("operator",),
                project_ids=("analog-validation-studio",),
            ),
        )
    )
    endpoint = (
        f"/app/api/candidates/{bundle.attestation.candidate.candidate_id}/evidence-replay-export"
    )
    command = dict(
        expected_revision=4,
        expected_bundle_id=bundle.bundle_id,
        acknowledge_private_sources=True,
        files=[
            dict(sha256=k, content_base64=base64.b64encode(v).decode()) for k, v in files.items()
        ],
    )
    with TestClient(
        create_api_app(
            root / "forgegate.db",
            application=application,
            authenticator=ApiAuthenticator(trust),
            dashboard=True,
        ),
        base_url=ORIGIN,
    ) as client:
        assert client.post(endpoint, json=command, headers=ORIGIN_HEADER).status_code == 401
        activated = _activate(client, project_ids=["analog-validation-studio"])
        headers = {**ORIGIN_HEADER, "X-ForgeGate-CSRF": activated["csrf_token"]}
        assert client.post(endpoint, json=command, headers=ORIGIN_HEADER).status_code == 403
        assert (
            client.post(
                endpoint, json={**command, "expected_revision": 3}, headers=headers
            ).status_code
            == 409
        )
        assert (
            client.post(
                endpoint, json={**command, "acknowledge_private_sources": False}, headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post(
                endpoint, json={**command, "files": command["files"][:-1]}, headers=headers
            ).status_code
            == 400
        )
        response = client.post(endpoint, json=command, headers=headers)
        assert response.status_code == 200, response.text[:100]
        assert response.headers["cache-control"] == "no-store"
        assert (
            hashlib.sha256(response.content).hexdigest()
            == response.headers["x-forgegate-archive-sha256"]
        )
        assert verify_evidence_replay(response.content, expected_commit="a" * 40).decision == "FAIL"
    assert application.get_assurance_bundle(bundle.attestation.candidate.candidate_id) == bundle
