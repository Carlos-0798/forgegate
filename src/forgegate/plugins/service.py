from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from forgegate.artifacts import ArtifactError, ArtifactRegistry

from .models import (
    PLUGIN_API_VERSION,
    PLUGIN_ENTRY_POINT_GROUP,
    PLUGIN_ID_PATTERN,
    PLUGIN_MANIFEST_FILENAME,
    DiscoveredPlugin,
    PluginDiscoveryIssue,
    PluginDiscoveryReport,
    PluginDiscoveryStatus,
    PluginManifest,
    create_plugin_discovery_report,
)

DEFAULT_MAX_PLUGIN_MANIFEST_BYTES = 64 * 1024
DEFAULT_MAX_PLUGIN_MANIFEST_NODES = 2_048
DEFAULT_MAX_PLUGIN_MANIFEST_DEPTH = 16
DEFAULT_MAX_DISTRIBUTIONS = 4_096
DEFAULT_MAX_PLUGIN_ENTRIES = 1_024
DEFAULT_MAX_DISTRIBUTION_FILES = 10_000
ENTRY_POINT_VALUE_RE = re.compile(
    r"^(?P<module>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
    r":(?P<attribute>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)$"
)
PLUGIN_ID_RE = re.compile(PLUGIN_ID_PATTERN)
SAFE_METADATA_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")


class PluginDiscoveryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def discover_plugins(
    distributions: Iterable[metadata.Distribution] | None = None,
    *,
    max_manifest_bytes: int = DEFAULT_MAX_PLUGIN_MANIFEST_BYTES,
    max_manifest_nodes: int = DEFAULT_MAX_PLUGIN_MANIFEST_NODES,
    max_manifest_depth: int = DEFAULT_MAX_PLUGIN_MANIFEST_DEPTH,
    max_distributions: int = DEFAULT_MAX_DISTRIBUTIONS,
    max_plugin_entries: int = DEFAULT_MAX_PLUGIN_ENTRIES,
    max_distribution_files: int = DEFAULT_MAX_DISTRIBUTION_FILES,
) -> PluginDiscoveryReport:
    limits = (
        max_manifest_bytes,
        max_manifest_nodes,
        max_manifest_depth,
        max_distributions,
        max_plugin_entries,
        max_distribution_files,
    )
    if min(limits) <= 0:
        raise ValueError("plugin discovery limits must be positive")
    try:
        source = metadata.distributions() if distributions is None else distributions
        installed: list[metadata.Distribution] = []
        for distribution in source:
            if len(installed) >= max_distributions:
                raise PluginDiscoveryError(
                    "PLUGIN_DISTRIBUTION_LIMIT",
                    "installed distribution count exceeds the discovery limit",
                )
            installed.append(distribution)
    except PluginDiscoveryError:
        raise
    except Exception as exc:
        raise PluginDiscoveryError(
            "PLUGIN_DISCOVERY_UNAVAILABLE", "installed distribution metadata is unavailable"
        ) from exc

    discovered: list[DiscoveredPlugin] = []
    for distribution in installed:
        distribution_name = _safe_distribution_field(
            _distribution_metadata(distribution, "Name"), "unknown-distribution"
        )
        distribution_version = _safe_distribution_field(
            _distribution_version(distribution), "unknown-version"
        )
        try:
            entry_points = tuple(distribution.entry_points)
        except Exception:
            continue
        for entry_point in entry_points:
            if entry_point.group != PLUGIN_ENTRY_POINT_GROUP:
                continue
            if len(discovered) >= max_plugin_entries:
                raise PluginDiscoveryError(
                    "PLUGIN_ENTRY_LIMIT", "plugin entry count exceeds the discovery limit"
                )
            discovered.append(
                _discover_entry_point(
                    distribution,
                    distribution_name=distribution_name,
                    distribution_version=distribution_version,
                    entry_point_name=str(entry_point.name),
                    entry_point_value=str(entry_point.value),
                    max_manifest_bytes=max_manifest_bytes,
                    max_manifest_nodes=max_manifest_nodes,
                    max_manifest_depth=max_manifest_depth,
                    max_distribution_files=max_distribution_files,
                )
            )

    discovered = _mark_plugin_id_conflicts(discovered)
    return create_plugin_discovery_report(tuple(discovered))


def _discover_entry_point(
    distribution: metadata.Distribution,
    *,
    distribution_name: str,
    distribution_version: str,
    entry_point_name: str,
    entry_point_value: str,
    max_manifest_bytes: int,
    max_manifest_nodes: int,
    max_manifest_depth: int,
    max_distribution_files: int,
) -> DiscoveredPlugin:
    safe_name = entry_point_name if SAFE_METADATA_RE.fullmatch(entry_point_name) else "invalid"
    value_match = ENTRY_POINT_VALUE_RE.fullmatch(entry_point_value)
    safe_value = entry_point_value if value_match is not None else "invalid"
    if PLUGIN_ID_RE.fullmatch(entry_point_name) is None or value_match is None:
        return _invalid_plugin(
            distribution_name,
            distribution_version,
            safe_name,
            safe_value,
            None,
            "PLUGIN_ENTRY_POINT_INVALID",
            "entry point name or value violates the ForgeGate plugin contract",
        )

    top_package = value_match.group("module").split(".", maxsplit=1)[0]
    manifest_path = f"{top_package}/{PLUGIN_MANIFEST_FILENAME}"
    files = distribution.files
    if files is not None and len(files) > max_distribution_files:
        return _invalid_plugin(
            distribution_name,
            distribution_version,
            safe_name,
            safe_value,
            manifest_path,
            "PLUGIN_DISTRIBUTION_FILE_LIMIT",
            "distribution file count exceeds the discovery limit",
        )
    if files is None or not any(manifest_path == str(item).replace("\\", "/") for item in files):
        return _invalid_plugin(
            distribution_name,
            distribution_version,
            safe_name,
            safe_value,
            manifest_path,
            "PLUGIN_MANIFEST_MISSING",
            "distribution does not contain the required listed plugin manifest",
        )
    try:
        root = Path(str(distribution.locate_file("")))
        manifest_candidate = root / Path(manifest_path)
        if manifest_candidate.is_symlink():
            raise PluginDiscoveryError(
                "PLUGIN_MANIFEST_UNSAFE", "plugin manifest cannot be a symbolic link"
            )
        artifact = ArtifactRegistry(root, max_bytes=max_manifest_bytes).register(
            manifest_path, media_type="application/vnd.forgegate.plugin-manifest+json"
        )
        raw = _strict_json(artifact.content)
        _enforce_tree_limits(raw, max_nodes=max_manifest_nodes, max_depth=max_manifest_depth)
        if not isinstance(raw, dict):
            raise PluginDiscoveryError(
                "PLUGIN_MANIFEST_ROOT_INVALID", "plugin manifest root must be an object"
            )
        manifest = PluginManifest.model_validate(raw)
    except PluginDiscoveryError as exc:
        return _invalid_plugin(
            distribution_name,
            distribution_version,
            safe_name,
            safe_value,
            manifest_path,
            exc.code,
            str(exc),
        )
    except ArtifactError:
        return _invalid_plugin(
            distribution_name,
            distribution_version,
            safe_name,
            safe_value,
            manifest_path,
            "PLUGIN_MANIFEST_UNAVAILABLE",
            "plugin manifest cannot be read safely",
        )
    except ValidationError as exc:
        first = exc.errors(include_url=False, include_input=False)[0]
        return _invalid_plugin(
            distribution_name,
            distribution_version,
            safe_name,
            safe_value,
            manifest_path,
            "PLUGIN_MANIFEST_CONTRACT_INVALID",
            f"plugin manifest violates its contract: {first['msg']}",
        )

    if manifest.plugin_id != entry_point_name:
        return _invalid_plugin(
            distribution_name,
            distribution_version,
            safe_name,
            safe_value,
            manifest_path,
            "PLUGIN_ID_MISMATCH",
            "entry point name does not match the manifest plugin ID",
        )
    if manifest.forgegate_api_version != PLUGIN_API_VERSION:
        return DiscoveredPlugin(
            distribution_name=distribution_name,
            distribution_version=distribution_version,
            entry_point_name=safe_name,
            entry_point_value=safe_value,
            manifest_path=manifest_path,
            plugin_id=manifest.plugin_id,
            manifest=manifest,
            status=PluginDiscoveryStatus.INCOMPATIBLE,
            issues=(
                PluginDiscoveryIssue(
                    code="PLUGIN_API_INCOMPATIBLE",
                    message="plugin targets an unsupported ForgeGate plugin API version",
                ),
            ),
        )
    return DiscoveredPlugin(
        distribution_name=distribution_name,
        distribution_version=distribution_version,
        entry_point_name=safe_name,
        entry_point_value=safe_value,
        manifest_path=manifest_path,
        plugin_id=manifest.plugin_id,
        manifest=manifest,
        status=PluginDiscoveryStatus.COMPATIBLE,
    )


def _invalid_plugin(
    distribution_name: str,
    distribution_version: str,
    entry_point_name: str,
    entry_point_value: str,
    manifest_path: str | None,
    code: str,
    message: str,
) -> DiscoveredPlugin:
    return DiscoveredPlugin(
        distribution_name=distribution_name,
        distribution_version=distribution_version,
        entry_point_name=entry_point_name,
        entry_point_value=entry_point_value,
        manifest_path=manifest_path,
        status=PluginDiscoveryStatus.INVALID,
        issues=(PluginDiscoveryIssue(code=code, message=message),),
    )


def _mark_plugin_id_conflicts(plugins: list[DiscoveredPlugin]) -> list[DiscoveredPlugin]:
    by_id: dict[str, list[int]] = defaultdict(list)
    for index, plugin in enumerate(plugins):
        if plugin.plugin_id is not None and plugin.manifest is not None:
            by_id[plugin.plugin_id].append(index)
    for indices in by_id.values():
        if len(indices) < 2:
            continue
        for index in indices:
            plugin = plugins[index]
            plugins[index] = DiscoveredPlugin(
                **plugin.model_dump(mode="python", exclude={"status", "issues"}),
                status=PluginDiscoveryStatus.CONFLICT,
                issues=(
                    PluginDiscoveryIssue(
                        code="PLUGIN_ID_CONFLICT",
                        message="multiple installed entry points declare the same plugin ID",
                    ),
                ),
            )
    return plugins


def _strict_json(content: bytes) -> Any:
    if b"\x00" in content:
        raise PluginDiscoveryError(
            "PLUGIN_MANIFEST_ENCODING_INVALID", "plugin manifest must not contain NUL bytes"
        )
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PluginDiscoveryError(
            "PLUGIN_MANIFEST_ENCODING_INVALID", "plugin manifest must be strict UTF-8"
        ) from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except PluginDiscoveryError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise PluginDiscoveryError(
            "PLUGIN_MANIFEST_JSON_INVALID", "plugin manifest is not valid strict JSON"
        ) from exc


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PluginDiscoveryError(
                "PLUGIN_MANIFEST_DUPLICATE_KEY", "plugin manifest contains a duplicate key"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise PluginDiscoveryError(
        "PLUGIN_MANIFEST_NUMBER_INVALID", f"plugin manifest contains non-finite number {value}"
    )


def _enforce_tree_limits(root: Any, *, max_nodes: int, max_depth: int) -> None:
    observed = 0
    stack: list[tuple[Any, int]] = [(root, 1)]
    while stack:
        value, depth = stack.pop()
        observed += 1
        if observed > max_nodes:
            raise PluginDiscoveryError(
                "PLUGIN_MANIFEST_NODE_LIMIT", "plugin manifest exceeds the JSON node limit"
            )
        if depth > max_depth:
            raise PluginDiscoveryError(
                "PLUGIN_MANIFEST_DEPTH_LIMIT", "plugin manifest exceeds the JSON depth limit"
            )
        if isinstance(value, dict):
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)


def _safe_distribution_field(value: str | None, fallback: str) -> str:
    return value if value is not None and SAFE_METADATA_RE.fullmatch(value) else fallback


def _distribution_metadata(distribution: metadata.Distribution, key: str) -> str | None:
    try:
        value = distribution.metadata.get(key)
    except Exception:
        return None
    return str(value) if value is not None else None


def _distribution_version(distribution: metadata.Distribution) -> str | None:
    try:
        return str(distribution.version)
    except Exception:
        return None


__all__ = [
    "DEFAULT_MAX_DISTRIBUTIONS",
    "DEFAULT_MAX_DISTRIBUTION_FILES",
    "DEFAULT_MAX_PLUGIN_ENTRIES",
    "DEFAULT_MAX_PLUGIN_MANIFEST_BYTES",
    "DEFAULT_MAX_PLUGIN_MANIFEST_DEPTH",
    "DEFAULT_MAX_PLUGIN_MANIFEST_NODES",
    "PluginDiscoveryError",
    "discover_plugins",
]
