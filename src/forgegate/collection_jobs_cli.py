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
from forgegate.collection_jobs import CollectionJobRequest, CollectionJobStore, JobError

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
    typer.echo("CREATED collection-job store v1; local file authority only")


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


@jobs_app.command("show")
def show(store: Path, job_id: str) -> None:
    with _guard():
        typer.echo(CollectionJobStore(store).show(job_id).model_dump_json(indent=2))


@jobs_app.command("list")
def list_jobs(
    store: Path, after: str = "", limit: Annotated[int, typer.Option(min=1, max=100)] = 25
) -> None:
    """Page lexically by job ID; use the last ID as --after, not a timestamp."""
    with _guard():
        rows = CollectionJobStore(store).list_jobs(after=after, limit=limit)
        typer.echo(json.dumps([row.model_dump(mode="json") for row in rows], indent=2))


@jobs_app.command("run")
def run(
    store: Path,
    job_id: str,
    database: Annotated[Path, typer.Option()],
    revision: Annotated[int, typer.Option(min=0, max=2)],
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
def cancel(store: Path, job_id: str, revision: Annotated[int, typer.Option(min=0, max=2)]) -> None:
    """Cancel publication and logically release input; does not kill a parser process."""
    with _guard():
        typer.echo(CollectionJobStore(store).cancel(job_id, revision).model_dump_json(indent=2))


@jobs_app.command("recover")
def recover(store: Path, job_id: str, revision: Annotated[int, typer.Option(min=0, max=2)]) -> None:
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
