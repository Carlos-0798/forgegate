import json
import platform
from pathlib import Path
from typing import Annotated

import typer

from forgegate import __version__
from forgegate.config import ConfigLoadError, load_config
from forgegate.schema_registry import SCHEMAS, schema_filename

app = typer.Typer(
    name="forgegate",
    help="ForgeGate Phase 0 contract and configuration tools.",
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
        "phase": "phase0-contract-baseline",
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
