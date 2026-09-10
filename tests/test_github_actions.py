from __future__ import annotations

import json
import stat
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
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
from forgegate.assurance import publish_assurance_bundle, verify_assurance_bundle
from forgegate.assurance.portable import VerifiedAssuranceBundle
from forgegate.cli import app
from forgegate.config import load_config
from forgegate.domain.enums import CandidateStatus, Decision
from forgegate.domain.models import ProjectConfig
from forgegate.github_actions import (
    GitHubActionGateError,
    GitHubActionReport,
    append_github_file,
    create_github_action_report,
    github_action_exit_code,
    render_github_error_outputs,
    render_github_error_summary,
    render_github_outputs,
    render_github_step_summary,
)
from forgegate.github_actions import service as github_service
from forgegate.github_actions.models import RECOMMENDED_CONCLUSIONS
from forgegate.github_actions.service import (
    MAX_GITHUB_APPEND_BYTES,
    MAX_GITHUB_COMMAND_FILE_BYTES,
)

runner = CliRunner()
COMMIT = "a" * 40


def _published_pass_bundle(tmp_path: Path, repository_root: Path) -> Path:
    application = CandidateApplication.for_database(tmp_path / "forgegate.db")
    application.initialize()
    project = load_config(repository_root / "examples/sample-python-api/forgegate.yaml")
    assert isinstance(project, ProjectConfig)
    application.register_project(
        ProjectRegisterCommand(
            config=project,
            registered_at=datetime(2026, 8, 30, 11, 59, tzinfo=UTC),
        ),
        idempotency_key="project:github-action",
    )
    candidate = application.create_candidate(
        CandidateCreateCommand(
            project_id="sample-api",
            version="1.2.0",
            commit_sha=COMMIT,
            source_branch="main",
            release_track="pull-request",
            created_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
        ),
        idempotency_key="candidate:github-action",
    )
    application.advance_candidate(
        candidate.candidate_id,
        CandidateAdvanceCommand(
            to_status=CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
        ),
        idempotency_key="advance:github-action-collecting",
    )
    application.bind_evidence(
        candidate.candidate_id,
        CandidateBindEvidenceCommand(
            assembly=load_config(repository_root / "tests/golden/evidence_bundle_assembly.json"),
            bound_at=datetime(2026, 8, 30, 20, 31, tzinfo=UTC),
        ),
        idempotency_key="binding:github-action",
    )
    for revision, target, timestamp in (
        (1, CandidateStatus.READY, datetime(2026, 8, 30, 20, 32, tzinfo=UTC)),
        (2, CandidateStatus.EVALUATING, datetime(2026, 8, 30, 20, 33, tzinfo=UTC)),
    ):
        application.advance_candidate(
            candidate.candidate_id,
            CandidateAdvanceCommand(
                to_status=target,
                expected_revision=revision,
                occurred_at=timestamp,
            ),
            idempotency_key=f"advance:github-action-{target.value.lower()}",
        )
    material = application.materialize_policy(
        candidate.candidate_id,
        repository_root / "examples/sample-python-api",
    )
    application.evaluate_candidate(
        candidate.candidate_id,
        CandidateEvaluateCommand(
            policy_material=material,
            expected_revision=3,
            evaluated_at=datetime(2026, 8, 30, 21, 0, tzinfo=UTC),
        ),
        idempotency_key="evaluate:github-action",
    )
    application.attest_candidate(
        candidate.candidate_id,
        CandidateAttestCommand(issued_at=datetime(2026, 8, 30, 22, 0, tzinfo=UTC)),
    )
    return publish_assurance_bundle(
        application.get_assurance_bundle(candidate.candidate_id),
        tmp_path / "portable",
    ).directory


def test_report_binds_verified_bundle_to_complete_ci_commit(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    verified = verify_assurance_bundle(_published_pass_bundle(tmp_path, repository_root))
    report = create_github_action_report(verified, expected_commit=COMMIT.upper())

    assert report.schema_version == "forgegate.github-action-report.v1"
    assert report.decision is Decision.PASS
    assert report.recommended_conclusion == "success"
    assert report.candidate_commit == report.expected_commit == COMMIT
    assert report.commit_binding == "exact"
    assert report.assurance == "unsigned_local"
    assert GitHubActionReport.model_validate(report.model_dump(mode="json")) == report

    with pytest.raises(ValueError, match="exactly match"):
        report.model_copy(update={"expected_commit": "b" * 40}).identity_and_decision_must_match()
    with pytest.raises(ValueError, match="recommended conclusion"):
        report.model_copy(
            update={"recommended_conclusion": "failure"}
        ).identity_and_decision_must_match()
    with pytest.raises(ValueError, match="report_id"):
        report.model_copy(
            update={"report_id": "sha256:" + "0" * 64}
        ).identity_and_decision_must_match()


def test_report_rejects_partial_invalid_and_mismatched_commits(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    verified = verify_assurance_bundle(_published_pass_bundle(tmp_path, repository_root))

    for expected in ("a" * 39, "not-a-commit"):
        with pytest.raises(GitHubActionGateError, match="GITHUB_EXPECTED_COMMIT_INVALID"):
            create_github_action_report(verified, expected_commit=expected)
    with pytest.raises(GitHubActionGateError, match="GITHUB_COMMIT_MISMATCH"):
        create_github_action_report(verified, expected_commit="b" * 40)

    candidate = verified.bundle.attestation.candidate.model_copy(update={"commit_sha": "a" * 7})
    attestation = verified.bundle.attestation.model_copy(update={"candidate": candidate})
    incomplete = VerifiedAssuranceBundle(
        directory=verified.directory,
        bundle=verified.bundle.model_copy(update={"attestation": attestation}),
        manifest=verified.manifest,
    )
    with pytest.raises(GitHubActionGateError, match="GITHUB_CANDIDATE_COMMIT_INCOMPLETE"):
        create_github_action_report(incomplete, expected_commit=COMMIT)

    no_evaluation = verified.bundle.attestation.model_copy(update={"policy_evaluation": None})
    missing = VerifiedAssuranceBundle(
        directory=verified.directory,
        bundle=verified.bundle.model_copy(update={"attestation": no_evaluation}),
        manifest=verified.manifest,
    )
    with pytest.raises(GitHubActionGateError, match="GITHUB_EVALUATION_MISSING"):
        create_github_action_report(missing, expected_commit=COMMIT)


def test_decision_exit_and_recommended_conclusion_contract() -> None:
    assert {decision: github_action_exit_code(decision) for decision in Decision} == {
        Decision.PASS: 0,
        Decision.FAIL: 1,
        Decision.REVIEW: 2,
        Decision.ERROR: 3,
    }
    assert RECOMMENDED_CONCLUSIONS == {
        Decision.PASS: "success",
        Decision.FAIL: "failure",
        Decision.REVIEW: "action_required",
        Decision.ERROR: "failure",
    }


def test_summary_outputs_and_error_rendering_are_bounded_and_safe(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    verified = verify_assurance_bundle(_published_pass_bundle(tmp_path, repository_root))
    report = create_github_action_report(verified, expected_commit=COMMIT)
    evaluation = verified.bundle.attestation.policy_evaluation
    assert evaluation is not None
    hostile_rule = evaluation.rule_results[0].model_copy(
        update={"explanation": "<script>|line\nnext" + "x" * 2000}
    )
    hostile_evaluation = evaluation.model_copy(update={"rule_results": [hostile_rule] * 100})
    hostile_attestation = verified.bundle.attestation.model_copy(
        update={"policy_evaluation": hostile_evaluation}
    )
    hostile_bundle = verified.bundle.model_copy(update={"attestation": hostile_attestation})

    summary = render_github_step_summary(report, hostile_bundle)
    outputs = render_github_outputs(report)
    assert "&lt;script&gt;&#124;line next" in summary
    assert "additional rule result(s) omitted" in summary
    assert "does not call the GitHub Checks" in summary
    assert len(summary.encode("utf-8")) <= MAX_GITHUB_APPEND_BYTES
    assert "decision=PASS\n" in outputs
    assert f"candidate_commit={COMMIT}\n" in outputs
    assert render_github_error_outputs() == (
        "gate_status=ERROR\ndecision=ERROR\nrecommended_conclusion=failure\n"
    )
    assert "`GITHUB_COMMIT_MISMATCH`" in render_github_error_summary("GITHUB_COMMIT_MISMATCH")
    assert "`GITHUB_GATE_ERROR`" in render_github_error_summary("unsafe code")


def test_github_command_file_append_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "github-output.txt"
    append_github_file(output, "decision=PASS\n")
    append_github_file(output, "gate_status=VALID\n")
    assert output.read_text(encoding="utf-8") == "decision=PASS\ngate_status=VALID\n"

    with pytest.raises(GitHubActionGateError, match="PAYLOAD_INVALID"):
        append_github_file(output, "")
    with pytest.raises(GitHubActionGateError, match="PAYLOAD_INVALID"):
        append_github_file(output, "x" * (MAX_GITHUB_APPEND_BYTES + 1))
    with pytest.raises(GitHubActionGateError, match="FILE_UNSAFE"):
        append_github_file(tmp_path, "x")
    with pytest.raises(GitHubActionGateError, match="PARENT_INVALID"):
        append_github_file(tmp_path / "missing" / "output", "x")
    occupied_parent = tmp_path / "occupied-parent"
    occupied_parent.write_text("file", encoding="utf-8")
    with pytest.raises(GitHubActionGateError, match="PARENT_INVALID"):
        append_github_file(occupied_parent / "output", "x")

    full = tmp_path / "full.txt"
    full.write_bytes(b"x" * MAX_GITHUB_COMMAND_FILE_BYTES)
    with pytest.raises(GitHubActionGateError, match="FILE_TOO_LARGE"):
        append_github_file(full, "x")

    monkeypatch.setattr(
        github_service.os,
        "fstat",
        lambda _descriptor: SimpleNamespace(st_mode=stat.S_IFDIR, st_size=0),
    )
    with pytest.raises(GitHubActionGateError, match="FILE_UNSAFE"):
        append_github_file(tmp_path / "irregular.txt", "x")
    monkeypatch.undo()

    def fail_open(*_args: Any, **_kwargs: Any) -> int:
        raise OSError("denied")

    monkeypatch.setattr(github_service.os, "open", fail_open)
    with pytest.raises(GitHubActionGateError, match="FILE_IO"):
        append_github_file(tmp_path / "denied.txt", "x")


def test_github_command_file_rejects_symlink_when_available(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("host does not permit symlink creation")
    with pytest.raises(GitHubActionGateError, match="FILE_UNSAFE"):
        append_github_file(link, "decision=PASS\n")


def test_cli_writes_github_files_and_emits_versioned_report(
    tmp_path: Path,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _published_pass_bundle(tmp_path, repository_root)
    output = tmp_path / "output.txt"
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    result = runner.invoke(
        app,
        ["github-gate", str(directory), "--expected-commit", COMMIT],
    )
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["schema_version"] == "forgegate.github-action-report.v1"
    assert report["decision"] == "PASS"
    assert "gate_status=VALID" in output.read_text(encoding="utf-8")
    assert "**Decision: PASS**" in summary.read_text(encoding="utf-8")

    report_path = tmp_path / "report.json"
    report_path.write_text(result.stdout, encoding="utf-8")
    validated = runner.invoke(app, ["validate-config", str(report_path)])
    assert validated.exit_code == 0
    assert "VALID forgegate.github-action-report.v1" in validated.stdout


def test_cli_commit_mismatch_fails_closed_and_writes_error_files(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    directory = _published_pass_bundle(tmp_path, repository_root)
    output = tmp_path / "output.txt"
    summary = tmp_path / "summary.md"
    result = runner.invoke(
        app,
        [
            "github-gate",
            str(directory),
            "--expected-commit",
            "b" * 40,
            "--github-output",
            str(output),
            "--step-summary",
            str(summary),
        ],
    )
    assert result.exit_code == 3
    assert "GITHUB_COMMIT_MISMATCH" in result.output
    assert output.read_text(encoding="utf-8") == render_github_error_outputs()
    assert "**Decision: ERROR**" in summary.read_text(encoding="utf-8")
    assert COMMIT not in output.read_text(encoding="utf-8")


def test_cli_reports_secondary_github_file_failure(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    directory = _published_pass_bundle(tmp_path, repository_root)
    result = runner.invoke(
        app,
        [
            "github-gate",
            str(directory),
            "--expected-commit",
            "b" * 40,
            "--github-output",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 3
    assert "additionally failed to write GitHub files" in result.output


def test_action_metadata_uses_environment_not_inline_inputs(repository_root: Path) -> None:
    action = (repository_root / ".github/actions/assurance-gate/action.yml").read_text(
        encoding="utf-8"
    )
    run_block = action.split("run: >-", maxsplit=1)[1]
    assert "${{ inputs.assurance-directory }}" not in run_block
    assert "${{ inputs.expected-commit }}" not in run_block
    assert '"$FORGEGATE_ACTION_ASSURANCE_DIRECTORY"' in run_block
    assert '"$FORGEGATE_ACTION_EXPECTED_COMMIT"' in run_block
    assert "GITHUB_TOKEN" not in action


def test_repository_cloud_workflows_require_explicit_dispatch(repository_root: Path) -> None:
    workflow_paths = sorted(
        path
        for path in (repository_root / ".github/workflows").iterdir()
        if path.suffix in {".yml", ".yaml"}
    )
    assert workflow_paths
    for path in workflow_paths:
        # BaseLoader preserves GitHub's `on` key rather than YAML 1.1's boolean coercion.
        workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        assert set(workflow["on"]) == {"workflow_dispatch"}, path.name


def test_committed_generic_fixture_verifies_and_matches_action_workflow(
    repository_root: Path,
) -> None:
    fixture = (
        repository_root
        / "examples/sample-python-api/github-action-fixture"
        / "assurance-dbb54d911ff973918e1e89e52c4d58785ee6b8cb3f43e6f76c946c0a6ae605c9"
    )
    verified = verify_assurance_bundle(fixture)
    report = create_github_action_report(verified, expected_commit=COMMIT)
    workflow = (repository_root / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert report.decision is Decision.PASS
    assert str(fixture.relative_to(repository_root)).replace("\\", "/") in workflow
    assert "GitHub Action smoke (generic fixture)" in workflow
    assert "fixture-only portable assurance gate" in workflow
