"""Read-only owner preflight of explicit snapshots and a cold rehearsal copy."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forgegate.adoption_inventory import inspect_bounds, inspect_domain, inventory
from forgegate.adoption_models import (
    AdoptionDifference,
    AdoptionTableComparison,
    WorkspaceAdoptionPreflight,
)
from forgegate.candidates.backups import _check_time, _deadline, _sidecars
from forgegate.canonical import sha256_fingerprint
from forgegate.collection_jobs import JobError
from forgegate.recovery_readiness import _check_recovery_readiness
from forgegate.recovery_rehearsal import (
    MAX_RECOVERY_RECEIPT_BYTES,
    RecoveryRehearsalReceipt,
    _identities,
    build_rehearsal_review,
)
from forgegate.workspace_backups import WorkspaceBackupError, _guard, _hash, _require, _verified


def _plain(path: Path, *, directory: bool = False) -> Path:
    path = path.absolute()
    _require(
        all(not p.is_symlink() and not p.is_junction() for p in (path, *path.parents)),
        "ADOPTION_PATH_INVALID",
    )
    _require(path.is_dir() if directory else path.is_file(), "ADOPTION_PATH_INVALID")
    if not directory:
        _require(path.stat().st_nlink == 1 and not _sidecars(path), "ADOPTION_NOT_COLD")
    return path


def _cold(
    target: Path, receipt: RecoveryRehearsalReceipt, receipt_hash: str, deadline: float
) -> None:
    _plain(target, directory=True)
    for name, expected in (
        ("candidates.db", receipt.candidate_store),
        ("jobs.db", receipt.job_store),
    ):
        path = _plain(target / name)
        _require(_hash(path, deadline, expected.size_bytes) == expected, "ADOPTION_TARGET_CHANGED")
        _plain(path)
    path = _plain(target / "REHEARSAL.json")
    _require(
        _hash(path, deadline, MAX_RECOVERY_RECEIPT_BYTES).sha256 == receipt_hash,
        "ADOPTION_RECEIPT_CHANGED",
    )


def preflight_adoption(
    source_backup: Path,
    target_backup: Path,
    target: Path,
    *,
    source_sha256: str,
    receipt_sha256: str,
    source_dependencies: dict[str, Path] | None = None,
    target_dependencies: dict[str, Path] | None = None,
    offset: int = 0,
    limit: int = 100,
    timeout_seconds: float = 30,
) -> WorkspaceAdoptionPreflight:
    """No live databases opened, subprocesses, sockets, write admission or switch.

    Only explicitly requested output (CLI) and disposable verification files are written.
    MATCH describes snapshots, not authenticated lineage, live freshness or adoption readiness.
    """
    try:
        with _guard():
            deadline = _deadline(timeout_seconds)
            _require(
                type(offset) is int
                and 0 <= offset <= 200_000
                and type(limit) is int
                and 1 <= limit <= 200,
                "ADOPTION_PAGE_INVALID",
            )
            target = _plain(target, directory=True)
            marker = _plain(target / "REHEARSAL.json")
            _require(
                marker.stat().st_size <= MAX_RECOVERY_RECEIPT_BYTES, "ADOPTION_RECEIPT_TOO_LARGE"
            )
            with marker.open("rb") as stream:
                raw = stream.read(MAX_RECOVERY_RECEIPT_BYTES + 1)
            receipt = build_rehearsal_review(raw.decode("utf-8"), receipt_sha256).receipt
            _cold(target, receipt, receipt_sha256, deadline)
            source_backup, target_backup = _plain(source_backup), _plain(target_backup)
            source_deps, target_deps = source_dependencies or {}, target_dependencies or {}
            _require(
                len(source_deps) <= 1000 and len(target_deps) <= 1000,
                "RECOVERY_DEPENDENCY_MAP_INVALID",
            )
            with (
                _verified(
                    source_backup, source_sha256, deadline, pre_inspect=inspect_bounds
                ) as source,
                _verified(
                    target_backup,
                    receipt.rechecked_readiness.backup_sha256,
                    deadline,
                    pre_inspect=inspect_bounds,
                ) as restored,
            ):
                sr, _sm, sd, _ = source
                tr, tm, td, details = restored
                _require(
                    tm == receipt.manifest
                    and sha256_fingerprint(details) == receipt.post_restore_inspection_fingerprint,
                    "ADOPTION_RECEIPT_MISMATCH",
                )
                inspect_domain(sr, deadline)
                inspect_domain(tr, deadline)
                # Bound original dependency copies before their existing exact job/payload checks.
                for mapping in (source_deps, target_deps):
                    for digest, path in mapping.items():
                        with _verified(_plain(path), digest, deadline, pre_inspect=inspect_bounds):
                            pass
                sready = _check_recovery_readiness(
                    source_backup, source_sha256, source_deps, deadline
                )
                tready = _check_recovery_readiness(target_backup, td.sha256, target_deps, deadline)
                _require(
                    sready.status == tready.status == "READY", "ADOPTION_DEPENDENCIES_INCOMPLETE"
                )
                _require(
                    _identities(tready) == _identities(receipt.rechecked_readiness),
                    "ADOPTION_RECEIPT_MISMATCH",
                )
                si, ss = inventory(sr, deadline)
                ti, ts = inventory(tr, deadline)
                tables = []
                differences = []
                for table in sorted(si):
                    left, right = si[table], ti[table]
                    changed = unchanged = source_only = target_only = 0
                    for key in sorted(left.keys() | right.keys()):
                        a, b = left.get(key), right.get(key)
                        if a == b:
                            unchanged += 1
                            continue
                        kind = (
                            "TARGET_ONLY"
                            if a is None
                            else "SOURCE_ONLY"
                            if b is None
                            else "CHANGED"
                        )
                        changed += kind == "CHANGED"
                        source_only += kind == "SOURCE_ONLY"
                        target_only += kind == "TARGET_ONLY"
                        differences.append(
                            AdoptionDifference.model_validate(
                                {
                                    "table": table,
                                    "key_fingerprint": key,
                                    "kind": kind,
                                    "source_fingerprint": a,
                                    "target_fingerprint": b,
                                }
                            )
                        )
                    tables.append(
                        AdoptionTableComparison(
                            table=table,
                            source_rows=len(left),
                            target_rows=len(right),
                            changed=changed,
                            unchanged=unchanged,
                            source_only=source_only,
                            target_only=target_only,
                        )
                    )
                _require(offset <= len(differences), "ADOPTION_PAGE_INVALID")
                identity: dict[str, Any] = {
                    "source_backup_sha256": sd.sha256,
                    "target_backup_sha256": td.sha256,
                    "target_receipt_sha256": receipt_sha256,
                    "target_rehearsal_id": receipt.rehearsal_id,
                    "source_inventory_fingerprint": sha256_fingerprint(si),
                    "target_inventory_fingerprint": sha256_fingerprint(ti),
                    "source_schema_fingerprint": ss,
                    "target_schema_fingerprint": ts,
                    "tables": [t.model_dump(mode="json") for t in tables],
                }
                _cold(target, receipt, receipt_sha256, deadline)
                _check_time(deadline)
                # Fill fixed defaults before deriving the final content identity.
                report = WorkspaceAdoptionPreflight.model_construct(
                    **{**identity, "tables": tables},
                    report_id="",
                    comparison_id=sha256_fingerprint(identity),
                    checked_at=datetime.now(UTC),
                    comparison="MATCH" if not differences and ss == ts else "DIFFERENT",
                    differences_total=len(differences),
                    differences=differences[offset : offset + limit],
                    offset=offset,
                    limit=limit,
                    next_offset=offset + limit if offset + limit < len(differences) else None,
                )
                values = report.model_dump(mode="json", exclude={"report_id"})
                return WorkspaceAdoptionPreflight.model_validate(
                    {"report_id": sha256_fingerprint(values), **values}
                )
    except (KeyError, TypeError, RecursionError, JobError) as exc:
        raise WorkspaceBackupError("ADOPTION_DOMAIN_INVALID") from exc
