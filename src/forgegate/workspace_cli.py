"""Owner-operated database protection. No browser path, migration or service control."""

import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from forgegate.canonical import sha256_fingerprint
from forgegate.job_archival import (
    archive_job,
    load_archive_plan,
    plan_job_archive,
    read_archived_result,
)
from forgegate.recovery_readiness import check_recovery_readiness
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


@workspace_app.command("recovery-check")
def recovery_check(
    backup: Path,
    sha256: Annotated[str, typer.Option()],
    dependency: Annotated[
        list[str] | None,
        typer.Option(help="Explicit SHA256=PATH mapping; repeat for each original backup."),
    ] = None,
    timeout_seconds: Timeout = 30,
) -> None:
    """Check an exact snapshot and archived payload dependencies; no restore or live reads."""
    with _guard():
        mappings: dict[str, Path] = {}
        for entry in dependency or []:
            digest, separator, path = entry.partition("=")
            if not separator or not path or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise WorkspaceBackupError("RECOVERY_DEPENDENCY_MAP_INVALID")
            if digest in mappings:
                raise WorkspaceBackupError("RECOVERY_DUPLICATE_DEPENDENCY")
            mappings[digest] = Path(path)
        report = check_recovery_readiness(
            backup, expected_sha256=sha256, dependencies=mappings, timeout_seconds=timeout_seconds
        )
        typer.echo(report.model_dump_json(indent=2))
        if report.status != "READY":
            raise typer.Exit(code=2)


@contextmanager
def _guard() -> Iterator[None]:
    try:
        yield
    except (WorkspaceBackupError, OSError) as exc:
        code = str(exc) if isinstance(exc, WorkspaceBackupError) else "WORKSPACE_FILE_IO_FAILED"
        typer.echo(f"ERROR: {code}", err=True)
        raise typer.Exit(code=3) from exc


@workspace_app.command("backup")
def backup(
    database: Path,
    job_store: Path,
    destination: Path,
    timeout_seconds: Timeout = 30,
) -> None:
    """Create a NEW ZIP snapshot of candidate v9 + job v3/v4; running jobs block backup."""
    with _guard():
        typer.echo(
            json.dumps(
                backup_workspace(database, job_store, destination, timeout_seconds=timeout_seconds),
                indent=2,
            )
        )


@workspace_app.command("plan-job-archive")
def archive_plan(
    database: Path,
    job_store: Path,
    backup: Path,
    job_id: str,
    sha256: Annotated[str, typer.Option()],
    revision: Annotated[int, typer.Option(min=1, max=64)],
    terminal_before: Annotated[
        datetime, typer.Option(formats=["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"])
    ],
    output: Annotated[Path, typer.Option(help="NEW private plan file; never overwrite.")],
    timeout_seconds: Timeout = 30,
) -> None:
    """Review one terminal unbound job against an exact verified backup; no job writes."""
    with _guard():
        plan = plan_job_archive(
            database,
            job_store,
            backup,
            job_id,
            expected_sha256=sha256,
            expected_revision=revision,
            terminal_before=terminal_before,
            timeout_seconds=timeout_seconds,
        )
        with output.open("x", encoding="utf-8") as stream:
            stream.write(plan.model_dump_json(indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        typer.echo(
            json.dumps(
                {
                    "plan": plan.model_dump(mode="json"),
                    "plan_fingerprint": sha256_fingerprint(plan.model_dump(mode="json")),
                },
                indent=2,
            )
        )


@workspace_app.command("archive-job")
def apply_archive(
    database: Path,
    job_store: Path,
    backup: Path,
    plan_file: Path,
    confirm_plan: Annotated[str, typer.Option(help="Exact reviewed plan fingerprint.")],
    timeout_seconds: Timeout = 30,
) -> None:
    """Recheck then archive one result logically; preserve history and duplicate-request keys."""
    with _guard():
        receipt = archive_job(
            database,
            job_store,
            backup,
            load_archive_plan(plan_file),
            confirm_plan=confirm_plan,
            timeout_seconds=timeout_seconds,
        )
        typer.echo(receipt.model_dump_json(indent=2))


@workspace_app.command("archived-result")
def archived_result(
    backup: Path,
    job_id: str,
    sha256: Annotated[str, typer.Option()],
    assembly: Annotated[bool, typer.Option()] = False,
    timeout_seconds: Timeout = 30,
) -> None:
    """Read retained payload from an explicit original backup; never auto-follow paths."""
    with _guard():
        result = read_archived_result(
            backup, job_id, expected_sha256=sha256, timeout_seconds=timeout_seconds
        )
        if assembly:
            if result.assembly is None:
                raise WorkspaceBackupError("ARCHIVE_ASSEMBLY_UNAVAILABLE")
            typer.echo(result.assembly.model_dump_json(indent=2))
        else:
            typer.echo(result.model_dump_json(indent=2))


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
