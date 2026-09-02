from __future__ import annotations

import json
import sys
from importlib import metadata
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from forgegate.cli import app
from forgegate.config import load_config
from forgegate.plugins import (
    PLUGIN_API_VERSION,
    PLUGIN_ENTRY_POINT_GROUP,
    DiscoveredPlugin,
    PluginCapability,
    PluginDiscoveryError,
    PluginDiscoveryIssue,
    PluginDiscoveryReport,
    PluginDiscoveryStatus,
    PluginManifest,
    PluginPermission,
    create_plugin_discovery_report,
    create_plugin_manifest,
    discover_plugins,
)
from forgegate.plugins.service import DEFAULT_MAX_PLUGIN_MANIFEST_BYTES

runner = CliRunner()
PLUGIN_ID = "example.test-collector"
PACKAGE_NAME = "test_plugin"


def manifest(*, plugin_id: str = PLUGIN_ID, api_version: str = "1") -> PluginManifest:
    return create_plugin_manifest(
        plugin_id=plugin_id,
        display_name="Test Plugin",
        description="Generic import-free discovery test plugin.",
        plugin_version="1.2.3",
        forgegate_api_version=api_version,
        capabilities=(PluginCapability.COLLECTOR,),
        input_schemas=("example.test-input.v1",),
        permissions=(PluginPermission.ARTIFACT_READ,),
        output_evidence_kinds=("test.metric",),
    )


def install_metadata_distribution(
    root: Path,
    *,
    distribution_name: str = "forgegate-test-plugin",
    distribution_version: str = "1.2.3",
    entry_point_name: str = PLUGIN_ID,
    package_name: str = PACKAGE_NAME,
    entry_point_value: str | None = None,
    manifest_bytes: bytes | None = b"default",
) -> metadata.Distribution:
    package = root / package_name
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text(
        'raise RuntimeError("plugin discovery imported executable code")\n', encoding="utf-8"
    )
    relative_manifest = f"{package_name}/forgegate-plugin.json"
    if manifest_bytes == b"default":
        manifest_bytes = (
            manifest(plugin_id=entry_point_name).model_dump_json(indent=2) + "\n"
        ).encode()
    if manifest_bytes is not None:
        (package / "forgegate-plugin.json").write_bytes(manifest_bytes)

    normalized = distribution_name.replace("-", "_")
    dist_info = root / f"{normalized}-{distribution_version}.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.4\nName: {distribution_name}\nVersion: {distribution_version}\n",
        encoding="utf-8",
    )
    value = entry_point_value or f"{package_name}.runtime:plugin"
    (dist_info / "entry_points.txt").write_text(
        f"[{PLUGIN_ENTRY_POINT_GROUP}]\n{entry_point_name} = {value}\n", encoding="utf-8"
    )
    records = [
        f"{package_name}/__init__.py,,",
        f"{dist_info.name}/METADATA,,",
        f"{dist_info.name}/entry_points.txt,,",
        f"{dist_info.name}/RECORD,,",
    ]
    if manifest_bytes is not None:
        records.append(f"{relative_manifest},,")
    (dist_info / "RECORD").write_text("\n".join(records) + "\n", encoding="utf-8")
    matches = tuple(metadata.distributions(path=[str(root)]))
    assert len(matches) == 1
    return matches[0]


def test_manifest_factory_is_canonical_and_content_derived() -> None:
    created = create_plugin_manifest(
        plugin_id=PLUGIN_ID,
        display_name="Test Plugin",
        description="Generic import-free discovery test plugin.",
        plugin_version="1.2.3",
        forgegate_api_version="1",
        capabilities=(PluginCapability.EXPORTER, PluginCapability.COLLECTOR),
        input_schemas=("example.z-input.v1", "example.a-input.v1"),
        permissions=(PluginPermission.NETWORK, PluginPermission.ARTIFACT_READ),
        output_evidence_kinds=("test.z-metric", "test.a-metric"),
    )
    assert created.capabilities == (PluginCapability.COLLECTOR, PluginCapability.EXPORTER)
    assert created.input_schemas == ("example.a-input.v1", "example.z-input.v1")
    assert created.manifest_id.startswith("sha256:")
    with pytest.raises(ValidationError, match="manifest_id"):
        PluginManifest.model_validate({**created.model_dump(mode="json"), "description": "changed"})


@pytest.mark.parametrize(
    "change",
    [
        {"input_schemas": []},
        {"output_evidence_kinds": []},
        {"input_schemas": ["not-versioned"]},
        {"output_evidence_kinds": ["not_dotted"]},
        {"capabilities": ["collector", "collector"]},
    ],
)
def test_manifest_rejects_incomplete_or_ambiguous_collector_contracts(
    change: dict[str, object],
) -> None:
    payload = manifest().model_dump(mode="json")
    payload.update(change)
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(payload)


def test_manifest_factory_rejects_duplicate_set_values() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        create_plugin_manifest(
            plugin_id=PLUGIN_ID,
            display_name="Test Plugin",
            description="Duplicate schema test.",
            plugin_version="1.2.3",
            forgegate_api_version="1",
            capabilities=(PluginCapability.COLLECTOR,),
            input_schemas=("example.test-input.v1", "example.test-input.v1"),
            output_evidence_kinds=("test.metric",),
        )
    with pytest.raises(ValueError, match="duplicates"):
        create_plugin_manifest(
            plugin_id=PLUGIN_ID,
            display_name="Test Plugin",
            description="Duplicate capability test.",
            plugin_version="1.2.3",
            forgegate_api_version="1",
            capabilities=(PluginCapability.EXPORTER, PluginCapability.EXPORTER),
        )


def test_discovery_reads_valid_manifest_without_importing_plugin(tmp_path: Path) -> None:
    distribution = install_metadata_distribution(tmp_path)
    report = discover_plugins((distribution,))
    assert report.total == report.compatible == 1
    assert report.incompatible == report.invalid == report.conflicts == 0
    plugin = report.plugins[0]
    assert plugin.status is PluginDiscoveryStatus.COMPATIBLE
    assert plugin.execution == "NOT_LOADED"
    assert plugin.manifest == manifest()
    assert PACKAGE_NAME not in sys.modules


def test_discovery_reports_incompatible_api_without_loading_code(tmp_path: Path) -> None:
    payload = manifest(api_version="2").model_dump_json(indent=2).encode()
    distribution = install_metadata_distribution(tmp_path, manifest_bytes=payload)
    report = discover_plugins((distribution,))
    assert report.incompatible == 1
    assert report.plugins[0].issues[0].code == "PLUGIN_API_INCOMPATIBLE"
    assert PACKAGE_NAME not in sys.modules


@pytest.mark.parametrize(
    ("entry_point_name", "entry_point_value"),
    [
        ("invalid", "test_plugin.runtime:plugin"),
        (PLUGIN_ID, "../../unsafe:plugin"),
        (PLUGIN_ID, "test_plugin"),
    ],
)
def test_discovery_isolates_invalid_entry_point_metadata(
    tmp_path: Path, entry_point_name: str, entry_point_value: str
) -> None:
    distribution = install_metadata_distribution(
        tmp_path,
        entry_point_name=entry_point_name,
        entry_point_value=entry_point_value,
        manifest_bytes=None,
    )
    report = discover_plugins((distribution,))
    assert report.invalid == 1
    assert report.plugins[0].issues[0].code == "PLUGIN_ENTRY_POINT_INVALID"


def test_discovery_isolates_missing_manifest(tmp_path: Path) -> None:
    distribution = install_metadata_distribution(tmp_path, manifest_bytes=None)
    report = discover_plugins((distribution,))
    assert report.invalid == 1
    assert report.plugins[0].issues[0].code == "PLUGIN_MANIFEST_MISSING"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b'{"schema_version":"a","schema_version":"b"}', "PLUGIN_MANIFEST_DUPLICATE_KEY"),
        (b'{"value":NaN}', "PLUGIN_MANIFEST_NUMBER_INVALID"),
        (b'{"value":"bad\x00value"}', "PLUGIN_MANIFEST_ENCODING_INVALID"),
        (b"\xff", "PLUGIN_MANIFEST_ENCODING_INVALID"),
        (b"[1,2,3]", "PLUGIN_MANIFEST_ROOT_INVALID"),
        (b"{not-json}", "PLUGIN_MANIFEST_JSON_INVALID"),
    ],
)
def test_discovery_isolates_malformed_manifests(tmp_path: Path, content: bytes, code: str) -> None:
    distribution = install_metadata_distribution(tmp_path, manifest_bytes=content)
    report = discover_plugins((distribution,))
    assert report.invalid == 1
    assert report.plugins[0].issues[0].code == code


def test_discovery_isolates_contract_and_plugin_id_mismatch(tmp_path: Path) -> None:
    invalid_root = tmp_path / "invalid"
    invalid = install_metadata_distribution(
        invalid_root,
        manifest_bytes=json.dumps({"schema_version": "forgegate.plugin-manifest.v1"}).encode(),
    )
    mismatch_root = tmp_path / "mismatch"
    mismatch = install_metadata_distribution(
        mismatch_root,
        manifest_bytes=manifest(plugin_id="example.different-plugin").model_dump_json().encode(),
    )
    report = discover_plugins((invalid, mismatch))
    assert report.invalid == 2
    assert {plugin.issues[0].code for plugin in report.plugins} == {
        "PLUGIN_MANIFEST_CONTRACT_INVALID",
        "PLUGIN_ID_MISMATCH",
    }


def test_discovery_isolates_size_depth_and_node_limits(tmp_path: Path) -> None:
    large = install_metadata_distribution(
        tmp_path / "large",
        distribution_name="large-plugin",
        manifest_bytes=b"x" * (DEFAULT_MAX_PLUGIN_MANIFEST_BYTES + 1),
    )
    nested = install_metadata_distribution(
        tmp_path / "nested",
        distribution_name="nested-plugin",
        manifest_bytes=json.dumps({"a": {"b": {"c": 1}}}).encode(),
    )
    many = install_metadata_distribution(
        tmp_path / "many",
        distribution_name="many-plugin",
        manifest_bytes=json.dumps({"items": [1, 2, 3]}).encode(),
    )
    assert discover_plugins((large,)).plugins[0].issues[0].code == "PLUGIN_MANIFEST_UNAVAILABLE"
    assert (
        discover_plugins((nested,), max_manifest_depth=2).plugins[0].issues[0].code
        == "PLUGIN_MANIFEST_DEPTH_LIMIT"
    )
    assert (
        discover_plugins((many,), max_manifest_nodes=3).plugins[0].issues[0].code
        == "PLUGIN_MANIFEST_NODE_LIMIT"
    )


def test_discovery_marks_duplicate_plugin_ids_as_conflicts(tmp_path: Path) -> None:
    first = install_metadata_distribution(
        tmp_path / "first", distribution_name="first-plugin", package_name="first_plugin"
    )
    second = install_metadata_distribution(
        tmp_path / "second", distribution_name="second-plugin", package_name="second_plugin"
    )
    report = discover_plugins((second, first))
    assert report.conflicts == 2
    assert report.compatible == 0
    assert all(plugin.issues[0].code == "PLUGIN_ID_CONFLICT" for plugin in report.plugins)
    assert [plugin.distribution_name for plugin in report.plugins] == [
        "first-plugin",
        "second-plugin",
    ]


def test_discovered_plugin_status_contracts_fail_closed(tmp_path: Path) -> None:
    distribution = install_metadata_distribution(tmp_path)
    valid = discover_plugins((distribution,)).plugins[0]
    payload = valid.model_dump(mode="json")
    issue = PluginDiscoveryIssue(code="PLUGIN_TEST_INVALID", message="test issue")

    with pytest.raises(ValidationError, match="requires a valid manifest"):
        DiscoveredPlugin.model_validate({**payload, "manifest": None, "plugin_id": None})
    with pytest.raises(ValidationError, match="compatibility issues"):
        DiscoveredPlugin.model_validate({**payload, "issues": [issue.model_dump(mode="json")]})
    with pytest.raises(ValidationError, match="must explain"):
        DiscoveredPlugin.model_validate({**payload, "status": "INCOMPATIBLE"})
    with pytest.raises(ValidationError, match="require a valid manifest"):
        DiscoveredPlugin.model_validate(
            {
                **payload,
                "status": "CONFLICT",
                "manifest": None,
                "plugin_id": None,
                "issues": [issue.model_dump(mode="json")],
            }
        )
    with pytest.raises(ValidationError, match="cannot retain"):
        DiscoveredPlugin.model_validate(
            {**payload, "status": "INVALID", "issues": [issue.model_dump(mode="json")]}
        )


def test_discovery_report_order_counts_and_identity_fail_closed(tmp_path: Path) -> None:
    first = install_metadata_distribution(
        tmp_path / "first",
        distribution_name="first-plugin",
        entry_point_name="example.first-plugin",
        package_name="first_plugin",
    )
    second = install_metadata_distribution(
        tmp_path / "second",
        distribution_name="second-plugin",
        entry_point_name="example.second-plugin",
        package_name="second_plugin",
    )
    report = discover_plugins((first, second))
    payload = report.model_dump(mode="json")
    with pytest.raises(ValidationError, match="deterministic order"):
        PluginDiscoveryReport.model_validate(
            {**payload, "plugins": list(reversed(payload["plugins"]))}
        )
    with pytest.raises(ValidationError, match="total"):
        PluginDiscoveryReport.model_validate({**payload, "total": 3})
    with pytest.raises(ValidationError, match="status counts"):
        PluginDiscoveryReport.model_validate({**payload, "compatible": 1, "invalid": 1})
    with pytest.raises(ValidationError, match="report_id"):
        PluginDiscoveryReport.model_validate({**payload, "report_id": "sha256:" + "0" * 64})
    assert create_plugin_discovery_report(tuple(reversed(report.plugins))) == report


def test_discovery_ignores_unrelated_and_broken_distribution_metadata() -> None:
    class BrokenMetadataDistribution:
        @property
        def metadata(self) -> object:
            raise ValueError("bad metadata")

        @property
        def version(self) -> str:
            raise ValueError("bad version")

        @property
        def entry_points(self) -> tuple[metadata.EntryPoint, ...]:
            return (metadata.EntryPoint(name="ignored", value="ignored:entry", group="other"),)

    class BrokenEntryPointsDistribution:
        version = "1.0.0"

        @property
        def metadata(self) -> dict[str, str]:
            return {"Name": "broken-entry-points"}

        @property
        def entry_points(self) -> tuple[metadata.EntryPoint, ...]:
            raise ValueError("bad entry points")

    report = discover_plugins(  # type: ignore[arg-type]
        (BrokenMetadataDistribution(), BrokenEntryPointsDistribution())
    )
    assert report.total == 0


def test_discovery_rejects_symlink_manifest_when_supported(tmp_path: Path) -> None:
    distribution = install_metadata_distribution(tmp_path)
    manifest_path = tmp_path / PACKAGE_NAME / "forgegate-plugin.json"
    target = tmp_path / PACKAGE_NAME / "target.json"
    target.write_text(manifest().model_dump_json(), encoding="utf-8")
    manifest_path.unlink()
    try:
        manifest_path.symlink_to(target)
    except OSError:
        pytest.skip("host does not permit symlink creation")
    report = discover_plugins((distribution,))
    assert report.plugins[0].issues[0].code == "PLUGIN_MANIFEST_UNSAFE"


def test_discovery_rejects_invalid_limits_and_metadata_enumeration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="limits must be positive"):
        discover_plugins((), max_manifest_depth=0)

    def unavailable() -> tuple[metadata.Distribution, ...]:
        raise OSError("private host detail")

    monkeypatch.setattr("forgegate.plugins.service.metadata.distributions", unavailable)
    with pytest.raises(PluginDiscoveryError, match="metadata is unavailable") as raised:
        discover_plugins()
    assert raised.value.code == "PLUGIN_DISCOVERY_UNAVAILABLE"
    assert "private host detail" not in str(raised.value)
    monkeypatch.undo()

    first = install_metadata_distribution(
        tmp_path / "first", distribution_name="first-plugin", package_name="first_plugin"
    )
    second = install_metadata_distribution(
        tmp_path / "second",
        distribution_name="second-plugin",
        entry_point_name="example.second-plugin",
        package_name="second_plugin",
    )
    with pytest.raises(PluginDiscoveryError) as distribution_limit:
        discover_plugins((first, second), max_distributions=1)
    assert distribution_limit.value.code == "PLUGIN_DISTRIBUTION_LIMIT"
    with pytest.raises(PluginDiscoveryError) as entry_limit:
        discover_plugins((first, second), max_plugin_entries=1)
    assert entry_limit.value.code == "PLUGIN_ENTRY_LIMIT"
    file_limit = discover_plugins((first,), max_distribution_files=1)
    assert file_limit.plugins[0].issues[0].code == "PLUGIN_DISTRIBUTION_FILE_LIMIT"


def test_plugins_list_cli_and_versioned_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    distribution = install_metadata_distribution(tmp_path)
    monkeypatch.setattr("forgegate.plugins.service.metadata.distributions", lambda: (distribution,))
    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "forgegate.plugin-discovery.v1"
    assert payload["plugin_api_version"] == PLUGIN_API_VERSION
    assert payload["execution"] == "NOT_LOADED"
    assert payload["plugins"][0]["status"] == "COMPATIBLE"


def test_plugins_list_cli_sanitizes_system_discovery_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail() -> None:
        raise PluginDiscoveryError("PLUGIN_DISCOVERY_UNAVAILABLE", "metadata unavailable")

    monkeypatch.setattr("forgegate.cli.discover_plugins", fail)
    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 3
    assert "metadata unavailable" in result.output


def test_empty_environment_keeps_core_operational(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("forgegate.plugins.service.metadata.distributions", lambda: ())
    listed = runner.invoke(app, ["plugins", "list"])
    doctor = runner.invoke(app, ["doctor"])
    assert listed.exit_code == doctor.exit_code == 0
    assert json.loads(listed.stdout)["core_operational_without_plugins"] is True
    assert json.loads(listed.stdout)["total"] == 0
    assert json.loads(doctor.stdout)["phase"] == "phase18-windows-sandbox-readiness"


def test_committed_sample_manifest_matches_sdk_contract(repository_root: Path) -> None:
    sample = (
        repository_root
        / "examples/plugin-sdk/sample-collector-plugin/src/forgegate_sample_collector"
        / "forgegate-plugin.json"
    )
    loaded = load_config(sample)
    assert isinstance(loaded, PluginManifest)
    assert loaded.plugin_id == "example.forgegate-sample-collector"
    assert loaded.forgegate_api_version == PLUGIN_API_VERSION
