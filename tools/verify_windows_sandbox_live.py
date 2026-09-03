from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from forgegate.plugins import (
    WINDOWS_PODMAN_BACKEND,
    WINDOWS_PODMAN_BACKEND_VERSION,
    WINDOWS_SANDBOX_PROBE_IMAGE,
    PluginCapability,
    PluginExecutionTarget,
    PluginPermission,
    PluginResourceLimits,
    PluginRunPlan,
    PluginRunSubject,
    WindowsSandboxCapabilityReport,
    WindowsSandboxCapabilityStatus,
    WindowsSandboxControl,
    build_windows_podman_create_command,
    create_plugin_manifest,
    create_plugin_run_plan,
    probe_windows_podman_sandbox,
)

MAX_MANAGEMENT_OUTPUT_BYTES = 2 * 1024 * 1024
MANAGEMENT_TIMEOUT_SECONDS = 30.0
IMAGE_PULL_TIMEOUT_SECONDS = 300.0
FIXTURE_COMPLETION_MARKER = b"__FORGEGATE_FIXTURE_COMPLETE__\n"


class LiveVerificationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True, slots=True)
class OutputSummary:
    files: tuple[tuple[str, int, str], ...]
    total_bytes: int
    issue: str | None


@dataclass(frozen=True, slots=True)
class CaseResult:
    name: str
    exit_code: int | None
    elapsed_ms: int
    timed_out: bool
    stdout: bytes
    stderr: bytes
    stdout_overflow: bool
    stderr_overflow: bool
    oom_killed: bool
    fixture_completed: bool
    output: OutputSummary
    cleanup_verified: bool


def _case_diagnostic(case: CaseResult) -> dict[str, Any]:
    return {
        "name": case.name,
        "exit_code": case.exit_code,
        "elapsed_ms": case.elapsed_ms,
        "timed_out": case.timed_out,
        "oom_killed": case.oom_killed,
        "fixture_completed": case.fixture_completed,
        "stdout_bytes": len(case.stdout),
        "stderr_bytes": len(case.stderr),
        "stdout_overflow": case.stdout_overflow,
        "stderr_overflow": case.stderr_overflow,
        "stdout_preview": case.stdout[:512].decode("utf-8", errors="replace"),
        "stderr_preview": case.stderr[:512].decode("utf-8", errors="replace"),
        "output_issue": case.output.issue,
        "output_total_bytes": case.output.total_bytes,
        "output_files": [
            {"path": path, "bytes": size, "sha256": digest}
            for path, size, digest in case.output.files
        ],
        "cleanup_verified": case.cleanup_verified,
    }


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LiveVerificationError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise LiveVerificationError(f"non-finite JSON constant: {value}")


def _load_json_bytes(data: bytes) -> Any:
    if len(data) > MAX_MANAGEMENT_OUTPUT_BYTES:
        raise LiveVerificationError("management JSON exceeded its byte limit")
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_strict_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LiveVerificationError("management command returned invalid JSON") from exc


def _run_command(
    command: tuple[str, ...],
    *,
    timeout_seconds: float = MANAGEMENT_TIMEOUT_SECONDS,
    require_success: bool = True,
) -> CommandResult:
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise LiveVerificationError("management command could not complete") from exc
    if (
        len(completed.stdout) > MAX_MANAGEMENT_OUTPUT_BYTES
        or len(completed.stderr) > MAX_MANAGEMENT_OUTPUT_BYTES
    ):
        raise LiveVerificationError("management command output exceeded its byte limit")
    if require_success and completed.returncode != 0:
        operation = command[1] if len(command) > 1 else "unknown"
        detail = completed.stderr.decode("utf-8", errors="replace")
        detail = detail.replace(str(Path.home()), "<USER_HOME>")
        detail = " ".join(detail.split())[:512]
        raise LiveVerificationError(
            f"Podman {operation} failed with exit code {completed.returncode}: {detail}"
        )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _safe_podman_path(requested: Path | None) -> Path:
    candidate = requested or (Path(found) if (found := shutil.which("podman")) else None)
    if candidate is None:
        default = Path(r"C:\Program Files\RedHat\Podman\podman.exe")
        candidate = default if default.is_file() else None
    if candidate is None:
        raise LiveVerificationError("Podman executable is unavailable")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise LiveVerificationError("Podman executable is unavailable") from exc
    if not resolved.is_file() or resolved.is_symlink():
        raise LiveVerificationError("Podman executable is not a regular file")
    return resolved


def _fixture_plan(payload: bytes, *, limits: PluginResourceLimits) -> PluginRunPlan:
    permissions = (PluginPermission.ARTIFACT_READ, PluginPermission.FILESYSTEM_WRITE)
    manifest = create_plugin_manifest(
        plugin_id="example.windows-sandbox-live-verifier",
        display_name="Windows Sandbox Live Verifier",
        description="ForgeGate-owned hostile sandbox verification fixture.",
        plugin_version="1.0.0",
        forgegate_api_version="1",
        capabilities=(PluginCapability.COLLECTOR,),
        input_schemas=("forgegate-development.sandbox-fixture.v1",),
        permissions=permissions,
        output_evidence_kinds=("sandbox.verification",),
    )
    return create_plugin_run_plan(
        target=PluginExecutionTarget(
            distribution_name="forgegate-windows-sandbox-live-verifier",
            distribution_version="1.0.0",
            entry_point_name=manifest.plugin_id,
            entry_point_value="forgegate_sandbox_fixture.runtime:plugin",
            manifest=manifest,
        ),
        input_schema="forgegate-development.sandbox-fixture.v1",
        inputs=(
            PluginRunSubject(
                name="payload.txt",
                media_type="text/plain",
                digest="sha256:" + hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
            ),
        ),
        expected_output_evidence_kinds=("sandbox.verification",),
        approved_permissions=permissions,
        enforced_permissions=permissions,
        enforcement_backend=WINDOWS_PODMAN_BACKEND,
        enforcement_backend_version=WINDOWS_PODMAN_BACKEND_VERSION,
        resource_limits=limits,
        planned_at=datetime.now(UTC),
    )


def _copy_stream(
    stream: BinaryIO,
    limit: int,
    destination: bytearray,
    overflow: threading.Event,
) -> None:
    try:
        while chunk := os.read(stream.fileno(), 8192):
            remaining = max(0, limit - len(destination))
            destination.extend(chunk[:remaining])
            if len(chunk) > remaining:
                overflow.set()
                return
    finally:
        stream.close()


def _attached_start(
    podman: Path,
    container_name: str,
    limits: PluginResourceLimits,
    copy_output: Callable[[], OutputSummary],
) -> tuple[int | None, bytes, bytes, bool, bool, bool, bool, int, OutputSummary]:
    started = time.monotonic()
    process = subprocess.Popen(
        [str(podman), "start", "--attach", "--sig-proxy=false", container_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    stdout = bytearray()
    stderr = bytearray()
    stdout_overflow = threading.Event()
    stderr_overflow = threading.Event()
    readers = (
        threading.Thread(
            target=_copy_stream,
            args=(process.stdout, limits.stdout_bytes, stdout, stdout_overflow),
            daemon=True,
        ),
        threading.Thread(
            target=_copy_stream,
            args=(process.stderr, limits.stderr_bytes, stderr, stderr_overflow),
            daemon=True,
        ),
    )
    for reader in readers:
        reader.start()
    timed_out = False
    fixture_completed = False
    output = OutputSummary((), 0, None)
    deadline = started + limits.total_timeout_ms / 1000
    while process.poll() is None:
        if FIXTURE_COMPLETION_MARKER in stdout:
            fixture_completed = True
            output = copy_output()
            _run_command((str(podman), "kill", container_name), require_success=False)
            break
        if stdout_overflow.is_set() or stderr_overflow.is_set():
            _run_command((str(podman), "kill", container_name), require_success=False)
            break
        if time.monotonic() >= deadline:
            timed_out = True
            _run_command((str(podman), "kill", container_name), require_success=False)
            break
        time.sleep(0.01)
    try:
        exit_code = process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        exit_code = process.wait(timeout=5)
    for reader in readers:
        reader.join(timeout=2)
    elapsed_ms = math.ceil((time.monotonic() - started) * 1000)
    captured_stdout = bytes(stdout).replace(FIXTURE_COMPLETION_MARKER, b"")
    return (
        exit_code,
        captured_stdout,
        bytes(stderr),
        timed_out,
        stdout_overflow.is_set(),
        stderr_overflow.is_set(),
        fixture_completed,
        elapsed_ms,
        output,
    )


def _inspect_state(podman: Path, container_name: str) -> tuple[int | None, bool]:
    result = _run_command((str(podman), "inspect", container_name, "--format", "json"))
    document = _load_json_bytes(result.stdout)
    if not isinstance(document, list) or len(document) != 1:
        raise LiveVerificationError("container inspection returned an invalid shape")
    item = document[0]
    if not isinstance(item, Mapping):
        raise LiveVerificationError("container inspection returned an invalid item")
    state = item.get("State") or item.get("state")
    if not isinstance(state, Mapping):
        raise LiveVerificationError("container inspection omitted state")
    exit_code = state.get("ExitCode") if "ExitCode" in state else state.get("exitCode")
    oom_killed = state.get("OOMKilled") if "OOMKilled" in state else state.get("oomKilled")
    return (exit_code if isinstance(exit_code, int) else None, oom_killed is True)


def _summarize_outputs(root: Path, limits: PluginResourceLimits) -> OutputSummary:
    files: list[tuple[str, int, str]] = []
    total_bytes = 0
    issue: str | None = None
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            return OutputSummary((), 0, "symlink")
        if path.is_dir():
            continue
        if not path.is_file():
            return OutputSummary((), 0, "non-regular-member")
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        total_bytes += size
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append((relative, size, digest))
        if len(files) > limits.file_count:
            issue = "file-count"
        if total_bytes > limits.output_bytes:
            issue = "output-bytes"
    return OutputSummary(tuple(files), total_bytes, issue)


def _run_case(
    podman: Path,
    capability: WindowsSandboxCapabilityReport,
    root: Path,
    *,
    name: str,
    script: str,
    limits: PluginResourceLimits,
) -> CaseResult:
    payload = b"forgegate-private-input-v1\n"
    case_root = root / name
    input_root = case_root / "input"
    control_root = case_root / "control"
    retrieved_root = case_root / "retrieved"
    input_root.mkdir(parents=True)
    control_root.mkdir()
    retrieved_root.mkdir()
    (input_root / "payload.txt").write_bytes(payload)
    (control_root / "fixture.py").write_text(script, encoding="utf-8", newline="\n")
    plan = _fixture_plan(payload, limits=limits)
    container_name = f"forgegate-{secrets.token_hex(8)}"
    command = build_windows_podman_create_command(
        capability,
        plan,
        podman_executable=podman,
        container_name=container_name,
        image=WINDOWS_SANDBOX_PROBE_IMAGE,
        input_directory=input_root,
        control_directory=control_root,
        runner_argv=("/usr/local/bin/python", "-I", "-S", "/forgegate/control/fixture.py"),
    )
    created = False
    cleanup_verified = False
    output = OutputSummary((), 0, None)
    exit_code: int | None = None
    oom_killed = False
    attached: tuple[int | None, bytes, bytes, bool, bool, bool, bool, int, OutputSummary] = (
        None,
        b"",
        b"",
        False,
        False,
        False,
        False,
        0,
        OutputSummary((), 0, None),
    )

    def copy_output() -> OutputSummary:
        copy_result = _run_command(
            (
                str(podman),
                "cp",
                f"{container_name}:/forgegate/output/.",
                str(retrieved_root),
            ),
            require_success=False,
        )
        if copy_result.returncode != 0:
            return OutputSummary((), 0, "copy-failed")
        return _summarize_outputs(retrieved_root, limits)

    try:
        _run_command(command, timeout_seconds=limits.startup_timeout_ms / 1000)
        created = True
        attached = _attached_start(podman, container_name, limits, copy_output)
        inspected_exit, oom_killed = _inspect_state(podman, container_name)
        exit_code = inspected_exit if inspected_exit is not None else attached[0]
        output = attached[8]
    finally:
        if created:
            _run_command(
                (str(podman), "rm", "--force", "--time", "0", container_name),
                require_success=False,
            )
            exists = _run_command(
                (str(podman), "container", "exists", container_name),
                require_success=False,
            )
            cleanup_verified = exists.returncode == 1
    return CaseResult(
        name=name,
        exit_code=exit_code,
        elapsed_ms=attached[7],
        timed_out=attached[3],
        stdout=attached[1],
        stderr=attached[2],
        stdout_overflow=attached[4],
        stderr_overflow=attached[5],
        oom_killed=oom_killed,
        fixture_completed=attached[6],
        output=output,
        cleanup_verified=cleanup_verified,
    )


COMPOSITE_SCRIPT = """
import json
import os
from pathlib import Path
import socket
import subprocess

def denied(operation):
    try:
        operation()
    except BaseException:
        return True
    return False

input_path = Path('/forgegate/input/payload.txt')
results = {
    'input_read': input_path.read_text(encoding='utf-8') == 'forgegate-private-input-v1\\n',
    'input_write_denied': denied(lambda: input_path.write_text('mutated', encoding='utf-8')),
    'root_write_denied': denied(lambda: Path('/forgegate-root-write').write_text('x')),
    'host_read_denied': denied(lambda: Path('/mnt/c/Windows/win.ini').read_bytes()),
}
sock = socket.socket()
sock.settimeout(0.5)
try:
    results['network_denied'] = sock.connect_ex(('1.1.1.1', 53)) != 0
finally:
    sock.close()
results['subprocess_denied'] = denied(
    lambda: subprocess.run(['/usr/local/bin/python', '-c', 'pass'], check=False)
)
results['environment_keys'] = sorted(os.environ)
results['lc_ctype'] = os.environ.get('LC_CTYPE')
Path('/forgegate/output/results.json').write_text(
    json.dumps(results, sort_keys=True, separators=(',', ':')), encoding='utf-8'
)
print('__FORGEGATE_FIXTURE_COMPLETE__', flush=True)
import time
time.sleep(30)
""".strip()

MEMORY_SCRIPT = """
chunks = []
while True:
    chunks.append(bytearray(8 * 1024 * 1024))
""".strip()

CPU_SCRIPT = """
value = 0
while True:
    value += 1
""".strip()

WALL_SCRIPT = """
import time
time.sleep(30)
""".strip()

OUTPUT_SCRIPT = """
import errno
from pathlib import Path
try:
    Path('/forgegate/output/large.bin').write_bytes(b'x' * (2 * 1024 * 1024))
except OSError as exc:
    if exc.errno == errno.ENOSPC:
        print('output-limit-denied')
    else:
        raise
else:
    raise SystemExit(71)
print('__FORGEGATE_FIXTURE_COMPLETE__', flush=True)
import time
time.sleep(30)
""".strip()

FILE_COUNT_SCRIPT = """
from pathlib import Path
for index in range(3):
    Path(f'/forgegate/output/{index}.txt').write_text('x', encoding='utf-8')
print('__FORGEGATE_FIXTURE_COMPLETE__', flush=True)
import time
time.sleep(30)
""".strip()

STDOUT_SCRIPT = """
import os
while True:
    os.write(1, b'x' * 8192)
""".strip()

STDERR_SCRIPT = """
import os
while True:
    os.write(2, b'x' * 8192)
""".strip()


def _limits(**changes: int) -> PluginResourceLimits:
    values: dict[str, int] = {
        "startup_timeout_ms": 5_000,
        "total_timeout_ms": 10_000,
        "cpu_time_ms": 5_000,
        "memory_bytes": 268_435_456,
        "output_bytes": 1_048_576,
        "file_count": 8,
        "process_count": 1,
        "stdout_bytes": 65_536,
        "stderr_bytes": 65_536,
    }
    values.update(changes)
    return PluginResourceLimits.model_validate(values)


def _image_identity(podman: Path) -> str:
    _run_command(
        (str(podman), "pull", WINDOWS_SANDBOX_PROBE_IMAGE),
        timeout_seconds=IMAGE_PULL_TIMEOUT_SECONDS,
    )
    result = _run_command(
        (str(podman), "image", "inspect", WINDOWS_SANDBOX_PROBE_IMAGE, "--format", "json")
    )
    document = _load_json_bytes(result.stdout)
    if not isinstance(document, list) or len(document) != 1:
        raise LiveVerificationError("image inspection returned an invalid shape")
    item = document[0]
    if not isinstance(item, Mapping):
        raise LiveVerificationError("image inspection returned an invalid item")
    expected_digest = WINDOWS_SANDBOX_PROBE_IMAGE.rsplit("@", maxsplit=1)[-1]
    observed_digest = item.get("Digest")
    if observed_digest != expected_digest:
        raise LiveVerificationError("image inspection returned an unexpected digest")
    image_id = item.get("Id") or item.get("ID")
    if not isinstance(image_id, str):
        raise LiveVerificationError("image inspection omitted its content identity")
    if len(image_id) == 64 and all(character in "0123456789abcdef" for character in image_id):
        image_id = f"sha256:{image_id}"
    if not image_id.startswith("sha256:"):
        raise LiveVerificationError("image inspection returned an invalid content identity")
    return image_id


def verify_live_windows_sandbox(podman: Path) -> dict[str, Any]:
    capability = probe_windows_podman_sandbox(podman_executable=str(podman))
    if capability.status is not WindowsSandboxCapabilityStatus.READY_FOR_ADVERSARIAL_VERIFICATION:
        raise LiveVerificationError(
            f"sandbox capability is not ready: {capability.status.value}/{capability.reason.value}"
        )
    image_id = _image_identity(podman)
    started_at = datetime.now(UTC)
    with tempfile.TemporaryDirectory(prefix="forgegate-sandbox-live-") as raw_root:
        root = Path(raw_root).resolve(strict=True)
        composite = _run_case(
            podman,
            capability,
            root,
            name="composite",
            script=COMPOSITE_SCRIPT,
            limits=_limits(),
        )
        composite_path = root / "composite" / "retrieved" / "results.json"
        composite_payload: dict[str, Any] = {}
        if composite_path.is_file():
            parsed = _load_json_bytes(composite_path.read_bytes())
            if isinstance(parsed, dict):
                composite_payload = parsed
        memory = _run_case(
            podman,
            capability,
            root,
            name="memory",
            script=MEMORY_SCRIPT,
            limits=_limits(memory_bytes=67_108_864),
        )
        cpu = _run_case(
            podman,
            capability,
            root,
            name="cpu",
            script=CPU_SCRIPT,
            limits=_limits(total_timeout_ms=5_000, cpu_time_ms=1_000),
        )
        wall = _run_case(
            podman,
            capability,
            root,
            name="wall",
            script=WALL_SCRIPT,
            limits=_limits(startup_timeout_ms=500, total_timeout_ms=1_500, cpu_time_ms=1_000),
        )
        output = _run_case(
            podman,
            capability,
            root,
            name="output",
            script=OUTPUT_SCRIPT,
            limits=_limits(output_bytes=1_024),
        )
        file_count = _run_case(
            podman,
            capability,
            root,
            name="file-count",
            script=FILE_COUNT_SCRIPT,
            limits=_limits(file_count=2),
        )
        stdout = _run_case(
            podman,
            capability,
            root,
            name="stdout",
            script=STDOUT_SCRIPT,
            limits=_limits(stdout_bytes=1_024),
        )
        stderr = _run_case(
            podman,
            capability,
            root,
            name="stderr",
            script=STDERR_SCRIPT,
            limits=_limits(stderr_bytes=1_024),
        )

    cases = (composite, memory, cpu, wall, output, file_count, stdout, stderr)
    environment_keys = composite_payload.get("environment_keys")
    check_values: dict[WindowsSandboxControl, bool] = {
        WindowsSandboxControl.LOCAL_WSL2_MACHINE: capability.wsl2_provider
        and capability.local_transport,
        WindowsSandboxControl.ROOTLESS_RUNTIME: capability.rootless_runtime,
        WindowsSandboxControl.PINNED_IMAGE: image_id.startswith("sha256:"),
        WindowsSandboxControl.READ_ONLY_ROOT: composite_payload.get("root_write_denied") is True,
        WindowsSandboxControl.PRIVATE_INPUT_MOUNT: all(
            composite_payload.get(key) is True
            for key in ("input_read", "input_write_denied", "host_read_denied")
        ),
        WindowsSandboxControl.BOUNDED_PRIVATE_OUTPUT: composite.output.issue is None
        and composite.fixture_completed
        and output.fixture_completed
        and b"output-limit-denied" in output.stdout
        and file_count.output.issue == "file-count",
        WindowsSandboxControl.NETWORK_DENY: composite_payload.get("network_denied") is True,
        WindowsSandboxControl.SUBPROCESS_DENY: composite_payload.get("subprocess_denied") is True,
        WindowsSandboxControl.EMPTY_ENVIRONMENT: environment_keys
        == ["FORGEGATE_RUN_PLAN_ID", "LC_CTYPE"]
        and composite_payload.get("lc_ctype") == "C.UTF-8",
        WindowsSandboxControl.CPU_LIMIT: not cpu.timed_out
        and cpu.exit_code not in {None, 0}
        and cpu.elapsed_ms < 5_000,
        WindowsSandboxControl.MEMORY_LIMIT: memory.oom_killed and memory.exit_code not in {None, 0},
        WindowsSandboxControl.TOTAL_TIMEOUT: wall.timed_out and wall.elapsed_ms < 5_000,
        WindowsSandboxControl.BOUNDED_LOG_CAPTURE: stdout.stdout_overflow
        and stderr.stderr_overflow
        and len(stdout.stdout) == 1_024
        and len(stderr.stderr) == 1_024,
        WindowsSandboxControl.CLEANUP: all(case.cleanup_verified for case in cases),
    }
    checks = [
        {"control": control.value, "passed": check_values[control]}
        for control in sorted(WindowsSandboxControl, key=lambda item: item.value)
    ]
    finished_at = datetime.now(UTC)
    report: dict[str, Any] = {
        "report_format": "forgegate-development.windows-sandbox-live-verification.v1",
        "backend": WINDOWS_PODMAN_BACKEND,
        "backend_contract_version": WINDOWS_PODMAN_BACKEND_VERSION,
        "capability_id": capability.capability_id,
        "host_os": capability.host_os,
        "host_architecture": capability.host_architecture,
        "runtime_client_version": capability.runtime_version,
        "runtime_server_version": capability.server_runtime_version,
        "image": WINDOWS_SANDBOX_PROBE_IMAGE,
        "image_id": image_id,
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
        "checks": checks,
        "composite_observations": composite_payload,
        "case_results": [_case_diagnostic(case) for case in cases],
        "backend_enforcement_verified": all(check_values.values()),
        "external_plugin_execution": "PROHIBITED",
        "advertised_isolation_tier": "NONE",
        "limitations": [
            "WSL automatically mounts Windows drives inside the Podman machine.",
            "Only ForgeGate-owned hostile fixtures were executed.",
            (
                "Production plugin broker, protocol, output schema validation, "
                "and durable audit remain pending."
            ),
        ],
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    report["verification_id"] = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ForgeGate-owned hostile fixtures against the Windows Podman sandbox."
    )
    parser.add_argument("--podman", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        report = verify_live_windows_sandbox(_safe_podman_path(arguments.podman))
    except LiveVerificationError as exc:
        print(f"Windows sandbox live verification: ERROR ({exc})")
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if arguments.output is not None:
        arguments.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if report["backend_enforcement_verified"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
