from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from forgegate.canonical import canonical_json
from forgegate.plugins import (
    PLUGIN_ENTRY_POINT_GROUP,
    WINDOWS_PODMAN_BACKEND,
    WINDOWS_PODMAN_BACKEND_VERSION,
    PluginBrokerRequest,
    PluginDiscoveryStatus,
    PluginExecutionTarget,
    PluginPermission,
    PluginResourceLimits,
    PluginRunState,
    PluginRunSubject,
    SQLitePluginRunRepository,
    WindowsPluginBroker,
    create_plugin_run_plan,
    discover_plugins,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DISTRIBUTION = "forgegate-sample-collector-plugin"
PLUGIN_ID = "example.forgegate-sample-collector"
DEFAULT_EVIDENCE = REPOSITORY_ROOT / "reports/PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json"


class LiveBrokerVerificationError(RuntimeError):
    pass


def _installed_distribution() -> metadata.Distribution:
    matches: list[metadata.Distribution] = []
    for distribution in metadata.distributions():
        try:
            if distribution.metadata.get("Name") == PLUGIN_DISTRIBUTION:
                matches.append(distribution)
        except Exception:
            continue
    if len(matches) != 1:
        raise LiveBrokerVerificationError(
            "install exactly one forgegate-sample-collector-plugin distribution"
        )
    return matches[0]


def _target(distribution: metadata.Distribution) -> PluginExecutionTarget:
    report = discover_plugins((distribution,))
    if report.total != 1 or report.plugins[0].status is not PluginDiscoveryStatus.COMPATIBLE:
        raise LiveBrokerVerificationError("sample plugin is not compatible")
    plugin = report.plugins[0]
    if plugin.plugin_id != PLUGIN_ID or plugin.manifest is None:
        raise LiveBrokerVerificationError("unexpected sample plugin identity")
    entry_points = [
        item
        for item in distribution.entry_points
        if item.group == PLUGIN_ENTRY_POINT_GROUP and item.name == PLUGIN_ID
    ]
    if len(entry_points) != 1:
        raise LiveBrokerVerificationError("sample plugin entry point is ambiguous")
    return PluginExecutionTarget(
        distribution_name=str(distribution.metadata["Name"]),
        distribution_version=str(distribution.version),
        entry_point_name=PLUGIN_ID,
        entry_point_value=entry_points[0].value,
        manifest=plugin.manifest,
    )


def verify_live_broker(
    *, evidence_path: Path = DEFAULT_EVIDENCE, podman: Path | None = None
) -> dict[str, Any]:
    distribution = _installed_distribution()
    target = _target(distribution)
    started_at = datetime.now(UTC)
    input_payload = canonical_json(
        {
            "collected_at": started_at.isoformat().replace("+00:00", "Z"),
            "commit_sha": "a" * 40,
        }
    ).encode("utf-8")
    subject = PluginRunSubject(
        name="inputs/synthetic.json",
        media_type="application/json",
        digest="sha256:" + hashlib.sha256(input_payload).hexdigest(),
        size_bytes=len(input_payload),
    )
    permissions = (PluginPermission.ARTIFACT_READ, PluginPermission.FILESYSTEM_WRITE)
    plan = create_plugin_run_plan(
        target=target,
        input_schema="example.sample-input.v1",
        inputs=(subject,),
        expected_output_evidence_kinds=("sample.metric",),
        approved_permissions=permissions,
        enforced_permissions=permissions,
        enforcement_backend=WINDOWS_PODMAN_BACKEND,
        enforcement_backend_version=WINDOWS_PODMAN_BACKEND_VERSION,
        resource_limits=PluginResourceLimits(
            startup_timeout_ms=10_000,
            total_timeout_ms=30_000,
            cpu_time_ms=10_000,
            memory_bytes=134_217_728,
            output_bytes=1_048_576,
            file_count=8,
            stdout_bytes=65_536,
            stderr_bytes=65_536,
        ),
        planned_at=started_at,
    )
    with tempfile.TemporaryDirectory(prefix="forgegate-live-broker-") as raw_root:
        root = Path(raw_root)
        artifacts = root / "artifacts"
        work = root / "work"
        outputs = root / "outputs"
        for directory in (artifacts, work, outputs):
            directory.mkdir()
        (artifacts / "synthetic.json").write_bytes(input_payload)
        repository = SQLitePluginRunRepository(root / "plugin-runs.db")
        receipt = WindowsPluginBroker(repository, distributions=(distribution,)).execute(
            PluginBrokerRequest(
                plan=plan,
                artifact_root=artifacts,
                input_paths={subject.name: "synthetic.json"},
                work_root=work,
                accepted_output_root=outputs,
                sandbox_evidence_path=evidence_path,
                idempotency_key="phase20:live-sample:v1",
                podman_executable=podman,
            )
        )
        replay = WindowsPluginBroker(repository, distributions=(distribution,)).execute(
            PluginBrokerRequest(
                plan=plan,
                artifact_root=artifacts,
                input_paths={subject.name: "synthetic.json"},
                work_root=work,
                accepted_output_root=outputs,
                sandbox_evidence_path=evidence_path,
                idempotency_key="phase20:live-sample:v1",
                podman_executable=podman,
            )
        )
        if receipt != replay or receipt.result.status is not PluginRunState.SUCCEEDED:
            issue = receipt.result.issue.code.value if receipt.result.issue is not None else "NONE"
            raise LiveBrokerVerificationError(
                f"production broker run or replay did not succeed: {issue}"
            )
        accepted = tuple(outputs.rglob("*.json"))
        if len(accepted) != 1:
            raise LiveBrokerVerificationError("broker did not register exactly one output")
        output = json.loads(accepted[0].read_bytes())
        observations = output["evidence"]["value"]
        checks = {
            "input_read": observations.get("input_read") is True,
            "input_write_denied": observations.get("input_write_denied") is True,
            "root_write_denied": observations.get("root_write_denied") is True,
            "host_read_denied": observations.get("host_read_denied") is True,
            "network_denied": observations.get("network_denied") is True,
            "subprocess_denied": observations.get("subprocess_denied") is True,
            "environment_sanitized": observations.get("environment_keys")
            == ["FORGEGATE_RUN_PLAN_ID", "LC_CTYPE"],
            "protocol_complete": [item.kind.value for item in receipt.protocol_messages]
            == ["START", "READY", "RESULT"],
            "double_snapshot_validated": receipt.accepted_outputs_registered,
            "cleanup_verified": receipt.cleanup.container_removed
            and receipt.cleanup.staging_removed,
            "durable_replay_exact": replay.receipt_id == receipt.receipt_id,
            "low_trust_output": output["evidence"]["trust"] == "unsigned_local"
            and output["evidence"]["verification_level"] == "declared",
        }
        store_snapshot = repository.get(plan.run_plan_id)
        checks["durable_store_readback"] = store_snapshot.receipt == receipt
    report: dict[str, Any] = {
        "report_format": "forgegate.windows-production-plugin-broker-verification.v1",
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "plugin_distribution": PLUGIN_DISTRIBUTION,
        "plugin_id": PLUGIN_ID,
        "run_plan_id": plan.run_plan_id,
        "receipt": receipt.model_dump(mode="json"),
        "checks": [{"control": name, "passed": passed} for name, passed in sorted(checks.items())],
        "production_broker_verified": all(checks.values()),
        "advertised_isolation_tier": "SANDBOXED" if all(checks.values()) else "NONE",
        "evidence_level": "LOCAL_HOST_TEST",
        "hardware_access": "NOT_PERFORMED",
        "limitations": [
            "The executed plugin is the ForgeGate-owned generic package fixture.",
            "The accepted evidence remains unsigned_local and declared.",
            "Linux and macOS external-plugin execution remain unsupported.",
        ],
    }
    report["verification_id"] = (
        "sha256:" + hashlib.sha256(canonical_json(report).encode("utf-8")).hexdigest()
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute the installed generic plugin through the production Windows broker."
    )
    parser.add_argument("--sandbox-evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--podman", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        report = verify_live_broker(
            evidence_path=arguments.sandbox_evidence,
            podman=arguments.podman,
        )
    except (LiveBrokerVerificationError, ValueError, OSError) as exc:
        print(f"Windows production plugin broker verification: ERROR ({exc})")
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if arguments.output is not None:
        arguments.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if report["production_broker_verified"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
