from pathlib import Path
from typing import Annotated

import typer

from forgegate.application import CandidateApplication
from forgegate.artifacts import ArtifactRegistry
from forgegate.evidence_replay import (
    MAX_REPLAY_ARCHIVE_BYTES,
    publish_evidence_replay,
    verify_evidence_replay,
)

replay_app = typer.Typer(help="Export exact software source reports and verify offline replay.")


@replay_app.command("export")
def export_replay(
    database: Path,
    candidate_id: str,
    source_root: Annotated[Path, typer.Option("--source-root")],
    destination: Annotated[Path, typer.Option("--destination")],
) -> None:
    """Create a new directory with a private source-report ZIP; never overwrite."""
    try:
        bundle = CandidateApplication.for_database(database).get_assurance_bundle(candidate_id)
        path = publish_evidence_replay(bundle, source_root, destination)
    except (ValueError, OSError, RuntimeError) as exc:
        typer.echo(f"ERROR: {getattr(exc, 'code', 'REPLAY_IO')}: replay export refused.", err=True)
        raise typer.Exit(3) from exc
    typer.echo(str(path))


@replay_app.command("verify")
def verify_replay(
    archive: Path,
    expected_commit: Annotated[str, typer.Option("--expected-commit")],
) -> None:
    """Check exact ZIP bytes, reparse source reports and recompute the retained decision."""
    try:
        payload = (
            ArtifactRegistry(archive.parent, max_bytes=MAX_REPLAY_ARCHIVE_BYTES)
            .register(archive.name, media_type="application/zip")
            .content
        )
        result = verify_evidence_replay(payload, expected_commit=expected_commit)
    except (ValueError, OSError, RuntimeError) as exc:
        typer.echo(
            f"ERROR: {getattr(exc, 'code', 'REPLAY_IO')}: replay verification refused.", err=True
        )
        raise typer.Exit(3) from exc
    typer.echo(result.model_dump_json(indent=2))
