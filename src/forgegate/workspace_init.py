"""Self-contained first use of an installed local ForgeGate package."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from forgegate import __version__
from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    CandidateEvaluateCommand,
    ProjectRegisterCommand,
)
from forgegate.artifacts import ArtifactRegistry
from forgegate.assembly import CollectionResultLoader, assemble_evidence_bundle
from forgegate.collection_jobs import CollectionJobStore
from forgegate.collectors import JUnitCollectionRequest, JUnitCollector
from forgegate.domain.enums import (
    CandidateStatus,
    CollectorType,
    EvidenceTrust,
    Operator,
    VerificationLevel,
)
from forgegate.domain.models import (
    CollectorConfig,
    ExecutionContext,
    OutputConfig,
    PolicyConfig,
    PolicyRule,
    ProjectConfig,
    ProjectIdentity,
    ReleaseTrack,
    StrictModel,
)
from forgegate.identity import (
    IdentityRole,
    TrustedIdentity,
    create_trust_store,
    derive_signing_identity,
)
from forgegate.workspace_init_models import WorkspaceDemoCase, WorkspaceInitializationReport


class WorkspaceInitializationError(ValueError):
    """New-workspace initialization failed; existing workspaces are never adopted."""


def initialize_workspace(
    target: Path,
    *,
    project_id: str = "sample-project",
    project_name: str = "Sample Project",
    demo: bool = False,
) -> WorkspaceInitializationReport:
    """Reserve a new directory, then prepare all files needed by the installed Dashboard.

    Validate before any write. On an I/O or domain failure the new private directory
    is retained for inspection and no successful receipt is written. Retrying never
    overwrites an existing directory, including a partial initialization.
    """
    project, policy = _workspace_models(project_id, project_name)
    key = Ed25519PrivateKey.generate()
    identity = derive_signing_identity(key, display_name="Local workspace operator")
    trust = create_trust_store(
        (
            TrustedIdentity(
                identity=identity, roles=(IdentityRole.OPERATOR,), project_ids=(project.project.id,)
            ),
        )
    )
    requested = target.expanduser().absolute()
    if requested.exists() or requested.is_symlink() or requested.is_junction():
        raise WorkspaceInitializationError("WORKSPACE_TARGET_EXISTS: choose a NEW directory")
    if not requested.parent.is_dir():
        raise WorkspaceInitializationError("WORKSPACE_PARENT_MISSING: create the parent first")
    try:
        requested.mkdir(mode=0o700)
    except OSError as exc:
        raise WorkspaceInitializationError("WORKSPACE_CREATE_FAILED: no workspace created") from exc
    try:
        (requested / "policies").mkdir()
        (requested / "artifacts").mkdir()
        _write_new(requested / ".gitignore", b"*\n")
        _write_new(
            requested / "operator-key.pem",
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        )
        _write_new(requested / "identity.json", _json(identity))
        _write_new(requested / "trust-store.json", _json(trust))
        _write_new(requested / "forgegate.yaml", _yaml(project))
        _write_new(requested / "policies/pull-request.yaml", _yaml(policy))
        application = CandidateApplication.for_database(requested / "forgegate.db")
        application.initialize()
        CollectionJobStore(requested / "jobs.db").initialize()
        stamp = datetime.now(UTC)
        application.register_project(
            ProjectRegisterCommand(config=project, registered_at=stamp),
            idempotency_key="workspace-init:project",
        )
        cases = tuple(_seed_demo(application, requested, project.project.id, stamp)) if demo else ()
        _write_new(requested / "START_HERE.md", _instructions(project.project.id, demo).encode())
        report = WorkspaceInitializationReport(
            project_id=project.project.id,
            operator_identity_id=identity.identity_id,
            demo_cases=cases,
        )
        # This is the final completion marker, after stores and examples have passed readback.
        _write_new(requested / "workspace.json", _json(report))
        return report
    except (OSError, ValueError, RuntimeError) as exc:
        raise WorkspaceInitializationError(
            "WORKSPACE_INITIALIZATION_INCOMPLETE: new private directory retained; "
            "do not launch it, inspect it and choose a new destination for retry"
        ) from exc


def _workspace_models(project_id: str, project_name: str) -> tuple[ProjectConfig, PolicyConfig]:
    project = ProjectConfig(
        schema_version="forgegate.project.v1",
        project=ProjectIdentity(id=project_id, name=project_name),
        release_tracks={"pull-request": ReleaseTrack(policy="policies/pull-request.yaml")},
        collectors=[CollectorConfig(type=CollectorType.JUNIT, path="artifacts/junit.xml")],
        outputs=OutputConfig(
            **{"json": "output/attestation.json", "markdown": "output/summary.md"}
        ),
    )
    policy = PolicyConfig(
        schema_version="forgegate.policy.v1",
        name="pull-request",
        rules=[
            PolicyRule(
                id=rule,
                claim="tests.required-pass",
                evidence_kind="test.summary",
                operator=operator,
                expected=expected,
                where={"field": field},
            )
            for rule, field, operator, expected in (
                ("tests-executed", "passed", Operator.GREATER_THAN, 0),
                ("tests-pass", "failures", Operator.EQUALS, 0),
                ("tests-error-free", "errors", Operator.EQUALS, 0),
            )
        ],
    )
    return project, policy


def _seed_demo(
    application: CandidateApplication,
    root: Path,
    project_id: str,
    stamp: datetime,
) -> list[WorkspaceDemoCase]:
    cases: list[WorkspaceDemoCase] = []
    registry = ArtifactRegistry(root)
    for outcome in ("pass", "fail"):
        version = f"synthetic-demo-{outcome}"
        commit = ("d" if outcome == "pass" else "e") * 40
        report_path = f"artifacts/{version}.xml"
        failure = (
            '<failure message="Synthetic demonstration failure"/>' if outcome == "fail" else ""
        )
        xml = (
            '<testsuite name="SYNTHETIC ForgeGate demonstration">'
            '<testcase name="synthetic-success" time="0.01"/>'
            f'<testcase name="synthetic-control" time="0.01">{failure}</testcase>'
            "</testsuite>\n"
        )
        _write_new(root / report_path, xml.encode())
        collection = JUnitCollector(registry).collect(
            JUnitCollectionRequest(
                source_path=report_path,
                source_tool="forgegate-synthetic-demo",
                source_version=__version__,
                execution_context=ExecutionContext(
                    commit_sha=commit, tags={"evidence_origin": "SYNTHETIC"}
                ),
                collected_at=stamp,
                trust=EvidenceTrust.UNSIGNED_LOCAL,
                verification_level=VerificationLevel.DECLARED,
                scope="synthetic-demo",
            )
        )
        collection_path = f"artifacts/{version}-collection.json"
        _write_new(root / collection_path, _json(collection))
        assembly = assemble_evidence_bundle(
            (CollectionResultLoader(registry).load(collection_path),),
            candidate_commit=commit,
            generated_at=stamp,
            producer="forgegate-synthetic-demo",
            producer_version=__version__,
        )
        candidate = application.create_candidate(
            CandidateCreateCommand(
                project_id=project_id, version=version, commit_sha=commit, created_at=stamp
            ),
            idempotency_key=f"workspace-init:{outcome}:create",
        )
        candidate_id = candidate.candidate_id
        application.advance_candidate(
            candidate_id,
            CandidateAdvanceCommand(
                to_status=CandidateStatus.COLLECTING,
                expected_revision=0,
                occurred_at=stamp,
            ),
            idempotency_key=f"workspace-init:{outcome}:collecting",
        )
        application.bind_evidence(
            candidate_id,
            CandidateBindEvidenceCommand(
                assembly=assembly,
                bound_at=stamp,
            ),
            idempotency_key=f"workspace-init:{outcome}:bind",
        )
        for revision, status in ((1, CandidateStatus.READY), (2, CandidateStatus.EVALUATING)):
            application.advance_candidate(
                candidate_id,
                CandidateAdvanceCommand(
                    to_status=status,
                    expected_revision=revision,
                    occurred_at=stamp,
                ),
                idempotency_key=f"workspace-init:{outcome}:{status}",
            )
        result = application.evaluate_candidate(
            candidate_id,
            CandidateEvaluateCommand(
                policy_material=application.materialize_policy(candidate_id, root),
                expected_revision=3,
                evaluated_at=stamp,
            ),
            idempotency_key=f"workspace-init:{outcome}:evaluate",
        )
        if result.evaluation.decision.value != outcome.upper():
            raise WorkspaceInitializationError("WORKSPACE_DEMO_DECISION_MISMATCH")
        application.attest_candidate(candidate_id, CandidateAttestCommand(issued_at=stamp))
        # Independently reconstruct the retained handoff, including profile and policy binding.
        application.get_assurance_bundle(candidate_id)
        cases.append(
            WorkspaceDemoCase.model_validate(
                {
                    "candidate_id": candidate_id,
                    "version": version,
                    "decision": outcome.upper(),
                }
            )
        )
    return cases


def _write_new(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)


def _json(document: StrictModel) -> bytes:
    return (document.model_dump_json(indent=2) + "\n").encode("utf-8")


def _yaml(document: StrictModel) -> bytes:
    return yaml.safe_dump(
        document.model_dump(mode="json", by_alias=True, exclude_none=True), sort_keys=False
    ).encode("utf-8")


def _instructions(project_id: str, demo: bool) -> str:
    sample_note = (
        "Candidates synthetic-demo-pass and synthetic-demo-fail are ready for review.\n"
        "Their commit IDs and JUnit reports are synthetic, with unsigned_local / declared\n"
        "evidence. They demonstrate the workflow, not an actual project test run.\n"
        "\nTo repeat the workflow yourself, create another candidate with the corresponding\n"
        "commit, then choose Quick Assessment and select the single original XML file:\n"
        "\n| Report | Synthetic commit | Expected result |\n"
        "|---|---|---|\n"
        f"| artifacts/synthetic-demo-pass.xml | {'d' * 40} |"
        " PASS: 2 passed, 0 failures, 0 errors |\n"
        f"| artifacts/synthetic-demo-fail.xml | {'e' * 40} |"
        " FAIL tests-pass: 1 passed, 1 failure, 0 errors |\n"
        "\nSelect the saved pull-request policy, use forgegate-synthetic-demo as source tool,\n"
        "and retain declared verification and unsigned_local trust. The paired collection\n"
        "JSON files record complete generated metadata; upload the XML original, not that\n"
        "JSON, to Quick Assessment. Do not relabel these examples as actual test runs.\n"
        if demo
        else "This workspace starts without candidates or evidence. Create a candidate for your\n"
        "actual commit in Candidates. For the FIRST assessment, the workspace has no saved\n"
        "evaluated policy. Copy the candidate ID from its details and replace CANDIDATE_ID\n"
        "below. In the second terminal, materialize the profile-authorized starter policy:\n"
        "\n```powershell\n"
        "if (Test-Path ./policy-material.json) { throw 'Choose a new output filename first.' }\n"
        "$material = & $ForgeGatePython -m forgegate candidate materialize-policy `\n"
        "  ./forgegate.db CANDIDATE_ID --project-root .\n"
        "if ($LASTEXITCODE -ne 0) { throw 'Policy material creation failed.' }\n"
        "[System.IO.File]::WriteAllLines(\n"
        "  (Join-Path (Get-Location).Path 'policy-material.json'),\n"
        "  [string[]]$material,\n"
        "  [System.Text.UTF8Encoding]::new($false)\n"
        ")\n```\n"
        "\nThis writes UTF-8 without a BOM in Windows PowerShell 5 and PowerShell 7. In\n"
        "Quick Assessment, select policy-material.json in Profile-authorized policy material\n"
        "JSON, then select your original JUnit report separately. The YAML file itself is\n"
        "not a policy-material JSON upload. Review the exact rules and reported results.\n"
        "After one completed assessment, compatible candidates can reuse its saved policy.\n"
    )
    return f"""# Your local ForgeGate workspace

Use the Python 3.12 environment in which ForgeGate is installed. In PowerShell,
start from the installation directory containing that environment and resolve its
interpreter (replace .venv if you used another environment directory name):

```powershell
$ForgeGatePython = (Resolve-Path ./.venv/Scripts/python.exe).Path
& $ForgeGatePython -c "import forgegate; print('ForgeGate interpreter ready')"
```

Then change to this workspace directory with Set-Location. This uses the installed
interpreter explicitly, so it does not invoke the Windows Store python alias or
require a PowerShell execution-policy change for Activate.ps1. Start the Dashboard:

```powershell
& $ForgeGatePython -m forgegate dashboard --database ./forgegate.db `
  --trust-store ./trust-store.json --job-store ./jobs.db --existing-pair --port 8000
```

Keep that terminal running. Open http://127.0.0.1:8000/app/ and select Start local
activation. In a second terminal, repeat the interpreter-resolution step from the
installation directory, then change to this workspace directory. Replace
FG-ABCDE-FGHJK with the current page's code:

```powershell
& $ForgeGatePython -m forgegate dashboard-activate FG-ABCDE-FGHJK `
  --server http://127.0.0.1:8000 `
  --identity ./identity.json --private-key ./operator-key.pem `
  --role operator --project {project_id}
```

{sample_note}
The starter policy requires at least one passing test, zero failures and zero
errors. Missing evidence produces REVIEW. Select a suitable policy before using
real reports; this policy is a starting point, not a general release certification.

If port 8000 is occupied, choose another port in BOTH commands and the browser URL.
Press Ctrl+C in the server terminal to stop. Restart with the first command and
approve a new browser session. The database and identity persist across restarts.

operator-key.pem is your unencrypted local Ed25519 private key. Keep this directory
private, with access limited to your Windows account; permissions inherit from
its parent directory on Windows. Do not upload, commit, paste or share it. The
generated .gitignore excludes the entire workspace, but does not provide encryption.
Share only deliberately exported assurance files after reviewing their contents.

Setup has not started a service, activated a session or accessed hardware.
"""


__all__ = ["WorkspaceInitializationError", "WorkspaceInitializationReport", "initialize_workspace"]
