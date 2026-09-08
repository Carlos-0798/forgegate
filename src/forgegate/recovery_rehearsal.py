"""Owner-operated recovery rehearsal; never adopt or replace a live workspace."""

import hashlib
import json
import os
import re
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from forgegate.bounded_parsing import enforce_json_structure_limits
from forgegate.candidates.backups import _check_time, _deadline, _source
from forgegate.candidates.models import FINGERPRINT_PATTERN
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.domain.models import SHA256_PATTERN, StrictModel
from forgegate.recovery_models import (
    MAX_RECOVERY_REPORT_BYTES,
    RecoveryReadinessHandoff,
    WorkspaceRecoveryReadiness,
    _unique,
)
from forgegate.recovery_readiness import _check_recovery_readiness
from forgegate.workspace_backups import (
    MEMBERS,
    BackupManifest,
    SnapshotMember,
    _guard,
    _hash,
    _inspect_pair,
    _require,
    _stream,
    _verified,
)

# The handoff wraps a bounded readiness report with fixed additional metadata.
MAX_HANDOFF_BYTES = MAX_RECOVERY_REPORT_BYTES + 4096
MAX_RECOVERY_RECEIPT_BYTES = 1024 * 1024


class RecoveryRehearsalReceipt(StrictModel):
    schema_version: Literal["forgegate.recovery-rehearsal.v1"] = "forgegate.recovery-rehearsal.v1"
    rehearsal_id: str = Field(pattern=FINGERPRINT_PATTERN)
    handoff_sha256: str = Field(pattern=SHA256_PATTERN)
    handoff: RecoveryReadinessHandoff
    rechecked_readiness: WorkspaceRecoveryReadiness
    completed_at: datetime
    manifest: BackupManifest
    candidate_store: SnapshotMember
    job_store: SnapshotMember
    post_restore_job_count: int = Field(ge=0, le=1100)
    post_restore_job_event_count: int = Field(ge=0, le=71500)
    post_restore_inspection_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    status: Literal["RESTORED_COPY_VERIFIED"] = "RESTORED_COPY_VERIFIED"
    restore_mode: Literal["new_directory_only"] = "new_directory_only"
    validation_scope: Literal["exact_member_bytes_sqlite_job_and_referenced_candidate_history"] = (
        "exact_member_bytes_sqlite_job_and_referenced_candidate_history"
    )
    archived_payloads: Literal["VERIFIED_EXTERNAL_NOT_REHYDRATED"] = (
        "VERIFIED_EXTERNAL_NOT_REHYDRATED"
    )
    all_candidate_domain_history_validation: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    live_workspace_changed: Literal[False] = False
    automatic_execution: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    hardware_access: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    producer_authenticity: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"
    external_identity_and_artifact_files: Literal["NOT_CHECKED"] = "NOT_CHECKED"
    availability: Literal["observed_during_rehearsal_only"] = "observed_during_rehearsal_only"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.handoff.disposition != "READY_FOR_REHEARSAL":
            raise ValueError("blocked handoff cannot support completed rehearsal")
        if (
            self.completed_at.utcoffset() is None
            or self.completed_at < self.rechecked_readiness.checked_at
        ):
            raise ValueError("completion requires an offset and cannot precede the fresh check")
        if _identities(self.handoff.readiness) != _identities(self.rechecked_readiness):
            raise ValueError("rechecked readiness differs from reviewed identities")
        if (
            sha256_fingerprint(self.manifest.model_dump(mode="json"))
            != self.rechecked_readiness.manifest_fingerprint
            or self.candidate_store != self.manifest.candidate_store
            or self.job_store != self.manifest.job_store
            or self.post_restore_job_count < self.rechecked_readiness.archived_job_count
            or not self.post_restore_job_count
            <= self.post_restore_job_event_count
            <= self.post_restore_job_count * 65
        ):
            raise ValueError("restored members or counts disagree with snapshot")
        if self.rehearsal_id != sha256_fingerprint(
            self.model_dump(mode="json", exclude={"rehearsal_id"})
        ):
            raise ValueError("rehearsal receipt identity mismatch")
        return self


class RecoveryRehearsalReview(StrictModel):
    schema_version: Literal["forgegate.recovery-rehearsal-review.v1"] = (
        "forgegate.recovery-rehearsal-review.v1"
    )
    review_id: str = Field(pattern=FINGERPRINT_PATTERN)
    source_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    receipt: RecoveryRehearsalReceipt
    disposition: Literal["VERIFIED_RESTORED_COPY"] = "VERIFIED_RESTORED_COPY"
    path_input: Literal["NOT_ACCEPTED"] = "NOT_ACCEPTED"
    restore_execution: Literal["NOT_PERFORMED_BY_REVIEW"] = "NOT_PERFORMED_BY_REVIEW"
    live_workspace_switch: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    continuing_availability: Literal["NOT_CHECKED"] = "NOT_CHECKED"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.review_id != sha256_fingerprint(
            self.model_dump(mode="json", exclude={"review_id"})
        ):
            raise ValueError("rehearsal review identity mismatch")
        return self


def _identities(report: WorkspaceRecoveryReadiness) -> dict[str, object]:
    # Old local clock observations are not freshness or authorization tokens.
    return report.model_dump(mode="json", exclude={"checked_at"})


def _load_handoff(path: Path, expected_sha256: str, deadline: float) -> RecoveryReadinessHandoff:
    _require(
        re.fullmatch(SHA256_PATTERN, expected_sha256) is not None, "REHEARSAL_HANDOFF_HASH_INVALID"
    )
    source = _source(path)
    _require(source.stat().st_size <= MAX_HANDOFF_BYTES, "REHEARSAL_HANDOFF_TOO_LARGE")
    with source.open("rb") as stream:
        raw = stream.read(MAX_HANDOFF_BYTES + 1)
    _check_time(deadline)
    _require(len(raw) <= MAX_HANDOFF_BYTES, "REHEARSAL_HANDOFF_TOO_LARGE")
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256, "REHEARSAL_HANDOFF_HASH_MISMATCH")
    enforce_json_structure_limits(raw, max_nodes=25_000, max_depth=22)
    document = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")),
    )
    return RecoveryReadinessHandoff.model_validate(document)


def build_rehearsal_review(document: str, expected_sha256: str) -> RecoveryRehearsalReview:
    """Validate exact imported receipt bytes and derive a path-free review."""
    raw = document.encode("utf-8")
    if (
        not raw
        or len(raw) > MAX_RECOVERY_RECEIPT_BYTES
        or re.fullmatch(SHA256_PATTERN, expected_sha256) is None
        or hashlib.sha256(raw).hexdigest() != expected_sha256
    ):
        raise ValueError("recovery rehearsal receipt bytes or hash invalid")
    enforce_json_structure_limits(raw, max_nodes=50_000, max_depth=30)
    payload = json.loads(
        document,
        object_pairs_hook=_unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")),
    )
    receipt = RecoveryRehearsalReceipt.model_validate(payload)
    values: dict[str, object] = {
        "schema_version": "forgegate.recovery-rehearsal-review.v1",
        "source_receipt_sha256": expected_sha256,
        "receipt": receipt.model_dump(mode="json"),
        "disposition": "VERIFIED_RESTORED_COPY",
        "path_input": "NOT_ACCEPTED",
        "restore_execution": "NOT_PERFORMED_BY_REVIEW",
        "live_workspace_switch": "NOT_PERFORMED",
        "continuing_availability": "NOT_CHECKED",
    }
    return RecoveryRehearsalReview.model_validate(
        {"review_id": sha256_fingerprint(values), **values}
    )


def rehearse_recovery(
    backup: Path,
    destination: Path,
    handoff_file: Path,
    *,
    handoff_sha256: str,
    dependencies: dict[str, Path],
    timeout_seconds: float = 30,
) -> RecoveryRehearsalReceipt:
    """Verify explicit inputs, restore exact bytes, cold-read, then publish one receipt.

    No destination writes before input verification. After directory creation, a failure
    retains the partial directory for inspection; no completion marker is published.
    This deliberately does not reconstruct archived results inside the restored store.
    """
    with _guard():
        deadline = _deadline(timeout_seconds)
        handoff = _load_handoff(handoff_file, handoff_sha256, deadline)
        _require(handoff.disposition == "READY_FOR_REHEARSAL", "REHEARSAL_HANDOFF_BLOCKED")
        destination = destination.absolute()
        _require(not os.path.lexists(destination), "WORKSPACE_DESTINATION_EXISTS")
        _require(destination.parent.is_dir(), "WORKSPACE_PARENT_MISSING")
        digest = handoff.readiness.backup_sha256
        fresh = _check_recovery_readiness(backup, digest, dependencies, deadline)
        _require(fresh.status == "READY", "REHEARSAL_DEPENDENCIES_INCOMPLETE")
        _require(_identities(fresh) == _identities(handoff.readiness), "REHEARSAL_REVIEW_MISMATCH")
        # Reopen and pin a second verified disposable root; never copy an unchecked
        # file after a prior readiness observation. Both reads require the same hash.
        with _verified(backup, digest, deadline) as (root, manifest, _, details):
            _check_time(deadline)
            destination.mkdir()
            for name, expected in zip(
                MEMBERS[:2], (manifest.candidate_store, manifest.job_store), strict=True
            ):
                with (root / name).open("rb") as reader, (destination / name).open("xb") as writer:
                    _require(
                        _stream(reader, writer, deadline, expected.size_bytes) == expected,
                        "REHEARSAL_COPY_MISMATCH",
                    )
                    writer.flush()
                    os.fsync(writer.fileno())
            post = _inspect_pair(destination, deadline)
            _require(post == details, "REHEARSAL_READBACK_MISMATCH")
            _require(
                _hash(destination / MEMBERS[0], deadline) == manifest.candidate_store
                and _hash(destination / MEMBERS[1], deadline) == manifest.job_store,
                "REHEARSAL_COPY_MISMATCH",
            )
            values = RecoveryRehearsalReceipt.model_construct(
                handoff_sha256=handoff_sha256,
                handoff=handoff,
                rechecked_readiness=fresh,
                completed_at=datetime.now(UTC),
                manifest=manifest,
                candidate_store=manifest.candidate_store,
                job_store=manifest.job_store,
                post_restore_job_count=post["job_count"],
                post_restore_job_event_count=post["job_event_count"],
                post_restore_inspection_fingerprint=sha256_fingerprint(post),
            ).model_dump(mode="json")
            receipt = RecoveryRehearsalReceipt.model_validate(
                {"rehearsal_id": sha256_fingerprint(values), **values}
            )
            pending = destination / ".REHEARSAL.pending"
            with pending.open("xb") as stream:
                stream.write((canonical_json(receipt.model_dump(mode="json")) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
            _check_time(deadline)
            os.link(pending, destination / "REHEARSAL.json")
            # The exclusive final link is the commit point. A cleanup failure must
            # not misreport a completed rehearsal; the pending link is harmless.
            with suppress(OSError):
                pending.unlink()
            return receipt
