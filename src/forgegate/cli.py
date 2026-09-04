import json
import os
import platform
from datetime import datetime, timedelta
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
    CandidateEvaluateCommand,
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
from forgegate.assurance import (
    AssuranceBundleError,
    publish_assurance_bundle,
    verify_assurance_bundle,
)
from forgegate.attestations import AttestationPublishError, publish_attestation_bundle
from forgegate.bootstrap import InitializationError, initialize_project
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
from forgegate.github_actions import (
    GitHubActionGateError,
    append_github_file,
    create_github_action_report,
    github_action_exit_code,
    render_github_error_outputs,
    render_github_error_summary,
    render_github_outputs,
    render_github_step_summary,
)
from forgegate.identity import (
    AssuranceSignature,
    IdentityError,
    IdentityRole,
    IdentityStatus,
    SigningIdentity,
    TrustedIdentity,
    TrustStore,
    create_assurance_signature,
    create_trust_store,
    derive_signing_identity,
    load_ed25519_private_key,
    load_identity_document,
    publish_assurance_signature,
    verify_assurance_signature,
)
from forgegate.network import validated_loopback_host
from forgegate.plugins import (
    PluginDiscoveryError,
    PluginPermission,
    PluginRunState,
    PluginRunStoreError,
    PluginWorkflowError,
    collect_plugin_evidence,
    discover_plugins,
    execute_operator_plugin_run,
    list_plugin_runs,
    probe_windows_podman_sandbox,
    read_plugin_run,
)
from forgegate.policy import PolicyMaterial, evaluate_policy
from forgegate.policy.models import (
    PolicyEvaluation,
    PolicyEvaluationDocument,
    ProfileAuthorizedPolicyEvaluation,
)
from forgegate.schema_registry import ARTIFACT_SCHEMAS, SCHEMAS, schema_filename

app = typer.Typer(
    name="forgegate",
    help="ForgeGate evidence collection and release-assurance tools.",
    no_args_is_help=True,
)
candidate_app = typer.Typer(help="Create and advance immutable release candidates.")
project_app = typer.Typer(help="Register and inspect immutable project profiles.")
audit_app = typer.Typer(help="Query durable append-only audit events.")
identity_app = typer.Typer(help="Derive public identities and author local trust stores.")
plugins_app = typer.Typer(help="Inspect installed plugin metadata without importing plugin code.")
app.add_typer(candidate_app, name="candidate")
app.add_typer(project_app, name="project")
app.add_typer(audit_app, name="audit")
app.add_typer(identity_app, name="identity")
app.add_typer(plugins_app, name="plugins")


@app.command()
def doctor() -> None:
    """Report the local contract-tooling environment."""
    report = {
        "forgegate_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "supported_schemas": sorted(SCHEMAS),
        "supported_artifact_schemas": sorted(ARTIFACT_SCHEMAS),
        "phase": "phase22-windows-alpha",
    }
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


@app.command("init")
def init_project(
    target: Annotated[Path, typer.Argument(file_okay=False)] = Path("."),
    project_id: Annotated[str, typer.Option("--project-id")] = "sample-project",
    project_name: Annotated[str, typer.Option("--project-name")] = "Sample Project",
    repository: Annotated[str | None, typer.Option("--repository")] = None,
    default_branch: Annotated[str, typer.Option("--default-branch")] = "main",
) -> None:
    """Create a strict generic project template without overwriting existing files."""
    try:
        report = initialize_project(
            target,
            project_id=project_id,
            project_name=project_name,
            repository=repository,
            default_branch=default_branch,
        )
    except (InitializationError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(report.model_dump_json(indent=2))


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


@app.command("verify-assurance")
def verify_assurance(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
) -> None:
    """Verify a portable assurance directory without a database or project tree."""
    try:
        verified = verify_assurance_bundle(directory)
    except AssuranceBundleError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    payload = {
        "status": "VALID",
        "bundle_id": verified.bundle.bundle_id,
        "candidate_id": verified.bundle.attestation.candidate.candidate_id,
        "decision": verified.bundle.attestation.candidate.status.value,
        "assurance": verified.bundle.assurance,
        "source_artifact_bytes": verified.bundle.source_artifact_bytes,
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@app.command("github-gate")
def github_gate(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    expected_commit: Annotated[str, typer.Option("--expected-commit")],
    github_output: Annotated[Path | None, typer.Option("--github-output")] = None,
    step_summary: Annotated[Path | None, typer.Option("--step-summary")] = None,
) -> None:
    """Verify an assurance bundle, bind its commit, and drive a GitHub Actions gate."""
    output_path = github_output or _path_from_environment("GITHUB_OUTPUT")
    summary_path = step_summary or _path_from_environment("GITHUB_STEP_SUMMARY")
    try:
        verified = verify_assurance_bundle(directory)
        report = create_github_action_report(verified, expected_commit=expected_commit)
        if summary_path is not None:
            append_github_file(summary_path, render_github_step_summary(report, verified.bundle))
        if output_path is not None:
            append_github_file(output_path, render_github_outputs(report))
    except (AssuranceBundleError, GitHubActionGateError) as exc:
        code = exc.code
        try:
            if summary_path is not None:
                append_github_file(summary_path, render_github_error_summary(code))
            if output_path is not None:
                append_github_file(output_path, render_github_error_outputs())
        except GitHubActionGateError as output_exc:
            typer.echo(
                f"ERROR: {exc}; additionally failed to write GitHub files: {output_exc}",
                err=True,
            )
            raise typer.Exit(code=3) from output_exc
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(report.model_dump_json(indent=2))
    exit_code = github_action_exit_code(report.decision)
    if exit_code:
        raise typer.Exit(code=exit_code)


def _path_from_environment(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


@plugins_app.command("list")
def plugins_list() -> None:
    """List plugin compatibility from bounded manifests without loading code."""
    try:
        report = discover_plugins()
    except (PluginDiscoveryError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(report.model_dump_json(indent=2))


@plugins_app.command("sandbox-status")
def plugins_sandbox_status() -> None:
    """Probe Windows Podman/WSL2 readiness without executing plugin code."""
    report = probe_windows_podman_sandbox()
    typer.echo(report.model_dump_json(indent=2))


@plugins_app.command("run")
def plugins_run(
    plugin_id: Annotated[str, typer.Argument()],
    input_specs: Annotated[
        list[str],
        typer.Option("--input", help="Repeat PATH=MEDIA_TYPE; PATH is relative to --root."),
    ],
    grants: Annotated[list[PluginPermission], typer.Option("--grant")],
    sandbox_evidence: Annotated[
        Path, typer.Option("--sandbox-evidence", exists=True, dir_okay=False, readable=True)
    ],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    planned_at: Annotated[str, typer.Option("--planned-at")],
    database: Annotated[Path, typer.Option("--database")] = Path(".forgegate/plugin-runs.db"),
    root: Annotated[Path, typer.Option("--root", file_okay=False)] = Path("."),
    work_root: Annotated[Path, typer.Option("--work-root", file_okay=False)] = Path(
        ".forgegate/plugin-work"
    ),
    accepted_output_root: Annotated[
        Path, typer.Option("--accepted-output-root", file_okay=False)
    ] = Path(".forgegate/plugin-output"),
    input_schema: Annotated[str | None, typer.Option("--input-schema")] = None,
    podman: Annotated[Path | None, typer.Option("--podman", dir_okay=False)] = None,
) -> None:
    """Run one compatible collector through the verified Windows broker."""
    try:
        inputs = _parse_plugin_input_specs(input_specs)
        receipt = execute_operator_plugin_run(
            plugin_id=plugin_id,
            input_schema=input_schema,
            input_media_types=inputs,
            approved_permissions=tuple(grants),
            artifact_root=root,
            database_path=database,
            work_root=work_root,
            accepted_output_root=accepted_output_root,
            sandbox_evidence_path=sandbox_evidence,
            idempotency_key=idempotency_key,
            planned_at=datetime.fromisoformat(planned_at.replace("Z", "+00:00")),
            podman_executable=podman,
        )
    except (PluginWorkflowError, PluginRunStoreError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(receipt.model_dump_json(indent=2))
    if receipt.result.status is not PluginRunState.SUCCEEDED:
        raise typer.Exit(code=3)


@plugins_app.command("show")
def plugins_show(
    database: Annotated[Path, typer.Argument()],
    run_plan_id: Annotated[str, typer.Argument()],
) -> None:
    """Read one path-free durable plugin run and its receipt."""
    try:
        record = read_plugin_run(database, run_plan_id)
    except (PluginRunStoreError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(record.model_dump_json(indent=2))


@plugins_app.command("runs")
def plugins_runs(
    database: Annotated[Path, typer.Argument()],
    after: Annotated[str | None, typer.Option("--after")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 100,
) -> None:
    """List a bounded path-free page from the separate plugin-run store."""
    try:
        page = list_plugin_runs(database, after_run_plan_id=after, limit=limit)
    except (PluginRunStoreError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(page.model_dump_json(indent=2))


@plugins_app.command("collect")
def plugins_collect(
    database: Annotated[Path, typer.Argument()],
    run_plan_id: Annotated[str, typer.Argument()],
    root: Annotated[Path, typer.Option("--root", file_okay=False)] = Path("."),
    accepted_output_root: Annotated[
        Path, typer.Option("--accepted-output-root", file_okay=False)
    ] = Path(".forgegate/plugin-output"),
) -> None:
    """Project a successful broker receipt into the audited collection boundary."""
    try:
        result = collect_plugin_evidence(
            database,
            run_plan_id,
            artifact_root=root,
            accepted_output_root=accepted_output_root,
        )
    except (
        ArtifactError,
        PluginWorkflowError,
        PluginRunStoreError,
        ValidationError,
        ValueError,
    ) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    _emit_collection(result)


def _parse_plugin_input_specs(values: list[str]) -> dict[str, str]:
    if not values:
        raise ValueError("at least one --input PATH=MEDIA_TYPE is required")
    parsed: dict[str, str] = {}
    for value in values:
        path, separator, media_type = value.partition("=")
        if not separator or not path.strip() or not media_type.strip():
            raise ValueError("each --input must use PATH=MEDIA_TYPE")
        if path in parsed:
            raise ValueError("plugin input paths must be unique")
        parsed[path] = media_type
    return parsed


@identity_app.command("derive")
def identity_derive(
    private_key_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    display_name: Annotated[str, typer.Option("--display-name", min=1, max=120)],
) -> None:
    """Derive a public ForgeGate identity from an existing Ed25519 private key."""
    try:
        private_key = load_ed25519_private_key(private_key_path)
        identity = derive_signing_identity(private_key, display_name=display_name)
    except (IdentityError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(identity.model_dump_json(indent=2))


@identity_app.command("trust")
def identity_trust(
    identity_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    roles: Annotated[list[IdentityRole], typer.Option("--role")],
    projects: Annotated[list[str], typer.Option("--project")],
    status: Annotated[IdentityStatus, typer.Option("--status")] = IdentityStatus.ACTIVE,
) -> None:
    """Create a one-identity trust store for explicit roles and projects."""
    try:
        identity = load_identity_document(identity_path)
        if not isinstance(identity, SigningIdentity):
            raise ValueError("identity path must contain forgegate.signing-identity.v1")
        trusted = TrustedIdentity(
            identity=identity,
            roles=tuple(sorted(set(roles), key=lambda item: item.value)),
            project_ids=tuple(sorted(set(projects))),
            status=status,
        )
        trust_store = create_trust_store((trusted,))
    except (IdentityError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(trust_store.model_dump_json(indent=2))


@identity_app.command("sign-api-challenge")
def identity_sign_api_challenge(
    challenge_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    identity_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    private_key_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Sign one short-lived API challenge without exposing the private key to the server."""
    from forgegate.api import ApiAuthenticationError, load_api_challenge, sign_api_challenge

    try:
        challenge = load_api_challenge(challenge_path)
        identity = load_identity_document(identity_path)
        if not isinstance(identity, SigningIdentity):
            raise ValueError("identity path must contain forgegate.signing-identity.v1")
        request = sign_api_challenge(
            challenge,
            identity=identity,
            private_key=load_ed25519_private_key(private_key_path),
        )
    except (ApiAuthenticationError, IdentityError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(request.model_dump_json(indent=2))


@app.command("sign-assurance")
def sign_assurance(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    identity_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    private_key_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    role: Annotated[IdentityRole, typer.Option("--role")],
    signed_at: Annotated[str, typer.Option("--signed-at")],
    output_root: Annotated[Path, typer.Option("--output-root", file_okay=False)],
) -> None:
    """Sign one verified portable assurance bundle with an Ed25519 identity."""
    try:
        verified = verify_assurance_bundle(directory)
        identity = load_identity_document(identity_path)
        if not isinstance(identity, SigningIdentity):
            raise ValueError("identity path must contain forgegate.signing-identity.v1")
        signature = create_assurance_signature(
            verified.bundle,
            signer=identity,
            role=role,
            signed_at=datetime.fromisoformat(signed_at.replace("Z", "+00:00")),
            private_key=load_ed25519_private_key(private_key_path),
        )
        published = publish_assurance_signature(signature, output_root)
    except (AssuranceBundleError, IdentityError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    payload = {
        "signature": signature.model_dump(mode="json"),
        "signature_path": str(published.path),
        "output_replayed": published.replayed,
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@app.command("verify-assurance-signature")
def verify_assurance_signature_command(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    signature_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    trust_store_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Verify a bundle signature against an external local trust store."""
    try:
        bundle = verify_assurance_bundle(directory).bundle
        signature = load_identity_document(signature_path)
        trust_store = load_identity_document(trust_store_path)
        if not isinstance(signature, AssuranceSignature):
            raise ValueError("signature path must contain forgegate.assurance-signature.v1")
        if not isinstance(trust_store, TrustStore):
            raise ValueError("trust path must contain forgegate.trust-store.v1")
        authenticated = verify_assurance_signature(bundle, signature, trust_store)
    except (AssuranceBundleError, IdentityError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    payload = {
        "status": "AUTHENTICATED",
        "bundle_id": authenticated.bundle_id,
        "candidate_id": authenticated.candidate_id,
        "project_id": authenticated.project_id,
        "identity_id": authenticated.identity_id,
        "display_name": authenticated.display_name,
        "role": authenticated.role.value,
        "trust_store_id": authenticated.trust_store_id,
        "trusted_time": "not_established",
        "source_artifact_authentication": "not_established",
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


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
            create_api_app(Path("forgegate-openapi-contract.db"), contract_only=True).openapi(),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    output_file.write_bytes(payload.encode("utf-8"))
    typer.echo(str(output_file))


@app.command("export-dashboard-openapi")
def export_dashboard_openapi(
    output_file: Annotated[Path, typer.Argument(dir_okay=False)],
) -> None:
    """Export the deterministic build-time Dashboard BFF OpenAPI contract."""
    from forgegate.dashboard.openapi import create_dashboard_openapi

    if not output_file.parent.is_dir():
        typer.echo(f"ERROR: output parent does not exist: {output_file.parent}", err=True)
        raise typer.Exit(code=3)
    payload = json.dumps(create_dashboard_openapi(), indent=2, sort_keys=True) + "\n"
    output_file.write_bytes(payload.encode("utf-8"))
    typer.echo(str(output_file))


@app.command("serve")
def serve(
    database: Annotated[Path, typer.Option("--database", dir_okay=False)],
    trust_store_path: Annotated[
        Path,
        typer.Option("--trust-store", exists=True, dir_okay=False, readable=True),
    ],
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8000,
    session_ttl_seconds: Annotated[
        int,
        typer.Option("--session-ttl-seconds", min=60, max=3600),
    ] = 900,
) -> None:
    """Serve the authenticated REST API on an explicitly loopback-only address."""
    import uvicorn

    from forgegate.api import ApiAuthenticator, create_api_app

    try:
        bind_host = validated_loopback_host(host)
        runtime_trust_store_path = trust_store_path.expanduser().absolute()

        def load_runtime_trust_store() -> TrustStore:
            document = load_identity_document(runtime_trust_store_path)
            if not isinstance(document, TrustStore):
                raise ValueError("--trust-store must contain forgegate.trust-store.v1")
            return document

        trust_store = load_runtime_trust_store()
        authenticator = ApiAuthenticator(
            trust_store,
            session_ttl=timedelta(seconds=session_ttl_seconds),
            trust_store_loader=load_runtime_trust_store,
        )
        application = CandidateApplication.for_database(database)
        application.initialize()
    except (CandidateStoreError, IdentityError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    uvicorn.run(
        create_api_app(
            database,
            application=application,
            authenticator=authenticator,
        ),
        host=bind_host,
        port=port,
        log_level="info",
    )


@app.command("dashboard")
def dashboard(
    database: Annotated[Path, typer.Option("--database", dir_okay=False)],
    trust_store_path: Annotated[
        Path,
        typer.Option("--trust-store", exists=True, dir_okay=False, readable=True),
    ],
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8000,
    session_ttl_seconds: Annotated[
        int,
        typer.Option("--session-ttl-seconds", min=60, max=3600),
    ] = 900,
) -> None:
    """Serve the authenticated local Dashboard and established REST API."""
    import uvicorn

    from forgegate.api import ApiAuthenticator, create_api_app

    try:
        bind_host = validated_loopback_host(host)
        runtime_trust_store_path = trust_store_path.expanduser().absolute()

        def load_runtime_trust_store() -> TrustStore:
            document = load_identity_document(runtime_trust_store_path)
            if not isinstance(document, TrustStore):
                raise ValueError("--trust-store must contain forgegate.trust-store.v1")
            return document

        trust_store = load_runtime_trust_store()
        authenticator = ApiAuthenticator(
            trust_store,
            session_ttl=timedelta(seconds=session_ttl_seconds),
            trust_store_loader=load_runtime_trust_store,
        )
        application = CandidateApplication.for_database(database)
        application.initialize()
        local_url = f"http://{bind_host}:{port}/app/"
        dashboard_app = create_api_app(
            database,
            application=application,
            authenticator=authenticator,
            dashboard=True,
        )
    except (CandidateStoreError, IdentityError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(f"ForgeGate Dashboard: {local_url}")
    typer.echo("Close this process explicitly to stop the local service.")
    uvicorn.run(
        dashboard_app,
        host=bind_host,
        port=port,
        log_level="info",
    )


@app.command("dashboard-activate")
def dashboard_activate(
    activation_code: Annotated[str, typer.Argument()],
    identity_path: Annotated[
        Path,
        typer.Option("--identity", exists=True, dir_okay=False, readable=True),
    ],
    private_key_path: Annotated[
        Path,
        typer.Option("--private-key", exists=True, dir_okay=False, readable=True),
    ],
    role: Annotated[IdentityRole, typer.Option("--role")],
    projects: Annotated[list[str], typer.Option("--project")],
    server: Annotated[str, typer.Option("--server")] = "http://127.0.0.1:8000",
) -> None:
    """Approve one browser-bound Dashboard session without exposing the private key."""
    from forgegate.dashboard.client import DashboardClientError, activate_dashboard

    try:
        identity = load_identity_document(identity_path)
        if not isinstance(identity, SigningIdentity):
            raise ValueError("--identity must contain forgegate.signing-identity.v1")
        completed = activate_dashboard(
            server,
            activation_code,
            identity=identity,
            private_key=load_ed25519_private_key(private_key_path),
            role=role,
            project_ids=tuple(projects),
        )
    except (DashboardClientError, IdentityError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(completed.model_dump_json(indent=2))


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
    """Initialize or validate a local SQLite WAL candidate store at schema v8."""
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
    """Explicitly migrate a validated candidate store from schema v1-v7 to v8."""
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


@candidate_app.command("materialize-policy")
def candidate_materialize_policy(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
    project_root: Annotated[
        Path,
        typer.Option("--project-root", exists=True, file_okay=False, readable=True),
    ],
) -> None:
    """Resolve exact policy bytes through the candidate's frozen project profile."""
    try:
        material = CandidateApplication.for_database(database).materialize_policy(
            candidate_id,
            project_root,
        )
    except (
        ArtifactError,
        CandidateLifecycleError,
        CandidateStoreError,
        ValidationError,
        ValueError,
    ) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(material.model_dump_json(indent=2))


@candidate_app.command("evaluate")
def candidate_evaluate(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
    policy_material_path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    expected_revision: Annotated[int, typer.Option("--expected-revision", min=0)],
    evaluated_at: Annotated[str, typer.Option("--evaluated-at")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    reason: Annotated[str | None, typer.Option("--reason")] = None,
) -> None:
    """Evaluate retained profile-authorized policy material and advance atomically."""
    try:
        material = load_config(policy_material_path)
        if not isinstance(material, PolicyMaterial):
            raise ValueError("policy material path must contain forgegate.policy-material.v1")
        result = CandidateApplication.for_database(database).evaluate_candidate(
            candidate_id,
            CandidateEvaluateCommand(
                policy_material=material,
                expected_revision=expected_revision,
                evaluated_at=datetime.fromisoformat(evaluated_at.replace("Z", "+00:00")),
                reason=reason,
            ),
            idempotency_key=idempotency_key,
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


@candidate_app.command("show-policy")
def candidate_show_policy(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
) -> None:
    """Read and validate retained profile-authorized policy material."""
    try:
        material = CandidateApplication.for_database(database).get_policy_material(candidate_id)
    except CandidateStoreError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(material.model_dump_json(indent=2))


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
        if not isinstance(evaluation, PolicyEvaluation):
            raise ValueError("only legacy forgegate.policy-evaluation.v1 can be backfilled")
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


@candidate_app.command("export-assurance")
def candidate_export_assurance(
    database: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    candidate_id: Annotated[str, typer.Argument()],
    output_root: Annotated[Path, typer.Option("--output-root", file_okay=False)],
) -> None:
    """Publish a content-addressed portable assurance bundle from durable state."""
    try:
        bundle = CandidateApplication.for_database(database).get_assurance_bundle(candidate_id)
        published = publish_assurance_bundle(bundle, output_root)
    except (
        AssuranceBundleError,
        CandidateLifecycleError,
        CandidateStoreError,
        ValidationError,
        ValueError,
    ) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    payload = {
        "bundle": bundle.model_dump(mode="json"),
        "bundle_directory": str(published.directory),
        "bundle_path": str(published.bundle_path),
        "readme_path": str(published.readme_path),
        "manifest_path": str(published.manifest_path),
        "output_replayed": published.replayed,
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _load_policy_evaluation(path: Path | None) -> PolicyEvaluationDocument | None:
    if path is None:
        return None
    evaluation = load_config(path)
    if not isinstance(evaluation, (PolicyEvaluation, ProfileAuthorizedPolicyEvaluation)):
        raise ValueError("evaluation path must contain a ForgeGate policy evaluation")
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
