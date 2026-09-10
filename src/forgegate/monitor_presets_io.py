"""Owner-selected local preset files; never browser-selected paths or executable code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forgegate.monitor_presets import MonitorPresetCatalog

MAX_PRESET_BYTES = 64 * 1024


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("MONITOR_PRESETS_DUPLICATE_KEY")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("MONITOR_PRESETS_NONFINITE_NUMBER")


def load_monitor_presets(path: Path) -> MonitorPresetCatalog:
    if not path.is_file():
        raise ValueError("MONITOR_PRESETS_FILE_REQUIRED")
    with path.open("rb") as stream:
        data = stream.read(MAX_PRESET_BYTES + 1)
    if len(data) > MAX_PRESET_BYTES:
        raise ValueError("MONITOR_PRESETS_TOO_LARGE")
    try:
        raw = json.loads(
            data.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except RecursionError as exc:
        raise ValueError("MONITOR_PRESETS_TOO_DEEP") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != "forgegate.monitor-presets.v1":
        raise ValueError("MONITOR_PRESETS_VERSION_REQUIRED")
    return MonitorPresetCatalog.model_validate(raw)


def save_monitor_presets(path: Path, catalog: MonitorPresetCatalog) -> None:
    data = catalog.model_dump_json(indent=2) + "\n"
    if len(data.encode("utf-8")) > MAX_PRESET_BYTES:
        raise ValueError("MONITOR_PRESETS_TOO_LARGE")
    # Exclusive creation: an existing user catalog is never overwritten.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(data)
