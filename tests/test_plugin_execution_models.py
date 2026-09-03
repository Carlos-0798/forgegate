from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from forgegate.config import load_config
from forgegate.plugins import (
    PluginCapability,
    PluginExecutionTarget,
    PluginIsolationTier,
    PluginPermission,
    PluginProtocolDirection,
    PluginProtocolMessage,
    PluginProtocolMessageKind,
    PluginResourceLimits,
    PluginRunIssue,
    PluginRunIssueCode,
    PluginRunPlan,
    PluginRunResult,
    PluginRunState,
    PluginRunSubject,
    create_plugin_manifest,
    create_plugin_protocol_message,
    create_plugin_run_plan,
    create_plugin_run_result,
    create_plugin_run_transition,
    create_plugin_validated_output,
    plugin_output_set_id,
)

BASE_TIME = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
PLUGIN_ID = "example.sandbox-collector"


def execution_target(
    *, permissions: tuple[PluginPermission, ...] | None = None
) -> PluginExecutionTarget:
    selected_permissions = permissions or (
        PluginPermission.FILESYSTEM_WRITE,
        PluginPermission.ARTIFACT_READ,
    )
    manifest = create_plugin_manifest(
        plugin_id=PLUGIN_ID,
        display_name="Sandbox Collector",
        description="Generic execution-contract test plugin.",
        plugin_version="1.2.3",
        forgegate_api_version="1",
        capabilities=(PluginCapability.COLLECTOR,),
        input_schemas=("example.generic-input.v1",),
        permissions=selected_permissions,
        output_evidence_kinds=("test.secondary", "test.metric"),
    )
    return PluginExecutionTarget(
        distribution_name="forgegate-sandbox-collector",
        distribution_version="1.2.3",
        entry_point_name=PLUGIN_ID,
        entry_point_value="sandbox_collector.runtime:plugin",
        manifest=manifest,
    )


def input_subject(*, name: str = "inputs/evidence.json") -> PluginRunSubject:
    return PluginRunSubject(
        name=name,
        media_type="application/json",
        digest="sha256:" + "a" * 64,
        size_bytes=512,
    )


def run_plan(
    *,
    target: PluginExecutionTarget | None = None,
    limits: PluginResourceLimits | None = None,
) -> PluginRunPlan:
    approved = (
        PluginPermission.FILESYSTEM_WRITE,
        PluginPermission.ARTIFACT_READ,
    )
    return create_plugin_run_plan(
        target=target or execution_target(),
        input_schema="example.generic-input.v1",
        inputs=(input_subject(),),
        expected_output_evidence_kinds=("test.secondary", "test.metric"),
        approved_permissions=approved,
        enforced_permissions=approved,
        enforcement_backend="test-sandbox",
        enforcement_backend_version="1.0.0",
        resource_limits=limits or PluginResourceLimits(),
        planned_at=BASE_TIME,
    )


def successful_documents() -> tuple[
    PluginRunPlan,
    PluginProtocolMessage,
    object,
    PluginRunResult,
]:
    plan = run_plan()
    output = create_plugin_validated_output(
        subject=PluginRunSubject(
            name="outputs/evidence.json",
            media_type="application/json",
            digest="sha256:" + "b" * 64,
            size_bytes=768,
        ),
        evidence_kind="test.metric",
        evidence_id="plugin.test.metric",
    )
    output_set_id = plugin_output_set_id((output,))
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
    result_message = create_plugin_protocol_message(
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
        protocol_message_id=result_message.message_id,
        output_set_id=output_set_id,
    )
    result = create_plugin_run_result(
        run_plan=plan,
        status=PluginRunState.SUCCEEDED,
        transitions=(planned, starting, running, succeeded),
        validated_outputs=(output,),
    )
    return plan, start, planned, result


def test_run_plan_is_canonical_content_addressed_and_utc_normalized() -> None:
    target = execution_target()
    local_time = BASE_TIME.astimezone(timezone(timedelta(hours=-4)))
    plan = create_plugin_run_plan(
        target=target,
        input_schema="example.generic-input.v1",
        inputs=(
            PluginRunSubject(
                name="inputs/z.json",
                media_type="application/json",
                digest="sha256:" + "c" * 64,
                size_bytes=20,
            ),
            input_subject(name="inputs/a.json"),
        ),
        expected_output_evidence_kinds=("test.secondary", "test.metric"),
        approved_permissions=(
            PluginPermission.FILESYSTEM_WRITE,
            PluginPermission.ARTIFACT_READ,
        ),
        enforced_permissions=(
            PluginPermission.FILESYSTEM_WRITE,
            PluginPermission.ARTIFACT_READ,
        ),
        enforcement_backend="test-sandbox",
        enforcement_backend_version="1.0.0",
        resource_limits=PluginResourceLimits(),
        planned_at=local_time,
    )
    assert [item.name for item in plan.inputs] == ["inputs/a.json", "inputs/z.json"]
    assert plan.planned_at == BASE_TIME
    assert plan.isolation_tier is PluginIsolationTier.SANDBOXED
    assert plan.network_policy == "deny"
    assert plan.subprocess_policy == "deny"
    assert plan.run_plan_id.startswith("sha256:")

    with pytest.raises(ValidationError, match="run_plan_id"):
        PluginRunPlan.model_validate(
            {**plan.model_dump(mode="json"), "enforcement_backend_version": "1.0.1"}
        )


def test_run_plan_rejects_unenforceable_authority_and_unsafe_subject_names() -> None:
    target = execution_target(
        permissions=(
            PluginPermission.ARTIFACT_READ,
            PluginPermission.FILESYSTEM_WRITE,
            PluginPermission.NETWORK,
        )
    )
    with pytest.raises(ValidationError, match="cannot be enforced"):
        create_plugin_run_plan(
            target=target,
            input_schema="example.generic-input.v1",
            inputs=(input_subject(),),
            expected_output_evidence_kinds=("test.metric",),
            approved_permissions=target.manifest.permissions,
            enforced_permissions=target.manifest.permissions,
            enforcement_backend="test-sandbox",
            enforcement_backend_version="1.0.0",
            resource_limits=PluginResourceLimits(),
            planned_at=BASE_TIME,
        )

    with pytest.raises(ValidationError, match="relative logical name"):
        input_subject(name="C:/private/input.json")
    with pytest.raises(ValidationError, match="traversal"):
        input_subject(name="inputs/../private.json")

    valid = run_plan()
    with pytest.raises(ValidationError, match="at least 1 item"):
        PluginRunPlan.model_validate({**valid.model_dump(mode="json"), "inputs": []})


def test_contract_rejects_ambiguous_or_incoherent_authority_fields() -> None:
    with pytest.raises(ValidationError, match="shorter than startup"):
        PluginResourceLimits(startup_timeout_ms=200, total_timeout_ms=100)
    with pytest.raises(ValidationError, match="CPU limit"):
        PluginResourceLimits(startup_timeout_ms=100, total_timeout_ms=200, cpu_time_ms=300)
    with pytest.raises(ValidationError, match="unsupported characters"):
        input_subject(name="inputs/not allowed.json")

    target = execution_target()
    with pytest.raises(ValidationError, match="entry-point name"):
        PluginExecutionTarget(
            **(target.model_dump(mode="python") | {"entry_point_name": "example.other"})
        )
    incompatible_manifest = create_plugin_manifest(
        plugin_id=PLUGIN_ID,
        display_name="Sandbox Collector",
        description="Generic execution-contract test plugin.",
        plugin_version="1.2.3",
        forgegate_api_version="2",
        capabilities=(PluginCapability.COLLECTOR,),
        input_schemas=("example.generic-input.v1",),
        permissions=(PluginPermission.ARTIFACT_READ, PluginPermission.FILESYSTEM_WRITE),
        output_evidence_kinds=("test.metric",),
    )
    with pytest.raises(ValidationError, match="current ForgeGate API"):
        PluginExecutionTarget(
            distribution_name="forgegate-sandbox-collector",
            distribution_version="1.2.3",
            entry_point_name=PLUGIN_ID,
            entry_point_value="sandbox_collector.runtime:plugin",
            manifest=incompatible_manifest,
        )

    payload = run_plan().model_dump(mode="json")
    mutations = (
        ({"approved_permissions": ["artifact-read", "artifact-read"]}, "duplicates"),
        ({"expected_output_evidence_kinds": ["test.metric", "test.metric"]}, "duplicates"),
        ({"expected_output_evidence_kinds": ["not dotted"]}, "dotted identifiers"),
        ({"inputs": [payload["inputs"][0], payload["inputs"][0]]}, "duplicates"),
        ({"input_schema": "example.other.v1"}, "input schema"),
        ({"expected_output_evidence_kinds": ["other.metric"]}, "output kinds"),
        ({"declared_permissions": ["artifact-read"]}, "match the manifest"),
        ({"approved_permissions": ["artifact-read", "filesystem-write", "network"]}, "exceed"),
        ({"enforced_permissions": ["artifact-read"]}, "enforced exactly"),
        (
            {
                "approved_permissions": ["artifact-read"],
                "enforced_permissions": ["artifact-read"],
            },
            "brokered read and write",
        ),
        ({"planned_at": "2026-09-01T12:00:00"}, "UTC offset"),
    )
    for mutation, message in mutations:
        with pytest.raises(ValidationError, match=message):
            PluginRunPlan.model_validate(payload | mutation)


def test_protocol_messages_are_strict_and_content_addressed() -> None:
    plan = run_plan()
    start = create_plugin_protocol_message(
        run_plan_id=plan.run_plan_id,
        sequence=0,
        direction=PluginProtocolDirection.CORE_TO_PLUGIN,
        kind=PluginProtocolMessageKind.START,
        run_plan=plan,
    )
    assert start.protocol_version == "1"
    assert start.message_id.startswith("sha256:")

    with pytest.raises(ValidationError, match="direction or sequence"):
        create_plugin_protocol_message(
            run_plan_id=plan.run_plan_id,
            sequence=2,
            direction=PluginProtocolDirection.PLUGIN_TO_CORE,
            kind=PluginProtocolMessageKind.READY,
        )
    with pytest.raises(ValidationError, match="START message"):
        create_plugin_protocol_message(
            run_plan_id="sha256:" + "f" * 64,
            sequence=0,
            direction=PluginProtocolDirection.CORE_TO_PLUGIN,
            kind=PluginProtocolMessageKind.START,
            run_plan=plan,
        )
    with pytest.raises(ValidationError, match="message_id"):
        PluginProtocolMessage.model_validate(
            {
                **start.model_dump(mode="json"),
                "protocol_version": "1",
                "issue": None,
                "sequence": 0,
                "message_id": "sha256:" + "f" * 64,
            }
        )


def test_successful_run_result_validates_complete_transition_chain() -> None:
    _, _, _, result = successful_documents()
    assert result.status is PluginRunState.SUCCEEDED
    assert result.output_set_id == result.transitions[-1].output_set_id
    assert result.result_id.startswith("sha256:")

    reversed_chain = list(result.model_dump(mode="json")["transitions"])
    reversed_chain[1], reversed_chain[2] = reversed_chain[2], reversed_chain[1]
    with pytest.raises(ValidationError, match="sequence"):
        PluginRunResult.model_validate(
            {**result.model_dump(mode="json"), "transitions": reversed_chain}
        )
    with pytest.raises(ValidationError, match="result_id"):
        PluginRunResult.model_validate(
            {**result.model_dump(mode="json"), "result_id": "sha256:" + "f" * 64}
        )


def test_error_result_uses_stable_issue_and_no_output() -> None:
    plan = run_plan()
    issue = PluginRunIssue(code=PluginRunIssueCode.PLUGIN_ISOLATION_UNAVAILABLE)
    planned = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=0,
        from_state=None,
        to_state=PluginRunState.PLANNED,
        occurred_at=BASE_TIME,
    )
    failed = create_plugin_run_transition(
        run_plan_id=plan.run_plan_id,
        sequence=1,
        from_state=PluginRunState.PLANNED,
        to_state=PluginRunState.ERROR,
        occurred_at=BASE_TIME + timedelta(milliseconds=1),
        previous_transition_id=planned.transition_id,
        issue=issue,
    )
    result = create_plugin_run_result(
        run_plan=plan,
        status=PluginRunState.ERROR,
        transitions=(planned, failed),
        issue=issue,
    )
    assert result.issue == issue
    assert result.validated_outputs == ()
    assert result.output_set_id is None


def test_result_rejects_output_over_resource_limit() -> None:
    plan = run_plan(limits=PluginResourceLimits(output_bytes=1_024))
    output = create_plugin_validated_output(
        subject=PluginRunSubject(
            name="outputs/too-large.json",
            media_type="application/json",
            digest="sha256:" + "d" * 64,
            size_bytes=1_025,
        ),
        evidence_kind="test.metric",
        evidence_id="plugin.too-large",
    )
    output_set_id = plugin_output_set_id((output,))
    transitions = []
    states = (
        (None, PluginRunState.PLANNED),
        (PluginRunState.PLANNED, PluginRunState.STARTING),
        (PluginRunState.STARTING, PluginRunState.RUNNING),
        (PluginRunState.RUNNING, PluginRunState.SUCCEEDED),
    )
    for index, (from_state, to_state) in enumerate(states):
        transitions.append(
            create_plugin_run_transition(
                run_plan_id=plan.run_plan_id,
                sequence=index,
                from_state=from_state,
                to_state=to_state,
                occurred_at=BASE_TIME + timedelta(seconds=index),
                previous_transition_id=(transitions[-1].transition_id if transitions else None),
                output_set_id=(output_set_id if to_state is PluginRunState.SUCCEEDED else None),
            )
        )
    with pytest.raises(ValidationError, match="bytes exceed"):
        create_plugin_run_result(
            run_plan=plan,
            status=PluginRunState.SUCCEEDED,
            transitions=tuple(transitions),
            validated_outputs=(output,),
        )


def test_execution_documents_load_through_public_config_boundary(tmp_path: Path) -> None:
    plan, start, planned, result = successful_documents()
    documents = (plan, start, planned, result)
    for index, document in enumerate(documents):
        path = tmp_path / f"document-{index}.json"
        path.write_text(
            json.dumps(document.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        assert load_config(path) == document
