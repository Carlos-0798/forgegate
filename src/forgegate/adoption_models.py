"""Path-free snapshot comparison, never runtime adoption authority."""

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from forgegate.candidates.backups import TABLES
from forgegate.candidates.models import FINGERPRINT_PATTERN
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.models import SHA256_PATTERN, StrictModel

MAX_INVENTORY_ROWS = 100_000
MAX_PAGE = 200
TABLE_NAMES = sorted(
    [f"candidates.{t}" for t in TABLES]
    + [
        "jobs.events",
        "jobs.jobs",
        "jobs.job_archives",
    ]
)


class AdoptionTableComparison(StrictModel):
    table: str = Field(pattern=r"^(candidates|jobs)\.[a-z_]{1,64}$")
    source_rows: int = Field(ge=0, le=MAX_INVENTORY_ROWS)
    target_rows: int = Field(ge=0, le=MAX_INVENTORY_ROWS)
    unchanged: int = Field(ge=0, le=MAX_INVENTORY_ROWS)
    changed: int = Field(ge=0, le=MAX_INVENTORY_ROWS)
    source_only: int = Field(ge=0, le=MAX_INVENTORY_ROWS)
    target_only: int = Field(ge=0, le=MAX_INVENTORY_ROWS)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if (self.source_rows, self.target_rows) != (
            self.unchanged + self.changed + self.source_only,
            self.unchanged + self.changed + self.target_only,
        ):
            raise ValueError("table totals disagree")
        return self


class AdoptionDifference(StrictModel):
    table: str = Field(pattern=r"^(candidates|jobs)\.[a-z_]{1,64}$")
    key_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    kind: Literal["CHANGED", "SOURCE_ONLY", "TARGET_ONLY"]
    source_fingerprint: str | None = Field(pattern=FINGERPRINT_PATTERN)
    target_fingerprint: str | None = Field(pattern=FINGERPRINT_PATTERN)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        pair = (self.source_fingerprint is not None, self.target_fingerprint is not None)
        if (
            pair
            != {
                "CHANGED": (True, True),
                "SOURCE_ONLY": (True, False),
                "TARGET_ONLY": (False, True),
            }[self.kind]
        ):
            raise ValueError("difference kind disagrees with row fingerprints")
        if self.source_fingerprint == self.target_fingerprint:
            raise ValueError("unchanged row cannot be a difference")
        return self


class WorkspaceAdoptionPreflight(StrictModel):
    schema_version: Literal["forgegate.workspace-adoption-preflight.v1"] = (
        "forgegate.workspace-adoption-preflight.v1"
    )
    report_id: str = Field(pattern=FINGERPRINT_PATTERN)
    comparison_id: str = Field(pattern=FINGERPRINT_PATTERN)
    checked_at: datetime
    source_backup_sha256: str = Field(pattern=SHA256_PATTERN)
    target_backup_sha256: str = Field(pattern=SHA256_PATTERN)
    target_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    target_rehearsal_id: str = Field(pattern=FINGERPRINT_PATTERN)
    source_inventory_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    target_inventory_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    source_schema_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    target_schema_fingerprint: str = Field(pattern=FINGERPRINT_PATTERN)
    comparison: Literal["MATCH", "DIFFERENT"]
    tables: list[AdoptionTableComparison] = Field(min_length=20, max_length=20)
    differences_total: int = Field(ge=0, le=MAX_INVENTORY_ROWS * 2)
    offset: int = Field(ge=0, le=MAX_INVENTORY_ROWS * 2)
    limit: int = Field(ge=1, le=MAX_PAGE)
    differences: list[AdoptionDifference] = Field(max_length=MAX_PAGE)
    next_offset: int | None = Field(ge=1, le=MAX_INVENTORY_ROWS * 2)
    domain_validation: Literal["CURRENT_READERS_AUDIT_SUBJECTS_REPLAY_LINKS"] = (
        "CURRENT_READERS_AUDIT_SUBJECTS_REPLAY_LINKS"
    )
    comparison_scope: Literal["ALL_SUPPORTED_TABLE_ROWS_EXACT_VALUES"] = (
        "ALL_SUPPORTED_TABLE_ROWS_EXACT_VALUES"
    )
    archive_dependencies: Literal["RECHECKED_EXTERNAL_NOT_REHYDRATED"] = (
        "RECHECKED_EXTERNAL_NOT_REHYDRATED"
    )
    original_request_reconstruction: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    lineage_authenticity: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    live_source_state: Literal["NOT_CHECKED"] = "NOT_CHECKED"
    runtime_ownership: Literal["NOT_CHECKED"] = "NOT_CHECKED"
    adoption_authorized: Literal[False] = False
    live_workspace_changed: Literal[False] = False
    hardware_access: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        names = [t.table for t in self.tables]
        if names != TABLE_NAMES or self.checked_at.utcoffset() is None:
            raise ValueError("table identities or timestamp invalid")
        if (
            max(sum(t.source_rows for t in self.tables), sum(t.target_rows for t in self.tables))
            > MAX_INVENTORY_ROWS
        ):
            raise ValueError("inventory row limit exceeded")
        total = sum(t.changed + t.source_only + t.target_only for t in self.tables)
        if total != self.differences_total or self.offset > total:
            raise ValueError("difference total or offset invalid")
        same_schema = self.source_schema_fingerprint == self.target_schema_fingerprint
        same_rows = self.source_inventory_fingerprint == self.target_inventory_fingerprint
        if same_rows != (total == 0) or self.comparison != (
            "MATCH" if same_rows and same_schema else "DIFFERENT"
        ):
            raise ValueError("comparison disposition invalid")
        size = min(self.limit, total - self.offset)
        next_offset = self.offset + size if self.offset + size < total else None
        if len(self.differences) != size or self.next_offset != next_offset:
            raise ValueError("page completeness invalid")
        keys = [(d.table, d.key_fingerprint) for d in self.differences]
        if keys != sorted(set(keys)) or any(d.table not in names for d in self.differences):
            raise ValueError("difference page ordering invalid")
        identity = self.model_dump(
            mode="json",
            include={
                "source_backup_sha256",
                "target_backup_sha256",
                "target_receipt_sha256",
                "target_rehearsal_id",
                "source_inventory_fingerprint",
                "target_inventory_fingerprint",
                "source_schema_fingerprint",
                "target_schema_fingerprint",
                "tables",
            },
        )
        if self.comparison_id != sha256_fingerprint(identity):
            raise ValueError("comparison identity mismatch")
        if self.report_id != sha256_fingerprint(
            self.model_dump(mode="json", exclude={"report_id"})
        ):
            raise ValueError("report identity mismatch")
        return self
