from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import forgegate.plugins.workflow as workflow
from forgegate.artifacts import ArtifactRegistry
from forgegate.assembly import CollectionResultLoader, assemble_evidence_bundle
from forgegate.canonical import canonical_json
from forgegate.cli import app
from forgegate.domain.enums import EvidenceTrust, VerificationLevel
from forgegate.domain.models import ArtifactReference, EvidenceRecord, ExecutionContext
from forgegate.plugins import (
    WINDOWS_PODMAN_BACKEND,
    WINDOWS_PODMAN_BACKEND_VERSION,
    DiscoveredPlugin,
    PluginCleanupResult,
    PluginDiscoveryStatus,
    PluginExecutionSummary,
    PluginExecutionTarget,
    PluginOutputDocument,
    PluginPermission,
    PluginResourceLimits,
    PluginRunIssue,
    PluginRunIssueCode,
    PluginRunState,
    PluginRunSubject,
    SQLitePluginRunRepository,
    collect_plugin_evidence,
    create_plugin_manifest,
    create_plugin_protocol_message,
    create_plugin_run_plan,
    create_plugin_run_receipt,
    create_plugin_run_result,
    create_plugin_run_transition,
    create_plugin_validated_output,
    list_plugin_runs,
    plugin_output_set_id,
    read_plugin_run,
)
from forgegate.plugins.execution_models import (
    PluginProtocolDirection,
    PluginProtocolMessageKind,
)
from forgegate.plugins.models import PluginCapability
from forgegate.plugins.workflow import PluginWorkflowError, _ensure_runtime_directory, _strict_json

BASE_TIME = datetime(2026, 9, 3, 20, 0, tzinfo=UTC)
runner = CliRunner()


def _plan(content: bytes):
    manifest = create_plugin_manifest(
        plugin_id="example.workflow-collector",
        display_name="Workflow Collector",
        description="Generic workflow test collector.",
        plugin_version="1.0.0",
        forgegate_api_version="1",
        capabilities=(PluginCapability.COLLECTOR,),
        input_schemas=("example.workflow-input.v1",),
        permissions=(PluginPermission.ARTIFACT_READ, PluginPermission.FILESYSTEM_WRITE),
        output_evidence_kinds=("test.metric",),
    )
    permissions = (PluginPermission.ARTIFACT_READ, PluginPermission.FILESYSTEM_WRITE)
    return create_plugin_run_plan(
        target=PluginExecutionTarget(
            distribution_name="workflow-collector",
            distribution_version="1.0.0",
            entry_point_name=manifest.plugin_id,
            entry_point_value="workflow_collector.runtime:plugin",
            manifest=manifest,
        ),
        input_schema="example.workflow-input.v1",
        inputs=(
            PluginRunSubject(
                name="inputs/source.json",
                media_type="application/json",
                digest="sha256:" + hashlib.sha256(content).hexdigest(),
                size_bytes=len(content),
            ),
        ),
        expected_output_evidence_kinds=("test.metric",),
        approved_permissions=permissions,
        enforced_permissions=permissions,
        enforcement_backend=WINDOWS_PODMAN_BACKEND,
        enforcement_backend_version=WINDOWS_PODMAN_BACKEND_VERSION,
        resource_limits=PluginResourceLimits(),
        planned_at=BASE_TIME,
    )


def _successful_run(tmp_path: Path):
    artifact_root = tmp_path / "artifacts"
    accepted_root = tmp_path / "accepted"
    artifact_root.mkdir(parents=True)
    accepted_root.mkdir()
    content = b'{"input":"generic"}'
    source = artifact_root / "inputs/source.json"
    source.parent.mkdir()
    source.write_bytes(content)
    plan = _plan(content)
    evidence = EvidenceRecord(
        evidence_id="plugin.workflow.metric",
        kind="test.metric",
        scope="generic-workflow",
        value={"passed": True},
        status="observed",
        source_tool="workflow-collector",
        source_version="1.0.0",
        execution_context=ExecutionContext(commit_sha="a" * 40),
        artifact=ArtifactReference(
            path_or_uri="inputs/source.json",
            media_type="application/json",
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        ),
        collected_at=BASE_TIME,
        trust=EvidenceTrust.UNSIGNED_LOCAL,
        verification_level=VerificationLevel.DECLARED,
    )
    document = PluginOutputDocument(run_plan_id=plan.run_plan_id, evidence=evidence)
    output_bytes = canonical_json(document.model_dump(mode="json")).encode()
    subject = PluginRunSubject(
        name="evidence/plugin.workflow.metric.json",
        media_type="application/vnd.forgegate.plugin-output+json",
        digest="sha256:" + hashlib.sha256(output_bytes).hexdigest(),
        size_bytes=len(output_bytes),
    )
    validated = create_plugin_validated_output(
        subject=subject,
        evidence_kind=evidence.kind,
        evidence_id=evidence.evidence_id,
    )
    output_set_id = plugin_output_set_id((validated,))
    start = create_plugin_protocol_message(
        run_plan_id=plan.run_plan_id,
        sequence=0,
        direction=PluginProtocolDirection.CORE_TO_PLUGIN,
        kind=PluginProtocolMessageKind.START,
        run_plan=plan,
    )
    ready = create_plugin_protocol_message(
        run_plan_id=plan.run_plan_id,
        sequence=1,
        direction=PluginProtocolDirection.PLUGIN_TO_CORE,
        kind=PluginProtocolMessageKind.READY,
    )
    terminal = create_plugin_protocol_message(
        run_plan_id=plan.run_plan_id,
        sequence=2,
        direction=PluginProtocolDirection.PLUGIN_TO_CORE,
        kind=PluginProtocolMessageKind.RESULT,
        output_set_id=output_set_id,
    )
    planned = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=0,
        from_state=None,
        to_state=PluginRunState.PLANNED,
        occurred_at=BASE_TIME,
    )
    starting = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=1,
        from_state=PluginRunState.PLANNED,
        to_state=PluginRunState.STARTING,
        occurred_at=BASE_TIME + timedelta(seconds=1),
        previous_transition_id=planned.transition_id,
        protocol_message_id=start.message_id,
    )
    running = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=2,
        from_state=PluginRunState.STARTING,
        to_state=PluginRunState.RUNNING,
        occurred_at=BASE_TIME + timedelta(seconds=2),
        previous_transition_id=starting.transition_id,
        protocol_message_id=ready.message_id,
    )
    succeeded = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=3,
        from_state=PluginRunState.RUNNING,
        to_state=PluginRunState.SUCCEEDED,
        occurred_at=BASE_TIME + timedelta(seconds=3),
        previous_transition_id=running.transition_id,
        protocol_message_id=terminal.message_id,
        output_set_id=output_set_id,
    )
    result = create_plugin_run_result(
        run_plan=plan,
        status=PluginRunState.SUCCEEDED,
        transitions=(planned, starting, running, succeeded),
        validated_outputs=(validated,),
    )
    receipt = create_plugin_run_receipt(
        result=result,
        protocol_messages=(start, ready, terminal),
        execution=PluginExecutionSummary(
            runner_started=True,
            ready_observed=True,
            completion_observed=True,
            elapsed_ms=10,
            exit_code=0,
            stdout_bytes=0,
            stderr_bytes=0,
        ),
        cleanup=PluginCleanupResult(container_removed=True, staging_removed=True),
        accepted_outputs_registered=True,
    )
    database = tmp_path / "plugin-runs.db"
    repository = SQLitePluginRunRepository(database)
    repository.initialize()
    repository.reserve(plan, planned, idempotency_key="workflow:success")
    repository.append_transition(starting)
    repository.append_transition(running)
    repository.complete(receipt)
    output = accepted_root / ("plugin-run-" + plan.run_plan_id.removeprefix("sha256:"))
    output_path = output / subject.name
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(output_bytes)
    return database, artifact_root, accepted_root, receipt


def _failed_receipt(success):
    plan = success.result.run_plan.model_copy(
        update={"planned_at": BASE_TIME + timedelta(minutes=1)}
    )
    plan = create_plugin_run_plan(
        target=plan.target,
        input_schema=plan.input_schema,
        inputs=plan.inputs,
        expected_output_evidence_kinds=plan.expected_output_evidence_kinds,
        approved_permissions=plan.approved_permissions,
        enforced_permissions=plan.enforced_permissions,
        enforcement_backend=plan.enforcement_backend,
        enforcement_backend_version=plan.enforcement_backend_version,
        resource_limits=plan.resource_limits,
        planned_at=plan.planned_at,
    )
    issue = PluginRunIssue(code=PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE)
    planned = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=0,
        from_state=None,
        to_state=PluginRunState.PLANNED,
        occurred_at=plan.planned_at,
    )
    failed = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=1,
        from_state=PluginRunState.PLANNED,
        to_state=PluginRunState.ERROR,
        occurred_at=plan.planned_at + timedelta(seconds=1),
        previous_transition_id=planned.transition_id,
        issue=issue,
    )
    result = create_plugin_run_result(
        run_plan=plan,
        status=PluginRunState.ERROR,
        transitions=(planned, failed),
        issue=issue,
    )
    return create_plugin_run_receipt(
        result=result,
        protocol_messages=(),
        execution=PluginExecutionSummary(
            runner_started=False,
            ready_observed=False,
            completion_observed=False,
            elapsed_ms=0,
            stdout_bytes=0,
            stderr_bytes=0,
        ),
        cleanup=PluginCleanupResult(container_removed=True, staging_removed=True),
        accepted_outputs_registered=False,
    )


def test_plugin_run_queries_collection_and_assembly_are_path_free(tmp_path: Path) -> None:
    database, artifact_root, accepted_root, receipt = _successful_run(tmp_path)
    record = read_plugin_run(database, receipt.result.run_plan.run_plan_id)
    page = list_plugin_runs(database, limit=1)
    collection = collect_plugin_evidence(
        database,
        receipt.result.run_plan.run_plan_id,
        artifact_root=artifact_root,
        accepted_output_root=accepted_root,
    )
    serialized = record.model_dump_json() + page.model_dump_json() + collection.model_dump_json()
    assert str(tmp_path) not in serialized
    assert record.receipt == receipt
    assert page.runs[0].state is PluginRunState.SUCCEEDED
    assert collection.evidence[0].trust is EvidenceTrust.UNSIGNED_LOCAL
    assert collection.evidence[0].verification_level is VerificationLevel.DECLARED

    collection_path = artifact_root / "plugin.collection.json"
    collection_path.write_text(collection.model_dump_json(indent=2), encoding="utf-8")
    loaded = CollectionResultLoader(ArtifactRegistry(artifact_root)).load("plugin.collection.json")
    assembly = assemble_evidence_bundle(
        (loaded,),
        candidate_commit="a" * 40,
        generated_at=BASE_TIME + timedelta(minutes=1),
        producer="forgegate",
        producer_version="test",
    )
    assert assembly.bundle.evidence == collection.evidence


def test_plugin_collection_rejects_tamper_and_failed_run(tmp_path: Path) -> None:
    database, artifact_root, accepted_root, receipt = _successful_run(tmp_path)
    output = next(accepted_root.rglob("*.json"))
    output.write_bytes(output.read_bytes() + b" ")
    with pytest.raises(PluginWorkflowError, match="PLUGIN_OUTPUT_CHANGED"):
        collect_plugin_evidence(
            database,
            receipt.result.run_plan.run_plan_id,
            artifact_root=artifact_root,
            accepted_output_root=accepted_root,
        )

    database, artifact_root, accepted_root, receipt = _successful_run(tmp_path / "same-size")
    output = next(accepted_root.rglob("*.json"))
    changed = bytearray(output.read_bytes())
    changed[-1] = ord(" ")
    output.write_bytes(changed)
    with pytest.raises(PluginWorkflowError, match="PLUGIN_OUTPUT_CHANGED"):
        collect_plugin_evidence(
            database,
            receipt.result.run_plan.run_plan_id,
            artifact_root=artifact_root,
            accepted_output_root=accepted_root,
        )

    database, artifact_root, accepted_root, receipt = _successful_run(tmp_path / "input-change")
    source = artifact_root / "inputs/source.json"
    source.write_bytes(b'{"input":"changed"}')
    with pytest.raises(PluginWorkflowError, match="PLUGIN_INPUT_CHANGED"):
        collect_plugin_evidence(
            database,
            receipt.result.run_plan.run_plan_id,
            artifact_root=artifact_root,
            accepted_output_root=accepted_root,
        )

    database, artifact_root, accepted_root, receipt = _successful_run(tmp_path / "extra")
    (next(accepted_root.iterdir()) / "extra.json").write_bytes(b"")
    with pytest.raises(PluginWorkflowError, match="member set"):
        collect_plugin_evidence(
            database,
            receipt.result.run_plan.run_plan_id,
            artifact_root=artifact_root,
            accepted_output_root=accepted_root,
        )


def test_plugin_collection_rejects_failed_or_unavailable_output(tmp_path: Path) -> None:
    database, artifact_root, accepted_root, receipt = _successful_run(tmp_path)
    failed = _failed_receipt(receipt)
    repository = SQLitePluginRunRepository(database)
    initial, terminal = failed.result.transitions
    repository.reserve(failed.result.run_plan, initial, idempotency_key="workflow:failure")
    repository.complete(failed)
    with pytest.raises(PluginWorkflowError, match="PLUGIN_RUN_NOT_SUCCESSFUL"):
        collect_plugin_evidence(
            database,
            failed.result.run_plan.run_plan_id,
            artifact_root=artifact_root,
            accepted_output_root=accepted_root,
        )
    assert terminal.to_state is PluginRunState.ERROR

    missing = accepted_root / "missing"
    missing.mkdir()
    with pytest.raises(PluginWorkflowError, match="PLUGIN_OUTPUT_UNAVAILABLE"):
        collect_plugin_evidence(
            database,
            receipt.result.run_plan.run_plan_id,
            artifact_root=artifact_root,
            accepted_output_root=missing,
        )
    unsafe = tmp_path / "accepted-file"
    unsafe.write_text("keep", encoding="utf-8")
    with pytest.raises(PluginWorkflowError, match="PLUGIN_PATH_UNSAFE"):
        collect_plugin_evidence(
            database,
            receipt.result.run_plan.run_plan_id,
            artifact_root=artifact_root,
            accepted_output_root=unsafe,
        )


def test_operator_workflow_builds_exact_plan_and_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _database, artifact_root, _accepted_root, receipt = _successful_run(tmp_path / "fixture")
    target = receipt.result.run_plan.target
    discovered = DiscoveredPlugin(
        distribution_name=target.distribution_name,
        distribution_version=target.distribution_version,
        entry_point_name=target.entry_point_name,
        entry_point_value=target.entry_point_value,
        manifest_path="workflow_collector/forgegate-plugin.json",
        plugin_id=target.manifest.plugin_id,
        manifest=target.manifest,
        status=PluginDiscoveryStatus.COMPATIBLE,
    )
    monkeypatch.setattr(
        workflow,
        "discover_plugins",
        lambda _distributions: type("Report", (), {"plugins": (discovered,)})(),
    )
    observed = {}

    class FakeBroker:
        def __init__(self, repository, *, distributions):
            observed["repository"] = repository
            observed["distributions"] = distributions

        def execute(self, request):
            observed["request"] = request
            assert request.plan == receipt.result.run_plan
            return receipt

    monkeypatch.setattr(workflow, "WindowsPluginBroker", FakeBroker)
    database = tmp_path / "state/plugin-runs.db"
    work = tmp_path / "state/work"
    accepted = tmp_path / "state/accepted"
    returned = workflow.execute_operator_plugin_run(
        plugin_id=target.manifest.plugin_id,
        input_schema=None,
        input_media_types={"inputs/source.json": "application/json"},
        approved_permissions=(
            PluginPermission.FILESYSTEM_WRITE,
            PluginPermission.ARTIFACT_READ,
            PluginPermission.ARTIFACT_READ,
        ),
        artifact_root=artifact_root,
        database_path=database,
        work_root=work,
        accepted_output_root=accepted,
        sandbox_evidence_path=tmp_path / "sandbox.json",
        idempotency_key="workflow:operator",
        planned_at=BASE_TIME,
        distributions=(),
    )
    assert returned == receipt
    assert database.parent.is_dir() and work.is_dir() and accepted.is_dir()
    assert observed["request"].input_paths == {"inputs/source.json": "inputs/source.json"}


def test_operator_workflow_rejects_selection_inputs_and_unsafe_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        workflow,
        "discover_plugins",
        lambda _distributions: type("Report", (), {"plugins": ()})(),
    )
    common = {
        "plugin_id": "example.missing-plugin",
        "input_schema": None,
        "input_media_types": {"source.json": "application/json"},
        "approved_permissions": (),
        "artifact_root": tmp_path,
        "database_path": tmp_path / "state/plugin-runs.db",
        "work_root": tmp_path / "state/work",
        "accepted_output_root": tmp_path / "state/output",
        "sandbox_evidence_path": tmp_path / "sandbox.json",
        "idempotency_key": "workflow:error",
        "planned_at": BASE_TIME,
        "distributions": (),
    }
    with pytest.raises(PluginWorkflowError, match="PLUGIN_SELECTION_INVALID"):
        workflow.execute_operator_plugin_run(**common)

    _database, artifact_root, _accepted_root, receipt = _successful_run(tmp_path / "valid")
    target = receipt.result.run_plan.target
    discovered = DiscoveredPlugin(
        distribution_name=target.distribution_name,
        distribution_version=target.distribution_version,
        entry_point_name=target.entry_point_name,
        entry_point_value=target.entry_point_value,
        manifest_path="workflow_collector/forgegate-plugin.json",
        plugin_id=target.manifest.plugin_id,
        manifest=target.manifest,
        status=PluginDiscoveryStatus.COMPATIBLE,
    )
    monkeypatch.setattr(
        workflow,
        "discover_plugins",
        lambda _distributions: type("Report", (), {"plugins": (discovered,)})(),
    )
    valid = common | {
        "plugin_id": target.manifest.plugin_id,
        "artifact_root": artifact_root,
        "approved_permissions": target.manifest.permissions,
        "input_media_types": {"inputs/source.json": "application/json"},
    }
    with pytest.raises(PluginWorkflowError, match="PLUGIN_INPUT_REQUIRED"):
        workflow.execute_operator_plugin_run(**(valid | {"input_media_types": {}}))
    with pytest.raises(PluginWorkflowError, match="PLUGIN_WORKFLOW_INVALID"):
        workflow.execute_operator_plugin_run(
            **(valid | {"input_media_types": {"missing.json": "application/json"}})
        )

    unsafe_parent = tmp_path / "not-a-directory"
    unsafe_parent.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(workflow, "WindowsPluginBroker", lambda *_args, **_kwargs: None)
    with pytest.raises(PluginWorkflowError, match="PLUGIN_PATH_UNSAFE"):
        workflow.execute_operator_plugin_run(
            **(valid | {"database_path": unsafe_parent / "plugin-runs.db"})
        )

    incompatible = discovered.model_copy(update={"status": PluginDiscoveryStatus.INCOMPATIBLE})
    monkeypatch.setattr(
        workflow,
        "discover_plugins",
        lambda _distributions: type("Report", (), {"plugins": (incompatible,)})(),
    )
    with pytest.raises(PluginWorkflowError, match="PLUGIN_SELECTION_INVALID"):
        workflow.execute_operator_plugin_run(**valid)


def test_operator_workflow_requires_explicit_schema_for_ambiguous_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _database, artifact_root, _accepted_root, receipt = _successful_run(tmp_path)
    original = receipt.result.run_plan.target
    manifest = create_plugin_manifest(
        plugin_id=original.manifest.plugin_id,
        display_name=original.manifest.display_name,
        description=original.manifest.description,
        plugin_version=original.manifest.plugin_version,
        forgegate_api_version="1",
        capabilities=(PluginCapability.COLLECTOR,),
        input_schemas=("example.a.v1", "example.b.v1"),
        permissions=original.manifest.permissions,
        output_evidence_kinds=original.manifest.output_evidence_kinds,
    )
    discovered = DiscoveredPlugin(
        distribution_name=original.distribution_name,
        distribution_version=original.distribution_version,
        entry_point_name=original.entry_point_name,
        entry_point_value=original.entry_point_value,
        manifest_path="workflow_collector/forgegate-plugin.json",
        plugin_id=manifest.plugin_id,
        manifest=manifest,
        status=PluginDiscoveryStatus.COMPATIBLE,
    )
    monkeypatch.setattr(
        workflow,
        "discover_plugins",
        lambda _distributions: type("Report", (), {"plugins": (discovered,)})(),
    )
    with pytest.raises(PluginWorkflowError, match="PLUGIN_INPUT_SCHEMA_REQUIRED"):
        workflow.execute_operator_plugin_run(
            plugin_id=manifest.plugin_id,
            input_schema=None,
            input_media_types={"inputs/source.json": "application/json"},
            approved_permissions=manifest.permissions,
            artifact_root=artifact_root,
            database_path=tmp_path / "state/plugin-runs.db",
            work_root=tmp_path / "state/work",
            accepted_output_root=tmp_path / "state/output",
            sandbox_evidence_path=tmp_path / "sandbox.json",
            idempotency_key="workflow:ambiguous",
            planned_at=BASE_TIME,
            distributions=(),
        )


def test_plugin_record_and_page_reject_invalid_shapes(tmp_path: Path) -> None:
    database, _artifact_root, _accepted_root, receipt = _successful_run(tmp_path)
    record = read_plugin_run(database, receipt.result.run_plan.run_plan_id)
    page = list_plugin_runs(database, limit=1)
    with pytest.raises(ValidationError, match="record_id"):
        type(record).model_validate(
            record.model_dump(mode="json") | {"record_id": "sha256:" + "f" * 64}
        )
    with pytest.raises(ValidationError, match="page_id"):
        type(page).model_validate(page.model_dump(mode="json") | {"page_id": "sha256:" + "f" * 64})
    empty = list_plugin_runs(database, after_run_plan_id="sha256:" + "f" * 64, limit=1)
    assert empty.runs == () and empty.next_after_run_plan_id is None

    bad_initial = record.model_copy(
        update={
            "transitions": (
                record.transitions[0].model_copy(update={"from_state": PluginRunState.PLANNED}),
                *record.transitions[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="initial transition"):
        bad_initial.record_chain_and_identity_hold()
    bad_plan = record.model_copy(
        update={
            "transitions": (
                record.transitions[0].model_copy(update={"run_plan_id": "sha256:" + "f" * 64}),
                *record.transitions[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="does not match its plan"):
        bad_plan.record_chain_and_identity_hold()
    bad_chain = record.model_copy(
        update={
            "transitions": (
                record.transitions[0],
                record.transitions[1].model_copy(
                    update={"previous_transition_id": "sha256:" + "f" * 64}
                ),
                *record.transitions[2:],
            )
        }
    )
    with pytest.raises(ValueError, match="chain is invalid"):
        bad_chain.record_chain_and_identity_hold()
    with pytest.raises(ValueError, match="requires its receipt"):
        record.model_copy(update={"receipt": None}).record_chain_and_identity_hold()
    with pytest.raises(ValueError, match="does not match its durable state"):
        record.model_copy(
            update={
                "receipt": receipt.model_copy(
                    update={
                        "result": receipt.result.model_copy(
                            update={"run_plan": _failed_receipt(receipt).result.run_plan}
                        )
                    }
                )
            }
        ).record_chain_and_identity_hold()

    summary = page.runs[0]
    with pytest.raises(ValueError, match="exactly one receipt"):
        summary.model_copy(update={"receipt_id": None}).terminal_shape_is_consistent()
    with pytest.raises(ValueError, match="successful"):
        summary.model_copy(
            update={"issue": PluginRunIssueCode.PLUGIN_OUTPUT_INVALID}
        ).terminal_shape_is_consistent()
    failed_summary = summary.model_copy(
        update={
            "state": PluginRunState.ERROR,
            "issue": None,
            "accepted_outputs_registered": False,
        }
    )
    with pytest.raises(ValueError, match="failed"):
        failed_summary.terminal_shape_is_consistent()
    incomplete = summary.model_copy(
        update={"state": PluginRunState.PLANNED, "receipt_id": None, "output_count": 1}
    )
    with pytest.raises(ValueError, match="incomplete"):
        incomplete.terminal_shape_is_consistent()

    duplicate_page = page.model_copy(update={"runs": (summary, summary)})
    with pytest.raises(ValueError, match="unique and ordered"):
        duplicate_page.page_order_and_identity_hold()
    cursor_page = page.model_copy(update={"query_after_run_plan_id": summary.run_plan_id})
    with pytest.raises(ValueError, match="before its cursor"):
        cursor_page.page_order_and_identity_hold()
    next_page = page.model_copy(update={"next_after_run_plan_id": "sha256:" + "f" * 64})
    with pytest.raises(ValueError, match="next cursor"):
        next_page.page_order_and_identity_hold()


def test_plugin_store_page_validation_and_incomplete_summary(tmp_path: Path) -> None:
    content = b'{"input":"generic"}'
    plan = _plan(content)
    repository = SQLitePluginRunRepository(tmp_path / "plugin-runs.db")
    repository.initialize()
    planned = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=0,
        from_state=None,
        to_state=PluginRunState.PLANNED,
        occurred_at=plan.planned_at,
    )
    repository.reserve(plan, planned, idempotency_key="workflow:incomplete")
    record = read_plugin_run(repository.database_path, plan.run_plan_id)
    page = list_plugin_runs(repository.database_path)
    assert record.receipt is None
    assert page.runs[0].state is PluginRunState.PLANNED
    with pytest.raises(ValueError, match="limit"):
        repository.page(limit=0)
    with pytest.raises(ValueError, match="cursor"):
        repository.page(after_run_plan_id="invalid")


def test_plugin_workflow_strict_json_and_cli_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicate"):
        _strict_json(b'{"a":1,"a":2}')
    with pytest.raises(ValueError, match="non-finite"):
        _strict_json(b'{"a":NaN}')
    existing = tmp_path / "existing"
    existing.mkdir()
    _ensure_runtime_directory(existing, "existing")

    database, artifact_root, accepted_root, receipt = _successful_run(tmp_path / "commands")
    malformed = runner.invoke(
        app,
        [
            "plugins",
            "run",
            "example.workflow-collector",
            "--input",
            "malformed",
            "--grant",
            "artifact-read",
            "--sandbox-evidence",
            str(next(accepted_root.rglob("*.json"))),
            "--idempotency-key",
            "workflow:bad-input",
            "--planned-at",
            "2026-09-03T20:00:00Z",
        ],
    )
    missing = "sha256:" + "f" * 64
    show = runner.invoke(app, ["plugins", "show", str(database), missing])
    runs = runner.invoke(app, ["plugins", "runs", str(database), "--after", "invalid"])
    collect = runner.invoke(
        app,
        [
            "plugins",
            "collect",
            str(database),
            missing,
            "--root",
            str(artifact_root),
            "--accepted-output-root",
            str(accepted_root),
        ],
    )
    assert malformed.exit_code == show.exit_code == runs.exit_code == collect.exit_code == 3
    assert receipt.result.status is PluginRunState.SUCCEEDED


def test_plugin_cli_success_replay_failure_and_query_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, artifact_root, accepted_root, receipt = _successful_run(tmp_path)
    sandbox = tmp_path / "sandbox.json"
    sandbox.write_text("{}", encoding="utf-8")
    returned = [receipt, receipt, _failed_receipt(receipt)]
    monkeypatch.setattr(
        "forgegate.cli.execute_operator_plugin_run",
        lambda **_kwargs: returned.pop(0),
    )
    command = [
        "plugins",
        "run",
        "example.workflow-collector",
        "--input",
        "inputs/source.json=application/json",
        "--grant",
        "artifact-read",
        "--grant",
        "filesystem-write",
        "--sandbox-evidence",
        str(sandbox),
        "--idempotency-key",
        "workflow:cli",
        "--planned-at",
        "2026-09-03T20:00:00Z",
        "--root",
        str(artifact_root),
    ]
    first = runner.invoke(app, command)
    replay = runner.invoke(app, command)
    failed = runner.invoke(app, command)
    assert first.exit_code == replay.exit_code == 0
    assert json.loads(first.stdout) == json.loads(replay.stdout)
    assert failed.exit_code == 3
    assert json.loads(failed.stdout)["result"]["status"] == "ERROR"

    run_plan_id = receipt.result.run_plan.run_plan_id
    show = runner.invoke(app, ["plugins", "show", str(database), run_plan_id])
    runs = runner.invoke(app, ["plugins", "runs", str(database), "--limit", "1"])
    collect = runner.invoke(
        app,
        [
            "plugins",
            "collect",
            str(database),
            run_plan_id,
            "--root",
            str(artifact_root),
            "--accepted-output-root",
            str(accepted_root),
        ],
    )
    assert show.exit_code == runs.exit_code == collect.exit_code == 0
    assert json.loads(show.stdout)["schema_version"] == "forgegate.plugin-run-record.v1"
    assert json.loads(runs.stdout)["schema_version"] == "forgegate.plugin-run-page.v1"
    assert json.loads(collect.stdout)["status"] == "COMPLETE"
