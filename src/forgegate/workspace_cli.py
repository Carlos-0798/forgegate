"""Owner-operated database protection. No browser path, migration or service control."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from forgegate.workspace_backups import (
    WorkspaceBackupError,
    backup_workspace,
    plan_workspace_retention,
    restore_workspace,
    verify_workspace_backup,
)

workspace_app = typer.Typer(
    help="Coordinated private candidate/job backup, recovery and retention planning."
)
Timeout = Annotated[float, typer.Option(min=0.1, max=300)]


@contextmanager
def _guard() -> Iterator[None]:
    try:
        yield
    except WorkspaceBackupError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc


@workspace_app.command("backup")
def backup(
    database: Path,
    job_store: Path,
    destination: Path,
    timeout_seconds: Timeout = 30,
) -> None:
    """Create a NEW ZIP snapshot of candidate v9 + job v3; running jobs block backup."""
    with _guard():
        typer.echo(
            json.dumps(
                backup_workspace(database, job_store, destination, timeout_seconds=timeout_seconds),
                indent=2,
            )
        )


@workspace_app.command("verify-backup")
def verify(
    backup: Path,
    sha256: Annotated[str | None, typer.Option()] = None,
    timeout_seconds: Timeout = 30,
) -> None:
    """Verify a private offline backup; --sha256 compares a separately retained receipt."""
    with _guard():
        typer.echo(
            json.dumps(
                verify_workspace_backup(
                    backup, expected_sha256=sha256, timeout_seconds=timeout_seconds
                ),
                indent=2,
            )
        )


@workspace_app.command("restore")
def restore(
    backup: Path,
    destination: Path,
    sha256: Annotated[str, typer.Option()],
    timeout_seconds: Timeout = 30,
) -> None:
    """Restore both stores to a NEW directory. RESTORED.json marks completed copy only."""
    with _guard():
        typer.echo(
            json.dumps(
                restore_workspace(
                    backup, destination, expected_sha256=sha256, timeout_seconds=timeout_seconds
                ),
                indent=2,
            )
        )


@workspace_app.command("retention-plan")
def retention(
    backup: Path,
    sha256: Annotated[str, typer.Option()],
    as_of: Annotated[
        datetime, typer.Option(formats=["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"])
    ],
    terminal_before: Annotated[
        datetime, typer.Option(formats=["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"])
    ],
    timeout_seconds: Timeout = 30,
) -> None:
    """Plan from a verified snapshot: retain active/bound/recent jobs; NEVER delete."""
    with _guard():
        typer.echo(
            json.dumps(
                plan_workspace_retention(
                    backup,
                    expected_sha256=sha256,
                    as_of=as_of,
                    terminal_before=terminal_before,
                    timeout_seconds=timeout_seconds,
                ),
                indent=2,
            )
        )
