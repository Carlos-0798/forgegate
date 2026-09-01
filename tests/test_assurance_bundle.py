from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    CandidateEvaluateCommand,
    ProjectRegisterCommand,
)
from forgegate.assurance import (
    AssuranceBundle,
    AssuranceBundleError,
    publish_assurance_bundle,
    render_assurance_bundle_json,
    render_assurance_bundle_readme,
    verify_assurance_bundle,
)
from forgegate.assurance import portable as portable_module
from forgegate.assurance.models import create_assurance_manifest
from forgegate.candidates import CandidateStoreError
from forgegate.cli import app
from forgegate.config import load_config
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import ProjectConfig
from forgegate.policy import create_policy_material
from forgegate.policy.materials import decode_policy_content

runner = CliRunner()
CREATED = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def _completed_application(
    tmp_path: Path,
    repository_root: Path,
) -> tuple[CandidateApplication, str]:
    application = CandidateApplication.for_database(tmp_path / "forgegate.db")
    application.initialize()
    project = load_config(repository_root / "examples/sample-python-api/forgegate.yaml")
    assert isinstance(project, ProjectConfig)
    application.register_project(
        ProjectRegisterCommand(
            config=project,
            registered_at=datetime(2026, 8, 30, 11, 59, tzinfo=UTC),
        ),
        idempotency_key="project:assurance-bundle",
    )
    candidate = application.create_candidate(
        CandidateCreateCommand(
            project_id="sample-api",
            version="1.2.0",
            commit_sha="a" * 40,
            source_branch="main",
            release_track="pull-request",
            created_at=CREATED,
        ),
        idempotency_key="candidate:assurance-bundle",
    )
    candidate_id = candidate.candidate_id
    application.advance_candidate(
        candidate_id,
        CandidateAdvanceCommand(
            to_status=CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
        ),
        idempotency_key="advance:assurance-collecting",
    )
    application.bind_evidence(
        candidate_id,
        CandidateBindEvidenceCommand(
            assembly=load_config(repository_root / "tests/golden/evidence_bundle_assembly.json"),
            bound_at=datetime(2026, 8, 30, 20, 31, tzinfo=UTC),
        ),
        idempotency_key="binding:assurance",
    )
    for revision, target, timestamp in (
        (1, CandidateStatus.READY, datetime(2026, 8, 30, 20, 32, tzinfo=UTC)),
        (2, CandidateStatus.EVALUATING, datetime(2026, 8, 30, 20, 33, tzinfo=UTC)),
    ):
        application.advance_candidate(
            candidate_id,
            CandidateAdvanceCommand(
                to_status=target,
                expected_revision=revision,
                occurred_at=timestamp,
            ),
            idempotency_key=f"advance:assurance-{target.value.lower()}",
        )
    material = application.materialize_policy(
        candidate_id,
        repository_root / "examples/sample-python-api",
    )
    application.evaluate_candidate(
        candidate_id,
        CandidateEvaluateCommand(
            policy_material=material,
            expected_revision=3,
            evaluated_at=datetime(2026, 8, 30, 21, 0, tzinfo=UTC),
        ),
        idempotency_key="evaluate:assurance",
    )
    application.attest_candidate(
        candidate_id,
        CandidateAttestCommand(issued_at=datetime(2026, 8, 30, 22, 0, tzinfo=UTC)),
    )
    return application, candidate_id


def test_assurance_bundle_is_self_contained_and_cross_document_bound(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    bundle = application.get_assurance_bundle(candidate_id)

    assert bundle.schema_version == "forgegate.assurance-bundle.v1"
    assert bundle.attestation.candidate.candidate_id == candidate_id
    assert bundle.policy_material.content_base64
    assert bundle.source_artifact_bytes == "not_embedded"
    assert AssuranceBundle.model_validate(bundle.model_dump(mode="json")) == bundle
    assert render_assurance_bundle_json(bundle).endswith("\n")
    assert "does not independently re-run collectors" in render_assurance_bundle_readme(bundle)

    detached = create_policy_material(
        project_id="other-project",
        project_profile_id=bundle.policy_material.project_profile_id,
        project_profile_version=bundle.policy_material.project_profile_version,
        release_track=bundle.policy_material.release_track,
        artifact=bundle.policy_material.artifact,
        content=decode_policy_content(bundle.policy_material.content_base64),
    )
    with pytest.raises(ValidationError, match="profile authority"):
        AssuranceBundle(
            **bundle.model_dump(exclude={"bundle_id", "policy_material"}),
            bundle_id=bundle.bundle_id,
            policy_material=detached,
        )


def test_assurance_model_rejects_each_detached_association(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    bundle = application.get_assurance_bundle(candidate_id)
    legacy_candidate = load_config(
        repository_root / "examples/sample-python-api/candidates/draft.json"
    )
    legacy_evaluation = load_config(repository_root / "tests/golden/policy_pass.json")

    cases = (
        (
            bundle.model_copy(update={"generator_version": "detached"}),
            "generator metadata",
        ),
        (
            bundle.model_copy(
                update={
                    "project_profile": bundle.project_profile.model_copy(
                        update={"project_id": "other-project"}
                    )
                }
            ),
            "project profile",
        ),
        (
            bundle.model_copy(
                update={
                    "evidence_binding": bundle.evidence_binding.model_copy(
                        update={
                            "candidate": bundle.evidence_binding.candidate.model_copy(
                                update={"candidate_id": "cand-" + "0" * 24}
                            )
                        }
                    )
                }
            ),
            "evidence binding",
        ),
        (
            bundle.model_copy(
                update={
                    "attestation": bundle.attestation.model_copy(
                        update={"candidate": legacy_candidate}
                    )
                }
            ),
            "profile-bound candidate",
        ),
        (
            bundle.model_copy(
                update={
                    "attestation": bundle.attestation.model_copy(
                        update={"policy_evaluation": legacy_evaluation}
                    )
                }
            ),
            "profile-authorized policy evaluation",
        ),
        (
            bundle.model_copy(
                update={
                    "attestation": bundle.attestation.model_copy(
                        update={
                            "policy_evaluation": bundle.attestation.policy_evaluation.model_copy(
                                update={"policy_material_id": "sha256:" + "0" * 64}
                            )
                        }
                    )
                }
            ),
            "evaluation does not match",
        ),
        (bundle.model_copy(update={"bundle_id": "sha256:" + "0" * 64}), "bundle_id"),
    )
    for detached, message in cases:
        with pytest.raises(ValueError, match=message):
            detached.bundle_must_be_cross_document_consistent()

    no_track = bundle.project_profile.model_copy(
        update={"config": bundle.project_profile.config.model_copy(update={"release_tracks": {}})}
    )
    with pytest.raises(ValueError, match="not uniquely authorized"):
        bundle.model_copy(update={"project_profile": no_track})._validate_profile_policy_path(
            bundle.attestation.candidate
        )

    changed_artifact = bundle.policy_material.artifact.model_copy(
        update={"path_or_uri": "policies/other.yaml"}
    )
    changed_material = bundle.policy_material.model_copy(update={"artifact": changed_artifact})
    with pytest.raises(ValueError, match="path is not authorized"):
        bundle.model_copy(
            update={"policy_material": changed_material}
        )._validate_profile_policy_path(bundle.attestation.candidate)


def test_assurance_manifest_rejects_order_media_and_identity_drift(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    bundle = application.get_assurance_bundle(candidate_id)
    bundle_json = render_assurance_bundle_json(bundle).encode("utf-8")
    readme = render_assurance_bundle_readme(bundle).encode("utf-8")
    manifest = create_assurance_manifest(bundle, bundle_json=bundle_json, readme=readme)

    with pytest.raises(ValueError, match="canonical path order"):
        manifest.model_copy(
            update={"files": tuple(reversed(manifest.files))}
        ).manifest_must_be_canonical()
    wrong_media = manifest.files[0].model_copy(update={"media_type": "application/json"})
    with pytest.raises(ValueError, match="media types"):
        manifest.model_copy(
            update={"files": (wrong_media, manifest.files[1])}
        ).manifest_must_be_canonical()
    with pytest.raises(ValueError, match="manifest_id"):
        manifest.model_copy(
            update={"manifest_id": "sha256:" + "0" * 64}
        ).manifest_must_be_canonical()


def test_publish_verify_and_exact_replay_without_database(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    bundle = application.get_assurance_bundle(candidate_id)

    first = publish_assurance_bundle(bundle, tmp_path / "portable")
    second = publish_assurance_bundle(bundle, tmp_path / "portable")
    application.repository.database_path.unlink()
    verified = verify_assurance_bundle(first.directory)

    assert first.replayed is False
    assert second.replayed is True
    assert verified.bundle == bundle
    assert verified.manifest.bundle_id == bundle.bundle_id
    assert load_config(first.bundle_path) == bundle
    assert load_config(first.manifest_path) == verified.manifest
    assert {item.path for item in verified.manifest.files} == {
        "README.md",
        "assurance-bundle.json",
    }


@pytest.mark.parametrize("member", ["README.md", "assurance-bundle.json", "manifest.json"])
def test_verifier_rejects_any_member_tampering(
    tmp_path: Path,
    repository_root: Path,
    member: str,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    published = publish_assurance_bundle(
        application.get_assurance_bundle(candidate_id),
        tmp_path / member.replace(".", "-"),
    )
    path = published.directory / member
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(AssuranceBundleError):
        verify_assurance_bundle(published.directory)
    with pytest.raises(AssuranceBundleError, match="ASSURANCE_OUTPUT_CONFLICT"):
        publish_assurance_bundle(application.get_assurance_bundle(candidate_id), path.parent.parent)


def test_verifier_rejects_wrong_directory_shape_and_unsafe_members(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    published = publish_assurance_bundle(
        application.get_assurance_bundle(candidate_id), tmp_path / "portable"
    )
    renamed = published.directory.with_name("wrong-name")
    published.directory.rename(renamed)
    with pytest.raises(AssuranceBundleError, match="DIRECTORY_MISMATCH"):
        verify_assurance_bundle(renamed)

    (renamed / "extra.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(AssuranceBundleError, match="CONTENTS_INVALID"):
        verify_assurance_bundle(renamed)

    (renamed / "extra.txt").unlink()
    (renamed / "manifest.json").unlink()
    with pytest.raises(AssuranceBundleError, match="CONTENTS_INVALID"):
        verify_assurance_bundle(renamed)

    not_directory = tmp_path / "file"
    not_directory.write_text("not a bundle", encoding="utf-8")
    with pytest.raises(AssuranceBundleError, match="ASSURANCE_BUNDLE_INVALID"):
        verify_assurance_bundle(not_directory)


@pytest.mark.parametrize(
    "invalid_json",
    [
        b'{"schema_version":"forgegate.assurance-bundle.v1","schema_version":"duplicate"}',
        b'{"schema_version":"forgegate.assurance-bundle.v1","value":NaN}',
        b"\xff",
    ],
)
def test_verifier_rejects_non_strict_json(
    tmp_path: Path,
    repository_root: Path,
    invalid_json: bytes,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    published = publish_assurance_bundle(
        application.get_assurance_bundle(candidate_id), tmp_path / "strict"
    )
    published.bundle_path.write_bytes(invalid_json)
    with pytest.raises(AssuranceBundleError, match="DOCUMENT_INVALID"):
        verify_assurance_bundle(published.directory)


def test_verifier_enforces_member_size_and_regular_file(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    published = publish_assurance_bundle(
        application.get_assurance_bundle(candidate_id), tmp_path / "bounded"
    )
    published.readme_path.write_bytes(b"x" * (portable_module.MAX_ASSURANCE_AUXILIARY_BYTES + 1))
    with pytest.raises(AssuranceBundleError, match="FILE_TOO_LARGE"):
        verify_assurance_bundle(published.directory)

    published.readme_path.unlink()
    published.readme_path.mkdir()
    with pytest.raises(AssuranceBundleError, match="FILE_INVALID"):
        verify_assurance_bundle(published.directory)


def test_cli_exports_replays_and_verifies_portable_bundle(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    command = [
        "candidate",
        "export-assurance",
        str(application.repository.database_path),
        candidate_id,
        "--output-root",
        str(tmp_path / "exports"),
    ]
    first = runner.invoke(app, command)
    second = runner.invoke(app, command)
    assert first.exit_code == second.exit_code == 0
    assert json.loads(first.stdout)["output_replayed"] is False
    second_payload = json.loads(second.stdout)
    assert second_payload["output_replayed"] is True

    verified = runner.invoke(app, ["verify-assurance", second_payload["bundle_directory"]])
    assert verified.exit_code == 0
    report = json.loads(verified.stdout)
    assert report == {
        "assurance": "unsigned_local",
        "bundle_id": second_payload["bundle"]["bundle_id"],
        "candidate_id": candidate_id,
        "decision": "PASS",
        "source_artifact_bytes": "not_embedded",
        "status": "VALID",
    }

    bad = runner.invoke(app, ["verify-assurance", str(tmp_path / "exports")])
    assert bad.exit_code == 3
    assert "unexpected contents" in bad.output


def test_application_rejects_unknown_candidate(tmp_path: Path) -> None:
    application = CandidateApplication.for_database(tmp_path / "incomplete.db")
    application.initialize()
    with pytest.raises(CandidateStoreError, match="STORE_CANDIDATE_NOT_FOUND"):
        application.get_assurance_bundle("cand-" + "0" * 24)


def test_publication_translates_filesystem_failures(
    tmp_path: Path,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    bundle = application.get_assurance_bundle(candidate_id)
    occupied = tmp_path / "occupied"
    occupied.write_text("file", encoding="utf-8")
    with pytest.raises(AssuranceBundleError, match="OUTPUT_ROOT_INVALID"):
        publish_assurance_bundle(bundle, occupied)

    root = tmp_path / "staging-failure"

    def fail_mkdtemp(*_args: Any, **_kwargs: Any) -> str:
        raise OSError("staging denied")

    monkeypatch.setattr(portable_module.tempfile, "mkdtemp", fail_mkdtemp)
    with pytest.raises(AssuranceBundleError, match="cannot create staging directory"):
        publish_assurance_bundle(bundle, root)
    monkeypatch.undo()

    with pytest.raises(AssuranceBundleError, match="cannot stage assurance file"):
        portable_module._write_file(tmp_path / "absent" / "file", b"payload")


def test_publication_handles_rename_conflicts_and_existing_unsafe_targets(
    tmp_path: Path,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    bundle = application.get_assurance_bundle(candidate_id)
    original_replace = Path.replace

    def concurrent_replace(staging: Path, target: Path) -> Path:
        target.mkdir()
        for member in staging.iterdir():
            (target / member.name).write_bytes(member.read_bytes())
        raise OSError("concurrent publisher won")

    monkeypatch.setattr(Path, "replace", concurrent_replace)
    replay = publish_assurance_bundle(bundle, tmp_path / "concurrent")
    assert replay.replayed is True
    monkeypatch.setattr(Path, "replace", original_replace)

    def fail_replace(_staging: Path, _target: Path) -> Path:
        raise OSError("rename denied")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(AssuranceBundleError, match="cannot publish assurance bundle"):
        publish_assurance_bundle(bundle, tmp_path / "rename-failure")
    monkeypatch.setattr(Path, "replace", original_replace)

    root = tmp_path / "unsafe-existing"
    root.mkdir()
    target = root / ("assurance-" + bundle.bundle_id.removeprefix("sha256:"))
    target.write_text("occupied", encoding="utf-8")
    with pytest.raises(AssuranceBundleError, match="not a safe directory"):
        publish_assurance_bundle(bundle, root)

    symlink_root = tmp_path / "symlink-signal"
    symlink_target = symlink_root / ("assurance-" + bundle.bundle_id.removeprefix("sha256:"))
    original_is_symlink = Path.is_symlink

    def report_target_symlink(path: Path) -> bool:
        return path == symlink_target or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", report_target_symlink)
    with pytest.raises(AssuranceBundleError, match="unsafe symlink"):
        publish_assurance_bundle(bundle, symlink_root)


def test_portable_io_errors_are_stable(
    tmp_path: Path,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, candidate_id = _completed_application(tmp_path, repository_root)
    bundle = application.get_assurance_bundle(candidate_id)
    root = tmp_path / "mkdir-failure"
    original_mkdir = Path.mkdir

    def fail_root_mkdir(path: Path, *args: Any, **kwargs: Any) -> None:
        if path == root.resolve(strict=False):
            raise OSError("mkdir denied")
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_root_mkdir)
    with pytest.raises(AssuranceBundleError, match="cannot create output root"):
        publish_assurance_bundle(bundle, root)
    monkeypatch.setattr(Path, "mkdir", original_mkdir)

    published = publish_assurance_bundle(bundle, tmp_path / "read-failure")
    original_read_bytes = Path.read_bytes

    def fail_read(path: Path) -> bytes:
        if path == published.bundle_path:
            raise OSError("read denied")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    with pytest.raises(AssuranceBundleError, match="cannot read bundle member"):
        verify_assurance_bundle(published.directory)
    monkeypatch.setattr(Path, "read_bytes", original_read_bytes)

    original_iterdir = Path.iterdir

    def fail_iterdir(path: Path) -> Any:
        if path == published.directory:
            raise OSError("inspect denied")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fail_iterdir)
    with pytest.raises(AssuranceBundleError, match="cannot inspect bundle directory"):
        verify_assurance_bundle(published.directory)
