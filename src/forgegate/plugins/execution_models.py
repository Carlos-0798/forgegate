from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from forgegate.canonical import sha256_fingerprint
from forgegate.domain.enums import EvidenceTrust, VerificationLevel
from forgegate.domain.models import (
    EVIDENCE_KIND_PATTERN,
    RULE_ID_PATTERN,
    EvidenceRecord,
    StrictModel,
)
from forgegate.plugins.models import (
    FINGERPRINT_PATTERN,
    PLUGIN_API_VERSION,
    PLUGIN_ID_PATTERN,
    PluginCapability,
    PluginManifest,
    PluginPermission,
)

PLUGIN_PROTOCOL_VERSION = "1"
ENTRY_POINT_VALUE_PATTERN = (
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*:"
    r"[A-Za-z_][A-Za-z0-9_]*$"
)
DISTRIBUTION_VALUE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$"
MEDIA_TYPE_PATTERN = (
    r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}/"
    r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}$"
)
INITIAL_ENFORCEABLE_PERMISSIONS = frozenset(
    {PluginPermission.ARTIFACT_READ, PluginPermission.FILESYSTEM_WRITE}
)
TERMINAL_RUN_STATES = frozenset(
    {
        "SUCCEEDED",
        "ERROR",
        "CANCELLED",
    }
)


class PluginIsolationTier(StrEnum):
    NONE = "NONE"
    PROCESS_ONLY = "PROCESS_ONLY"
    SANDBOXED = "SANDBOXED"


class PluginRunState(StrEnum):
    PLANNED = "PLANNED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class PluginProtocolDirection(StrEnum):
    CORE_TO_PLUGIN = "CORE_TO_PLUGIN"
    PLUGIN_TO_CORE = "PLUGIN_TO_CORE"


class PluginProtocolMessageKind(StrEnum):
    START = "START"
    READY = "READY"
    RESULT = "RESULT"
    ERROR = "ERROR"


class PluginRunIssueCode(StrEnum):
    PLUGIN_PLAN_INVALID = "PLUGIN_PLAN_INVALID"
    PLUGIN_PERMISSION_DENIED = "PLUGIN_PERMISSION_DENIED"
    PLUGIN_PERMISSION_UNENFORCEABLE = "PLUGIN_PERMISSION_UNENFORCEABLE"
    PLUGIN_ISOLATION_UNAVAILABLE = "PLUGIN_ISOLATION_UNAVAILABLE"
    PLUGIN_START_FAILED = "PLUGIN_START_FAILED"
    PLUGIN_PROTOCOL_INVALID = "PLUGIN_PROTOCOL_INVALID"
    PLUGIN_TIMEOUT = "PLUGIN_TIMEOUT"
    PLUGIN_RESOURCE_LIMIT = "PLUGIN_RESOURCE_LIMIT"
    PLUGIN_EXIT_ERROR = "PLUGIN_EXIT_ERROR"
    PLUGIN_OUTPUT_INVALID = "PLUGIN_OUTPUT_INVALID"
    PLUGIN_AUDIT_FAILED = "PLUGIN_AUDIT_FAILED"
    PLUGIN_CLEANUP_FAILED = "PLUGIN_CLEANUP_FAILED"
    PLUGIN_CANCELLED = "PLUGIN_CANCELLED"


class PluginRunIssue(StrictModel):
    """Stable, non-secret-bearing failure classification."""

    code: PluginRunIssueCode


class PluginRunSubject(StrictModel):
    """Broker-owned logical artifact presented to a plugin runner."""

    name: str = Field(min_length=1, max_length=255)
    media_type: str = Field(pattern=MEDIA_TYPE_PATTERN)
    digest: str = Field(pattern=FINGERPRINT_PATTERN)
    size_bytes: int = Field(ge=0, le=4_294_967_296)

    @field_validator("name")
    @classmethod
    def name_is_logical_and_path_safe(cls, value: str) -> str:
        if "\\" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
            raise ValueError("plugin run subject name must be a relative logical name")
        parts = value.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("plugin run subject name cannot contain traversal or empty segments")
        if any(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", part) is None for part in parts):
            raise ValueError("plugin run subject name contains unsupported characters")
        return value


class PluginResourceLimits(StrictModel):
    startup_timeout_ms: int = Field(default=5_000, ge=100, le=120_000)
    total_timeout_ms: int = Field(default=60_000, ge=100, le=900_000)
    cpu_time_ms: int = Field(default=30_000, ge=100, le=900_000)
    memory_bytes: int = Field(default=268_435_456, ge=16_777_216, le=4_294_967_296)
    output_bytes: int = Field(default=67_108_864, ge=1_024, le=1_073_741_824)
    file_count: int = Field(default=64, ge=1, le=4_096)
    process_count: Literal[1] = 1
    stdout_bytes: int = Field(default=1_048_576, ge=0, le=16_777_216)
    stderr_bytes: int = Field(default=1_048_576, ge=0, le=16_777_216)

    @model_validator(mode="after")
    def time_limits_are_coherent(self) -> PluginResourceLimits:
        if self.total_timeout_ms < self.startup_timeout_ms:
            raise ValueError("total plugin timeout cannot be shorter than startup timeout")
        if self.cpu_time_ms > self.total_timeout_ms:
            raise ValueError("plugin CPU limit cannot exceed total timeout")
        return self


class PluginExecutionTarget(StrictModel):
    """Pinned metadata for a discovered plugin without importing its entry point."""

    distribution_name: str = Field(pattern=DISTRIBUTION_VALUE_PATTERN)
    distribution_version: str = Field(pattern=DISTRIBUTION_VALUE_PATTERN)
    entry_point_name: str = Field(pattern=PLUGIN_ID_PATTERN)
    entry_point_value: str = Field(pattern=ENTRY_POINT_VALUE_PATTERN, max_length=256)
    manifest: PluginManifest

    @model_validator(mode="after")
    def target_matches_manifest(self) -> PluginExecutionTarget:
        if self.entry_point_name != self.manifest.plugin_id:
            raise ValueError("plugin target entry-point name must match manifest plugin_id")
        if self.manifest.forgegate_api_version != PLUGIN_API_VERSION:
            raise ValueError("plugin target must use the current ForgeGate API version")
        return self


class PluginRunPlan(StrictModel):
    """Content-addressed authority envelope for one future plugin invocation."""

    schema_version: Literal["forgegate.plugin-run-plan.v1"] = "forgegate.plugin-run-plan.v1"
    run_plan_id: str = Field(pattern=FINGERPRINT_PATTERN)
    target: PluginExecutionTarget
    capability: PluginCapability
    input_schema: str
    inputs: tuple[PluginRunSubject, ...] = Field(min_length=1, max_length=64)
    expected_output_evidence_kinds: tuple[str, ...] = Field(min_length=1, max_length=64)
    declared_permissions: tuple[PluginPermission, ...] = Field(default=(), max_length=16)
    approved_permissions: tuple[PluginPermission, ...] = Field(default=(), max_length=16)
    enforced_permissions: tuple[PluginPermission, ...] = Field(default=(), max_length=16)
    isolation_tier: Literal[PluginIsolationTier.SANDBOXED] = PluginIsolationTier.SANDBOXED
    enforcement_backend: str = Field(pattern=r"^[a-z][a-z0-9-]{1,62}$")
    enforcement_backend_version: str = Field(pattern=DISTRIBUTION_VALUE_PATTERN)
    input_policy: Literal["broker-private-read-only"] = "broker-private-read-only"
    environment_policy: Literal["sanitized-empty"] = "sanitized-empty"
    network_policy: Literal["deny"] = "deny"
    subprocess_policy: Literal["deny"] = "deny"
    resource_limits: PluginResourceLimits
    planned_at: datetime

    @field_validator("declared_permissions", "approved_permissions", "enforced_permissions")
    @classmethod
    def permissions_are_unique_and_canonical(
        cls, value: tuple[PluginPermission, ...]
    ) -> tuple[PluginPermission, ...]:
        rendered = [item.value for item in value]
        if len(rendered) != len(set(rendered)):
            raise ValueError("plugin run permissions cannot contain duplicates")
        return tuple(sorted(value, key=lambda item: item.value))

    @field_validator("expected_output_evidence_kinds")
    @classmethod
    def output_kinds_are_unique_and_canonical(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("expected plugin output kinds cannot contain duplicates")
        if any(re.fullmatch(EVIDENCE_KIND_PATTERN, item) is None for item in value):
            raise ValueError("expected plugin output kinds must be dotted identifiers")
        return tuple(sorted(value))

    @field_validator("inputs")
    @classmethod
    def inputs_are_unique_and_canonical(
        cls, value: tuple[PluginRunSubject, ...]
    ) -> tuple[PluginRunSubject, ...]:
        keys = [(item.name, item.digest) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("plugin run inputs cannot contain duplicates")
        return tuple(sorted(value, key=lambda item: (item.name, item.digest)))

    @field_validator("planned_at")
    @classmethod
    def planned_at_is_timezone_aware(cls, value: datetime) -> datetime:
        return _utc_timestamp(value, "planned_at")

    @model_validator(mode="after")
    def authority_and_identity_contracts_hold(self) -> PluginRunPlan:
        manifest = self.target.manifest
        if self.capability is not PluginCapability.COLLECTOR:
            raise ValueError("plugin execution contract v1 supports collector capability only")
        if self.capability not in manifest.capabilities:
            raise ValueError("plugin run capability is not declared by the manifest")
        if self.input_schema not in manifest.input_schemas:
            raise ValueError("plugin run input schema is not declared by the manifest")
        if not set(self.expected_output_evidence_kinds).issubset(manifest.output_evidence_kinds):
            raise ValueError("plugin run output kinds exceed the manifest declaration")
        if self.declared_permissions != manifest.permissions:
            raise ValueError("declared plugin run permissions must match the manifest")
        if not set(self.approved_permissions).issubset(self.declared_permissions):
            raise ValueError("approved plugin permissions exceed the manifest declaration")
        if self.enforced_permissions != self.approved_permissions:
            raise ValueError("approved plugin permissions must be enforced exactly")
        if not set(self.enforced_permissions).issubset(INITIAL_ENFORCEABLE_PERMISSIONS):
            raise ValueError("plugin permission cannot be enforced by contract v1")
        required = {
            PluginPermission.ARTIFACT_READ,
            PluginPermission.FILESYSTEM_WRITE,
        }
        if not required.issubset(self.enforced_permissions):
            raise ValueError("collector execution requires brokered read and write permissions")
        if self.run_plan_id != sha256_fingerprint(_run_plan_identity(self)):
            raise ValueError("run_plan_id does not match plugin run plan content")
        return self


class PluginProtocolMessage(StrictModel):
    """Strict, bounded message envelope for the future runner protocol."""

    schema_version: Literal["forgegate.plugin-protocol-message.v1"] = (
        "forgegate.plugin-protocol-message.v1"
    )
    message_id: str = Field(pattern=FINGERPRINT_PATTERN)
    protocol_version: Literal["1"] = "1"
    run_plan_id: str = Field(pattern=FINGERPRINT_PATTERN)
    sequence: int = Field(ge=0, le=2)
    direction: PluginProtocolDirection
    kind: PluginProtocolMessageKind
    run_plan: PluginRunPlan | None = None
    output_set_id: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)
    issue: PluginRunIssue | None = None

    @model_validator(mode="after")
    def message_shape_and_identity_hold(self) -> PluginProtocolMessage:
        expected: dict[
            PluginProtocolMessageKind, tuple[PluginProtocolDirection, tuple[int, ...]]
        ] = {
            PluginProtocolMessageKind.START: (PluginProtocolDirection.CORE_TO_PLUGIN, (0,)),
            PluginProtocolMessageKind.READY: (PluginProtocolDirection.PLUGIN_TO_CORE, (1,)),
            PluginProtocolMessageKind.RESULT: (PluginProtocolDirection.PLUGIN_TO_CORE, (2,)),
            PluginProtocolMessageKind.ERROR: (
                PluginProtocolDirection.PLUGIN_TO_CORE,
                (1, 2),
            ),
        }
        direction, sequences = expected[self.kind]
        if self.direction is not direction or self.sequence not in sequences:
            raise ValueError("plugin protocol direction or sequence is invalid for message kind")
        if self.kind is PluginProtocolMessageKind.START:
            if self.run_plan is None or self.run_plan.run_plan_id != self.run_plan_id:
                raise ValueError("START message must embed its exact run plan")
            if self.output_set_id is not None or self.issue is not None:
                raise ValueError("START message cannot carry result fields")
        elif self.kind is PluginProtocolMessageKind.READY:
            if any(item is not None for item in (self.run_plan, self.output_set_id, self.issue)):
                raise ValueError("READY message cannot carry a payload")
        elif self.kind is PluginProtocolMessageKind.RESULT:
            if self.output_set_id is None or self.run_plan is not None or self.issue is not None:
                raise ValueError("RESULT message must carry only an output_set_id")
        elif self.issue is None or self.run_plan is not None or self.output_set_id is not None:
            raise ValueError("ERROR message must carry only a stable issue code")
        if self.message_id != sha256_fingerprint(_protocol_message_identity(self)):
            raise ValueError("message_id does not match plugin protocol message content")
        return self


class PluginRunTransition(StrictModel):
    """One content-addressed transition in a plugin run state chain."""

    schema_version: Literal["forgegate.plugin-run-transition.v1"] = (
        "forgegate.plugin-run-transition.v1"
    )
    transition_id: str = Field(pattern=FINGERPRINT_PATTERN)
    run_plan_id: str = Field(pattern=FINGERPRINT_PATTERN)
    sequence: int = Field(ge=0, le=3)
    from_state: PluginRunState | None
    to_state: PluginRunState
    occurred_at: datetime
    previous_transition_id: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)
    protocol_message_id: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)
    output_set_id: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)
    issue: PluginRunIssue | None = None

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_is_timezone_aware(cls, value: datetime) -> datetime:
        return _utc_timestamp(value, "occurred_at")

    @model_validator(mode="after")
    def transition_shape_and_identity_hold(self) -> PluginRunTransition:
        allowed = {
            (None, PluginRunState.PLANNED),
            (PluginRunState.PLANNED, PluginRunState.STARTING),
            (PluginRunState.PLANNED, PluginRunState.ERROR),
            (PluginRunState.PLANNED, PluginRunState.CANCELLED),
            (PluginRunState.STARTING, PluginRunState.RUNNING),
            (PluginRunState.STARTING, PluginRunState.ERROR),
            (PluginRunState.STARTING, PluginRunState.CANCELLED),
            (PluginRunState.RUNNING, PluginRunState.SUCCEEDED),
            (PluginRunState.RUNNING, PluginRunState.ERROR),
            (PluginRunState.RUNNING, PluginRunState.CANCELLED),
        }
        if (self.from_state, self.to_state) not in allowed:
            raise ValueError("illegal plugin run state transition")
        if self.sequence == 0:
            if self.from_state is not None or self.to_state is not PluginRunState.PLANNED:
                raise ValueError("initial plugin transition must create PLANNED state")
            if self.previous_transition_id is not None or self.protocol_message_id is not None:
                raise ValueError("initial plugin transition cannot reference prior protocol state")
        elif self.previous_transition_id is None or self.from_state is None:
            raise ValueError("non-initial plugin transition must reference its predecessor")

        if self.to_state is PluginRunState.SUCCEEDED:
            if self.output_set_id is None or self.issue is not None:
                raise ValueError("successful plugin transition requires only an output_set_id")
        elif self.to_state in {PluginRunState.ERROR, PluginRunState.CANCELLED}:
            if self.issue is None or self.output_set_id is not None:
                raise ValueError("failed plugin transition requires only a stable issue code")
        elif self.output_set_id is not None or self.issue is not None:
            raise ValueError("non-terminal plugin transition cannot carry terminal fields")
        if self.transition_id != sha256_fingerprint(_transition_identity(self)):
            raise ValueError("transition_id does not match plugin transition content")
        return self


class PluginOutputDocument(StrictModel):
    """Untrusted plugin proposal revalidated by the ForgeGate core."""

    schema_version: Literal["forgegate.plugin-output.v1"] = "forgegate.plugin-output.v1"
    run_plan_id: str = Field(pattern=FINGERPRINT_PATTERN)
    evidence: EvidenceRecord

    @model_validator(mode="after")
    def evidence_remains_low_trust(self) -> PluginOutputDocument:
        if self.evidence.trust is not EvidenceTrust.UNSIGNED_LOCAL:
            raise ValueError("external plugin output must remain unsigned_local")
        if self.evidence.verification_level is not VerificationLevel.DECLARED:
            raise ValueError("external plugin output must remain declared evidence")
        return self


class PluginValidatedOutput(StrictModel):
    """Output accepted only after broker rehashing and core schema validation."""

    output_id: str = Field(pattern=FINGERPRINT_PATTERN)
    subject: PluginRunSubject
    evidence_kind: str = Field(pattern=EVIDENCE_KIND_PATTERN)
    evidence_id: str = Field(pattern=RULE_ID_PATTERN)
    validation: Literal["CORE_REHASHED_AND_SCHEMA_VALIDATED"] = "CORE_REHASHED_AND_SCHEMA_VALIDATED"

    @model_validator(mode="after")
    def output_identity_holds(self) -> PluginValidatedOutput:
        if self.output_id != sha256_fingerprint(_validated_output_identity(self)):
            raise ValueError("output_id does not match validated plugin output content")
        return self


class PluginRunResult(StrictModel):
    """Terminal, replay-verifiable record of a plugin run state chain."""

    schema_version: Literal["forgegate.plugin-run-result.v1"] = "forgegate.plugin-run-result.v1"
    result_id: str = Field(pattern=FINGERPRINT_PATTERN)
    run_plan: PluginRunPlan
    status: PluginRunState
    transitions: tuple[PluginRunTransition, ...] = Field(min_length=2, max_length=4)
    output_set_id: str | None = Field(default=None, pattern=FINGERPRINT_PATTERN)
    validated_outputs: tuple[PluginValidatedOutput, ...] = Field(default=(), max_length=4_096)
    issue: PluginRunIssue | None = None

    @field_validator("validated_outputs")
    @classmethod
    def outputs_are_unique_and_canonical(
        cls, value: tuple[PluginValidatedOutput, ...]
    ) -> tuple[PluginValidatedOutput, ...]:
        keys = [(item.subject.name, item.subject.digest, item.evidence_id) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("validated plugin outputs cannot contain duplicates")
        return tuple(
            sorted(
                value,
                key=lambda item: (item.subject.name, item.subject.digest, item.evidence_id),
            )
        )

    @model_validator(mode="after")
    def terminal_chain_outputs_and_identity_hold(self) -> PluginRunResult:
        if self.status.value not in TERMINAL_RUN_STATES:
            raise ValueError("plugin run result status must be terminal")
        plan_id = self.run_plan.run_plan_id
        transition_ids: set[str] = set()
        protocol_ids: set[str] = set()
        for index, transition in enumerate(self.transitions):
            if transition.run_plan_id != plan_id or transition.sequence != index:
                raise ValueError("plugin result transitions must match the plan and sequence")
            if transition.transition_id in transition_ids:
                raise ValueError("plugin result transition IDs must be unique")
            transition_ids.add(transition.transition_id)
            if index == 0:
                if (
                    transition.from_state is not None
                    or transition.to_state is not PluginRunState.PLANNED
                ):
                    raise ValueError("plugin result chain must begin at PLANNED")
            else:
                previous = self.transitions[index - 1]
                if transition.previous_transition_id != previous.transition_id:
                    raise ValueError("plugin result transition predecessor is invalid")
                if transition.from_state is not previous.to_state:
                    raise ValueError("plugin result transition states do not form a chain")
                if transition.occurred_at < previous.occurred_at:
                    raise ValueError("plugin result transition timestamps must be monotonic")
            if transition.protocol_message_id is not None:
                if transition.protocol_message_id in protocol_ids:
                    raise ValueError("plugin protocol message IDs cannot be reused")
                protocol_ids.add(transition.protocol_message_id)

        terminal = self.transitions[-1]
        if terminal.to_state is not self.status:
            raise ValueError("plugin result status must match the terminal transition")
        if self.status is PluginRunState.SUCCEEDED:
            if not self.validated_outputs or self.issue is not None:
                raise ValueError("successful plugin result requires validated outputs only")
            expected_set_id = plugin_output_set_id(self.validated_outputs)
            if self.output_set_id != expected_set_id or terminal.output_set_id != expected_set_id:
                raise ValueError("plugin result output_set_id does not match validated outputs")
            kinds = {item.evidence_kind for item in self.validated_outputs}
            if not kinds.issubset(self.run_plan.expected_output_evidence_kinds):
                raise ValueError("validated plugin output kind was not authorized by the plan")
            if len(self.validated_outputs) > self.run_plan.resource_limits.file_count:
                raise ValueError("validated plugin output count exceeds the run limit")
            if sum(item.subject.size_bytes for item in self.validated_outputs) > (
                self.run_plan.resource_limits.output_bytes
            ):
                raise ValueError("validated plugin output bytes exceed the run limit")
            output_ids = [item.output_id for item in self.validated_outputs]
            evidence_ids = [item.evidence_id for item in self.validated_outputs]
            names = [item.subject.name for item in self.validated_outputs]
            if len(output_ids) != len(set(output_ids)):
                raise ValueError("validated plugin output IDs must be unique")
            if len(evidence_ids) != len(set(evidence_ids)):
                raise ValueError("validated plugin evidence IDs must be unique")
            if len(names) != len(set(names)):
                raise ValueError("validated plugin output names must be unique")
        else:
            if self.validated_outputs or self.output_set_id is not None:
                raise ValueError("non-success plugin result cannot retain outputs")
            if self.issue is None or terminal.issue != self.issue:
                raise ValueError("non-success plugin result must match its terminal issue")
        if self.result_id != sha256_fingerprint(_run_result_identity(self)):
            raise ValueError("result_id does not match plugin run result content")
        return self


class PluginExecutionSummary(StrictModel):
    """Bounded, path-free execution metadata retained by the broker."""

    runner_started: bool
    ready_observed: bool
    completion_observed: bool
    elapsed_ms: int = Field(ge=0, le=900_000)
    exit_code: int | None = Field(default=None, ge=-255, le=255)
    oom_killed: bool = False
    stdout_bytes: int = Field(ge=0, le=16_777_216)
    stderr_bytes: int = Field(ge=0, le=16_777_216)
    stdout_truncated: bool = False
    stderr_truncated: bool = False


class PluginCleanupResult(StrictModel):
    """Cleanup proof without retaining a host path or container identifier."""

    container_removed: bool
    staging_removed: bool


class PluginRunReceipt(StrictModel):
    """Self-validating terminal broker record persisted in plugin_runs."""

    schema_version: Literal["forgegate.plugin-run-receipt.v1"] = "forgegate.plugin-run-receipt.v1"
    receipt_id: str = Field(pattern=FINGERPRINT_PATTERN)
    result: PluginRunResult
    protocol_messages: tuple[PluginProtocolMessage, ...] = Field(default=(), max_length=3)
    execution: PluginExecutionSummary
    cleanup: PluginCleanupResult
    accepted_outputs_registered: bool
    recovered_after_interruption: bool = False

    @field_validator("protocol_messages")
    @classmethod
    def messages_are_ordered_and_unique(
        cls, value: tuple[PluginProtocolMessage, ...]
    ) -> tuple[PluginProtocolMessage, ...]:
        ordered = tuple(sorted(value, key=lambda item: item.sequence))
        if value != ordered:
            raise ValueError("plugin protocol messages must use sequence order")
        if len({item.message_id for item in value}) != len(value):
            raise ValueError("plugin protocol message IDs must be unique")
        if len({item.sequence for item in value}) != len(value):
            raise ValueError("plugin protocol message sequences must be unique")
        return value

    @model_validator(mode="after")
    def receipt_chain_and_identity_hold(self) -> PluginRunReceipt:
        plan_id = self.result.run_plan.run_plan_id
        if any(message.run_plan_id != plan_id for message in self.protocol_messages):
            raise ValueError("plugin receipt messages must match the run plan")
        message_ids = {message.message_id for message in self.protocol_messages}
        transition_message_ids = {
            transition.protocol_message_id
            for transition in self.result.transitions
            if transition.protocol_message_id is not None
        }
        succeeded = self.result.status is PluginRunState.SUCCEEDED
        if succeeded:
            if message_ids != transition_message_ids:
                raise ValueError("successful plugin receipt must retain every protocol message")
            kinds = tuple(message.kind for message in self.protocol_messages)
            expected = (
                PluginProtocolMessageKind.START,
                PluginProtocolMessageKind.READY,
                PluginProtocolMessageKind.RESULT,
            )
            if kinds != expected:
                raise ValueError("successful plugin receipt requires START, READY, RESULT")
            if not (
                self.execution.runner_started
                and self.execution.ready_observed
                and self.execution.completion_observed
                and self.cleanup.container_removed
                and self.cleanup.staging_removed
                and self.accepted_outputs_registered
            ):
                raise ValueError(
                    "successful plugin receipt requires complete execution and cleanup"
                )
            if self.recovered_after_interruption:
                raise ValueError("recovered plugin run cannot be marked successful")
        else:
            if not message_ids.issubset(transition_message_ids):
                raise ValueError("failed plugin receipt contains an unreferenced protocol message")
            if self.accepted_outputs_registered:
                raise ValueError("failed plugin receipt cannot register accepted output")
        if self.receipt_id != sha256_fingerprint(_run_receipt_identity(self)):
            raise ValueError("receipt_id does not match plugin run receipt content")
        return self


def create_plugin_run_plan(
    *,
    target: PluginExecutionTarget,
    input_schema: str,
    inputs: tuple[PluginRunSubject, ...],
    expected_output_evidence_kinds: tuple[str, ...],
    approved_permissions: tuple[PluginPermission, ...],
    enforced_permissions: tuple[PluginPermission, ...],
    enforcement_backend: str,
    enforcement_backend_version: str,
    resource_limits: PluginResourceLimits,
    planned_at: datetime,
) -> PluginRunPlan:
    candidate = PluginRunPlan.model_construct(
        run_plan_id="sha256:" + "0" * 64,
        target=target,
        capability=PluginCapability.COLLECTOR,
        input_schema=input_schema,
        inputs=tuple(sorted(inputs, key=lambda item: (item.name, item.digest))),
        expected_output_evidence_kinds=tuple(sorted(expected_output_evidence_kinds)),
        declared_permissions=target.manifest.permissions,
        approved_permissions=tuple(sorted(approved_permissions, key=lambda item: item.value)),
        enforced_permissions=tuple(sorted(enforced_permissions, key=lambda item: item.value)),
        isolation_tier=PluginIsolationTier.SANDBOXED,
        enforcement_backend=enforcement_backend,
        enforcement_backend_version=enforcement_backend_version,
        resource_limits=resource_limits,
        planned_at=_utc_timestamp(planned_at, "planned_at"),
    )
    return PluginRunPlan.model_validate(
        {
            **candidate.model_dump(mode="json"),
            "run_plan_id": sha256_fingerprint(_run_plan_identity(candidate)),
        }
    )


def create_plugin_protocol_message(
    *,
    run_plan_id: str,
    sequence: int,
    direction: PluginProtocolDirection,
    kind: PluginProtocolMessageKind,
    run_plan: PluginRunPlan | None = None,
    output_set_id: str | None = None,
    issue: PluginRunIssue | None = None,
) -> PluginProtocolMessage:
    candidate = PluginProtocolMessage.model_construct(
        message_id="sha256:" + "0" * 64,
        run_plan_id=run_plan_id,
        sequence=sequence,
        direction=direction,
        kind=kind,
        run_plan=run_plan,
        output_set_id=output_set_id,
        issue=issue,
    )
    return PluginProtocolMessage.model_validate(
        {
            **candidate.model_dump(mode="json"),
            "message_id": sha256_fingerprint(_protocol_message_identity(candidate)),
        }
    )


def create_plugin_run_transition(
    *,
    run_plan_id: str,
    sequence: int,
    from_state: PluginRunState | None,
    to_state: PluginRunState,
    occurred_at: datetime,
    previous_transition_id: str | None = None,
    protocol_message_id: str | None = None,
    output_set_id: str | None = None,
    issue: PluginRunIssue | None = None,
) -> PluginRunTransition:
    candidate = PluginRunTransition.model_construct(
        transition_id="sha256:" + "0" * 64,
        run_plan_id=run_plan_id,
        sequence=sequence,
        from_state=from_state,
        to_state=to_state,
        occurred_at=_utc_timestamp(occurred_at, "occurred_at"),
        previous_transition_id=previous_transition_id,
        protocol_message_id=protocol_message_id,
        output_set_id=output_set_id,
        issue=issue,
    )
    return PluginRunTransition.model_validate(
        {
            **candidate.model_dump(mode="json"),
            "transition_id": sha256_fingerprint(_transition_identity(candidate)),
        }
    )


def create_plugin_validated_output(
    *,
    subject: PluginRunSubject,
    evidence_kind: str,
    evidence_id: str,
) -> PluginValidatedOutput:
    fields: dict[str, object] = {
        "subject": subject.model_dump(mode="json"),
        "evidence_kind": evidence_kind,
        "evidence_id": evidence_id,
        "validation": "CORE_REHASHED_AND_SCHEMA_VALIDATED",
    }
    return PluginValidatedOutput(
        output_id=sha256_fingerprint(fields),
        subject=subject,
        evidence_kind=evidence_kind,
        evidence_id=evidence_id,
    )


def create_plugin_run_result(
    *,
    run_plan: PluginRunPlan,
    status: PluginRunState,
    transitions: tuple[PluginRunTransition, ...],
    validated_outputs: tuple[PluginValidatedOutput, ...] = (),
    issue: PluginRunIssue | None = None,
) -> PluginRunResult:
    ordered_outputs = tuple(
        sorted(
            validated_outputs,
            key=lambda item: (item.subject.name, item.subject.digest, item.evidence_id),
        )
    )
    output_set_id = plugin_output_set_id(ordered_outputs) if ordered_outputs else None
    candidate = PluginRunResult.model_construct(
        result_id="sha256:" + "0" * 64,
        run_plan=run_plan,
        status=status,
        transitions=transitions,
        output_set_id=output_set_id,
        validated_outputs=ordered_outputs,
        issue=issue,
    )
    return PluginRunResult.model_validate(
        {
            **candidate.model_dump(mode="json"),
            "result_id": sha256_fingerprint(_run_result_identity(candidate)),
        }
    )


def create_plugin_run_receipt(
    *,
    result: PluginRunResult,
    protocol_messages: tuple[PluginProtocolMessage, ...],
    execution: PluginExecutionSummary,
    cleanup: PluginCleanupResult,
    accepted_outputs_registered: bool,
    recovered_after_interruption: bool = False,
) -> PluginRunReceipt:
    candidate = PluginRunReceipt.model_construct(
        receipt_id="sha256:" + "0" * 64,
        result=result,
        protocol_messages=protocol_messages,
        execution=execution,
        cleanup=cleanup,
        accepted_outputs_registered=accepted_outputs_registered,
        recovered_after_interruption=recovered_after_interruption,
    )
    return PluginRunReceipt.model_validate(
        {
            **candidate.model_dump(mode="json"),
            "receipt_id": sha256_fingerprint(_run_receipt_identity(candidate)),
        }
    )


def plugin_output_set_id(outputs: tuple[PluginValidatedOutput, ...]) -> str:
    ordered = tuple(
        sorted(outputs, key=lambda item: (item.subject.name, item.subject.digest, item.evidence_id))
    )
    return sha256_fingerprint({"outputs": [item.model_dump(mode="json") for item in ordered]})


def _utc_timestamp(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(UTC)


def _run_plan_identity(plan: PluginRunPlan) -> dict[str, object]:
    return plan.model_dump(mode="json", exclude={"schema_version", "run_plan_id"})


def _protocol_message_identity(message: PluginProtocolMessage) -> dict[str, object]:
    return message.model_dump(mode="json", exclude={"schema_version", "message_id"})


def _transition_identity(transition: PluginRunTransition) -> dict[str, object]:
    return transition.model_dump(mode="json", exclude={"schema_version", "transition_id"})


def _validated_output_identity(output: PluginValidatedOutput) -> dict[str, object]:
    return output.model_dump(mode="json", exclude={"output_id"})


def _run_result_identity(result: PluginRunResult) -> dict[str, object]:
    return result.model_dump(mode="json", exclude={"schema_version", "result_id"})


def _run_receipt_identity(receipt: PluginRunReceipt) -> dict[str, object]:
    return receipt.model_dump(mode="json", exclude={"schema_version", "receipt_id"})


__all__ = [
    "PLUGIN_PROTOCOL_VERSION",
    "PluginCleanupResult",
    "PluginExecutionSummary",
    "PluginExecutionTarget",
    "PluginIsolationTier",
    "PluginOutputDocument",
    "PluginProtocolDirection",
    "PluginProtocolMessage",
    "PluginProtocolMessageKind",
    "PluginResourceLimits",
    "PluginRunIssue",
    "PluginRunIssueCode",
    "PluginRunPlan",
    "PluginRunReceipt",
    "PluginRunResult",
    "PluginRunState",
    "PluginRunSubject",
    "PluginRunTransition",
    "PluginValidatedOutput",
    "create_plugin_protocol_message",
    "create_plugin_run_plan",
    "create_plugin_run_receipt",
    "create_plugin_run_result",
    "create_plugin_run_transition",
    "create_plugin_validated_output",
    "plugin_output_set_id",
]
