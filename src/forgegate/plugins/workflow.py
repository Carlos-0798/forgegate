from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Iterable, Mapping
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from forgegate.artifacts import ArtifactError, ArtifactRegistry
from forgegate.canonical import canonical_json
from forgegate.collectors.base import CollectionResult, CollectionStatus

from .broker import PluginBrokerRequest, WindowsPluginBroker
from .execution_models import (
    PluginExecutionTarget,
    PluginOutputDocument,
    PluginResourceLimits,
    PluginRunPage,
    PluginRunReceipt,
    PluginRunRecord,
    PluginRunState,
    PluginRunSubject,
    PluginRunSummary,
    create_plugin_run_page,
    create_plugin_run_plan,
    create_plugin_run_record,
)
from .models import PluginCapability, PluginDiscoveryStatus, PluginPermission
from .run_store import PluginRunSnapshot, SQLitePluginRunRepository
from .service import discover_plugins
from .windows_sandbox import WINDOWS_PODMAN_BACKEND, WINDOWS_PODMAN_BACKEND_VERSION


class PluginWorkflowError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def execute_operator_plugin_run(
    *,
    plugin_id: str,
    input_schema: str | None,
    input_media_types: Mapping[str, str],
    approved_permissions: tuple[PluginPermission, ...],
    artifact_root: Path,
    database_path: Path,
    work_root: Path,
    accepted_output_root: Path,
    sandbox_evidence_path: Path,
    idempotency_key: str,
    planned_at: datetime,
    podman_executable: Path | None = None,
    resource_limits: PluginResourceLimits | None = None,
    distributions: Iterable[metadata.Distribution] | None = None,
) -> PluginRunReceipt:
    """Discover one compatible collector, freeze authority, and invoke the broker."""

    installed = tuple(metadata.distributions() if distributions is None else distributions)
    target = _select_target(plugin_id, installed)
    manifest = target.manifest
    selected_schema = input_schema
    if selected_schema is None:
        if len(manifest.input_schemas) != 1:
            raise PluginWorkflowError(
                "PLUGIN_INPUT_SCHEMA_REQUIRED",
                "--input-schema is required when the plugin declares multiple schemas",
            )
        selected_schema = manifest.input_schemas[0]
    if not input_media_types:
        raise PluginWorkflowError("PLUGIN_INPUT_REQUIRED", "at least one --input is required")

    try:
        registry = ArtifactRegistry(artifact_root)
        subjects: list[PluginRunSubject] = []
        input_paths: dict[str, str] = {}
        for source_path, media_type in input_media_types.items():
            registered = registry.register(source_path, media_type=media_type)
            logical_name = registered.reference.path_or_uri
            if logical_name in input_paths:
                raise PluginWorkflowError(
                    "PLUGIN_INPUT_DUPLICATE", "plugin input paths must be unique"
                )
            subjects.append(
                PluginRunSubject(
                    name=logical_name,
                    media_type=registered.reference.media_type,
                    digest="sha256:" + registered.reference.sha256,
                    size_bytes=registered.reference.size_bytes,
                )
            )
            input_paths[logical_name] = logical_name
        permissions = tuple(sorted(set(approved_permissions), key=lambda item: item.value))
        plan = create_plugin_run_plan(
            target=target,
            input_schema=selected_schema,
            inputs=tuple(subjects),
            expected_output_evidence_kinds=manifest.output_evidence_kinds,
            approved_permissions=permissions,
            enforced_permissions=permissions,
            enforcement_backend=WINDOWS_PODMAN_BACKEND,
            enforcement_backend_version=WINDOWS_PODMAN_BACKEND_VERSION,
            resource_limits=resource_limits or PluginResourceLimits(),
            planned_at=planned_at,
        )
        _ensure_runtime_directory(database_path.parent, "plugin database parent")
        _ensure_runtime_directory(work_root, "plugin work root")
        _ensure_runtime_directory(accepted_output_root, "accepted output root")
        repository = SQLitePluginRunRepository(database_path)
        return WindowsPluginBroker(repository, distributions=installed).execute(
            PluginBrokerRequest(
                plan=plan,
                artifact_root=artifact_root,
                input_paths=input_paths,
                work_root=work_root,
                accepted_output_root=accepted_output_root,
                sandbox_evidence_path=sandbox_evidence_path,
                idempotency_key=idempotency_key,
                podman_executable=podman_executable,
            )
        )
    except PluginWorkflowError:
        raise
    except (ArtifactError, OSError, ValidationError, ValueError) as exc:
        raise PluginWorkflowError("PLUGIN_WORKFLOW_INVALID", str(exc)) from exc


def read_plugin_run(database_path: Path, run_plan_id: str) -> PluginRunRecord:
    repository = SQLitePluginRunRepository(database_path)
    repository.initialize()
    snapshot = repository.get(run_plan_id)
    return create_plugin_run_record(
        run_plan=snapshot.plan,
        transitions=snapshot.transitions,
        receipt=snapshot.receipt,
    )


def list_plugin_runs(
    database_path: Path,
    *,
    after_run_plan_id: str | None = None,
    limit: int = 100,
) -> PluginRunPage:
    repository = SQLitePluginRunRepository(database_path)
    repository.initialize()
    snapshots, next_cursor = repository.page(
        after_run_plan_id=after_run_plan_id,
        limit=limit,
    )
    return create_plugin_run_page(
        runs=tuple(_summarize(snapshot) for snapshot in snapshots),
        query_after_run_plan_id=after_run_plan_id,
        next_after_run_plan_id=next_cursor,
        limit=limit,
    )


def collect_plugin_evidence(
    database_path: Path,
    run_plan_id: str,
    *,
    artifact_root: Path,
    accepted_output_root: Path,
) -> CollectionResult:
    """Revalidate broker output and project it into the existing collection boundary."""

    repository = SQLitePluginRunRepository(database_path)
    repository.initialize()
    snapshot = repository.get(run_plan_id)
    receipt = snapshot.receipt
    if receipt is None or receipt.result.status is not PluginRunState.SUCCEEDED:
        raise PluginWorkflowError(
            "PLUGIN_RUN_NOT_SUCCESSFUL", "only a successful terminal plugin run can be collected"
        )
    expected = {item.subject.name: item for item in receipt.result.validated_outputs}
    target = _accepted_run_directory(accepted_output_root, run_plan_id)
    observed = _read_exact_output_tree(
        target,
        sum(item.subject.size_bytes for item in expected.values()),
    )
    if set(observed) != set(expected):
        raise PluginWorkflowError(
            "PLUGIN_OUTPUT_CHANGED",
            "accepted plugin output member set no longer matches the receipt",
        )

    registry = ArtifactRegistry(artifact_root)
    evidence = []
    artifacts = {}
    for name, validated in sorted(expected.items()):
        content = observed[name]
        if (
            len(content) != validated.subject.size_bytes
            or "sha256:" + hashlib.sha256(content).hexdigest() != validated.subject.digest
        ):
            raise PluginWorkflowError(
                "PLUGIN_OUTPUT_CHANGED", "accepted plugin output bytes no longer match the receipt"
            )
        try:
            raw = _strict_json(content)
            document = PluginOutputDocument.model_validate(raw)
        except (ValidationError, ValueError, TypeError) as exc:
            raise PluginWorkflowError(
                "PLUGIN_OUTPUT_CHANGED", "accepted plugin output no longer validates"
            ) from exc
        if canonical_json(document.model_dump(mode="json")).encode("utf-8") != content:
            raise PluginWorkflowError(
                "PLUGIN_OUTPUT_CHANGED", "accepted plugin output is no longer canonical"
            )
        record = document.evidence
        if (
            document.run_plan_id != run_plan_id
            or record.evidence_id != validated.evidence_id
            or record.kind != validated.evidence_kind
        ):
            raise PluginWorkflowError(
                "PLUGIN_OUTPUT_CHANGED", "accepted plugin output identity no longer matches"
            )
        registered = registry.register(
            record.artifact.path_or_uri,
            media_type=record.artifact.media_type,
        ).reference
        if registered != record.artifact:
            raise PluginWorkflowError(
                "PLUGIN_INPUT_CHANGED", "plugin evidence input bytes no longer match the run"
            )
        artifacts[registered.path_or_uri] = registered
        evidence.append(record)

    return CollectionResult(
        collector_name=f"plugin:{receipt.result.run_plan.target.manifest.plugin_id}",
        collector_version=receipt.result.run_plan.target.manifest.plugin_version,
        status=CollectionStatus.COMPLETE,
        artifacts=[artifacts[key] for key in sorted(artifacts)],
        evidence=sorted(evidence, key=lambda item: item.evidence_id),
    )


def _select_target(
    plugin_id: str,
    distributions: tuple[metadata.Distribution, ...],
) -> PluginExecutionTarget:
    report = discover_plugins(distributions)
    matches = [item for item in report.plugins if item.plugin_id == plugin_id]
    if len(matches) != 1:
        raise PluginWorkflowError(
            "PLUGIN_SELECTION_INVALID", "plugin ID must resolve to exactly one installed manifest"
        )
    selected = matches[0]
    if (
        selected.status is not PluginDiscoveryStatus.COMPATIBLE
        or selected.manifest is None
        or PluginCapability.COLLECTOR not in selected.manifest.capabilities
    ):
        raise PluginWorkflowError(
            "PLUGIN_SELECTION_INVALID", "selected plugin is not a compatible collector"
        )
    return PluginExecutionTarget(
        distribution_name=selected.distribution_name,
        distribution_version=selected.distribution_version,
        entry_point_name=selected.entry_point_name,
        entry_point_value=selected.entry_point_value,
        manifest=selected.manifest,
    )


def _summarize(snapshot: PluginRunSnapshot) -> PluginRunSummary:
    receipt = snapshot.receipt
    state = snapshot.transitions[-1].to_state
    issue = receipt.result.issue.code if receipt is not None and receipt.result.issue else None
    return PluginRunSummary(
        run_plan_id=snapshot.plan.run_plan_id,
        plugin_id=snapshot.plan.target.manifest.plugin_id,
        plugin_version=snapshot.plan.target.manifest.plugin_version,
        state=state,
        planned_at=snapshot.plan.planned_at,
        receipt_id=receipt.receipt_id if receipt is not None else None,
        issue=issue,
        output_count=len(receipt.result.validated_outputs) if receipt is not None else 0,
        accepted_outputs_registered=(
            receipt.accepted_outputs_registered if receipt is not None else False
        ),
    )


def _ensure_runtime_directory(path: Path, label: str) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_dir():
            raise PluginWorkflowError("PLUGIN_PATH_UNSAFE", f"{label} must be a real directory")
        return
    path.mkdir(parents=True)


def _accepted_run_directory(output_root: Path, run_plan_id: str) -> Path:
    if output_root.is_symlink() or not output_root.is_dir():
        raise PluginWorkflowError(
            "PLUGIN_PATH_UNSAFE", "accepted output root must be a real directory"
        )
    root = output_root.resolve(strict=True)
    target = root / ("plugin-run-" + run_plan_id.removeprefix("sha256:"))
    if target.is_symlink() or not target.is_dir():
        raise PluginWorkflowError(
            "PLUGIN_OUTPUT_UNAVAILABLE", "accepted output for this run is unavailable"
        )
    if target.resolve(strict=True).parent != root:
        raise PluginWorkflowError("PLUGIN_PATH_UNSAFE", "accepted output escapes its root")
    return target


def _read_exact_output_tree(root: Path, max_bytes: int) -> dict[str, bytes]:
    observed: dict[str, bytes] = {}
    total = 0
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise PluginWorkflowError("PLUGIN_PATH_UNSAFE", "accepted output contains a symlink")
        if candidate.is_dir():
            continue
        try:
            with candidate.open("rb") as handle:
                before = os.fstat(handle.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise PluginWorkflowError(
                        "PLUGIN_PATH_UNSAFE", "accepted output contains a non-regular file"
                    )
                content = handle.read(max_bytes + 1)
                after = os.fstat(handle.fileno())
        except OSError as exc:
            raise PluginWorkflowError(
                "PLUGIN_OUTPUT_UNAVAILABLE", "accepted output cannot be read"
            ) from exc
        if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
            raise PluginWorkflowError("PLUGIN_OUTPUT_CHANGED", "accepted output changed while read")
        total += len(content)
        if total > max_bytes:
            raise PluginWorkflowError(
                "PLUGIN_OUTPUT_CHANGED", "accepted output exceeds its receipt"
            )
        observed[candidate.relative_to(root).as_posix()] = content
    return observed


def _strict_json(content: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(_: str) -> None:
        raise ValueError("non-finite JSON number")

    return json.loads(
        content.decode("utf-8", errors="strict"),
        object_pairs_hook=pairs,
        parse_constant=constant,
    )


__all__ = [
    "PluginWorkflowError",
    "collect_plugin_evidence",
    "execute_operator_plugin_run",
    "list_plugin_runs",
    "read_plugin_run",
]
