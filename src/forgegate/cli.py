import json
import platform
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from forgegate import __version__
from forgegate.application import (
    AuditEventQuery,
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    CandidateQuery,
    ProjectProfileQuery,
    ProjectQuery,
    ProjectRegisterCommand,
    ProjectReviseCommand,
)
from forgegate.artifacts import ArtifactBoundaryError, ArtifactError, ArtifactRegistry
from forgegate.assembly import (
    CollectionResultLoader,
    CollectionResultLoadError,
    EvidenceAssemblyError,
    EvidenceBundleAssembly,
    assemble_evidence_bundle,
)
from forgegate.attestations import AttestationPublishError, publish_attestation_bundle
from forgegate.candidates import (
    CandidateDocument,
    CandidateLifecycleError,
    CandidateStoreError,
    ProfileBoundReleaseCandidate,
    ReleaseCandidate,
    SQLiteCandidateRepository,
    transition_candidate,
)
from forgegate.collectors import (
    AnalogValidationCollectionRequest,
    AnalogValidationResultCollector,
    BenchmarkCollectionRequest,
    BenchmarkJsonCollector,
    CollectionResult,
    CollectionStatus,
    CoverageCollectionRequest,
    CoverageXmlCollector,
    JUnitCollectionRequest,
    JUnitCollector,
    LcovCollector,
    SarifCollectionRequest,
    SarifCollector,
)
from forgegate.config import ConfigLoadError, load_config
from forgegate.domain.enums import CandidateStatus, Decision, EvidenceTrust, VerificationLevel
from forgegate.domain.models import EvidenceBundle, ExecutionContext, PolicyConfig, ProjectConfig
from forgegate.network import validated_loopback_host
from forgegate.policy import evaluate_policy
from forgegate.policy.models import PolicyEvaluation
from forgegate.schema_registry import ARTIFACT_SCHEMAS, SCHEMAS, schema_filename

app = typer.Typer(
    name="forgegate",
    help="ForgeGate evidence collection and release-assurance tools.",
    no_args_is_help=True,
)
candidate_app = typer.Typer(help="Create and advance immutable release candidates.")
project_app = typer.Typer(help="Register and inspect immutable project profiles.")
audit_app = typer.Typer(help="Query durable append-only audit events.")
app.add_typer(candidate_app, name="candidate")
app.add_typer(project_app, name="project")
app.add_typer(audit_app, name="audit")


@app.command()
def doctor() -> None:
    """Report the local contract-tooling environment."""
    report = {
        "forgegate_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "supported_schemas": sorted(SCHEMAS),
        "supported_artifact_schemas": sorted(ARTIFACT_SCHEMAS),
        "phase": "phase9-project-profile-revisions",
    }
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


@app.command("validate-config")
def validate_config(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Validate a versioned ForgeGate YAML or JSON document."""
    try:
        config = load_config(path)
    except ConfigLoadError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(f"VALID {config.schema_version}: {path}")


@app.command("export-schemas")
def export_schemas(
    output_dir: Annotated[Path, typer.Argument(file_okay=False)],
) -> None:
    """Export canonical document and collector-artifact JSON Schemas."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for schema_version, model in sorted(SCHEMAS.items()):
        target = output_dir / schema_filename(schema_version)
        payload = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        target.write_bytes(payload.encode("utf-8"))
        typer.echo(str(target))
    for schema_name, schema in sorted(ARTIFACT_SCHEMAS.items()):
        target = output_dir / schema_filename(schema_name)
        payload = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        target.write_bytes(payload.encode("utf-8"))
        typer.echo(str(target))


@app.command("export-openapi")
def export_openapi(
    output_file: Annotated[Path, typer.Argument(dir_okay=False)],
) -> None:
    """Export the deterministic local REST API OpenAPI contract."""
    from forgegate.api import create_api_app

    if not output_file.parent.is_dir():
        typer.echo(f"ERROR: output parent does not exist: {output_file.parent}", err=True)
        raise typer.Exit(code=3)
    payload = (
        json.dumps(
            create_api_app(Path("forgegate-openapi-contract.db")).openapi(),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    output_file.write_bytes(payload.encode("utf-8"))
    typer.echo(str(output_file))


@app.command("serve")
def serve(
    database: Annotated[Path, typer.Option("--database", dir_okay=False)],
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8000,
) -> None:
    """Serve the local REST API on an explicitly loopback-only address."""
    import uvicorn

    from forgegate.api import create_api_app

    try:
        bind_host = validated_loopback_host(host)
        application = CandidateApplication.for_database(database)
        application.initialize()
    except (CandidateStoreError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    uvicorn.run(
        create_api_app(database, application=application),
        host=bind_host,
        port=port,
        log_level="info",
    )


@project_app.command("register")
def project_register(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    config_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    registered_at: Annotated[str, typer.Option("--registered-at")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
) -> None:
    """Persist one immutable project profile with exact idempotent replay."""
    try:
        config = load_config(config_path)
        if not isinstance(config, ProjectConfig):
            raise ValueError("config path must contain forgegate.project.v1")
        project = CandidateApplication.for_database(database).register_project(
            ProjectRegisterCommand(
                config=config,
                registered_at=datetime.fromisoformat(registered_at.replace("Z", "+00:00")),
            ),
            idempotency_key=idempotency_key,
        )
    except (CandidateStoreError, ConfigLoadError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(project.model_dump_json(indent=2))


@project_app.command("show")
def project_show(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    project_id: Annotated[str, typer.Argument()],
) -> None:
    """Read and validate one immutable project profile."""
    try:
        project = CandidateApplication.for_database(database).get_project(project_id)
    except CandidateStoreError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(project.model_dump_json(indent=2))


@project_app.command("revise")
def project_revise(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    project_id: Annotated[str, typer.Argument()],
    config_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    expected_profile_version: Annotated[int, typer.Option("--expected-profile-version", min=1)],
    effective_at: Annotated[str, typer.Option("--effective-at")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
) -> None:
    """Append a complete replacement profile under compare-and-swap authority."""
    try:
        config = load_config(config_path)
        if not isinstance(config, ProjectConfig):
            raise ValueError("config path must contain forgegate.project.v1")
        revision = CandidateApplication.for_database(database).revise_project(
            project_id,
            ProjectReviseCommand(
                config=config,
                expected_profile_version=expected_profile_version,
                effective_at=datetime.fromisoformat(effective_at.replace("Z", "+00:00")),
            ),
            idempotency_key=idempotency_key,
        )
    except (CandidateStoreError, ConfigLoadError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(revision.model_dump_json(indent=2))


@project_app.command("current")
def project_current(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    project_id: Annotated[str, typer.Argument()],
) -> None:
    """Read and validate the current immutable project profile."""
    try:
        profile = CandidateApplication.for_database(database).get_current_project_profile(
            project_id
        )
    except CandidateStoreError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(profile.model_dump_json(indent=2))


@project_app.command("history")
def project_history(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    project_id: Annotated[str, typer.Argument()],
    after_profile_version: Annotated[int, typer.Option("--after-profile-version", min=0)] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 100,
) -> None:
    """List a bounded version-ordered page of one project's immutable profiles."""
    try:
        page = CandidateApplication.for_database(database).list_project_profiles(
            ProjectProfileQuery(
                project_id=project_id,
                after_profile_version=after_profile_version,
                limit=limit,
            )
        )
    except (CandidateStoreError, ValidationError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(page.model_dump_json(indent=2))


@project_app.command("list")
def project_list(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    after_project_id: Annotated[str | None, typer.Option("--after-project")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 100,
) -> None:
    """List a bounded lexicographic page of registered projects."""
    try:
        page = CandidateApplication.for_database(database).list_projects(
            ProjectQuery(after_project_id=after_project_id, limit=limit)
        )
    except (CandidateStoreError, ValidationError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(page.model_dump_json(indent=2))


@audit_app.command("events")
def audit_events(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    after_sequence: Annotated[int, typer.Option("--after-sequence", min=0)] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 100,
    project_id: Annotated[str | None, typer.Option("--project")] = None,
    candidate_id: Annotated[str | None, typer.Option("--candidate")] = None,
) -> None:
    """Query a bounded stable-cursor page of append-only audit events."""
    try:
        page = CandidateApplication.for_database(database).query_audit_events(
            AuditEventQuery(
                after_sequence=after_sequence,
                limit=limit,
                project_id=project_id,
                candidate_id=candidate_id,
            )
        )
    except (CandidateStoreError, ValidationError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(page.model_dump_json(indent=2))


@candidate_app.command("create")
def candidate_create(
    project_id: Annotated[str, typer.Option("--project")],
    version: Annotated[str, typer.Option("--version")],
    commit: Annotated[str, typer.Option("--commit")],
    created_at: Annotated[str, typer.Option("--created-at")],
    source_branch: Annotated[str, typer.Option("--branch")] = "main",
    release_track: Annotated[str, typer.Option("--track")] = "pull-request",
    database: Annotated[Path | None, typer.Option("--database", dir_okay=False)] = None,
    idempotency_key: Annotated[str | None, typer.Option("--idempotency-key")] = None,
) -> None:
    """Preview a DRAFT or persist it under registered project/track authority."""
    try:
        command = CandidateCreateCommand(
            project_id=project_id,
            version=version,
            commit_sha=commit,
            source_branch=source_branch,
            release_track=release_track,
            created_at=datetime.fromisoformat(created_at.replace("Z", "+00:00")),
        )
        candidate: CandidateDocument = CandidateApplication.preview_candidate(command)
        if database is None and idempotency_key is not None:
            raise ValueError("--idempotency-key requires --database")
        if database is not None:
            if idempotency_key is None:
                raise ValueError("--database requires --idempotency-key")
            candidate = CandidateApplication.for_database(database).create_candidate(
                command,
                idempotency_key=idempotency_key,
            )
    except (CandidateLifecycleError, CandidateStoreError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(candidate.model_dump_json(indent=2))


@candidate_app.command("list")
def candidate_list(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    project_id: Annotated[str, typer.Option("--project")],
    after_candidate_id: Annotated[str | None, typer.Option("--after-candidate")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 100,
) -> None:
    """List a bounded page of current candidates for one registered project."""
    try:
        page = CandidateApplication.for_database(database).list_candidates(
            CandidateQuery(
                project_id=project_id,
                after_candidate_id=after_candidate_id,
                limit=limit,
            )
        )
    except (CandidateStoreError, ValidationError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(page.model_dump_json(indent=2))


@candidate_app.command("init-store")
def candidate_init_store(
    database: Annotated[Path, typer.Argument(dir_okay=False)],
) -> None:
    """Initialize or validate a local SQLite WAL candidate store at schema v6."""
    try:
        repository = SQLiteCandidateRepository(database)
        repository.initialize()
    except (CandidateStoreError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(f"INITIALIZED {repository.database_path}")


@candidate_app.command("migrate-store")
def candidate_migrate_store(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Explicitly migrate a validated candidate store from schema v1-v5 to v6."""
    try:
        repository = SQLiteCandidateRepository(database)
        repository.migrate()
    except CandidateStoreError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(f"MIGRATED {repository.database_path}")


@candidate_app.command("transition")
def candidate_transition(
    candidate_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    to_status: Annotated[CandidateStatus, typer.Option("--to")],
    occurred_at: Annotated[str, typer.Option("--occurred-at")],
    reason: Annotated[str | None, typer.Option("--reason")] = None,
    evaluation_path: Annotated[
        Path | None,
        typer.Option("--evaluation", exists=True, dir_okay=False, readable=True),
    ] = None,
) -> None:
    """Preview one legal transition and emit the next candidate plus audit event."""
    try:
        candidate = load_config(candidate_path)
        if not isinstance(candidate, (ReleaseCandidate, ProfileBoundReleaseCandidate)):
            raise ValueError("candidate path must contain a ForgeGate release candidate")
        evaluation = _load_policy_evaluation(evaluation_path)
        result = transition_candidate(
            candidate,
            to_status,
            occurred_at=datetime.fromisoformat(occurred_at.replace("Z", "+00:00")),
            reason=reason,
            evaluation=evaluation,
        )
    except (CandidateLifecycleError, ConfigLoadError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(result.model_dump_json(indent=2))


@candidate_app.command("advance")
def candidate_advance(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
    to_status: Annotated[CandidateStatus, typer.Option("--to")],
    expected_revision: Annotated[int, typer.Option("--expected-revision")],
    occurred_at: Annotated[str, typer.Option("--occurred-at")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    reason: Annotated[str | None, typer.Option("--reason")] = None,
    evaluation_path: Annotated[
        Path | None,
        typer.Option("--evaluation", exists=True, dir_okay=False, readable=True),
    ] = None,
) -> None:
    """Atomically append one persisted transition at an expected revision."""
    try:
        evaluation = _load_policy_evaluation(evaluation_path)
        result = CandidateApplication.for_database(database).advance_candidate(
            candidate_id,
            CandidateAdvanceCommand(
                to_status=to_status,
                expected_revision=expected_revision,
                occurred_at=datetime.fromisoformat(occurred_at.replace("Z", "+00:00")),
                reason=reason,
            ),
            idempotency_key=idempotency_key,
            evaluation=evaluation,
        )
    except (
        CandidateLifecycleError,
        CandidateStoreError,
        ConfigLoadError,
        ValidationError,
        ValueError,
    ) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(result.model_dump_json(indent=2))


@candidate_app.command("show")
def candidate_show(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
) -> None:
    """Read and validate the current persisted candidate plus its audit chain."""
    try:
        candidate = CandidateApplication.for_database(database).get_candidate(candidate_id)
    except CandidateStoreError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(candidate.model_dump_json(indent=2))


@candidate_app.command("history")
def candidate_history(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
) -> None:
    """Read the current candidate and its ordered append-only transition events."""
    try:
        history = CandidateApplication.for_database(database).get_history(candidate_id)
    except CandidateStoreError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    payload = {
        **history.model_dump(mode="json"),
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@candidate_app.command("bind-evidence")
def candidate_bind_evidence(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
    assembly_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    bound_at: Annotated[str, typer.Option("--bound-at")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
) -> None:
    """Bind one validated assembly to a persisted COLLECTING candidate."""
    try:
        assembly = _load_evidence_assembly(assembly_path)
        binding = CandidateApplication.for_database(database).bind_evidence(
            candidate_id,
            CandidateBindEvidenceCommand(
                assembly=assembly,
                bound_at=datetime.fromisoformat(bound_at.replace("Z", "+00:00")),
            ),
            idempotency_key=idempotency_key,
        )
    except (CandidateStoreError, ConfigLoadError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(binding.model_dump_json(indent=2))


@candidate_app.command("show-evidence")
def candidate_show_evidence(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
) -> None:
    """Read and validate a candidate's durable evidence binding."""
    try:
        binding = CandidateApplication.for_database(database).get_evidence(candidate_id)
    except CandidateStoreError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(binding.model_dump_json(indent=2))


@candidate_app.command("import-evaluation")
def candidate_import_evaluation(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
    evaluation_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Backfill the exact evaluation document for a migrated terminal candidate."""
    try:
        evaluation = _load_policy_evaluation(evaluation_path)
        assert evaluation is not None
        stored = SQLiteCandidateRepository(database).record_evaluation(candidate_id, evaluation)
    except (CandidateStoreError, ConfigLoadError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(stored.model_dump_json(indent=2))


@candidate_app.command("attest")
def candidate_attest(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
    issued_at: Annotated[str, typer.Option("--issued-at")],
    output_root: Annotated[Path, typer.Option("--output-root", file_okay=False)],
) -> None:
    """Persist and atomically publish deterministic JSON/Markdown attestation files."""
    try:
        attestation = CandidateApplication.for_database(database).attest_candidate(
            candidate_id,
            CandidateAttestCommand(
                issued_at=datetime.fromisoformat(issued_at.replace("Z", "+00:00")),
            ),
        )
        published = publish_attestation_bundle(attestation, output_root)
    except (
        AttestationPublishError,
        CandidateStoreError,
        ValidationError,
        ValueError,
    ) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    payload = {
        "attestation": attestation.model_dump(mode="json"),
        "bundle_directory": str(published.directory),
        "json_path": str(published.json_path),
        "markdown_path": str(published.markdown_path),
        "output_replayed": published.replayed,
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@candidate_app.command("show-attestation")
def candidate_show_attestation(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
) -> None:
    """Read and validate the durable self-contained release attestation."""
    try:
        attestation = CandidateApplication.for_database(database).get_attestation(candidate_id)
    except CandidateStoreError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(attestation.model_dump_json(indent=2))


def _load_policy_evaluation(path: Path | None) -> PolicyEvaluation | None:
    if path is None:
        return None
    evaluation = load_config(path)
    if not isinstance(evaluation, PolicyEvaluation):
        raise ValueError("evaluation path must contain forgegate.policy-evaluation.v1")
    return evaluation


def _load_evidence_assembly(path: Path) -> EvidenceBundleAssembly:
    assembly = load_config(path)
    if not isinstance(assembly, EvidenceBundleAssembly):
        raise ValueError("assembly path must contain forgegate.evidence-bundle-assembly.v1")
    return assembly


@app.command("evaluate-policy")
def evaluate_policy_command(
    policy_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    evidence_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    evaluated_at: Annotated[str, typer.Option("--evaluated-at")],
) -> None:
    """Evaluate a policy against an evidence bundle at an explicit timestamp."""
    try:
        policy = load_config(policy_path)
        evidence_document = load_config(evidence_path)
        if not isinstance(policy, PolicyConfig):
            raise ValueError("policy path must contain forgegate.policy.v1")
        if isinstance(evidence_document, EvidenceBundleAssembly):
            bundle = evidence_document.bundle
        elif isinstance(evidence_document, EvidenceBundle):
            bundle = evidence_document
        else:
            raise ValueError(
                "evidence path must contain forgegate.evidence-bundle.v1 or "
                "forgegate.evidence-bundle-assembly.v1"
            )
        timestamp = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00"))
        result = evaluate_policy(policy, bundle, evaluated_at=timestamp)
    except (ConfigLoadError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc

    typer.echo(result.model_dump_json(indent=2))
    exit_codes = {
        Decision.PASS: 0,
        Decision.FAIL: 1,
        Decision.REVIEW: 2,
        Decision.ERROR: 3,
    }
    if result.decision is not Decision.PASS:
        raise typer.Exit(code=exit_codes[result.decision])


@app.command("assemble-evidence")
def assemble_evidence(
    collection_paths: Annotated[
        list[str], typer.Argument(help="Collection-result JSON paths relative to --root")
    ],
    commit: Annotated[str, typer.Option("--commit")],
    generated_at: Annotated[str, typer.Option("--generated-at")],
    root: Annotated[Path, typer.Option("--root", file_okay=False, resolve_path=True)] = Path("."),
    producer: Annotated[str, typer.Option("--producer")] = "forgegate",
    producer_version: Annotated[str, typer.Option("--producer-version")] = __version__,
    retain_warnings: Annotated[bool, typer.Option("--retain-warnings")] = False,
) -> None:
    """Assemble audited collection results into one candidate-bound evidence bundle."""
    try:
        registry = ArtifactRegistry(root)
        loader = CollectionResultLoader(registry)
        loaded = [loader.load(path) for path in collection_paths]
        assembly = assemble_evidence_bundle(
            loaded,
            candidate_commit=commit,
            generated_at=datetime.fromisoformat(generated_at.replace("Z", "+00:00")),
            producer=producer,
            producer_version=producer_version,
            retain_warnings=retain_warnings,
        )
    except (
        ArtifactError,
        CollectionResultLoadError,
        EvidenceAssemblyError,
        ValidationError,
        ValueError,
    ) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(assembly.model_dump_json(indent=2))


@app.command("collect-junit")
def collect_junit(
    source_path: Annotated[str, typer.Argument(help="Artifact path relative to --root")],
    commit: Annotated[str, typer.Option("--commit")],
    collected_at: Annotated[str, typer.Option("--collected-at")],
    root: Annotated[Path, typer.Option("--root", file_okay=False, resolve_path=True)] = Path("."),
    source_tool: Annotated[str, typer.Option("--source-tool")] = "junit",
    source_version: Annotated[str, typer.Option("--source-version")] = "unknown",
    trust: Annotated[EvidenceTrust, typer.Option("--trust")] = EvidenceTrust.UNSIGNED_LOCAL,
    verification_level: Annotated[
        VerificationLevel, typer.Option("--verification-level")
    ] = VerificationLevel.DECLARED,
) -> None:
    """Collect one JUnit artifact into normalized evidence without policy evaluation."""
    try:
        registry = ArtifactRegistry(root)
        request = JUnitCollectionRequest(
            source_path=source_path,
            source_tool=source_tool,
            source_version=source_version,
            execution_context=ExecutionContext(commit_sha=commit),
            collected_at=datetime.fromisoformat(collected_at.replace("Z", "+00:00")),
            trust=trust,
            verification_level=verification_level,
        )
    except (ArtifactBoundaryError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc

    result = JUnitCollector(registry).collect(request)
    typer.echo(result.model_dump_json(indent=2))
    if result.status is CollectionStatus.REJECTED:
        raise typer.Exit(code=3)


@app.command("collect-coverage-xml")
def collect_coverage_xml(
    source_path: Annotated[str, typer.Argument(help="Artifact path relative to --root")],
    commit: Annotated[str, typer.Option("--commit")],
    collected_at: Annotated[str, typer.Option("--collected-at")],
    root: Annotated[Path, typer.Option("--root", file_okay=False, resolve_path=True)] = Path("."),
    source_tool: Annotated[str, typer.Option("--source-tool")] = "coverage.py",
    source_version: Annotated[str, typer.Option("--source-version")] = "unknown",
    trust: Annotated[EvidenceTrust, typer.Option("--trust")] = EvidenceTrust.UNSIGNED_LOCAL,
    verification_level: Annotated[
        VerificationLevel, typer.Option("--verification-level")
    ] = VerificationLevel.DECLARED,
) -> None:
    """Collect Cobertura/coverage.py XML into normalized coverage evidence."""
    registry, request = _coverage_inputs(
        source_path=source_path,
        commit=commit,
        collected_at=collected_at,
        root=root,
        source_tool=source_tool,
        source_version=source_version,
        trust=trust,
        verification_level=verification_level,
    )
    _emit_collection(CoverageXmlCollector(registry).collect(request))


@app.command("collect-lcov")
def collect_lcov(
    source_path: Annotated[str, typer.Argument(help="Artifact path relative to --root")],
    commit: Annotated[str, typer.Option("--commit")],
    collected_at: Annotated[str, typer.Option("--collected-at")],
    root: Annotated[Path, typer.Option("--root", file_okay=False, resolve_path=True)] = Path("."),
    source_tool: Annotated[str, typer.Option("--source-tool")] = "lcov",
    source_version: Annotated[str, typer.Option("--source-version")] = "unknown",
    trust: Annotated[EvidenceTrust, typer.Option("--trust")] = EvidenceTrust.UNSIGNED_LOCAL,
    verification_level: Annotated[
        VerificationLevel, typer.Option("--verification-level")
    ] = VerificationLevel.DECLARED,
) -> None:
    """Collect LCOV text into normalized coverage evidence."""
    registry, request = _coverage_inputs(
        source_path=source_path,
        commit=commit,
        collected_at=collected_at,
        root=root,
        source_tool=source_tool,
        source_version=source_version,
        trust=trust,
        verification_level=verification_level,
    )
    _emit_collection(LcovCollector(registry).collect(request))


@app.command("collect-sarif")
def collect_sarif(
    source_path: Annotated[str, typer.Argument(help="Artifact path relative to --root")],
    commit: Annotated[str, typer.Option("--commit")],
    collected_at: Annotated[str, typer.Option("--collected-at")],
    root: Annotated[Path, typer.Option("--root", file_okay=False, resolve_path=True)] = Path("."),
    trust: Annotated[EvidenceTrust, typer.Option("--trust")] = EvidenceTrust.UNSIGNED_LOCAL,
    verification_level: Annotated[
        VerificationLevel, typer.Option("--verification-level")
    ] = VerificationLevel.DECLARED,
) -> None:
    """Collect SARIF 2.1.0 into normalized summary and finding evidence."""
    try:
        registry = ArtifactRegistry(root)
        request = SarifCollectionRequest(
            source_path=source_path,
            execution_context=ExecutionContext(commit_sha=commit),
            collected_at=datetime.fromisoformat(collected_at.replace("Z", "+00:00")),
            trust=trust,
            verification_level=verification_level,
        )
    except (ArtifactBoundaryError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    _emit_collection(SarifCollector(registry).collect(request))


@app.command("collect-benchmark")
def collect_benchmark(
    source_path: Annotated[str, typer.Argument(help="Artifact path relative to --root")],
    commit: Annotated[str, typer.Option("--commit")],
    collected_at: Annotated[str, typer.Option("--collected-at")],
    root: Annotated[Path, typer.Option("--root", file_okay=False, resolve_path=True)] = Path("."),
    trust: Annotated[EvidenceTrust, typer.Option("--trust")] = EvidenceTrust.UNSIGNED_LOCAL,
    verification_level: Annotated[
        VerificationLevel, typer.Option("--verification-level")
    ] = VerificationLevel.DECLARED,
) -> None:
    """Collect forgegate.benchmark.v1 JSON into normalized metric evidence."""
    try:
        registry = ArtifactRegistry(root)
        request = BenchmarkCollectionRequest(
            source_path=source_path,
            execution_context=ExecutionContext(commit_sha=commit),
            collected_at=datetime.fromisoformat(collected_at.replace("Z", "+00:00")),
            trust=trust,
            verification_level=verification_level,
        )
    except (ArtifactBoundaryError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    _emit_collection(BenchmarkJsonCollector(registry).collect(request))


@app.command("collect-analog-validation")
def collect_analog_validation(
    source_path: Annotated[str, typer.Argument(help="Artifact path relative to --root")],
    commit: Annotated[str, typer.Option("--commit")],
    collected_at: Annotated[str, typer.Option("--collected-at")],
    root: Annotated[Path, typer.Option("--root", file_okay=False, resolve_path=True)] = Path("."),
    trust: Annotated[EvidenceTrust, typer.Option("--trust")] = EvidenceTrust.UNSIGNED_LOCAL,
    scope: Annotated[str, typer.Option("--scope")] = "analog-validation",
) -> None:
    """Collect Analog Validation Studio result-export.v1 without evidence promotion."""
    try:
        registry = ArtifactRegistry(root)
        request = AnalogValidationCollectionRequest(
            source_path=source_path,
            execution_context=ExecutionContext(commit_sha=commit),
            collected_at=datetime.fromisoformat(collected_at.replace("Z", "+00:00")),
            trust=trust,
            scope=scope,
        )
    except (ArtifactBoundaryError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    _emit_collection(AnalogValidationResultCollector(registry).collect(request))


def _coverage_inputs(
    *,
    source_path: str,
    commit: str,
    collected_at: str,
    root: Path,
    source_tool: str,
    source_version: str,
    trust: EvidenceTrust,
    verification_level: VerificationLevel,
) -> tuple[ArtifactRegistry, CoverageCollectionRequest]:
    try:
        registry = ArtifactRegistry(root)
        request = CoverageCollectionRequest(
            source_path=source_path,
            source_tool=source_tool,
            source_version=source_version,
            execution_context=ExecutionContext(commit_sha=commit),
            collected_at=datetime.fromisoformat(collected_at.replace("Z", "+00:00")),
            trust=trust,
            verification_level=verification_level,
        )
    except (ArtifactBoundaryError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    return registry, request


def _emit_collection(result: CollectionResult) -> None:
    typer.echo(result.model_dump_json(indent=2))
    if result.status is CollectionStatus.REJECTED:
        raise typer.Exit(code=3)
