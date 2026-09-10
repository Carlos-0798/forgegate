"""Local-only job commands; no HTTP authority or automatic binding is implied."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any

import typer

from forgegate.application import CandidateApplication
from forgegate.artifacts import ArtifactRegistry
from forgegate.bounded_parsing import enforce_json_structure_limits
from forgegate.collection_jobs import (
    MAX_JOB_REVISION,
    CollectionJobRequest,
    CollectionJobStore,
    JobArchiveFilter,
    JobError,
)

jobs_app = typer.Typer(help="Explicit local report jobs; separate private store, no daemon.")


@contextmanager
def _guard() -> Iterator[None]:
    try:
        yield
    except (OSError, ValueError) as exc:
        code = str(exc) if isinstance(exc, JobError) else "JOB_INPUT_OR_OPERATION_INVALID"
        typer.echo(f"ERROR: {code}", err=True)
        raise typer.Exit(code=3) from exc


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise JobError("JOB_INPUT_DUPLICATE_KEY")
        result[key] = value
    return result


def load_request(path: Path) -> CollectionJobRequest:
    content = (
        ArtifactRegistry(path.parent, max_bytes=4 * 1024 * 1024)
        .register(path.name, media_type="application/json")
        .content
    )
    enforce_json_structure_limits(content, max_nodes=1000, max_depth=12)
    raw = json.loads(content.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_nonfinite)
    return CollectionJobRequest.model_validate(raw)


def _nonfinite(value: str) -> None:
    raise JobError("JOB_INPUT_NONFINITE_NUMBER")


@jobs_app.command("init")
def initialize(store: Path) -> None:
    """Create a NEW private job database; existing files are never overwritten."""
    with _guard():
        CollectionJobStore(store).initialize()
    typer.echo("CREATED collection-job store v3; local file authority only")


@jobs_app.command("migrate")
def migrate(store: Path) -> None:
    """Explicit v1/v2-to-v3 migration; existing record bytes and actors are preserved."""
    with _guard():
        CollectionJobStore(store).migrate()
    typer.echo("VALID collection-job store v3 or v4; no historical owner or actor inferred")


@jobs_app.command("submit")
def submit(
    store: Path,
    request: Path,
    database: Annotated[Path, typer.Option()],
    key: Annotated[str, typer.Option()],
) -> None:
    """Retain bounded input bytes with explicit idempotency; do not run or bind."""
    with _guard():
        record = CollectionJobStore(store).submit(
            load_request(request), CandidateApplication.for_database(database), key=key
        )
        typer.echo(record.model_dump_json(indent=2))


@jobs_app.command("enable-archiving")
def enable_archiving(store: Path) -> None:
    """Explicit v3-to-v4 upgrade after backup; retains exact existing records and events."""
    with _guard():
        CollectionJobStore(store).enable_archiving()
    typer.echo("VALID collection-job store v4; archiving enabled, no jobs archived")


@jobs_app.command("archive-info")
def archive_info(store: Path, job_id: str) -> None:
    """Show the retained archive receipt without opening any external backup."""
    with _guard():
        repository = CollectionJobStore(store)
        record = repository.show(job_id)
        review = repository.review(job_id, project_id=record.project_id)
        if review.archive is None:
            raise JobError("JOB_NOT_ARCHIVED")
        typer.echo(review.archive.model_dump_json(indent=2))


@jobs_app.command("show")
def show(store: Path, job_id: str) -> None:
    with _guard():
        typer.echo(CollectionJobStore(store).show(job_id).model_dump_json(indent=2))


@jobs_app.command("list")
def list_jobs(
    store: Path,
    after: str = "",
    limit: Annotated[int, typer.Option(min=1, max=100)] = 25,
    archive_filter: Annotated[JobArchiveFilter, typer.Option()] = "all",
) -> None:
    """Page by job ID and all/current/archived status; last ID is the cursor."""
    with _guard():
        rows = CollectionJobStore(store).list_jobs(
            after=after, limit=limit, archive_filter=archive_filter
        )
        typer.echo(json.dumps([row.model_dump(mode="json") for row in rows], indent=2))


@jobs_app.command("capacity")
def capacity(store: Path) -> None:
    """Show store-wide logical quotas; external backup availability is not checked."""
    with _guard():
        typer.echo(CollectionJobStore(store).capacity().model_dump_json(indent=2))


@jobs_app.command("run")
def run(
    store: Path,
    job_id: str,
    database: Annotated[Path, typer.Option()],
    revision: Annotated[int, typer.Option(min=0, max=MAX_JOB_REVISION)],
) -> None:
    """Run one queued job in the foreground; no automatic retries or policy decision."""
    with _guard():
        record = CollectionJobStore(store).run(
            job_id, revision, CandidateApplication.for_database(database)
        )
        typer.echo(record.model_dump_json(indent=2))
        if record.state != "SUCCEEDED":
            raise typer.Exit(code=3)


@jobs_app.command("cancel")
def cancel(
    store: Path,
    job_id: str,
    revision: Annotated[int, typer.Option(min=0, max=MAX_JOB_REVISION)],
) -> None:
    """Persist cancellation; a running parser observes it at a cooperative checkpoint."""
    with _guard():
        typer.echo(CollectionJobStore(store).cancel(job_id, revision).model_dump_json(indent=2))


@jobs_app.command("recover")
def recover(
    store: Path,
    job_id: str,
    revision: Annotated[int, typer.Option(min=0, max=MAX_JOB_REVISION)],
) -> None:
    """Mark an expired running lease INTERRUPTED; never restart execution."""
    with _guard():
        typer.echo(CollectionJobStore(store).recover(job_id, revision).model_dump_json(indent=2))


@jobs_app.command("result")
def result(store: Path, job_id: str, assembly: bool = False) -> None:
    """Print retained result or exact assembly JSON for a separate reviewed binding."""
    with _guard():
        value = CollectionJobStore(store).result(job_id)
        if assembly:
            if value.assembly is None:
                raise JobError("JOB_ASSEMBLY_UNAVAILABLE")
            typer.echo(value.assembly.model_dump_json(indent=2))
        else:
            typer.echo(value.model_dump_json(indent=2))
