from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

import forgegate.workspace_init as workspace_init
from forgegate.application import CandidateApplication, CandidateCreateCommand, CandidateQuery
from forgegate.artifacts import ArtifactRegistry
from forgegate.cli import app
from forgegate.collectors import JUnitCollectionRequest, JUnitCollector
from forgegate.config import load_config
from forgegate.domain.enums import Decision, EvidenceTrust, VerificationLevel
from forgegate.domain.models import EvidenceBundle, ExecutionContext, PolicyConfig, ProjectConfig
from forgegate.identity import (
    IdentityRole,
    SigningIdentity,
    TrustStore,
    derive_signing_identity,
    load_ed25519_private_key,
    load_identity_document,
)
from forgegate.policy import PolicyMaterial, evaluate_policy
from forgegate.workspace_init import (
    WorkspaceInitializationError,
    WorkspaceInitializationReport,
    initialize_workspace,
)


def test_workspace_creates_project_and_restricted_identity_without_demo(tmp_path: Path) -> None:
    root = tmp_path / "private"
    result = CliRunner().invoke(app, ["workspace-init", str(root), "--project-id", "my-project"])
    assert result.exit_code == 0, result.output
    receipt = WorkspaceInitializationReport.model_validate_json(result.stdout)
    assert receipt == WorkspaceInitializationReport.model_validate_json(
        (root / "workspace.json").read_text()
    )
    assert load_config(root / "workspace.json") == receipt
    validation = CliRunner().invoke(app, ["validate-config", str(root / "workspace.json")])
    assert validation.exit_code == 0, validation.output
    assert receipt.project_id == "my-project"
    assert receipt.demo_cases == ()
    assert receipt.service == "NOT_STARTED"
    assert receipt.browser_session == "NOT_ACTIVATED"
    assert receipt.hardware_access == "NOT_PERFORMED"
    assert str(root) not in result.stdout
    assert "PRIVATE KEY" not in result.output
    assert (root / ".gitignore").read_text() == "*\n"
    private_bytes = (root / "operator-key.pem").read_text()
    assert private_bytes.splitlines()[1] not in result.output
    identity = load_identity_document(root / "identity.json")
    assert isinstance(identity, SigningIdentity)
    assert (
        derive_signing_identity(
            load_ed25519_private_key(root / "operator-key.pem"), display_name=identity.display_name
        )
        == identity
    )
    trust = load_identity_document(root / "trust-store.json")
    assert isinstance(trust, TrustStore)
    assert trust.identities[0].identity == identity
    assert trust.identities[0].roles == (IdentityRole.OPERATOR,)
    assert trust.identities[0].project_ids == ("my-project",)
    application = CandidateApplication.for_database(root / "forgegate.db")
    assert application.get_project("my-project").config.project.id == "my-project"
    assert application.list_candidates(CandidateQuery(project_id="my-project")).candidates == ()
    assert isinstance(load_config(root / "forgegate.yaml"), ProjectConfig)
    with sqlite3.connect(root / "jobs.db") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
    instructions = (root / "START_HERE.md").read_text()
    assert "--existing-pair" in instructions
    assert "--project my-project" in instructions
    assert str(root) not in instructions


def test_keys_are_random_and_private_on_posix(tmp_path: Path) -> None:
    first = initialize_workspace(tmp_path / "one")
    second = initialize_workspace(tmp_path / "two")
    assert first.operator_identity_id != second.operator_identity_id
    if os.name != "nt":
        assert (tmp_path / "one/operator-key.pem").stat().st_mode & 0o777 == 0o600
        assert (tmp_path / "one").stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("existing", ["empty-directory", "file", "workspace"])
def test_existing_destination_is_never_modified(tmp_path: Path, existing: str) -> None:
    root = tmp_path / "existing"
    if existing == "workspace":
        initialize_workspace(root, demo=True)
    elif existing == "file":
        root.write_bytes(b"keep")
    else:
        root.mkdir()
    before = (
        {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()} if root.is_dir() else {}
    )
    result = CliRunner().invoke(app, ["workspace-init", str(root), "--demo"])
    assert result.exit_code in (2, 3)
    after = (
        {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()} if root.is_dir() else {}
    )
    assert before == after
    if existing == "file":
        assert root.read_bytes() == b"keep"


@pytest.mark.parametrize("option,value", [("--project-id", "../invalid"), ("--project-name", " ")])
def test_invalid_configuration_does_not_create_destination(
    tmp_path: Path, option: str, value: str
) -> None:
    root = tmp_path / "not-created"
    result = CliRunner().invoke(app, ["workspace-init", str(root), option, value])
    assert result.exit_code == 3
    assert not root.exists()


def test_missing_parent_and_creation_failure_are_actionable(tmp_path: Path, monkeypatch) -> None:
    with pytest.raises(WorkspaceInitializationError, match="PARENT_MISSING"):
        initialize_workspace(tmp_path / "missing/child")

    def fail(*_args, **_kwargs):
        raise PermissionError("injected")

    monkeypatch.setattr(Path, "mkdir", fail)
    with pytest.raises(WorkspaceInitializationError, match="CREATE_FAILED"):
        initialize_workspace(tmp_path / "cannot-create")


def test_partial_io_failure_keeps_original_bytes_without_completion_marker(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "incomplete"
    original = workspace_init._write_new

    def fail_selected(path: Path, content: bytes) -> None:
        if path.name == "trust-store.json":
            raise OSError("injected")
        original(path, content)

    monkeypatch.setattr(workspace_init, "_write_new", fail_selected)
    with pytest.raises(WorkspaceInitializationError, match="INCOMPLETE"):
        initialize_workspace(root)
    assert not (root / "workspace.json").exists()
    retained_key = (root / "operator-key.pem").read_bytes()
    with pytest.raises(WorkspaceInitializationError, match="TARGET_EXISTS"):
        initialize_workspace(root)
    assert (root / "operator-key.pem").read_bytes() == retained_key


def test_exclusive_file_write_does_not_replace_key(tmp_path: Path) -> None:
    path = tmp_path / "operator-key.pem"
    path.write_bytes(b"existing private key")
    with pytest.raises(FileExistsError):
        workspace_init._write_new(path, b"replacement")
    assert path.read_bytes() == b"existing private key"


def test_seeded_examples_retain_raw_inputs_and_honest_assurance(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    receipt = initialize_workspace(root, project_id="demo-project", demo=True)
    assert [case.decision for case in receipt.demo_cases] == ["PASS", "FAIL"]
    application = CandidateApplication.for_database(root / "forgegate.db")
    for case in receipt.demo_cases:
        candidate = application.get_candidate(case.candidate_id)
        assert candidate.version == case.version
        assert candidate.status.value == case.decision
        evaluation = application.get_evaluation(case.candidate_id)
        assert evaluation is not None
        assert evaluation.decision.value == case.decision
        assert application.get_assurance_bundle(case.candidate_id)
        evidence = application.get_evidence(case.candidate_id).assembly.bundle.evidence
        assert len(evidence) == 1
        assert evidence[0].verification_level is VerificationLevel.DECLARED
        assert evidence[0].trust is EvidenceTrust.UNSIGNED_LOCAL
        assert evidence[0].execution_context.tags["evidence_origin"] == "SYNTHETIC"
        assert evidence[0].scope == "synthetic-demo"
        raw = root / evidence[0].artifact.path_or_uri
        assert b"SYNTHETIC" in raw.read_bytes()
        assert (root / f"artifacts/{case.version}-collection.json").is_file()
        assert len(application.get_history(case.candidate_id).transitions) == 4
    assert "Select the saved pull-request policy" in (root / "START_HERE.md").read_text()


@pytest.mark.parametrize(
    "xml",
    [
        '<testsuite tests="0" failures="0" errors="0" skipped="0"/>',
        '<testsuite><testcase time="0"><skipped/></testcase></testsuite>',
        '<testsuite><testcase time="0"><error/></testcase></testsuite>',
    ],
)
def test_starter_policy_rejects_zero_executed_and_errored_tests(tmp_path: Path, xml: str) -> None:
    root = tmp_path / "policy"
    initialize_workspace(root)
    (root / "artifacts/control.xml").write_text(xml)
    stamp = datetime.now(UTC)
    collection = JUnitCollector(ArtifactRegistry(root)).collect(
        JUnitCollectionRequest(
            source_path="artifacts/control.xml",
            source_tool="synthetic-test",
            source_version="1",
            execution_context=ExecutionContext(commit_sha="a" * 40),
            collected_at=stamp,
            trust=EvidenceTrust.UNSIGNED_LOCAL,
            verification_level=VerificationLevel.DECLARED,
        )
    )
    policy = load_config(root / "policies/pull-request.yaml")
    assert isinstance(policy, PolicyConfig)
    evaluation = evaluate_policy(
        policy,
        EvidenceBundle(
            schema_version="forgegate.evidence-bundle.v1",
            producer="test",
            producer_version="1",
            candidate_commit="a" * 40,
            generated_at=stamp,
            evidence=collection.evidence,
        ),
        evaluated_at=stamp,
    )
    assert evaluation.decision is Decision.FAIL


def test_isolated_cli_works_from_unrelated_directory_without_fixture_files(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-m", "forgegate", "workspace-init", "new-workspace", "--demo"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "INITIALIZED"
    assert (tmp_path / "new-workspace/workspace.json").is_file()
    assert "PRIVATE KEY" not in result.stdout + result.stderr


def test_first_policy_instructions_create_loadable_utf8_in_windows_powershell(
    tmp_path: Path,
) -> None:
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("Windows PowerShell instruction check requires powershell.exe")
    root = tmp_path / "first-use"
    initialize_workspace(root)
    application = CandidateApplication.for_database(root / "forgegate.db")
    candidate = application.create_candidate(
        CandidateCreateCommand(
            project_id="sample-project",
            version="first-use",
            commit_sha="a" * 40,
            created_at=datetime.now(UTC),
        ),
        idempotency_key="first-use:create",
    )
    instructions = (root / "START_HERE.md").read_text()
    blocks = re.findall(r"```powershell\n(.*?)\n```", instructions, re.DOTALL)
    material_block = next(block for block in blocks if "materialize-policy" in block)
    script = tmp_path / "first-policy.ps1"
    script.write_text(
        "param([string]$ForgeGatePython)\n$ErrorActionPreference = 'Stop'\n"
        + material_block.replace("CANDIDATE_ID", candidate.candidate_id),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ForgeGatePython",
            sys.executable,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert not (root / "policy-material.json").read_bytes().startswith(b"\xef\xbb\xbf")
    material = load_config(root / "policy-material.json")
    assert isinstance(material, PolicyMaterial)
    assert material.project_id == candidate.project_id
    assert material.project_profile_id == candidate.project_profile_id
    assert "Resolve-Path ./.venv/Scripts/python.exe" in instructions
