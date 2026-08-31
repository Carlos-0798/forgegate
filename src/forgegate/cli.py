import json
import platform
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from forgegate import __version__
from forgegate.artifacts import ArtifactBoundaryError, ArtifactRegistry
from forgegate.collectors import (
    CollectionResult,
    CollectionStatus,
    CoverageCollectionRequest,
    CoverageXmlCollector,
    JUnitCollectionRequest,
    JUnitCollector,
    LcovCollector,
)
from forgegate.config import ConfigLoadError, load_config
from forgegate.domain.enums import EvidenceTrust, VerificationLevel
from forgegate.domain.models import ExecutionContext
from forgegate.schema_registry import SCHEMAS, schema_filename

app = typer.Typer(
    name="forgegate",
    help="ForgeGate evidence collection and release-assurance tools.",
    no_args_is_help=True,
)


@app.command()
def doctor() -> None:
    """Report the local contract-tooling environment."""
    report = {
        "forgegate_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "supported_schemas": sorted(SCHEMAS),
        "phase": "phase1-standard-collectors",
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
