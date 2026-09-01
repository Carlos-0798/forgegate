from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from forgegate.canonical import sha256_fingerprint
from forgegate.domain.models import EVIDENCE_KIND_PATTERN, StrictModel

PLUGIN_API_VERSION = "1"
PLUGIN_ENTRY_POINT_GROUP = "forgegate.plugins.v1"
PLUGIN_MANIFEST_FILENAME = "forgegate-plugin.json"
PLUGIN_ID_PATTERN = r"^[a-z][a-z0-9]*(?:[.-][a-z0-9][a-z0-9-]*){1,7}$"
PLUGIN_VERSION_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$"
SCHEMA_ID_PATTERN = r"^[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+)+\.v[1-9][0-9]*$"
FINGERPRINT_PATTERN = r"^sha256:[0-9a-f]{64}$"


class PluginCapability(StrEnum):
    COLLECTOR = "collector"
    EVALUATOR = "evaluator"
    EXPORTER = "exporter"
    NOTIFIER = "notifier"
    SOLUTION_PACK_METADATA = "solution-pack-metadata"


class PluginPermission(StrEnum):
    ARTIFACT_READ = "artifact-read"
    FILESYSTEM_WRITE = "filesystem-write"
    NETWORK = "network"
    NOTIFICATION = "notification"
    SECRETS = "secrets"
    SUBPROCESS = "subprocess"


class PluginDiscoveryStatus(StrEnum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    INVALID = "INVALID"
    CONFLICT = "CONFLICT"


class PluginManifest(StrictModel):
    """Declarative plugin metadata; validating it never imports plugin code."""

    schema_version: Literal["forgegate.plugin-manifest.v1"] = "forgegate.plugin-manifest.v1"
    manifest_id: str = Field(pattern=FINGERPRINT_PATTERN)
    plugin_id: str = Field(pattern=PLUGIN_ID_PATTERN)
    display_name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=512)
    plugin_version: str = Field(pattern=PLUGIN_VERSION_PATTERN)
    forgegate_api_version: str = Field(pattern=r"^[1-9][0-9]*$")
    capabilities: tuple[PluginCapability, ...] = Field(min_length=1, max_length=8)
    input_schemas: tuple[str, ...] = Field(default=(), max_length=32)
    permissions: tuple[PluginPermission, ...] = Field(default=(), max_length=16)
    output_evidence_kinds: tuple[str, ...] = Field(default=(), max_length=64)

    @field_validator("capabilities", "input_schemas", "permissions", "output_evidence_kinds")
    @classmethod
    def set_like_fields_are_unique_and_canonical(
        cls, value: tuple[object, ...]
    ) -> tuple[object, ...]:
        rendered = [item.value if isinstance(item, StrEnum) else str(item) for item in value]
        if len(rendered) != len(set(rendered)):
            raise ValueError("plugin manifest set-like fields cannot contain duplicates")
        return tuple(item for _, item in sorted(zip(rendered, value, strict=True)))

    @field_validator("input_schemas")
    @classmethod
    def input_schema_ids_are_versioned(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        invalid = [item for item in value if re.fullmatch(SCHEMA_ID_PATTERN, item) is None]
        if invalid:
            raise ValueError("plugin input schemas must be versioned dotted identifiers")
        return value

    @field_validator("output_evidence_kinds")
    @classmethod
    def evidence_kinds_are_canonical(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        invalid = [item for item in value if re.fullmatch(EVIDENCE_KIND_PATTERN, item) is None]
        if invalid:
            raise ValueError("plugin output evidence kinds must be dotted identifiers")
        return value

    @model_validator(mode="after")
    def collector_and_identity_contracts_hold(self) -> PluginManifest:
        if PluginCapability.COLLECTOR in self.capabilities:
            if not self.input_schemas:
                raise ValueError("collector plugins must declare at least one input schema")
            if not self.output_evidence_kinds:
                raise ValueError("collector plugins must declare output evidence kinds")
        if self.manifest_id != sha256_fingerprint(_manifest_identity(self)):
            raise ValueError("manifest_id does not match plugin manifest content")
        return self


class PluginDiscoveryIssue(StrictModel):
    code: str = Field(pattern=r"^PLUGIN_[A-Z0-9_]{2,120}$")
    message: str = Field(min_length=1, max_length=256)


class DiscoveredPlugin(StrictModel):
    distribution_name: str = Field(min_length=1, max_length=128)
    distribution_version: str = Field(min_length=1, max_length=128)
    entry_point_name: str = Field(min_length=1, max_length=128)
    entry_point_value: str = Field(min_length=1, max_length=256)
    manifest_path: str | None = Field(default=None, max_length=256)
    plugin_id: str | None = Field(default=None, pattern=PLUGIN_ID_PATTERN)
    manifest: PluginManifest | None = None
    status: PluginDiscoveryStatus
    core_api_version: Literal["1"] = "1"
    execution: Literal["NOT_LOADED"] = "NOT_LOADED"
    issues: tuple[PluginDiscoveryIssue, ...] = Field(default=(), max_length=16)

    @model_validator(mode="after")
    def status_shape_is_consistent(self) -> DiscoveredPlugin:
        valid_manifest = self.manifest is not None and self.plugin_id == self.manifest.plugin_id
        if self.status is PluginDiscoveryStatus.COMPATIBLE:
            if not valid_manifest or self.manifest is None:
                raise ValueError("compatible plugin discovery requires a valid manifest")
            if self.manifest.forgegate_api_version != PLUGIN_API_VERSION or self.issues:
                raise ValueError("compatible plugin discovery cannot retain compatibility issues")
        elif not self.issues:
            raise ValueError("non-compatible plugin discovery must explain its status")
        if (
            self.status
            in {
                PluginDiscoveryStatus.INCOMPATIBLE,
                PluginDiscoveryStatus.CONFLICT,
            }
            and not valid_manifest
        ):
            raise ValueError("incompatible or conflicting plugins require a valid manifest")
        if self.status is PluginDiscoveryStatus.INVALID and self.manifest is not None:
            raise ValueError("invalid plugin discovery cannot retain a trusted manifest")
        return self


class PluginDiscoveryReport(StrictModel):
    schema_version: Literal["forgegate.plugin-discovery.v1"] = "forgegate.plugin-discovery.v1"
    report_id: str = Field(pattern=FINGERPRINT_PATTERN)
    plugin_api_version: Literal["1"] = "1"
    entry_point_group: Literal["forgegate.plugins.v1"] = "forgegate.plugins.v1"
    execution: Literal["NOT_LOADED"] = "NOT_LOADED"
    core_operational_without_plugins: Literal[True] = True
    plugins: tuple[DiscoveredPlugin, ...]
    total: int = Field(ge=0)
    compatible: int = Field(ge=0)
    incompatible: int = Field(ge=0)
    invalid: int = Field(ge=0)
    conflicts: int = Field(ge=0)

    @model_validator(mode="after")
    def counts_order_and_identity_match(self) -> PluginDiscoveryReport:
        expected_order = sorted(
            self.plugins,
            key=lambda item: (
                item.entry_point_name,
                item.distribution_name,
                item.distribution_version,
                item.entry_point_value,
            ),
        )
        if list(self.plugins) != expected_order:
            raise ValueError("discovered plugins must use deterministic order")
        counts = {
            PluginDiscoveryStatus.COMPATIBLE: self.compatible,
            PluginDiscoveryStatus.INCOMPATIBLE: self.incompatible,
            PluginDiscoveryStatus.INVALID: self.invalid,
            PluginDiscoveryStatus.CONFLICT: self.conflicts,
        }
        if self.total != len(self.plugins):
            raise ValueError("plugin discovery total does not match entries")
        for status, expected in counts.items():
            if sum(item.status is status for item in self.plugins) != expected:
                raise ValueError("plugin discovery status counts do not match entries")
        if self.report_id != sha256_fingerprint(_report_identity(self)):
            raise ValueError("report_id does not match plugin discovery content")
        return self


def create_plugin_manifest(
    *,
    plugin_id: str,
    display_name: str,
    description: str,
    plugin_version: str,
    forgegate_api_version: str,
    capabilities: tuple[PluginCapability, ...],
    input_schemas: tuple[str, ...] = (),
    permissions: tuple[PluginPermission, ...] = (),
    output_evidence_kinds: tuple[str, ...] = (),
) -> PluginManifest:
    capability_values = _canonical_enums(capabilities)
    input_values = _canonical_strings(input_schemas)
    permission_values = _canonical_enums(permissions)
    evidence_values = _canonical_strings(output_evidence_kinds)
    payload = {
        "plugin_id": plugin_id,
        "display_name": display_name,
        "description": description,
        "plugin_version": plugin_version,
        "forgegate_api_version": forgegate_api_version,
        "capabilities": [item.value for item in capability_values],
        "input_schemas": list(input_values),
        "permissions": [item.value for item in permission_values],
        "output_evidence_kinds": list(evidence_values),
    }
    return PluginManifest(
        manifest_id=sha256_fingerprint(payload),
        plugin_id=plugin_id,
        display_name=display_name,
        description=description,
        plugin_version=plugin_version,
        forgegate_api_version=forgegate_api_version,
        capabilities=capability_values,
        input_schemas=input_values,
        permissions=permission_values,
        output_evidence_kinds=evidence_values,
    )


def create_plugin_discovery_report(
    plugins: tuple[DiscoveredPlugin, ...],
) -> PluginDiscoveryReport:
    ordered = tuple(
        sorted(
            plugins,
            key=lambda item: (
                item.entry_point_name,
                item.distribution_name,
                item.distribution_version,
                item.entry_point_value,
            ),
        )
    )
    compatible = sum(item.status is PluginDiscoveryStatus.COMPATIBLE for item in ordered)
    incompatible = sum(item.status is PluginDiscoveryStatus.INCOMPATIBLE for item in ordered)
    invalid = sum(item.status is PluginDiscoveryStatus.INVALID for item in ordered)
    conflicts = sum(item.status is PluginDiscoveryStatus.CONFLICT for item in ordered)
    fields: dict[str, object] = {
        "plugin_api_version": PLUGIN_API_VERSION,
        "entry_point_group": PLUGIN_ENTRY_POINT_GROUP,
        "execution": "NOT_LOADED",
        "core_operational_without_plugins": True,
        "plugins": [item.model_dump(mode="json") for item in ordered],
        "total": len(ordered),
        "compatible": compatible,
        "incompatible": incompatible,
        "invalid": invalid,
        "conflicts": conflicts,
    }
    return PluginDiscoveryReport(
        report_id=sha256_fingerprint(fields),
        plugins=ordered,
        total=len(ordered),
        compatible=compatible,
        incompatible=incompatible,
        invalid=invalid,
        conflicts=conflicts,
    )


def _canonical_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    if len(values) != len(set(values)):
        raise ValueError("plugin manifest set-like fields cannot contain duplicates")
    return tuple(sorted(values))


def _canonical_enums[T: StrEnum](values: tuple[T, ...]) -> tuple[T, ...]:
    rendered = [item.value for item in values]
    if len(rendered) != len(set(rendered)):
        raise ValueError("plugin manifest set-like fields cannot contain duplicates")
    return tuple(sorted(values, key=lambda item: item.value))


def _manifest_identity(manifest: PluginManifest) -> dict[str, object]:
    return manifest.model_dump(mode="json", exclude={"schema_version", "manifest_id"})


def _report_identity(report: PluginDiscoveryReport) -> dict[str, object]:
    return report.model_dump(mode="json", exclude={"schema_version", "report_id"})


__all__ = [
    "PLUGIN_API_VERSION",
    "PLUGIN_ENTRY_POINT_GROUP",
    "PLUGIN_MANIFEST_FILENAME",
    "DiscoveredPlugin",
    "PluginCapability",
    "PluginDiscoveryIssue",
    "PluginDiscoveryReport",
    "PluginDiscoveryStatus",
    "PluginManifest",
    "PluginPermission",
    "create_plugin_discovery_report",
    "create_plugin_manifest",
]
