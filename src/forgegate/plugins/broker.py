from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, BinaryIO

from pydantic import ValidationError

from forgegate.artifacts import ArtifactError, ArtifactRegistry
from forgegate.bounded_parsing import enforce_json_structure_limits
from forgegate.canonical import canonical_json
from forgegate.plugins.execution_models import (
    PluginCleanupResult,
    PluginExecutionSummary,
    PluginOutputDocument,
    PluginProtocolDirection,
    PluginProtocolMessage,
    PluginProtocolMessageKind,
    PluginRunIssue,
    PluginRunIssueCode,
    PluginRunPlan,
    PluginRunReceipt,
    PluginRunState,
    PluginRunSubject,
    PluginValidatedOutput,
    create_plugin_protocol_message,
    create_plugin_run_receipt,
    create_plugin_run_result,
    create_plugin_run_transition,
    create_plugin_validated_output,
    plugin_output_set_id,
)
from forgegate.plugins.models import PLUGIN_ENTRY_POINT_GROUP, PluginManifest
from forgegate.plugins.run_store import PluginRunSnapshot, SQLitePluginRunRepository
from forgegate.plugins.windows_sandbox import (
    REQUIRED_WINDOWS_SANDBOX_CONTROLS,
    WINDOWS_PODMAN_BACKEND,
    WINDOWS_PODMAN_BACKEND_VERSION,
    WINDOWS_SANDBOX_PROBE_IMAGE,
    WindowsSandboxCapabilityReport,
    WindowsSandboxCapabilityStatus,
    build_windows_podman_create_command,
    probe_windows_podman_sandbox,
)

MAX_PLUGIN_PACKAGE_BYTES = 16 * 1024 * 1024
MAX_PLUGIN_PACKAGE_FILES = 2_048
MAX_MANAGEMENT_BYTES = 2 * 1024 * 1024
MAX_MANAGEMENT_NODES = 100_000
MAX_MANAGEMENT_DEPTH = 64
PLUGIN_OUTPUT_MEDIA_TYPE = "application/vnd.forgegate.plugin-output+json"
CONTAINER_PREFIX = "forgegate-"
NATIVE_SUFFIXES = frozenset({".dll", ".dylib", ".exe", ".pyd", ".so"})


class PluginBrokerError(ValueError):
    def __init__(self, code: PluginRunIssueCode, message: str) -> None:
        super().__init__(f"{code.value}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class PluginBrokerRequest:
    plan: PluginRunPlan
    artifact_root: Path
    input_paths: Mapping[str, str]
    work_root: Path
    accepted_output_root: Path
    sandbox_evidence_path: Path
    idempotency_key: str
    podman_executable: Path | None = None


@dataclass(frozen=True, slots=True)
class WindowsBrokerAuthorization:
    capability: WindowsSandboxCapabilityReport
    podman_executable: Path
    image: str
    image_id: str


@dataclass(frozen=True, slots=True)
class SandboxObservation:
    ready_bytes: bytes | None
    terminal_bytes: bytes | None
    first_snapshot: Mapping[str, bytes]
    second_snapshot: Mapping[str, bytes]
    execution: PluginExecutionSummary
    container_removed: bool
    issue: PluginRunIssueCode | None = None


type BackendAuthorizer = Callable[[PluginBrokerRequest], WindowsBrokerAuthorization]
type ReadyObserver = Callable[[bytes], None]
type SandboxExecutor = Callable[
    [
        tuple[str, ...],
        WindowsBrokerAuthorization,
        str,
        PluginRunPlan,
        Path,
        ReadyObserver,
    ],
    SandboxObservation,
]


class WindowsPluginBroker:
    """Trusted host broker for one external collector inside the Windows sandbox."""

    def __init__(
        self,
        repository: SQLitePluginRunRepository,
        *,
        authorizer: BackendAuthorizer | None = None,
        executor: SandboxExecutor | None = None,
        clock: Callable[[], datetime] | None = None,
        distributions: Iterable[metadata.Distribution] | None = None,
    ) -> None:
        self.repository = repository
        self.authorizer = authorizer or authorize_windows_broker
        self.executor = executor or _execute_windows_container
        self.clock = clock or (lambda: datetime.now(UTC))
        self.distributions = distributions

    def execute(self, request: PluginBrokerRequest) -> PluginRunReceipt:
        plan = request.plan
        if (
            plan.enforcement_backend != WINDOWS_PODMAN_BACKEND
            or plan.enforcement_backend_version != WINDOWS_PODMAN_BACKEND_VERSION
        ):
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_PERMISSION_UNENFORCEABLE,
                "run plan does not select the production Windows backend",
            )
        self.repository.initialize()
        planned = create_plugin_run_transition(
            run_plan_id=plan.run_plan_id,
            sequence=0,
            from_state=None,
            to_state=PluginRunState.PLANNED,
            occurred_at=plan.planned_at,
        )
        reservation = self.repository.reserve(
            plan, planned, idempotency_key=request.idempotency_key
        )
        if not reservation.created:
            if reservation.snapshot.receipt is not None:
                return reservation.snapshot.receipt
            return self._recover_interrupted(reservation.snapshot, request)

        run_root = _run_root(request.work_root, plan.run_plan_id)
        container_name = _container_name(plan.run_plan_id)
        messages: list[PluginProtocolMessage] = []
        observation = _empty_observation()
        staging_removed = False
        accepted = False
        issue: PluginRunIssueCode | None = None
        validated_outputs: tuple[PluginValidatedOutput, ...] = ()
        terminal_protocol_id: str | None = None
        try:
            authorization = self.authorizer(request)
            input_root, control_root = _prepare_staging(
                run_root,
                request,
                distributions=self.distributions,
            )
            start = create_plugin_protocol_message(
                run_plan_id=plan.run_plan_id,
                sequence=0,
                direction=PluginProtocolDirection.CORE_TO_PLUGIN,
                kind=PluginProtocolMessageKind.START,
                run_plan=plan,
            )
            _write_exclusive(
                control_root / "start.json",
                canonical_json(start.model_dump(mode="json")).encode("utf-8"),
            )
            messages.append(start)
            snapshot = self.repository.append_transition(
                create_plugin_run_transition(
                    run_plan_id=plan.run_plan_id,
                    sequence=1,
                    from_state=PluginRunState.PLANNED,
                    to_state=PluginRunState.STARTING,
                    occurred_at=self._now(),
                    previous_transition_id=planned.transition_id,
                    protocol_message_id=start.message_id,
                )
            )

            ready_message: PluginProtocolMessage | None = None

            def ready_observed(content: bytes) -> None:
                nonlocal snapshot, ready_message
                ready_message = _load_protocol_message(content)
                if (
                    ready_message.run_plan_id != plan.run_plan_id
                    or ready_message.kind is not PluginProtocolMessageKind.READY
                ):
                    raise PluginBrokerError(
                        PluginRunIssueCode.PLUGIN_PROTOCOL_INVALID,
                        "runner READY message does not match the run plan",
                    )
                messages.append(ready_message)
                previous = snapshot.transitions[-1]
                snapshot = self.repository.append_transition(
                    create_plugin_run_transition(
                        run_plan_id=plan.run_plan_id,
                        sequence=2,
                        from_state=PluginRunState.STARTING,
                        to_state=PluginRunState.RUNNING,
                        occurred_at=self._now(),
                        previous_transition_id=previous.transition_id,
                        protocol_message_id=ready_message.message_id,
                    )
                )

            command = build_windows_podman_create_command(
                authorization.capability,
                plan,
                podman_executable=authorization.podman_executable,
                container_name=container_name,
                image=authorization.image,
                input_directory=input_root,
                control_directory=control_root,
                runner_argv=(
                    "/usr/local/bin/python",
                    "-I",
                    "-S",
                    "/forgegate/control/trusted_runner.py",
                ),
            )
            observation = self.executor(
                command,
                authorization,
                container_name,
                plan,
                run_root,
                ready_observed,
            )
            if observation.issue is not None:
                issue = observation.issue
            elif ready_message is None or observation.terminal_bytes is None:
                issue = PluginRunIssueCode.PLUGIN_PROTOCOL_INVALID
            else:
                terminal = _load_protocol_message(observation.terminal_bytes)
                if terminal.run_plan_id != plan.run_plan_id or terminal.sequence != 2:
                    raise PluginBrokerError(
                        PluginRunIssueCode.PLUGIN_PROTOCOL_INVALID,
                        "runner terminal message does not match the run plan",
                    )
                messages.append(terminal)
                terminal_protocol_id = terminal.message_id
                if terminal.kind is PluginProtocolMessageKind.ERROR:
                    assert terminal.issue is not None
                    issue = terminal.issue.code
                elif terminal.kind is not PluginProtocolMessageKind.RESULT:
                    issue = PluginRunIssueCode.PLUGIN_PROTOCOL_INVALID
                else:
                    validated_outputs = _validate_output_snapshots(
                        plan,
                        terminal,
                        observation.first_snapshot,
                        observation.second_snapshot,
                    )
                    accepted = _register_outputs(
                        request.accepted_output_root,
                        plan.run_plan_id,
                        observation.first_snapshot,
                        validated_outputs,
                    )
        except PluginBrokerError as exc:
            issue = exc.code
        except (ArtifactError, OSError, ValidationError, ValueError):
            issue = PluginRunIssueCode.PLUGIN_PLAN_INVALID
        finally:
            staging_removed = _remove_staging(run_root)

        if not observation.container_removed or not staging_removed:
            issue = PluginRunIssueCode.PLUGIN_CLEANUP_FAILED
            accepted = False
            validated_outputs = ()
        if issue is None and not accepted:
            issue = PluginRunIssueCode.PLUGIN_OUTPUT_INVALID
        return self._finish(
            plan,
            messages=tuple(messages),
            issue=issue,
            validated_outputs=validated_outputs,
            terminal_protocol_id=terminal_protocol_id,
            execution=observation.execution,
            cleanup=PluginCleanupResult(
                container_removed=observation.container_removed,
                staging_removed=staging_removed,
            ),
            accepted=accepted,
            recovered=False,
        )

    def _recover_interrupted(
        self, snapshot: PluginRunSnapshot, request: PluginBrokerRequest
    ) -> PluginRunReceipt:
        plan = snapshot.plan
        container_removed = _remove_abandoned_container(
            request.podman_executable, _container_name(plan.run_plan_id)
        )
        staging_removed = _remove_staging(_run_root(request.work_root, plan.run_plan_id))
        issue = (
            PluginRunIssueCode.PLUGIN_EXIT_ERROR
            if container_removed and staging_removed
            else PluginRunIssueCode.PLUGIN_CLEANUP_FAILED
        )
        return self._finish(
            plan,
            messages=(),
            issue=issue,
            validated_outputs=(),
            terminal_protocol_id=None,
            execution=PluginExecutionSummary(
                runner_started=len(snapshot.transitions) > 1,
                ready_observed=snapshot.transitions[-1].to_state is PluginRunState.RUNNING,
                completion_observed=False,
                elapsed_ms=0,
                stdout_bytes=0,
                stderr_bytes=0,
            ),
            cleanup=PluginCleanupResult(
                container_removed=container_removed,
                staging_removed=staging_removed,
            ),
            accepted=False,
            recovered=True,
        )

    def _finish(
        self,
        plan: PluginRunPlan,
        *,
        messages: tuple[PluginProtocolMessage, ...],
        issue: PluginRunIssueCode | None,
        validated_outputs: tuple[PluginValidatedOutput, ...],
        terminal_protocol_id: str | None,
        execution: PluginExecutionSummary,
        cleanup: PluginCleanupResult,
        accepted: bool,
        recovered: bool,
    ) -> PluginRunReceipt:
        snapshot = self.repository.get(plan.run_plan_id)
        previous = snapshot.transitions[-1]
        succeeded = issue is None
        output_set_id = plugin_output_set_id(validated_outputs) if succeeded else None
        terminal = create_plugin_run_transition(
            run_plan_id=plan.run_plan_id,
            sequence=len(snapshot.transitions),
            from_state=previous.to_state,
            to_state=PluginRunState.SUCCEEDED if succeeded else PluginRunState.ERROR,
            occurred_at=self._now(),
            previous_transition_id=previous.transition_id,
            protocol_message_id=terminal_protocol_id,
            output_set_id=output_set_id,
            issue=PluginRunIssue(code=issue) if issue is not None else None,
        )
        transitions = (*snapshot.transitions, terminal)
        result = create_plugin_run_result(
            run_plan=plan,
            status=PluginRunState.SUCCEEDED if succeeded else PluginRunState.ERROR,
            transitions=transitions,
            validated_outputs=validated_outputs,
            issue=PluginRunIssue(code=issue) if issue is not None else None,
        )
        receipt = create_plugin_run_receipt(
            result=result,
            protocol_messages=tuple(
                message
                for message in messages
                if message.message_id
                in {
                    transition.protocol_message_id
                    for transition in transitions
                    if transition.protocol_message_id is not None
                }
            ),
            execution=execution,
            cleanup=cleanup,
            accepted_outputs_registered=accepted,
            recovered_after_interruption=recovered,
        )
        return self.repository.complete(receipt)

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_AUDIT_FAILED, "broker clock must be timezone-aware"
            )
        return value.astimezone(UTC)


def authorize_windows_broker(
    request: PluginBrokerRequest,
) -> WindowsBrokerAuthorization:  # pragma: no cover - exercised by Windows live verification
    evidence = _load_json_file(request.sandbox_evidence_path, MAX_MANAGEMENT_BYTES)
    if not isinstance(evidence, dict):
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE,
            "sandbox verification evidence must be an object",
        )
    verification_id = evidence.get("verification_id")
    identity = {key: value for key, value in evidence.items() if key != "verification_id"}
    expected_id = "sha256:" + hashlib.sha256(canonical_json(identity).encode()).hexdigest()
    checks = evidence.get("checks")
    observed = (
        {
            item.get("control")
            for item in checks
            if isinstance(item, dict) and item.get("passed") is True
        }
        if isinstance(checks, list)
        else set()
    )
    required = {item.value for item in REQUIRED_WINDOWS_SANDBOX_CONTROLS}
    if (
        verification_id != expected_id
        or evidence.get("backend") != WINDOWS_PODMAN_BACKEND
        or evidence.get("backend_contract_version") != WINDOWS_PODMAN_BACKEND_VERSION
        or evidence.get("image") != WINDOWS_SANDBOX_PROBE_IMAGE
        or evidence.get("backend_enforcement_verified") is not True
        or observed != required
    ):
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE,
            "sandbox verification evidence is incomplete or invalid",
        )
    podman = _podman_path(request.podman_executable)
    capability = probe_windows_podman_sandbox(podman_executable=str(podman))
    if (
        capability.status is not WindowsSandboxCapabilityStatus.READY_FOR_ADVERSARIAL_VERIFICATION
        or capability.capability_id != evidence.get("capability_id")
        or capability.runtime_version != evidence.get("runtime_client_version")
        or capability.server_runtime_version != evidence.get("runtime_server_version")
    ):
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE,
            "current Podman capability does not match verified evidence",
        )
    image_id = _inspect_image(podman, WINDOWS_SANDBOX_PROBE_IMAGE)
    if image_id != evidence.get("image_id"):
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE,
            "local runner image does not match verified evidence",
        )
    return WindowsBrokerAuthorization(
        capability=capability,
        podman_executable=podman,
        image=WINDOWS_SANDBOX_PROBE_IMAGE,
        image_id=image_id,
    )


def _prepare_staging(
    run_root: Path,
    request: PluginBrokerRequest,
    *,
    distributions: Iterable[metadata.Distribution] | None,
) -> tuple[Path, Path]:
    work_root = _safe_directory(request.work_root, "work")
    _safe_directory(request.accepted_output_root, "accepted output")
    if run_root.exists():
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_START_FAILED, "broker staging directory already exists"
        )
    run_root.mkdir(mode=0o700)
    if run_root.parent != work_root:
        raise PluginBrokerError(PluginRunIssueCode.PLUGIN_START_FAILED, "invalid staging root")
    input_root = run_root / "input"
    control_root = run_root / "control"
    input_root.mkdir(mode=0o700)
    control_root.mkdir(mode=0o700)
    _stage_inputs(request.plan, request.artifact_root, request.input_paths, input_root)
    _stage_plugin(request.plan, control_root / "plugin", distributions)
    for source_name, target_name in (
        ("_trusted_runner.py", "trusted_runner.py"),
        ("_trusted_exporter.py", "trusted_exporter.py"),
    ):
        source = Path(__file__).with_name(source_name)
        _write_exclusive(control_root / target_name, _read_regular(source, 512 * 1024))
    return input_root, control_root


def _stage_inputs(
    plan: PluginRunPlan,
    artifact_root: Path,
    input_paths: Mapping[str, str],
    input_root: Path,
) -> None:
    expected_names = {subject.name for subject in plan.inputs}
    if set(input_paths) != expected_names:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_PLAN_INVALID, "input mapping does not match the run plan"
        )
    registry = ArtifactRegistry(
        artifact_root,
        max_bytes=max(subject.size_bytes for subject in plan.inputs),
    )
    for subject in plan.inputs:
        registered = registry.register(input_paths[subject.name], media_type=subject.media_type)
        if (
            registered.reference.size_bytes != subject.size_bytes
            or "sha256:" + registered.reference.sha256 != subject.digest
        ):
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_PLAN_INVALID,
                "input bytes do not match the content-addressed run plan",
            )
        target = input_root / Path(subject.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_exclusive(target, registered.content)
        target.chmod(stat.S_IREAD)


def _stage_plugin(
    plan: PluginRunPlan,
    plugin_root: Path,
    distributions: Iterable[metadata.Distribution] | None,
) -> None:
    source = tuple(metadata.distributions() if distributions is None else distributions)
    matching: list[metadata.Distribution] = []
    for distribution in source:
        try:
            name = str(distribution.metadata.get("Name"))
            version = str(distribution.version)
        except Exception:
            continue
        if name == plan.target.distribution_name and version == plan.target.distribution_version:
            matching.append(distribution)
    if len(matching) != 1:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_PLAN_INVALID,
            "run plan must resolve to exactly one installed distribution",
        )
    distribution = matching[0]
    entry_points = tuple(distribution.entry_points)
    expected_entry = (
        PLUGIN_ENTRY_POINT_GROUP,
        plan.target.entry_point_name,
        plan.target.entry_point_value,
    )
    observed = tuple(
        (entry.group, entry.name, entry.value)
        for entry in entry_points
        if entry.group == PLUGIN_ENTRY_POINT_GROUP and entry.name == plan.target.entry_point_name
    )
    if observed != (expected_entry,):
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_PLAN_INVALID, "installed entry point does not match the plan"
        )
    module_name = plan.target.entry_point_value.split(":", maxsplit=1)[0]
    top_package = module_name.split(".", maxsplit=1)[0]
    files = distribution.files
    if files is None:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_PLAN_INVALID, "installed distribution has no file inventory"
        )
    root = Path(str(distribution.locate_file(""))).resolve(strict=True)
    plugin_root.mkdir(mode=0o700)
    selected: list[tuple[Path, bytes]] = []
    total = 0
    for item in files:
        rendered = str(item).replace("\\", "/")
        parts = rendered.split("/")
        if not parts or parts[0] != top_package:
            continue
        relative = Path(*parts)
        if relative.suffix == ".pyc" or "__pycache__" in relative.parts:
            continue
        if relative.suffix.casefold() in NATIVE_SUFFIXES:
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_PLAN_INVALID,
                "native plugins are unsupported by contract v1",
            )
        candidate = Path(str(distribution.locate_file(item)))
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_PLAN_INVALID, "plugin file escapes its distribution"
            ) from exc
        content = _read_regular(candidate, MAX_PLUGIN_PACKAGE_BYTES)
        total += len(content)
        selected.append((relative, content))
        if len(selected) > MAX_PLUGIN_PACKAGE_FILES or total > MAX_PLUGIN_PACKAGE_BYTES:
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_PLAN_INVALID, "plugin package exceeds staging limits"
            )
    if not selected:
        raise PluginBrokerError(PluginRunIssueCode.PLUGIN_PLAN_INVALID, "plugin package is empty")
    for relative, content in selected:
        target = plugin_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_exclusive(target, content)
        target.chmod(stat.S_IREAD)
    manifest_path = plugin_root / top_package / "forgegate-plugin.json"
    manifest = PluginManifest.model_validate(_load_json_bytes(manifest_path.read_bytes()))
    if manifest != plan.target.manifest:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_PLAN_INVALID, "installed manifest does not match the run plan"
        )


def _validate_output_snapshots(
    plan: PluginRunPlan,
    terminal: PluginProtocolMessage,
    first: Mapping[str, bytes],
    second: Mapping[str, bytes],
) -> tuple[PluginValidatedOutput, ...]:
    if first != second:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_OUTPUT_INVALID, "plugin output changed during registration"
        )
    required_protocol = {"protocol/ready.json", "protocol/terminal.json"}
    if not required_protocol.issubset(first):
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_PROTOCOL_INVALID, "plugin protocol files are incomplete"
        )
    evidence_members = sorted(name for name in first if name.startswith("evidence/"))
    if set(first) != required_protocol | set(evidence_members) or not evidence_members:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_OUTPUT_INVALID, "plugin output contains unexpected members"
        )
    if len(evidence_members) > plan.resource_limits.file_count:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_RESOURCE_LIMIT, "plugin output file count exceeds its limit"
        )
    if sum(len(first[name]) for name in evidence_members) > plan.resource_limits.output_bytes:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_RESOURCE_LIMIT, "plugin output bytes exceed their limit"
        )
    input_by_name = {subject.name: subject for subject in plan.inputs}
    outputs: list[PluginValidatedOutput] = []
    for name in evidence_members:
        content = first[name]
        try:
            document = PluginOutputDocument.model_validate(_load_json_bytes(content))
        except (ValidationError, ValueError, TypeError) as exc:
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
                "plugin output violates its strict schema",
            ) from exc
        if canonical_json(document.model_dump(mode="json")).encode("utf-8") != content:
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_OUTPUT_INVALID, "plugin output is not canonical JSON"
            )
        evidence = document.evidence
        if document.run_plan_id != plan.run_plan_id:
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_OUTPUT_INVALID, "plugin output names another run plan"
            )
        if name != f"evidence/{evidence.evidence_id}.json":
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_OUTPUT_INVALID, "plugin output member name is invalid"
            )
        if evidence.kind not in plan.expected_output_evidence_kinds:
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_OUTPUT_INVALID, "plugin output kind was not authorized"
            )
        source = input_by_name.get(evidence.artifact.path_or_uri)
        if (
            source is None
            or evidence.artifact.sha256 != source.digest.removeprefix("sha256:")
            or evidence.artifact.size_bytes != source.size_bytes
            or evidence.artifact.media_type != source.media_type
        ):
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
                "plugin evidence does not reference an immutable run input",
            )
        subject = PluginRunSubject(
            name=name,
            media_type=PLUGIN_OUTPUT_MEDIA_TYPE,
            digest="sha256:" + hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        )
        outputs.append(
            create_plugin_validated_output(
                subject=subject,
                evidence_kind=evidence.kind,
                evidence_id=evidence.evidence_id,
            )
        )
    result = tuple(sorted(outputs, key=lambda item: item.subject.name))
    if terminal.output_set_id != plugin_output_set_id(result):
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_OUTPUT_INVALID, "runner output set identity is invalid"
        )
    return result


def _register_outputs(
    output_root: Path,
    run_plan_id: str,
    snapshot: Mapping[str, bytes],
    outputs: tuple[PluginValidatedOutput, ...],
) -> bool:
    root = _safe_directory(output_root, "accepted output")
    target = root / ("plugin-run-" + run_plan_id.removeprefix("sha256:"))
    expected = {output.subject.name: snapshot[output.subject.name] for output in outputs}
    if target.exists():
        return _read_tree(target, sum(map(len, expected.values())) + 1) == expected
    temporary = Path(tempfile.mkdtemp(prefix=".forgegate-output-", dir=root))
    try:
        for name, content in expected.items():
            path = temporary / Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_exclusive(path, content)
            path.chmod(stat.S_IREAD)
        os.replace(temporary, target)
        return True
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def _execute_windows_container(
    create_command: tuple[str, ...],
    authorization: WindowsBrokerAuthorization,
    container_name: str,
    plan: PluginRunPlan,
    run_root: Path,
    on_ready: ReadyObserver,
) -> SandboxObservation:  # pragma: no cover - exercised by Windows live verification
    podman = authorization.podman_executable
    created = False
    process: subprocess.Popen[bytes] | None = None
    started = time.monotonic()
    stdout = bytearray()
    stderr = bytearray()
    stdout_overflow = threading.Event()
    stderr_overflow = threading.Event()
    ready_bytes: bytes | None = None
    terminal_bytes: bytes | None = None
    first: Mapping[str, bytes] = {}
    second: Mapping[str, bytes] = {}
    issue: PluginRunIssueCode | None = None
    exit_code: int | None = None
    oom_killed = False
    try:
        created_result = _run_command(
            create_command, timeout=plan.resource_limits.startup_timeout_ms / 1000
        )
        if created_result[0] != 0:
            issue = PluginRunIssueCode.PLUGIN_START_FAILED
        else:
            created = True
            process = subprocess.Popen(
                [str(podman), "start", "--attach", "--sig-proxy=false", container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert process.stdout is not None and process.stderr is not None
            readers = (
                threading.Thread(
                    target=_copy_stream,
                    args=(
                        process.stdout,
                        plan.resource_limits.stdout_bytes,
                        stdout,
                        stdout_overflow,
                    ),
                    daemon=True,
                ),
                threading.Thread(
                    target=_copy_stream,
                    args=(
                        process.stderr,
                        plan.resource_limits.stderr_bytes,
                        stderr,
                        stderr_overflow,
                    ),
                    daemon=True,
                ),
            )
            for reader in readers:
                reader.start()
            startup_deadline = time.monotonic() + plan.resource_limits.startup_timeout_ms / 1000
            total_deadline = started + plan.resource_limits.total_timeout_ms / 1000
            probe_root = run_root / "probe"
            probe_root.mkdir()
            while process.poll() is None:
                if ready_bytes is None:
                    ready_bytes = _copy_container_file(
                        podman,
                        container_name,
                        "/forgegate/output/protocol/ready.json",
                        probe_root / "ready.json",
                    )
                    if ready_bytes is not None:
                        on_ready(ready_bytes)
                if ready_bytes is not None:
                    terminal_bytes = _copy_container_file(
                        podman,
                        container_name,
                        "/forgegate/output/protocol/terminal.json",
                        probe_root / "terminal.json",
                    )
                    if terminal_bytes is not None:
                        first = _copy_container_tree(
                            podman, container_name, run_root / "snapshot-one", plan
                        )
                        second = _copy_container_tree(
                            podman, container_name, run_root / "snapshot-two", plan
                        )
                        break
                if stdout_overflow.is_set() or stderr_overflow.is_set():
                    issue = PluginRunIssueCode.PLUGIN_RESOURCE_LIMIT
                    break
                now = time.monotonic()
                if ready_bytes is None and now >= startup_deadline:
                    issue = PluginRunIssueCode.PLUGIN_TIMEOUT
                    break
                if now >= total_deadline:
                    issue = PluginRunIssueCode.PLUGIN_TIMEOUT
                    break
                time.sleep(0.02)
            if process.poll() is not None and terminal_bytes is None and issue is None:
                issue = PluginRunIssueCode.PLUGIN_EXIT_ERROR
            _run_command((str(podman), "kill", container_name), timeout=5, require_success=False)
            try:
                exit_code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                exit_code = process.wait(timeout=5)
            for reader in readers:
                reader.join(timeout=2)
            inspect = _run_command(
                (str(podman), "inspect", container_name, "--format", "json"),
                timeout=5,
                require_success=False,
            )
            if inspect[0] == 0:
                document = _load_json_bytes(inspect[1])
                if isinstance(document, list) and len(document) == 1:
                    state = document[0].get("State") or document[0].get("state")
                    if isinstance(state, dict):
                        oom_killed = bool(state.get("OOMKilled") or state.get("oomKilled"))
            if oom_killed:
                issue = PluginRunIssueCode.PLUGIN_RESOURCE_LIMIT
    except PluginBrokerError as exc:
        issue = exc.code
    except (OSError, subprocess.SubprocessError, ValueError):
        issue = PluginRunIssueCode.PLUGIN_START_FAILED
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if created:
            _run_command(
                (str(podman), "rm", "--force", "--time", "0", container_name),
                timeout=10,
                require_success=False,
            )
        exists = _run_command(
            (str(podman), "container", "exists", container_name),
            timeout=5,
            require_success=False,
        )
    elapsed = math.ceil((time.monotonic() - started) * 1000)
    return SandboxObservation(
        ready_bytes=ready_bytes,
        terminal_bytes=terminal_bytes,
        first_snapshot=first,
        second_snapshot=second,
        execution=PluginExecutionSummary(
            runner_started=process is not None,
            ready_observed=ready_bytes is not None,
            completion_observed=terminal_bytes is not None,
            elapsed_ms=min(elapsed, 900_000),
            exit_code=None if terminal_bytes is not None else exit_code,
            oom_killed=oom_killed,
            stdout_bytes=len(stdout),
            stderr_bytes=len(stderr),
            stdout_truncated=stdout_overflow.is_set(),
            stderr_truncated=stderr_overflow.is_set(),
        ),
        container_removed=exists[0] == 1,
        issue=issue,
    )


def _copy_stream(
    stream: BinaryIO, limit: int, destination: bytearray, overflow: threading.Event
) -> None:  # pragma: no cover - exercised by Windows live verification
    try:
        while chunk := os.read(stream.fileno(), 8192):
            remaining = max(0, limit - len(destination))
            destination.extend(chunk[:remaining])
            if len(chunk) > remaining:
                overflow.set()
                return
    finally:
        stream.close()


def _copy_container_file(
    podman: Path, container_name: str, source: str, destination: Path
) -> bytes | None:  # pragma: no cover - exercised by Windows live verification
    if destination.exists():
        destination.unlink()
    result = _run_command(
        (str(podman), "cp", f"{container_name}:{source}", str(destination)),
        timeout=3,
        require_success=False,
    )
    if result[0] != 0 or not destination.is_file():
        return None
    return _read_regular(destination, MAX_MANAGEMENT_BYTES)


def _copy_container_tree(
    podman: Path, container_name: str, destination: Path, plan: PluginRunPlan
) -> Mapping[str, bytes]:  # pragma: no cover - exercised by Windows live verification
    archive_path = destination.with_suffix(".tar")
    content_limit = plan.resource_limits.output_bytes + MAX_MANAGEMENT_BYTES
    entry_limit = plan.resource_limits.file_count + 8
    archive_limit = content_limit + entry_limit * 4096
    try:
        _stream_container_archive(
            podman,
            container_name,
            archive_path,
            max_archive_bytes=archive_limit,
            max_content_bytes=content_limit,
            max_entries=entry_limit,
            timeout=10,
        )
        return _read_container_archive(
            archive_path,
            max_bytes=content_limit,
            max_entries=entry_limit,
        )
    finally:
        archive_path.unlink(missing_ok=True)


def _stream_container_archive(
    podman: Path,
    container_name: str,
    destination: Path,
    *,
    max_archive_bytes: int,
    max_content_bytes: int,
    max_entries: int,
    timeout: float,
) -> None:  # pragma: no cover - exercised by Windows live verification
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    stderr = bytearray()
    archive_overflow = threading.Event()
    stderr_overflow = threading.Event()
    process: subprocess.Popen[bytes] | None = None
    try:
        with os.fdopen(descriptor, "wb") as archive:
            process = subprocess.Popen(
                [
                    str(podman),
                    "exec",
                    container_name,
                    "/usr/local/bin/python",
                    "-I",
                    "-S",
                    "/forgegate/control/trusted_exporter.py",
                    str(max_content_bytes),
                    str(max_entries),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert process.stdout is not None and process.stderr is not None
            readers = (
                threading.Thread(
                    target=_copy_stream_to_file,
                    args=(process.stdout, max_archive_bytes, archive, archive_overflow),
                    daemon=True,
                ),
                threading.Thread(
                    target=_copy_stream,
                    args=(process.stderr, MAX_MANAGEMENT_BYTES, stderr, stderr_overflow),
                    daemon=True,
                ),
            )
            for reader in readers:
                reader.start()
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if archive_overflow.is_set() or stderr_overflow.is_set():
                    process.kill()
                    break
                if time.monotonic() >= deadline:
                    process.kill()
                    break
                time.sleep(0.02)
            try:
                return_code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                return_code = process.wait(timeout=5)
            for reader in readers:
                reader.join(timeout=2)
            archive.flush()
        if archive_overflow.is_set():
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_RESOURCE_LIMIT,
                "plugin output archive exceeds its bounded transfer limit",
            )
        if stderr_overflow.is_set() or return_code != 0:
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
                "cannot read broker-owned output archive",
            )
    except OSError as exc:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
            "cannot read broker-owned output archive",
        ) from exc
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def _copy_stream_to_file(
    stream: BinaryIO,
    limit: int,
    destination: BinaryIO,
    overflow: threading.Event,
) -> None:  # pragma: no cover - exercised by Windows live verification
    observed = 0
    try:
        while chunk := os.read(stream.fileno(), 64 * 1024):
            remaining = max(0, limit - observed)
            destination.write(chunk[:remaining])
            observed += len(chunk[:remaining])
            if len(chunk) > remaining:
                overflow.set()
                return
    finally:
        stream.close()


def _read_container_archive(
    path: Path,
    *,
    max_bytes: int,
    max_entries: int,
) -> Mapping[str, bytes]:
    result: dict[str, bytes] = {}
    total = 0
    entries = 0
    try:
        with tarfile.open(path, mode="r:*") as archive:
            for member in archive:
                entries += 1
                if entries > max_entries:
                    raise PluginBrokerError(
                        PluginRunIssueCode.PLUGIN_RESOURCE_LIMIT,
                        "plugin output archive exceeds its entry limit",
                    )
                name = member.name.replace("\\", "/")
                while name.startswith("./"):
                    name = name[2:]
                name = name.rstrip("/")
                if name in {"", "."}:
                    if not member.isdir():
                        raise PluginBrokerError(
                            PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
                            "plugin output archive root is invalid",
                        )
                    continue
                parts = name.split("/")
                if any(part in {"", ".", ".."} for part in parts):
                    raise PluginBrokerError(
                        PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
                        "plugin output archive contains an unsafe path",
                    )
                if member.isdir():
                    if name not in {"protocol", "evidence"}:
                        raise PluginBrokerError(
                            PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
                            "plugin output archive contains an unexpected directory",
                        )
                    continue
                if not member.isreg():
                    raise PluginBrokerError(
                        PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
                        "plugin output archive contains a non-regular member",
                    )
                if name not in {"protocol/ready.json", "protocol/terminal.json"} and not (
                    len(parts) == 2 and parts[0] == "evidence"
                ):
                    raise PluginBrokerError(
                        PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
                        "plugin output archive contains an unexpected member",
                    )
                if name in result:
                    raise PluginBrokerError(
                        PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
                        "plugin output archive contains a duplicate member",
                    )
                total += member.size
                if member.size < 0 or total > max_bytes:
                    raise PluginBrokerError(
                        PluginRunIssueCode.PLUGIN_RESOURCE_LIMIT,
                        "plugin output archive exceeds its byte limit",
                    )
                source = archive.extractfile(member)
                if source is None:
                    raise PluginBrokerError(
                        PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
                        "plugin output archive member cannot be read",
                    )
                content = source.read(member.size + 1)
                if len(content) != member.size:
                    raise PluginBrokerError(
                        PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
                        "plugin output archive member size is invalid",
                    )
                result[name] = content
    except (OSError, tarfile.TarError) as exc:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_OUTPUT_INVALID,
            "plugin output archive is invalid",
        ) from exc
    return result


def _read_tree(root: Path, max_bytes: int) -> Mapping[str, bytes]:
    result: dict[str, bytes] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_OUTPUT_INVALID, "plugin output contains a symlink"
            )
        if path.is_dir():
            continue
        content = _read_regular(path, max_bytes)
        total += len(content)
        if total > max_bytes:
            raise PluginBrokerError(
                PluginRunIssueCode.PLUGIN_RESOURCE_LIMIT, "plugin output exceeds its byte limit"
            )
        result[path.relative_to(root).as_posix()] = content
    return result


def _load_protocol_message(content: bytes) -> PluginProtocolMessage:
    try:
        message = PluginProtocolMessage.model_validate(_load_json_bytes(content))
    except (ValidationError, ValueError, TypeError) as exc:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_PROTOCOL_INVALID, "runner protocol message is invalid"
        ) from exc
    if canonical_json(message.model_dump(mode="json")).encode("utf-8") != content:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_PROTOCOL_INVALID, "runner protocol message is not canonical"
        )
    return message


def _load_json_file(path: Path, max_bytes: int) -> Any:
    return _load_json_bytes(_read_regular(path, max_bytes))


def _load_json_bytes(content: bytes) -> Any:
    if len(content) > MAX_MANAGEMENT_BYTES or b"\x00" in content:
        raise ValueError("JSON exceeds its boundary")
    enforce_json_structure_limits(
        content,
        max_nodes=MAX_MANAGEMENT_NODES,
        max_depth=MAX_MANAGEMENT_DEPTH,
    )

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


def _read_regular(path: Path, max_bytes: int) -> bytes:
    if path.is_symlink():
        raise ValueError("file cannot be a symlink")
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise ValueError("file is not a bounded regular file")
        content = handle.read(max_bytes + 1)
        after = os.fstat(handle.fileno())
    if (
        len(content) > max_bytes
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise ValueError("file changed while being read")
    return content


def _write_exclusive(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)
        handle.flush()


def _safe_directory(path: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_PLAN_INVALID, f"broker {label} root does not exist"
        ) from exc
    if not resolved.is_dir() or path.is_symlink():
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_PLAN_INVALID, f"broker {label} root is unsafe"
        )
    return resolved


def _run_root(work_root: Path, run_plan_id: str) -> Path:
    return work_root.resolve(strict=False) / ("plugin-run-" + run_plan_id.removeprefix("sha256:"))


def _container_name(run_plan_id: str) -> str:
    digest = run_plan_id.removeprefix("sha256:")
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise PluginBrokerError(PluginRunIssueCode.PLUGIN_PLAN_INVALID, "run plan ID is invalid")
    return CONTAINER_PREFIX + digest[:16]


def _remove_staging(path: Path) -> bool:
    def make_writable_and_retry(
        operation: Callable[[str], object], target: str, _error: object
    ) -> None:
        os.chmod(target, stat.S_IWRITE)
        operation(target)

    try:
        if path.exists():
            shutil.rmtree(path, onerror=make_writable_and_retry)
        return not path.exists()
    except OSError:
        return False


def _remove_abandoned_container(requested: Path | None, container_name: str) -> bool:
    try:
        podman = _podman_path(requested)
        _run_command(
            (str(podman), "rm", "--force", "--time", "0", container_name),
            timeout=10,
            require_success=False,
        )
        exists = _run_command(
            (str(podman), "container", "exists", container_name),
            timeout=5,
            require_success=False,
        )
        return exists[0] == 1
    except (OSError, ValueError):
        return False


def _podman_path(requested: Path | None) -> Path:
    candidate = requested
    if candidate is None:
        discovered = shutil.which("podman")
        candidate = (
            Path(discovered) if discovered else Path(r"C:\Program Files\RedHat\Podman\podman.exe")
        )
    resolved = candidate.resolve(strict=True)
    if not resolved.is_file() or resolved.is_symlink():
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE, "Podman executable is unavailable"
        )
    return resolved


def _inspect_image(
    podman: Path, image: str
) -> str:  # pragma: no cover - exercised by Windows live verification
    result = _run_command(
        (str(podman), "image", "inspect", image, "--format", "json"),
        timeout=30,
        require_success=False,
    )
    if result[0] != 0:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE, "pinned runner image is unavailable"
        )
    document = _load_json_bytes(result[1])
    if not isinstance(document, list) or len(document) != 1 or not isinstance(document[0], dict):
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE, "runner image response is invalid"
        )
    expected_digest = image.rsplit("@", maxsplit=1)[-1]
    if document[0].get("Digest") != expected_digest:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE, "runner image digest is invalid"
        )
    image_id = document[0].get("Id") or document[0].get("ID")
    if isinstance(image_id, str) and re.fullmatch(r"[0-9a-f]{64}", image_id):
        image_id = "sha256:" + image_id
    if not isinstance(image_id, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE, "runner image identity is invalid"
        )
    return image_id


def _run_command(
    command: tuple[str, ...],
    *,
    timeout: float,
    require_success: bool = True,
) -> tuple[int, bytes, bytes]:  # pragma: no cover - exercised by Windows live verification
    completed = subprocess.run(list(command), check=False, capture_output=True, timeout=timeout)
    if len(completed.stdout) > MAX_MANAGEMENT_BYTES or len(completed.stderr) > MAX_MANAGEMENT_BYTES:
        raise ValueError("management command output exceeds its limit")
    if require_success and completed.returncode != 0:
        raise ValueError("management command failed")
    return completed.returncode, completed.stdout, completed.stderr


def _empty_observation() -> SandboxObservation:
    return SandboxObservation(
        ready_bytes=None,
        terminal_bytes=None,
        first_snapshot={},
        second_snapshot={},
        execution=PluginExecutionSummary(
            runner_started=False,
            ready_observed=False,
            completion_observed=False,
            elapsed_ms=0,
            stdout_bytes=0,
            stderr_bytes=0,
        ),
        container_removed=True,
    )


__all__ = [
    "PLUGIN_OUTPUT_MEDIA_TYPE",
    "PluginBrokerError",
    "PluginBrokerRequest",
    "SandboxObservation",
    "WindowsBrokerAuthorization",
    "WindowsPluginBroker",
    "authorize_windows_broker",
]
