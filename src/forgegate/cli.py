import json
import platform
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from forgegate import __version__
from forgegate.artifacts import ArtifactBoundaryError, ArtifactRegistry
from forgegate.candidates import (
    CandidateLifecycleError,
    ReleaseCandidate,
    create_candidate,
    transition_candidate,
)
from forgegate.collectors import (
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
from forgegate.domain.models import EvidenceBundle, ExecutionContext, PolicyConfig
from forgegate.policy import evaluate_policy
from forgegate.policy.models import PolicyEvaluation
from forgegate.schema_registry import SCHEMAS, schema_filename

app = typer.Typer(
    name="forgegate",
    help="ForgeGate evidence collection and release-assurance tools.",
    no_args_is_help=True,
)
candidate_app = typer.Typer(help="Create and advance immutable release candidates.")
app.add_typer(candidate_app, name="candidate")


@app.command()
def doctor() -> None:
    """Report the local contract-tooling environment."""
    report = {
        "forgegate_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "supported_schemas": sorted(SCHEMAS),
        "phase": "phase2-candidate-lifecycle",
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
    """Export canonical JSON Schemas from the Pydantic contract models."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for schema_version, model in sorted(SCHEMAS.items()):
        target = output_dir / schema_filename(schema_version)
        payload = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        target.write_text(payload, encoding="utf-8")
        typer.echo(str(target))


@candidate_app.command("create")
def candidate_create(
    project_id: Annotated[str, typer.Option("--project")],
    version: Annotated[str, typer.Option("--version")],
    commit: Annotated[str, typer.Option("--commit")],
    created_at: Annotated[str, typer.Option("--created-at")],
    source_branch: Annotated[str, typer.Option("--branch")] = "main",
    release_track: Annotated[str, typer.Option("--track")] = "pull-request",
) -> None:
    """Create a deterministic DRAFT candidate document without persistence."""
    try:
        candidate = create_candidate(
            project_id=project_id,
            version=version,
            commit_sha=commit,
            source_branch=source_branch,
            release_track=release_track,
            created_at=datetime.fromisoformat(created_at.replace("Z", "+00:00")),
        )
    except (CandidateLifecycleError, ValidationError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(candidate.model_dump_json(indent=2))


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
        if not isinstance(candidate, ReleaseCandidate):
            raise ValueError("candidate path must contain forgegate.release-candidate.v1")
        evaluation = None
        if evaluation_path is not None:
            loaded_evaluation = load_config(evaluation_path)
            if not isinstance(loaded_evaluation, PolicyEvaluation):
                raise ValueError("evaluation path must contain forgegate.policy-evaluation.v1")
            evaluation = loaded_evaluation
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


@app.command("evaluate-policy")
def evaluate_policy_command(
    policy_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    evidence_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    evaluated_at: Annotated[str, typer.Option("--evaluated-at")],
) -> None:
    """Evaluate a policy against an evidence bundle at an explicit timestamp."""
    try:
        policy = load_config(policy_path)
        bundle = load_config(evidence_path)
        if not isinstance(policy, PolicyConfig):
            raise ValueError("policy path must contain forgegate.policy.v1")
        if not isinstance(bundle, EvidenceBundle):
            raise ValueError("evidence path must contain forgegate.evidence-bundle.v1")
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
