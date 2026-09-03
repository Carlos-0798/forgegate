from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from importlib import metadata
from pathlib import Path

import pytest
from pydantic import ValidationError

from forgegate.canonical import canonical_json
from forgegate.domain.enums import EvidenceTrust, VerificationLevel
from forgegate.domain.models import ArtifactReference, EvidenceRecord, ExecutionContext
from forgegate.plugins import (
    WINDOWS_PODMAN_BACKEND,
    WINDOWS_PODMAN_BACKEND_VERSION,
    WINDOWS_SANDBOX_PROBE_IMAGE,
    PluginBrokerError,
    PluginBrokerRequest,
    PluginCapability,
    PluginCleanupResult,
    PluginExecutionSummary,
    PluginExecutionTarget,
    PluginOutputDocument,
    PluginPermission,
    PluginResourceLimits,
    PluginRunIssueCode,
    PluginRunReceipt,
    PluginRunState,
    PluginRunSubject,
    SandboxObservation,
    SQLitePluginRunRepository,
    WindowsBrokerAuthorization,
    WindowsPluginBroker,
    create_plugin_manifest,
    create_plugin_protocol_message,
    create_plugin_run_plan,
    create_plugin_run_transition,
    create_plugin_validated_output,
    create_windows_sandbox_capability_report,
    plugin_output_set_id,
)
from forgegate.plugins.execution_models import (
    PluginProtocolDirection,
    PluginProtocolMessageKind,
)
from forgegate.plugins.run_store import PluginRunStoreError
from forgegate.plugins.windows_sandbox import (
    WindowsSandboxCapabilityReason,
    WindowsSandboxCapabilityStatus,
    WindowsSandboxControl,
)

BASE_TIME = datetime(2026, 9, 3, 20, 0, tzinfo=UTC)
PLUGIN_ID = "example.production-broker"
PACKAGE = "production_broker_fixture"
INPUT = (
    b'{"collected_at":"2026-09-03T20:00:00Z",'
    b'"commit_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
)


def _manifest():
    return create_plugin_manifest(
        plugin_id=PLUGIN_ID,
        display_name="Production Broker Fixture",
        description="Generic isolated production broker test fixture.",
        plugin_version="1.0.0",
        forgegate_api_version="1",
        capabilities=(PluginCapability.COLLECTOR,),
        input_schemas=("example.production-input.v1",),
        permissions=(PluginPermission.ARTIFACT_READ, PluginPermission.FILESYSTEM_WRITE),
        output_evidence_kinds=("test.metric",),
    )


def _distribution(root: Path) -> metadata.Distribution:
    root.mkdir()
    package = root / PACKAGE
    package.mkdir()
    (package / "__init__.py").write_text("\n", encoding="utf-8")
    (package / "runtime.py").write_text(
        "raise RuntimeError('host import is forbidden')\n", encoding="utf-8"
    )
    (package / "forgegate-plugin.json").write_text(
        _manifest().model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    dist_info = root / "forgegate_production_broker_fixture-1.0.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.4\nName: forgegate-production-broker-fixture\nVersion: 1.0.0\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(
        f"[forgegate.plugins.v1]\n{PLUGIN_ID} = {PACKAGE}.runtime:plugin\n",
        encoding="utf-8",
    )
    members = (
        f"{PACKAGE}/__init__.py",
        f"{PACKAGE}/runtime.py",
        f"{PACKAGE}/forgegate-plugin.json",
        f"{dist_info.name}/METADATA",
        f"{dist_info.name}/entry_points.txt",
        f"{dist_info.name}/RECORD",
    )
    (dist_info / "RECORD").write_text(
        "".join(f"{member},,\n" for member in members), encoding="utf-8"
    )
    result = tuple(metadata.distributions(path=[str(root)]))
    assert len(result) == 1
    return result[0]


def _plan(*, planned_at: datetime = BASE_TIME):
    manifest = _manifest()
    permissions = (PluginPermission.ARTIFACT_READ, PluginPermission.FILESYSTEM_WRITE)
    return create_plugin_run_plan(
        target=PluginExecutionTarget(
            distribution_name="forgegate-production-broker-fixture",
            distribution_version="1.0.0",
            entry_point_name=PLUGIN_ID,
            entry_point_value=f"{PACKAGE}.runtime:plugin",
            manifest=manifest,
        ),
        input_schema="example.production-input.v1",
        inputs=(
            PluginRunSubject(
                name="inputs/source.json",
                media_type="application/json",
                digest="sha256:" + hashlib.sha256(INPUT).hexdigest(),
                size_bytes=len(INPUT),
            ),
        ),
        expected_output_evidence_kinds=("test.metric",),
        approved_permissions=permissions,
        enforced_permissions=permissions,
        enforcement_backend=WINDOWS_PODMAN_BACKEND,
        enforcement_backend_version=WINDOWS_PODMAN_BACKEND_VERSION,
        resource_limits=PluginResourceLimits(),
        planned_at=planned_at,
    )


def _authorization() -> WindowsBrokerAuthorization:
    capability = create_windows_sandbox_capability_report(
        host_os="Windows",
        host_architecture="AMD64",
        runtime_version="5.8.6",
        server_runtime_version="5.8.6",
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
    return WindowsBrokerAuthorization(
        capability=capability,
        podman_executable=Path(sys.executable),
        image=WINDOWS_SANDBOX_PROBE_IMAGE,
        image_id="sha256:" + "1" * 64,
    )


def _evidence(plan, *, trust: EvidenceTrust = EvidenceTrust.UNSIGNED_LOCAL) -> EvidenceRecord:
    subject = plan.inputs[0]
    return EvidenceRecord(
        evidence_id="plugin.test.metric",
        kind="test.metric",
        scope="generic-fixture",
        value={"passed": True},
        status="observed",
        source_tool="production-broker-fixture",
        source_version="1.0.0",
        execution_context=ExecutionContext(commit_sha="a" * 40),
        artifact=ArtifactReference(
            path_or_uri=subject.name,
            media_type=subject.media_type,
            sha256=subject.digest.removeprefix("sha256:"),
            size_bytes=subject.size_bytes,
        ),
        collected_at=BASE_TIME,
        trust=trust,
        verification_level=VerificationLevel.DECLARED,
    )


def _executor(
    *,
    change_second: bool = False,
    extra: bool = False,
    high_trust: bool = False,
    protocol_case: str | None = None,
) -> tuple[Callable[..., SandboxObservation], list[int]]:
    calls: list[int] = []

    def execute(
        _command: tuple[str, ...],
        _authorization_value: WindowsBrokerAuthorization,
        _container_name: str,
        plan,
        _run_root: Path,
        on_ready: Callable[[bytes], None],
    ) -> SandboxObservation:
        calls.append(1)
        ready = create_plugin_protocol_message(
            run_plan_id=(
                "sha256:" + "f" * 64 if protocol_case == "wrong-ready-plan" else plan.run_plan_id
            ),
            sequence=1,
            direction=PluginProtocolDirection.PLUGIN_TO_CORE,
            kind=PluginProtocolMessageKind.READY,
        )
        ready_bytes = canonical_json(ready.model_dump(mode="json")).encode()
        if protocol_case == "noncanonical-ready":
            ready_bytes += b"\n"
        on_ready(ready_bytes)
        document = (
            PluginOutputDocument(
                run_plan_id=plan.run_plan_id,
                evidence=_evidence(
                    plan,
                    trust=(
                        EvidenceTrust.CLAIMED_CI_METADATA
                        if high_trust
                        else EvidenceTrust.UNSIGNED_LOCAL
                    ),
                ),
            )
            if not high_trust
            else {
                "schema_version": "forgegate.plugin-output.v1",
                "run_plan_id": plan.run_plan_id,
                "evidence": _evidence(plan).model_dump(mode="json")
                | {"trust": "claimed_ci_metadata"},
            }
        )
        payload = (
            document.model_dump(mode="json")
            if isinstance(document, PluginOutputDocument)
            else document
        )
        content = canonical_json(payload).encode()
        subject = PluginRunSubject(
            name="evidence/plugin.test.metric.json",
            media_type="application/vnd.forgegate.plugin-output+json",
            digest="sha256:" + hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        )
        output = create_plugin_validated_output(
            subject=subject, evidence_kind="test.metric", evidence_id="plugin.test.metric"
        )
        terminal = create_plugin_protocol_message(
            run_plan_id=plan.run_plan_id,
            sequence=2,
            direction=PluginProtocolDirection.PLUGIN_TO_CORE,
            kind=PluginProtocolMessageKind.RESULT,
            output_set_id=plugin_output_set_id((output,)),
        )
        terminal_bytes = canonical_json(terminal.model_dump(mode="json")).encode()
        if protocol_case == "noncanonical-terminal":
            terminal_bytes += b"\n"
        first: dict[str, bytes] = {
            "protocol/ready.json": ready_bytes,
            "protocol/terminal.json": terminal_bytes,
            subject.name: content,
        }
        if extra:
            first["unexpected.txt"] = b"bad"
        second = dict(first)
        if change_second:
            second[subject.name] += b" "
        return SandboxObservation(
            ready_bytes=ready_bytes,
            terminal_bytes=None if protocol_case == "missing-terminal" else terminal_bytes,
            first_snapshot=first,
            second_snapshot=second,
            execution=PluginExecutionSummary(
                runner_started=True,
                ready_observed=True,
                completion_observed=True,
                elapsed_ms=25,
                stdout_bytes=0,
                stderr_bytes=0,
            ),
            container_removed=True,
        )

    return execute, calls


def _request(tmp_path: Path, plan) -> PluginBrokerRequest:
    artifacts = tmp_path / "artifacts"
    work = tmp_path / "work"
    outputs = tmp_path / "outputs"
    for directory in (artifacts, work, outputs):
        directory.mkdir()
    (artifacts / "source.json").write_bytes(INPUT)
    evidence = tmp_path / "sandbox.json"
    evidence.write_text("{}", encoding="utf-8")
    return PluginBrokerRequest(
        plan=plan,
        artifact_root=artifacts,
        input_paths={"inputs/source.json": "source.json"},
        work_root=work,
        accepted_output_root=outputs,
        sandbox_evidence_path=evidence,
        idempotency_key="plugin:test:one",
    )


def _broker(
    tmp_path: Path,
    executor: Callable[..., SandboxObservation],
    *,
    clock_start: datetime = BASE_TIME + timedelta(seconds=1),
) -> WindowsPluginBroker:
    distribution = _distribution(tmp_path / "site")
    ticks = iter(clock_start + timedelta(milliseconds=index) for index in range(20))
    repository = SQLitePluginRunRepository(tmp_path / "plugin-runs.db")
    return WindowsPluginBroker(
        repository,
        authorizer=lambda _request: _authorization(),
        executor=executor,
        clock=lambda: next(ticks),
        distributions=(distribution,),
    )


def test_broker_executes_without_host_import_and_replays_exact_receipt(tmp_path: Path) -> None:
    executor, calls = _executor()
    broker = _broker(tmp_path, executor)
    request = _request(tmp_path, _plan())
    receipt = broker.execute(request)
    replay = broker.execute(request)

    assert receipt == replay
    assert receipt.result.status is PluginRunState.SUCCEEDED
    assert receipt.accepted_outputs_registered is True
    assert receipt.cleanup == PluginCleanupResult(container_removed=True, staging_removed=True)
    assert [item.kind.value for item in receipt.protocol_messages] == ["START", "READY", "RESULT"]
    assert calls == [1]
    assert PACKAGE not in sys.modules
    registered = tuple(request.accepted_output_root.rglob("*.json"))
    assert len(registered) == 1
    assert PluginOutputDocument.model_validate(json.loads(registered[0].read_bytes()))


@pytest.mark.parametrize(
    ("executor_options", "expected"),
    [
        ({"change_second": True}, PluginRunIssueCode.PLUGIN_OUTPUT_INVALID),
        ({"extra": True}, PluginRunIssueCode.PLUGIN_OUTPUT_INVALID),
        ({"high_trust": True}, PluginRunIssueCode.PLUGIN_OUTPUT_INVALID),
    ],
)
def test_broker_fails_closed_on_untrusted_output(
    tmp_path: Path, executor_options: Mapping[str, bool], expected: PluginRunIssueCode
) -> None:
    executor, _ = _executor(**executor_options)
    broker = _broker(tmp_path, executor)
    receipt = broker.execute(_request(tmp_path, _plan()))
    assert receipt.result.status is PluginRunState.ERROR
    assert receipt.result.issue is not None
    assert receipt.result.issue.code is expected
    assert receipt.accepted_outputs_registered is False


@pytest.mark.parametrize(
    "protocol_case",
    ("wrong-ready-plan", "noncanonical-ready", "noncanonical-terminal", "missing-terminal"),
)
def test_broker_rejects_invalid_runtime_protocol(tmp_path: Path, protocol_case: str) -> None:
    executor, _ = _executor(protocol_case=protocol_case)
    receipt = _broker(tmp_path, executor).execute(_request(tmp_path, _plan()))
    assert receipt.result.status is PluginRunState.ERROR
    assert receipt.result.issue is not None
    assert receipt.result.issue.code is PluginRunIssueCode.PLUGIN_PROTOCOL_INVALID
    assert receipt.accepted_outputs_registered is False


def test_store_is_append_only_and_idempotency_conflicts(tmp_path: Path) -> None:
    plan = _plan()
    repository = SQLitePluginRunRepository(tmp_path / "plugin-runs.db")
    repository.initialize()
    planned = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=0,
        from_state=None,
        to_state=PluginRunState.PLANNED,
        occurred_at=BASE_TIME,
    )
    reservation = repository.reserve(plan, planned, idempotency_key="plugin:test:one")
    assert reservation.created is True
    assert repository.reserve(plan, planned, idempotency_key="plugin:test:one").created is False
    other = _plan(planned_at=BASE_TIME + timedelta(seconds=1))
    other_planned = create_plugin_run_transition(
        run_plan_id=other.run_plan_id,
        sequence=0,
        from_state=None,
        to_state=PluginRunState.PLANNED,
        occurred_at=other.planned_at,
    )
    with pytest.raises(PluginRunStoreError, match="another run plan"):
        repository.reserve(other, other_planned, idempotency_key="plugin:test:one")
    with (
        sqlite3.connect(repository.database_path) as connection,
        pytest.raises(sqlite3.IntegrityError, match="append-only"),
    ):
        connection.execute("DELETE FROM plugin_run_plans")


def test_interrupted_run_is_closed_as_error_without_reexecution(tmp_path: Path) -> None:
    executor, calls = _executor()
    broker = _broker(tmp_path, executor)
    request = _request(tmp_path, _plan())
    planned = create_plugin_run_transition(
        run_plan_id=request.plan.run_plan_id,
        sequence=0,
        from_state=None,
        to_state=PluginRunState.PLANNED,
        occurred_at=BASE_TIME,
    )
    broker.repository.initialize()
    broker.repository.reserve(request.plan, planned, idempotency_key=request.idempotency_key)
    recovered = broker.execute(request)
    assert recovered.result.status is PluginRunState.ERROR
    assert recovered.recovered_after_interruption is True
    assert recovered.result.issue is not None
    assert recovered.result.issue.code is PluginRunIssueCode.PLUGIN_EXIT_ERROR
    assert calls == []


def test_interrupted_run_reports_cleanup_failure(tmp_path: Path) -> None:
    executor, calls = _executor()
    broker = _broker(tmp_path, executor)
    request = replace(
        _request(tmp_path, _plan()), podman_executable=tmp_path / "missing-podman.exe"
    )
    planned = create_plugin_run_transition(
        run_plan_id=request.plan.run_plan_id,
        sequence=0,
        from_state=None,
        to_state=PluginRunState.PLANNED,
        occurred_at=BASE_TIME,
    )
    broker.repository.initialize()
    broker.repository.reserve(request.plan, planned, idempotency_key=request.idempotency_key)

    receipt = broker.execute(request)

    assert receipt.result.issue is not None
    assert receipt.result.issue.code is PluginRunIssueCode.PLUGIN_CLEANUP_FAILED
    assert receipt.cleanup.container_removed is False
    assert receipt.recovered_after_interruption is True
    assert calls == []


def test_broker_persists_prestart_authorization_failure(tmp_path: Path) -> None:
    executor, calls = _executor()

    def reject(_request: PluginBrokerRequest) -> WindowsBrokerAuthorization:
        raise PluginBrokerError(
            PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE, "test runtime unavailable"
        )

    distribution = _distribution(tmp_path / "site")
    repository = SQLitePluginRunRepository(tmp_path / "plugin-runs.db")
    broker = WindowsPluginBroker(
        repository,
        authorizer=reject,
        executor=executor,
        clock=lambda: BASE_TIME + timedelta(seconds=1),
        distributions=(distribution,),
    )
    receipt = broker.execute(_request(tmp_path, _plan()))
    assert receipt.result.status is PluginRunState.ERROR
    assert receipt.result.issue is not None
    assert receipt.result.issue.code is PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE
    assert len(receipt.result.transitions) == 2
    assert receipt.protocol_messages == ()
    assert calls == []


def test_broker_maps_runtime_limit_and_cleanup_failure(tmp_path: Path) -> None:
    base_executor, _ = _executor()

    def limited(*args, **kwargs) -> SandboxObservation:
        observed = base_executor(*args, **kwargs)
        return SandboxObservation(
            ready_bytes=observed.ready_bytes,
            terminal_bytes=None,
            first_snapshot={},
            second_snapshot={},
            execution=observed.execution,
            container_removed=False,
            issue=PluginRunIssueCode.PLUGIN_RESOURCE_LIMIT,
        )

    receipt = _broker(tmp_path, limited).execute(_request(tmp_path, _plan()))
    assert receipt.result.issue is not None
    assert receipt.result.issue.code is PluginRunIssueCode.PLUGIN_CLEANUP_FAILED
    assert receipt.cleanup.container_removed is False


def test_broker_rejects_input_mapping_mismatch(tmp_path: Path) -> None:
    executor, calls = _executor()
    broker = _broker(tmp_path, executor)
    request = _request(tmp_path, _plan())
    invalid = replace(request, input_paths={"inputs/other.json": "source.json"})
    receipt = broker.execute(invalid)
    assert receipt.result.issue is not None
    assert receipt.result.issue.code is PluginRunIssueCode.PLUGIN_PLAN_INVALID
    assert calls == []


def test_broker_rejects_missing_installed_distribution(tmp_path: Path) -> None:
    executor, calls = _executor()
    repository = SQLitePluginRunRepository(tmp_path / "plugin-runs.db")
    broker = WindowsPluginBroker(
        repository,
        authorizer=lambda _request: _authorization(),
        executor=executor,
        clock=lambda: BASE_TIME + timedelta(seconds=1),
        distributions=(),
    )
    receipt = broker.execute(_request(tmp_path, _plan()))
    assert receipt.result.issue is not None
    assert receipt.result.issue.code is PluginRunIssueCode.PLUGIN_PLAN_INVALID
    assert calls == []


def test_store_rejects_invalid_keys_chains_and_missing_runs(tmp_path: Path) -> None:
    plan = _plan()
    repository = SQLitePluginRunRepository(tmp_path / "plugin-runs.db")
    repository.initialize()
    planned = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=0,
        from_state=None,
        to_state=PluginRunState.PLANNED,
        occurred_at=BASE_TIME,
    )
    with pytest.raises(PluginRunStoreError, match="idempotency key"):
        repository.reserve(plan, planned, idempotency_key="bad key")
    repository.reserve(plan, planned, idempotency_key="plugin:test:one")
    assert len(repository.incomplete()) == 1
    with pytest.raises(PluginRunStoreError, match="not found"):
        repository.get("sha256:" + "f" * 64)
    invalid_transition = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=1,
        from_state=PluginRunState.PLANNED,
        to_state=PluginRunState.STARTING,
        occurred_at=BASE_TIME + timedelta(seconds=1),
        previous_transition_id=planned.transition_id,
    )
    changed = invalid_transition.model_copy(update={"previous_transition_id": "sha256:" + "f" * 64})
    with pytest.raises(PluginRunStoreError, match="transition chain"):
        repository.append_transition(changed)


def test_store_rejects_foreign_and_corrupt_databases(tmp_path: Path) -> None:
    foreign = tmp_path / "foreign.db"
    sqlite3.connect(foreign).close()
    with pytest.raises(PluginRunStoreError, match="PLUGIN_AUDIT_FAILED"):
        SQLitePluginRunRepository(foreign).initialize()

    repository = SQLitePluginRunRepository(tmp_path / "plugin-runs.db")
    repository.initialize()
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "INSERT INTO plugin_run_plans(run_plan_id, plan_json) VALUES(?, ?)",
            ("sha256:" + "f" * 64, "{not-json}"),
        )
        connection.execute(
            "INSERT INTO plugin_run_transitions"
            "(run_plan_id, sequence, transition_id, transition_json) VALUES(?, 0, ?, ?)",
            ("sha256:" + "f" * 64, "sha256:" + "e" * 64, "{}"),
        )
    with pytest.raises(PluginRunStoreError, match="corrupt"):
        repository.get("sha256:" + "f" * 64)


def test_receipt_rejects_unregistered_success_and_message_reordering(tmp_path: Path) -> None:
    executor, _ = _executor()
    receipt = _broker(tmp_path, executor).execute(_request(tmp_path, _plan()))
    with pytest.raises(ValidationError, match="complete execution and cleanup"):
        PluginRunReceipt.model_validate(
            {**receipt.model_dump(mode="json"), "accepted_outputs_registered": False}
        )
    payload = receipt.model_dump(mode="json")
    payload["protocol_messages"] = list(reversed(payload["protocol_messages"]))
    with pytest.raises(ValidationError, match="sequence order"):
        PluginRunReceipt.model_validate(payload)
