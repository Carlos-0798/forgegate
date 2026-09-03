from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from forgegate.canonical import sha256_fingerprint
from forgegate.domain.models import StrictModel
from forgegate.plugins.execution_models import (
    PluginIsolationTier,
    PluginRunIssueCode,
    PluginRunPlan,
)

WINDOWS_PODMAN_BACKEND = "windows-podman-wsl2"
WINDOWS_PODMAN_BACKEND_VERSION = "1.0.0"
WINDOWS_SANDBOX_PROBE_IMAGE = (
    "docker.io/library/python@"
    "sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db"
)
MAX_PROBE_OUTPUT_BYTES = 1024 * 1024
DEFAULT_PROBE_TIMEOUT_SECONDS = 5.0
PINNED_OCI_IMAGE_PATTERN = (
    r"^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:[/:][a-z0-9]+(?:[._-][a-z0-9]+)*)*"
    r"@sha256:[0-9a-f]{64}$"
)
CONTAINER_NAME_PATTERN = r"^forgegate-[0-9a-f]{16}$"
SAFE_RUNTIME_VERSION_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$"


class WindowsSandboxCapabilityStatus(StrEnum):
    UNSUPPORTED_HOST = "UNSUPPORTED_HOST"
    RUNTIME_MISSING = "RUNTIME_MISSING"
    RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
    RUNTIME_INCOMPATIBLE = "RUNTIME_INCOMPATIBLE"
    READY_FOR_ADVERSARIAL_VERIFICATION = "READY_FOR_ADVERSARIAL_VERIFICATION"


class WindowsSandboxCapabilityReason(StrEnum):
    NOT_WINDOWS = "NOT_WINDOWS"
    PODMAN_NOT_FOUND = "PODMAN_NOT_FOUND"
    PODMAN_COMMAND_FAILED = "PODMAN_COMMAND_FAILED"
    PODMAN_RESPONSE_INVALID = "PODMAN_RESPONSE_INVALID"
    PODMAN_VERSION_MISMATCH = "PODMAN_VERSION_MISMATCH"
    PODMAN_CONNECTION_NOT_LOCAL = "PODMAN_CONNECTION_NOT_LOCAL"
    PODMAN_PROVIDER_NOT_WSL2 = "PODMAN_PROVIDER_NOT_WSL2"
    PODMAN_RUNTIME_NOT_ROOTLESS = "PODMAN_RUNTIME_NOT_ROOTLESS"
    ADVERSARIAL_VERIFICATION_PENDING = "ADVERSARIAL_VERIFICATION_PENDING"


class WindowsSandboxControl(StrEnum):
    LOCAL_WSL2_MACHINE = "local-wsl2-machine"
    ROOTLESS_RUNTIME = "rootless-runtime"
    PINNED_IMAGE = "pinned-image"
    READ_ONLY_ROOT = "read-only-root"
    PRIVATE_INPUT_MOUNT = "private-input-mount"
    BOUNDED_PRIVATE_OUTPUT = "bounded-private-output"
    NETWORK_DENY = "network-deny"
    SUBPROCESS_DENY = "subprocess-deny"
    EMPTY_ENVIRONMENT = "empty-environment"
    CPU_LIMIT = "cpu-limit"
    MEMORY_LIMIT = "memory-limit"
    TOTAL_TIMEOUT = "total-timeout"
    BOUNDED_LOG_CAPTURE = "bounded-log-capture"
    CLEANUP = "cleanup"


REQUIRED_WINDOWS_SANDBOX_CONTROLS = tuple(WindowsSandboxControl)


class WindowsSandboxCapabilityReport(StrictModel):
    """Host probe only; this document never authorizes external plugin execution."""

    schema_version: Literal["forgegate.windows-plugin-sandbox-capability.v1"] = (
        "forgegate.windows-plugin-sandbox-capability.v1"
    )
    capability_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    backend: Literal["windows-podman-wsl2"] = "windows-podman-wsl2"
    backend_contract_version: Literal["1.0.0"] = "1.0.0"
    host_os: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    host_architecture: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    runtime_name: Literal["podman"] = "podman"
    runtime_version: str | None = Field(default=None, pattern=SAFE_RUNTIME_VERSION_PATTERN)
    server_runtime_version: str | None = Field(default=None, pattern=SAFE_RUNTIME_VERSION_PATTERN)
    status: WindowsSandboxCapabilityStatus
    reason: WindowsSandboxCapabilityReason
    rootless_runtime: bool
    local_transport: bool
    wsl2_provider: bool
    required_controls: tuple[WindowsSandboxControl, ...]
    observed_controls: tuple[WindowsSandboxControl, ...]
    issue_code: Literal[PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE] = (
        PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE
    )
    external_plugin_execution: Literal["PROHIBITED"] = "PROHIBITED"
    advertised_isolation_tier: Literal[PluginIsolationTier.NONE] = PluginIsolationTier.NONE

    @field_validator("required_controls", "observed_controls")
    @classmethod
    def controls_are_unique_and_canonical(
        cls, value: tuple[WindowsSandboxControl, ...]
    ) -> tuple[WindowsSandboxControl, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Windows sandbox controls cannot contain duplicates")
        return tuple(sorted(value, key=lambda item: item.value))

    @model_validator(mode="after")
    def capability_shape_and_identity_hold(self) -> WindowsSandboxCapabilityReport:
        if self.required_controls != tuple(
            sorted(REQUIRED_WINDOWS_SANDBOX_CONTROLS, key=lambda item: item.value)
        ):
            raise ValueError("Windows sandbox report must retain every required control")
        if not set(self.observed_controls).issubset(self.required_controls):
            raise ValueError("observed Windows sandbox controls must be required controls")
        ready = self.status is WindowsSandboxCapabilityStatus.READY_FOR_ADVERSARIAL_VERIFICATION
        if ready:
            if self.reason is not WindowsSandboxCapabilityReason.ADVERSARIAL_VERIFICATION_PENDING:
                raise ValueError("ready Windows sandbox runtime must remain verification-pending")
            if self.runtime_version is None or self.server_runtime_version is None:
                raise ValueError(
                    "ready Windows sandbox runtime requires client and server versions"
                )
            if self.runtime_version != self.server_runtime_version:
                raise ValueError("ready Windows sandbox runtime requires matching versions")
            if not (self.rootless_runtime and self.local_transport and self.wsl2_provider):
                raise ValueError("ready Windows sandbox runtime requires local rootless WSL2")
            expected_observed = {
                WindowsSandboxControl.LOCAL_WSL2_MACHINE,
                WindowsSandboxControl.ROOTLESS_RUNTIME,
            }
            if set(self.observed_controls) != expected_observed:
                raise ValueError("runtime probe can observe only local WSL2 and rootless controls")
        elif self.observed_controls:
            raise ValueError("unavailable Windows sandbox runtime cannot claim observed controls")
        if self.capability_id != sha256_fingerprint(_capability_identity(self)):
            raise ValueError("capability_id does not match Windows sandbox report content")
        return self


@dataclass(frozen=True, slots=True)
class HostCommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class WindowsSandboxError(ValueError):
    def __init__(
        self,
        reason: WindowsSandboxCapabilityReason,
        message: str,
        *,
        issue_code: PluginRunIssueCode = PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.issue_code = issue_code


type HostCommandRunner = Callable[[tuple[str, ...], float], HostCommandResult]


def probe_windows_podman_sandbox(
    *,
    platform_name: str | None = None,
    architecture: str | None = None,
    podman_executable: str | None = None,
    command_runner: HostCommandRunner | None = None,
) -> WindowsSandboxCapabilityReport:
    """Probe a local rootless WSL2 Podman runtime without running plugin code."""

    host_os = _safe_host_value(platform_name or platform.system(), "unknown")
    host_architecture = _safe_host_value(architecture or platform.machine(), "unknown")
    if host_os.casefold() != "windows":
        return create_windows_sandbox_capability_report(
            host_os=host_os,
            host_architecture=host_architecture,
            status=WindowsSandboxCapabilityStatus.UNSUPPORTED_HOST,
            reason=WindowsSandboxCapabilityReason.NOT_WINDOWS,
        )

    executable = podman_executable or shutil.which("podman")
    if executable is None:
        return create_windows_sandbox_capability_report(
            host_os=host_os,
            host_architecture=host_architecture,
            status=WindowsSandboxCapabilityStatus.RUNTIME_MISSING,
            reason=WindowsSandboxCapabilityReason.PODMAN_NOT_FOUND,
        )

    runner = command_runner or _run_host_command
    commands = {
        "version": (executable, "version", "--format", "json"),
        "connection": (executable, "system", "connection", "list", "--format", "json"),
        "machine": (executable, "machine", "info", "--format", "json"),
        "info": (executable, "info", "--format", "json"),
    }
    documents: dict[str, Any] = {}
    for name, command in commands.items():
        try:
            result = runner(command, DEFAULT_PROBE_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError):
            return create_windows_sandbox_capability_report(
                host_os=host_os,
                host_architecture=host_architecture,
                status=WindowsSandboxCapabilityStatus.RUNTIME_UNAVAILABLE,
                reason=WindowsSandboxCapabilityReason.PODMAN_COMMAND_FAILED,
            )
        if result.returncode != 0:
            return create_windows_sandbox_capability_report(
                host_os=host_os,
                host_architecture=host_architecture,
                status=WindowsSandboxCapabilityStatus.RUNTIME_UNAVAILABLE,
                reason=WindowsSandboxCapabilityReason.PODMAN_COMMAND_FAILED,
            )
        if (
            len(result.stdout) > MAX_PROBE_OUTPUT_BYTES
            or len(result.stderr) > MAX_PROBE_OUTPUT_BYTES
        ):
            return create_windows_sandbox_capability_report(
                host_os=host_os,
                host_architecture=host_architecture,
                status=WindowsSandboxCapabilityStatus.RUNTIME_INCOMPATIBLE,
                reason=WindowsSandboxCapabilityReason.PODMAN_RESPONSE_INVALID,
            )
        try:
            documents[name] = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return create_windows_sandbox_capability_report(
                host_os=host_os,
                host_architecture=host_architecture,
                status=WindowsSandboxCapabilityStatus.RUNTIME_INCOMPATIBLE,
                reason=WindowsSandboxCapabilityReason.PODMAN_RESPONSE_INVALID,
            )

    runtime_versions = _podman_versions(documents["version"])
    if runtime_versions is None:
        return create_windows_sandbox_capability_report(
            host_os=host_os,
            host_architecture=host_architecture,
            status=WindowsSandboxCapabilityStatus.RUNTIME_INCOMPATIBLE,
            reason=WindowsSandboxCapabilityReason.PODMAN_RESPONSE_INVALID,
        )
    runtime_version, server_runtime_version = runtime_versions
    if runtime_version != server_runtime_version:
        return create_windows_sandbox_capability_report(
            host_os=host_os,
            host_architecture=host_architecture,
            runtime_version=runtime_version,
            server_runtime_version=server_runtime_version,
            status=WindowsSandboxCapabilityStatus.RUNTIME_INCOMPATIBLE,
            reason=WindowsSandboxCapabilityReason.PODMAN_VERSION_MISMATCH,
        )
    if not _default_connection_is_local(documents["connection"]):
        return create_windows_sandbox_capability_report(
            host_os=host_os,
            host_architecture=host_architecture,
            runtime_version=runtime_version,
            server_runtime_version=server_runtime_version,
            status=WindowsSandboxCapabilityStatus.RUNTIME_INCOMPATIBLE,
            reason=WindowsSandboxCapabilityReason.PODMAN_CONNECTION_NOT_LOCAL,
        )
    if not _machine_is_running_wsl2(documents["machine"]):
        return create_windows_sandbox_capability_report(
            host_os=host_os,
            host_architecture=host_architecture,
            runtime_version=runtime_version,
            server_runtime_version=server_runtime_version,
            status=WindowsSandboxCapabilityStatus.RUNTIME_INCOMPATIBLE,
            reason=WindowsSandboxCapabilityReason.PODMAN_PROVIDER_NOT_WSL2,
        )
    if not _runtime_is_rootless(documents["info"]):
        return create_windows_sandbox_capability_report(
            host_os=host_os,
            host_architecture=host_architecture,
            runtime_version=runtime_version,
            server_runtime_version=server_runtime_version,
            status=WindowsSandboxCapabilityStatus.RUNTIME_INCOMPATIBLE,
            reason=WindowsSandboxCapabilityReason.PODMAN_RUNTIME_NOT_ROOTLESS,
        )
    return create_windows_sandbox_capability_report(
        host_os=host_os,
        host_architecture=host_architecture,
        runtime_version=runtime_version,
        server_runtime_version=server_runtime_version,
        status=WindowsSandboxCapabilityStatus.READY_FOR_ADVERSARIAL_VERIFICATION,
        reason=WindowsSandboxCapabilityReason.ADVERSARIAL_VERIFICATION_PENDING,
        rootless_runtime=True,
        local_transport=True,
        wsl2_provider=True,
        observed_controls=(
            WindowsSandboxControl.LOCAL_WSL2_MACHINE,
            WindowsSandboxControl.ROOTLESS_RUNTIME,
        ),
    )


def create_windows_sandbox_capability_report(
    *,
    host_os: str,
    host_architecture: str,
    status: WindowsSandboxCapabilityStatus,
    reason: WindowsSandboxCapabilityReason,
    runtime_version: str | None = None,
    server_runtime_version: str | None = None,
    rootless_runtime: bool = False,
    local_transport: bool = False,
    wsl2_provider: bool = False,
    observed_controls: tuple[WindowsSandboxControl, ...] = (),
) -> WindowsSandboxCapabilityReport:
    fields: dict[str, object] = {
        "backend": WINDOWS_PODMAN_BACKEND,
        "backend_contract_version": WINDOWS_PODMAN_BACKEND_VERSION,
        "host_os": _safe_host_value(host_os, "unknown"),
        "host_architecture": _safe_host_value(host_architecture, "unknown"),
        "runtime_name": "podman",
        "runtime_version": runtime_version,
        "server_runtime_version": server_runtime_version,
        "status": status,
        "reason": reason,
        "rootless_runtime": rootless_runtime,
        "local_transport": local_transport,
        "wsl2_provider": wsl2_provider,
        "required_controls": [
            item.value for item in sorted(REQUIRED_WINDOWS_SANDBOX_CONTROLS, key=lambda x: x.value)
        ],
        "observed_controls": [
            item.value for item in sorted(observed_controls, key=lambda x: x.value)
        ],
        "issue_code": PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE,
        "external_plugin_execution": "PROHIBITED",
        "advertised_isolation_tier": PluginIsolationTier.NONE,
    }
    return WindowsSandboxCapabilityReport(
        capability_id=sha256_fingerprint(fields),
        **fields,  # type: ignore[arg-type]
    )


def build_windows_podman_create_command(
    report: WindowsSandboxCapabilityReport,
    plan: PluginRunPlan,
    *,
    podman_executable: Path,
    container_name: str,
    image: str,
    input_directory: Path,
    control_directory: Path,
    runner_argv: tuple[str, ...],
) -> tuple[str, ...]:
    """Build, but never execute, a fail-closed Podman container-create command."""

    if report.status is not WindowsSandboxCapabilityStatus.READY_FOR_ADVERSARIAL_VERIFICATION:
        raise WindowsSandboxError(
            WindowsSandboxCapabilityReason.ADVERSARIAL_VERIFICATION_PENDING,
            "Windows Podman runtime is not ready for adversarial verification",
        )
    if plan.enforcement_backend != WINDOWS_PODMAN_BACKEND:
        raise WindowsSandboxError(
            WindowsSandboxCapabilityReason.PODMAN_RESPONSE_INVALID,
            "plugin run plan does not select the Windows Podman backend",
            issue_code=PluginRunIssueCode.PLUGIN_PERMISSION_UNENFORCEABLE,
        )
    if plan.enforcement_backend_version != WINDOWS_PODMAN_BACKEND_VERSION:
        raise WindowsSandboxError(
            WindowsSandboxCapabilityReason.PODMAN_RESPONSE_INVALID,
            "plugin run plan uses an unsupported Windows Podman contract version",
            issue_code=PluginRunIssueCode.PLUGIN_PERMISSION_UNENFORCEABLE,
        )
    if re.fullmatch(CONTAINER_NAME_PATTERN, container_name) is None:
        raise ValueError("container name must be a broker-generated ForgeGate identifier")
    if re.fullmatch(PINNED_OCI_IMAGE_PATTERN, image) is None:
        raise ValueError("Windows sandbox image must use an exact sha256 digest")
    if plan.resource_limits.cpu_time_ms < 1_000:
        raise WindowsSandboxError(
            WindowsSandboxCapabilityReason.PODMAN_RESPONSE_INVALID,
            "Windows Podman backend cannot enforce a sub-second CPU limit",
            issue_code=PluginRunIssueCode.PLUGIN_PERMISSION_UNENFORCEABLE,
        )
    executable = _validated_executable(podman_executable)
    input_root = _validated_broker_directory(input_directory, "input")
    control_root = _validated_broker_directory(control_directory, "control")
    if (
        input_root == control_root
        or input_root in control_root.parents
        or control_root in input_root.parents
    ):
        raise ValueError("broker input and control directories must be separate roots")
    if not runner_argv or any(
        not value or len(value) > 512 or "\x00" in value or "\r" in value or "\n" in value
        for value in runner_argv
    ):
        raise ValueError("runner argv must contain bounded non-empty values")

    limits = plan.resource_limits
    cpu_seconds = max(1, limits.cpu_time_ms // 1_000)
    temporary_bytes = min(16 * 1024 * 1024, max(1024 * 1024, limits.memory_bytes // 8))
    input_mount = _bind_mount(input_root, "/forgegate/input")
    control_mount = _bind_mount(control_root, "/forgegate/control")
    # Podman 5.8.6 rejects uid/gid in --tmpfs. Keep the process non-root and
    # capability-free, but use its root group with mode 0770 root-owned tmpfs.
    return (
        str(executable),
        "create",
        "--name",
        container_name,
        "--pull=never",
        "--network=none",
        "--ipc=none",
        "--read-only",
        "--read-only-tmpfs=false",
        "--cap-drop=all",
        "--security-opt=no-new-privileges",
        "--pids-limit=1",
        f"--memory={limits.memory_bytes}",
        f"--memory-swap={limits.memory_bytes}",
        "--cpus=1.0",
        f"--ulimit=cpu={cpu_seconds}:{cpu_seconds}",
        "--user=65532:0",
        "--workdir=/tmp",
        "--mount",
        input_mount,
        "--mount",
        control_mount,
        "--tmpfs",
        (f"/forgegate/output:rw,noexec,nosuid,nodev,mode=0770,size={limits.output_bytes}"),
        "--tmpfs",
        (f"/tmp:rw,noexec,nosuid,nodev,mode=0770,size={temporary_bytes}"),
        "--entrypoint=/usr/bin/env",
        image,
        "-i",
        f"FORGEGATE_RUN_PLAN_ID={plan.run_plan_id}",
        *runner_argv,
    )


def _run_host_command(command: tuple[str, ...], timeout_seconds: float) -> HostCommandResult:
    completed = subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return HostCommandResult(completed.returncode, completed.stdout, completed.stderr)


def _podman_versions(document: Any) -> tuple[str, str] | None:
    if not isinstance(document, Mapping):
        return None
    client = _mapping_value(document, "client")
    server = _mapping_value(document, "server")
    if not isinstance(client, Mapping) or not isinstance(server, Mapping):
        return None
    client_value = _mapping_value(client, "version")
    server_value = _mapping_value(server, "version")
    if not isinstance(client_value, str) or not isinstance(server_value, str):
        return None
    if re.fullmatch(SAFE_RUNTIME_VERSION_PATTERN, client_value) is None:
        return None
    if re.fullmatch(SAFE_RUNTIME_VERSION_PATTERN, server_value) is None:
        return None
    return client_value, server_value


def _default_connection_is_local(document: Any) -> bool:
    if not isinstance(document, Sequence) or isinstance(document, (str, bytes, bytearray)):
        return False
    defaults = [item for item in document if isinstance(item, Mapping) and _truthy_default(item)]
    if len(defaults) != 1:
        return False
    uri = _mapping_value(defaults[0], "uri")
    if not isinstance(uri, str):
        return False
    parsed = urlsplit(uri)
    return parsed.scheme == "ssh" and parsed.hostname in {"127.0.0.1", "::1", "localhost"}


def _truthy_default(document: Mapping[object, object]) -> bool:
    value = _mapping_value(document, "default")
    return value is True or (isinstance(value, str) and value.casefold() == "true")


def _machine_is_running_wsl2(document: Any) -> bool:
    if not isinstance(document, Mapping):
        return False
    host = _mapping_value(document, "host")
    if not isinstance(host, Mapping):
        return False
    provider = _mapping_value(host, "vmtype")
    state = _mapping_value(host, "machinestate")
    if not isinstance(provider, str) or provider.casefold() != "wsl":
        return False
    return isinstance(state, str) and state.casefold() == "running"


def _runtime_is_rootless(document: Any) -> bool:
    if not isinstance(document, Mapping):
        return False
    host = _mapping_value(document, "host")
    if not isinstance(host, Mapping):
        return False
    security = _mapping_value(host, "security")
    if not isinstance(security, Mapping):
        return False
    return _mapping_value(security, "rootless") is True


def _mapping_value(document: Mapping[object, object], name: str) -> object | None:
    for key, value in document.items():
        if isinstance(key, str) and key.casefold() == name.casefold():
            return value
    return None


def _safe_host_value(value: str, fallback: str) -> str:
    normalized = value.strip()
    if re.fullmatch(r"[A-Za-z0-9._-]{1,32}", normalized) is None:
        return fallback
    return normalized


def _validated_executable(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError("Podman executable is unavailable") from exc
    if not resolved.is_file() or _is_reparse_point(resolved):
        raise ValueError("Podman executable must be a regular non-reparse file")
    return resolved


def _validated_broker_directory(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise ValueError(f"broker {label} directory must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"broker {label} directory is unavailable") from exc
    if not resolved.is_dir() or _is_reparse_point(path) or _is_reparse_point(resolved):
        raise ValueError(f"broker {label} directory must be a non-reparse directory")
    rendered = str(resolved)
    if any(character in rendered for character in (",", "\x00", "\r", "\n")):
        raise ValueError(f"broker {label} directory contains unsupported characters")
    return resolved


def _is_reparse_point(path: Path) -> bool:
    try:
        stat = path.lstat()
    except OSError:
        return True
    attributes = getattr(stat, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _bind_mount(source: Path, destination: str) -> str:
    return f"type=bind,source={source.as_posix()},destination={destination},ro=true"


def _capability_identity(report: WindowsSandboxCapabilityReport) -> dict[str, object]:
    return report.model_dump(mode="json", exclude={"schema_version", "capability_id"})


__all__ = [
    "WINDOWS_PODMAN_BACKEND",
    "WINDOWS_PODMAN_BACKEND_VERSION",
    "WINDOWS_SANDBOX_PROBE_IMAGE",
    "HostCommandResult",
    "WindowsSandboxCapabilityReason",
    "WindowsSandboxCapabilityReport",
    "WindowsSandboxCapabilityStatus",
    "WindowsSandboxControl",
    "WindowsSandboxError",
    "build_windows_podman_create_command",
    "create_windows_sandbox_capability_report",
    "probe_windows_podman_sandbox",
]
