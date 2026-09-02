from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from forgegate.cli import app
from forgegate.config import load_config
from forgegate.plugins import (
    WINDOWS_PODMAN_BACKEND,
    WINDOWS_PODMAN_BACKEND_VERSION,
    WINDOWS_SANDBOX_PROBE_IMAGE,
    HostCommandResult,
    PluginCapability,
    PluginExecutionTarget,
    PluginPermission,
    PluginResourceLimits,
    PluginRunSubject,
    WindowsSandboxCapabilityReason,
    WindowsSandboxCapabilityReport,
    WindowsSandboxCapabilityStatus,
    WindowsSandboxControl,
    WindowsSandboxError,
    build_windows_podman_create_command,
    create_plugin_manifest,
    create_plugin_run_plan,
    create_windows_sandbox_capability_report,
    probe_windows_podman_sandbox,
)

runner = CliRunner()


def _plan(
    *,
    cpu_time_ms: int = 30_000,
    backend: str = WINDOWS_PODMAN_BACKEND,
    backend_version: str = WINDOWS_PODMAN_BACKEND_VERSION,
):
    permissions = (PluginPermission.ARTIFACT_READ, PluginPermission.FILESYSTEM_WRITE)
    manifest = create_plugin_manifest(
        plugin_id="example.windows-sandbox",
        display_name="Windows Sandbox",
        description="Generic Windows sandbox readiness fixture.",
        plugin_version="1.0.0",
        forgegate_api_version="1",
        capabilities=(PluginCapability.COLLECTOR,),
        input_schemas=("example.generic-input.v1",),
        permissions=permissions,
        output_evidence_kinds=("test.metric",),
    )
    return create_plugin_run_plan(
        target=PluginExecutionTarget(
            distribution_name="forgegate-windows-sandbox-fixture",
            distribution_version="1.0.0",
            entry_point_name=manifest.plugin_id,
            entry_point_value="sandbox_fixture.runtime:plugin",
            manifest=manifest,
        ),
        input_schema="example.generic-input.v1",
        inputs=(
            PluginRunSubject(
                name="inputs/evidence.json",
                media_type="application/json",
                digest="sha256:" + "a" * 64,
                size_bytes=128,
            ),
        ),
        expected_output_evidence_kinds=("test.metric",),
        approved_permissions=permissions,
        enforced_permissions=permissions,
        enforcement_backend=backend,
        enforcement_backend_version=backend_version,
        resource_limits=PluginResourceLimits(cpu_time_ms=cpu_time_ms),
        planned_at=datetime(2026, 9, 1, 16, 0, tzinfo=UTC),
    )


def _ready_report() -> WindowsSandboxCapabilityReport:
    return create_windows_sandbox_capability_report(
        host_os="Windows",
        host_architecture="AMD64",
        runtime_version="5.8.3",
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


def _successful_command(command: tuple[str, ...], _timeout: float) -> HostCommandResult:
    key = tuple(command[1:3])
    payloads: dict[tuple[str, ...], object] = {
        ("version", "--format"): {"Client": {"Version": "5.8.3"}},
        ("system", "connection"): [
            {
                "Name": "podman-machine-default",
                "URI": "ssh://core@127.0.0.1:61234/run/podman.sock",
                "Default": True,
            }
        ],
        ("machine", "info"): {"Host": {"VMType": "wsl", "MachineState": "Running"}},
        ("info", "--format"): {"Host": {"Security": {"Rootless": True}}},
    }
    return HostCommandResult(0, json.dumps(payloads[key]).encode(), b"")


def test_probe_fails_closed_for_non_windows_and_missing_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("forgegate.plugins.windows_sandbox.shutil.which", lambda _name: None)
    called = False

    def unexpected(_command: tuple[str, ...], _timeout: float) -> HostCommandResult:
        nonlocal called
        called = True
        raise AssertionError

    unsupported = probe_windows_podman_sandbox(
        platform_name="Linux",
        architecture="x86_64",
        command_runner=unexpected,
    )
    assert unsupported.status is WindowsSandboxCapabilityStatus.UNSUPPORTED_HOST
    assert unsupported.reason is WindowsSandboxCapabilityReason.NOT_WINDOWS
    assert not called

    missing = probe_windows_podman_sandbox(
        platform_name="Windows",
        architecture="AMD64",
        podman_executable=None,
        command_runner=unexpected,
    )
    assert missing.status is WindowsSandboxCapabilityStatus.RUNTIME_MISSING
    assert missing.external_plugin_execution == "PROHIBITED"
    assert missing.advertised_isolation_tier.value == "NONE"
    assert not called


def test_probe_accepts_only_local_rootless_running_wsl2() -> None:
    report = probe_windows_podman_sandbox(
        platform_name="Windows",
        architecture="AMD64",
        podman_executable="podman.exe",
        command_runner=_successful_command,
    )
    assert report.status is WindowsSandboxCapabilityStatus.READY_FOR_ADVERSARIAL_VERIFICATION
    assert report.reason is WindowsSandboxCapabilityReason.ADVERSARIAL_VERIFICATION_PENDING
    assert report.runtime_version == "5.8.3"
    assert set(report.observed_controls) == {
        WindowsSandboxControl.LOCAL_WSL2_MACHINE,
        WindowsSandboxControl.ROOTLESS_RUNTIME,
    }
    assert report.external_plugin_execution == "PROHIBITED"

    changed = report.model_dump(mode="json")
    changed["rootless_runtime"] = False
    with pytest.raises(ValidationError, match="local rootless WSL2"):
        WindowsSandboxCapabilityReport.model_validate(changed)


@pytest.mark.parametrize(
    ("replacement", "reason"),
    [
        (
            [
                (
                    "connection",
                    [{"URI": "ssh://builder@example.com/run/podman.sock", "Default": True}],
                )
            ],
            WindowsSandboxCapabilityReason.PODMAN_CONNECTION_NOT_LOCAL,
        ),
        (
            [("machine", {"Host": {"VMType": "hyperv", "MachineState": "Running"}})],
            WindowsSandboxCapabilityReason.PODMAN_PROVIDER_NOT_WSL2,
        ),
        (
            [("info", {"Host": {"Security": {"Rootless": False}}})],
            WindowsSandboxCapabilityReason.PODMAN_RUNTIME_NOT_ROOTLESS,
        ),
    ],
)
def test_probe_rejects_remote_non_wsl_or_rootful_runtime(
    replacement: list[tuple[str, object]], reason: WindowsSandboxCapabilityReason
) -> None:
    def command_runner(command: tuple[str, ...], timeout: float) -> HostCommandResult:
        baseline = _successful_command(command, timeout)
        name = command[1]
        if name == "system":
            name = "connection"
        override = dict(replacement).get(name)
        if override is None:
            return baseline
        return HostCommandResult(0, json.dumps(override).encode(), b"")

    report = probe_windows_podman_sandbox(
        platform_name="Windows",
        architecture="AMD64",
        podman_executable="podman.exe",
        command_runner=command_runner,
    )
    assert report.status is WindowsSandboxCapabilityStatus.RUNTIME_INCOMPATIBLE
    assert report.reason is reason
    assert report.observed_controls == ()


def test_probe_rejects_command_failure_and_invalid_or_oversized_json() -> None:
    results = (
        HostCommandResult(1, b"", b"failed"),
        HostCommandResult(0, b"not-json", b""),
        HostCommandResult(0, b"{" + b" " * (1024 * 1024), b""),
    )
    expected = (
        WindowsSandboxCapabilityReason.PODMAN_COMMAND_FAILED,
        WindowsSandboxCapabilityReason.PODMAN_RESPONSE_INVALID,
        WindowsSandboxCapabilityReason.PODMAN_RESPONSE_INVALID,
    )
    for result, reason in zip(results, expected, strict=True):
        report = probe_windows_podman_sandbox(
            platform_name="Windows",
            architecture="AMD64",
            podman_executable="podman.exe",
            command_runner=lambda _command, _timeout, selected=result: selected,
        )
        assert report.reason is reason


def test_probe_rejects_timeout_oversized_stderr_and_invalid_version() -> None:
    def timed_out(_command: tuple[str, ...], _timeout: float) -> HostCommandResult:
        raise TimeoutError

    timeout = probe_windows_podman_sandbox(
        platform_name="Windows",
        architecture="AMD64",
        podman_executable="podman.exe",
        command_runner=timed_out,
    )
    assert timeout.reason is WindowsSandboxCapabilityReason.PODMAN_COMMAND_FAILED

    oversized = probe_windows_podman_sandbox(
        platform_name="Windows",
        architecture="AMD64",
        podman_executable="podman.exe",
        command_runner=lambda _command, _timeout: HostCommandResult(
            0, b"{}", b"x" * (1024 * 1024 + 1)
        ),
    )
    assert oversized.reason is WindowsSandboxCapabilityReason.PODMAN_RESPONSE_INVALID

    def invalid_version(command: tuple[str, ...], timeout: float) -> HostCommandResult:
        if command[1] == "version":
            return HostCommandResult(0, b'{"Client":{"Version":"latest"}}', b"")
        return _successful_command(command, timeout)

    incompatible = probe_windows_podman_sandbox(
        platform_name="Windows",
        architecture="AMD64",
        podman_executable="podman.exe",
        command_runner=invalid_version,
    )
    assert incompatible.reason is WindowsSandboxCapabilityReason.PODMAN_RESPONSE_INVALID


def test_capability_report_rejects_missing_extra_or_unavailable_control_claims() -> None:
    report = _ready_report()
    payload = report.model_dump(mode="json")

    missing = {**payload, "required_controls": payload["required_controls"][:-1]}
    with pytest.raises(ValidationError, match="every required control"):
        WindowsSandboxCapabilityReport.model_validate(missing)

    extra = {**payload, "observed_controls": [*payload["observed_controls"], "network-deny"]}
    with pytest.raises(ValidationError, match="only local WSL2 and rootless"):
        WindowsSandboxCapabilityReport.model_validate(extra)

    unavailable = create_windows_sandbox_capability_report(
        host_os="Windows",
        host_architecture="AMD64",
        status=WindowsSandboxCapabilityStatus.RUNTIME_MISSING,
        reason=WindowsSandboxCapabilityReason.PODMAN_NOT_FOUND,
    ).model_dump(mode="json")
    unavailable["observed_controls"] = ["rootless-runtime"]
    with pytest.raises(ValidationError, match="unavailable"):
        WindowsSandboxCapabilityReport.model_validate(unavailable)


def test_create_command_contains_enforcement_controls_and_no_writable_host_output(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "podman.exe"
    executable.write_bytes(b"fixture")
    input_directory = tmp_path / "inputs"
    control_directory = tmp_path / "control"
    input_directory.mkdir()
    control_directory.mkdir()
    plan = _plan()

    command = build_windows_podman_create_command(
        _ready_report(),
        plan,
        podman_executable=executable,
        container_name="forgegate-0123456789abcdef",
        image=WINDOWS_SANDBOX_PROBE_IMAGE,
        input_directory=input_directory,
        control_directory=control_directory,
        runner_argv=("/usr/local/bin/python", "-I", "-S", "-m", "forgegate_plugin_runner"),
    )
    rendered = "\n".join(command)
    for required in (
        "--network=none",
        "--ipc=none",
        "--read-only",
        "--read-only-tmpfs=false",
        "--cap-drop=all",
        "--security-opt=no-new-privileges",
        "--pids-limit=1",
        "--memory=268435456",
        "--memory-swap=268435456",
        "--ulimit=cpu=30:30",
        "--user=65532:65532",
        "--entrypoint=/usr/bin/env",
        "-i",
        f"FORGEGATE_RUN_PLAN_ID={plan.run_plan_id}",
    ):
        assert required in command
    assert "destination=/forgegate/input,ro=true" in rendered
    assert "destination=/forgegate/control,ro=true" in rendered
    assert "/forgegate/output:rw,noexec,nosuid,nodev" in rendered
    assert "destination=/forgegate/output" not in rendered


def test_create_command_rejects_unready_unpinned_wrong_backend_and_unsafe_roots(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "podman.exe"
    executable.write_bytes(b"fixture")
    inputs = tmp_path / "inputs"
    controls = tmp_path / "controls"
    inputs.mkdir()
    controls.mkdir()
    arguments = {
        "podman_executable": executable,
        "container_name": "forgegate-0123456789abcdef",
        "image": WINDOWS_SANDBOX_PROBE_IMAGE,
        "input_directory": inputs,
        "control_directory": controls,
        "runner_argv": ("runner",),
    }

    unavailable = create_windows_sandbox_capability_report(
        host_os="Windows",
        host_architecture="AMD64",
        status=WindowsSandboxCapabilityStatus.RUNTIME_MISSING,
        reason=WindowsSandboxCapabilityReason.PODMAN_NOT_FOUND,
    )
    with pytest.raises(WindowsSandboxError):
        build_windows_podman_create_command(unavailable, _plan(), **arguments)
    with pytest.raises(ValueError, match="exact sha256"):
        build_windows_podman_create_command(
            _ready_report(), _plan(), **{**arguments, "image": "python:latest"}
        )
    with pytest.raises(WindowsSandboxError, match="does not select"):
        build_windows_podman_create_command(
            _ready_report(), _plan(backend="other-backend"), **arguments
        )
    with pytest.raises(WindowsSandboxError, match="contract version"):
        build_windows_podman_create_command(
            _ready_report(), _plan(backend_version="2.0.0"), **arguments
        )
    with pytest.raises(WindowsSandboxError, match="sub-second"):
        build_windows_podman_create_command(_ready_report(), _plan(cpu_time_ms=999), **arguments)
    nested = inputs / "control"
    nested.mkdir()
    with pytest.raises(ValueError, match="separate roots"):
        build_windows_podman_create_command(
            _ready_report(), _plan(), **{**arguments, "control_directory": nested}
        )


def test_create_command_rejects_invalid_executable_name_roots_and_runner(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "podman.exe"
    executable.write_bytes(b"fixture")
    inputs = tmp_path / "inputs"
    controls = tmp_path / "controls"
    inputs.mkdir()
    controls.mkdir()
    arguments = {
        "podman_executable": executable,
        "container_name": "forgegate-0123456789abcdef",
        "image": WINDOWS_SANDBOX_PROBE_IMAGE,
        "input_directory": inputs,
        "control_directory": controls,
        "runner_argv": ("runner",),
    }
    with pytest.raises(ValueError, match="broker-generated"):
        build_windows_podman_create_command(
            _ready_report(), _plan(), **{**arguments, "container_name": "user-name"}
        )
    with pytest.raises(ValueError, match="executable is unavailable"):
        build_windows_podman_create_command(
            _ready_report(),
            _plan(),
            **{**arguments, "podman_executable": tmp_path / "missing.exe"},
        )
    with pytest.raises(ValueError, match="must be absolute"):
        build_windows_podman_create_command(
            _ready_report(), _plan(), **{**arguments, "input_directory": Path("relative")}
        )
    unsafe = tmp_path / "unsafe,root"
    unsafe.mkdir()
    with pytest.raises(ValueError, match="unsupported characters"):
        build_windows_podman_create_command(
            _ready_report(), _plan(), **{**arguments, "control_directory": unsafe}
        )
    with pytest.raises(ValueError, match="bounded non-empty"):
        build_windows_podman_create_command(
            _ready_report(), _plan(), **{**arguments, "runner_argv": ("",)}
        )


def test_capability_report_loads_through_public_config_and_cli_is_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _ready_report()
    path = tmp_path / "sandbox-capability.json"
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    assert load_config(path) == report

    monkeypatch.setattr("forgegate.cli.probe_windows_podman_sandbox", lambda: report)
    result = runner.invoke(app, ["plugins", "sandbox-status"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "READY_FOR_ADVERSARIAL_VERIFICATION"
    assert payload["external_plugin_execution"] == "PROHIBITED"
