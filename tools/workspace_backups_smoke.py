"""Installed-CLI recovery rehearsal with synthetic data and exact expected results."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateCreateCommand,
    ProjectRegisterCommand,
)
from forgegate.collection_jobs import CollectionJobRequest, CollectionJobStore
from forgegate.config import load_config
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import ProjectConfig

ROOT = Path(__file__).resolve().parents[1]
XML = b'<testsuite tests="4" failures="1" errors="0" skipped="0" time="0.5"/>'


def invoke(
    root: Path,
    *args: str,
    expected: int = 0,
    json_output: bool = True,
    expected_error: str = "WORKSPACE_DESTINATION_EXISTS",
) -> dict[str, Any]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, "-m", "forgegate", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if completed.returncode != expected:
        raise RuntimeError("workspace smoke failed; private command/output not echoed")
    if expected == 3:
        assert completed.stderr.strip() == f"ERROR: {expected_error}"
        return {"expected_rejection": True}
    if not json_output:
        assert "v4" in completed.stdout
        return {}
    result: dict[str, Any] = json.loads(completed.stdout)
    return result


def rows(path: Path) -> dict[str, list[Any]]:
    with closing(sqlite3.connect(path)) as con:
        return {
            str(r[0]): con.execute(f'SELECT * FROM "{r[0]}" ORDER BY 1').fetchall()
            for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="forgegate-workspace-smoke-") as temp:
        root = Path(temp).resolve(strict=True)
        database, jp = root / "candidates.db", root / "jobs.db"
        application = CandidateApplication.for_database(database)
        application.initialize()
        now = datetime.now(UTC)
        config = load_config(ROOT / "examples/dashboard-multi-report/forgegate.yaml")
        assert isinstance(config, ProjectConfig)
        application.register_project(
            ProjectRegisterCommand(config=config, registered_at=now),
            idempotency_key="smoke:project",
        )
        candidate = application.create_candidate(
            CandidateCreateCommand(
                project_id=config.project.id,
                version="workspace-smoke",
                commit_sha="a" * 40,
                release_track="pull-request",
                created_at=now,
            ),
            idempotency_key="smoke:candidate",
        )
        application.advance_candidate(
            candidate.candidate_id,
            CandidateAdvanceCommand(
                to_status=CandidateStatus.COLLECTING, expected_revision=0, occurred_at=now
            ),
            idempotency_key="smoke:collecting",
        )
        request = CollectionJobRequest.model_validate(
            {
                "candidate_id": candidate.candidate_id,
                "collection": {
                    "expected_revision": 1,
                    "reported_commit": "a" * 40,
                    "reports": [
                        {
                            "format": "junit",
                            "content_base64": base64.b64encode(XML).decode(),
                            "source_tool": "synthetic-workspace-smoke",
                            "source_version": "1",
                            "collected_at": now,
                        }
                    ],
                },
            }
        )
        store = CollectionJobStore(jp)
        store.initialize()
        done = store.submit(request, application, key="smoke:complete")
        store.run(done.job_id, 0, application)
        queued = store.submit(request, application, key="smoke:queued")
        cancelled = store.submit(request, application, key="smoke:cancel")
        store.cancel(cancelled.job_id, 0)
        before = (rows(database), rows(jp))
        backup, restored = root / "snapshot.zip", root / "recovered workspace"
        receipt = invoke(root, "workspace", "backup", str(database), str(jp), str(backup))
        digest = receipt["sha256"]
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == digest
        verified = invoke(root, "workspace", "verify-backup", str(backup), "--sha256", digest)
        assert verified["expected_hash_matched"]
        assert verified["job_states"] == {"SUCCEEDED": 1, "QUEUED": 1, "CANCELLED": 1}
        assert verified["job_event_count"] == 8
        recovery = invoke(
            root, "workspace", "restore", str(backup), str(restored), "--sha256", digest
        )
        assert recovery["status"] == "WORKSPACE_RESTORED_COPY"
        assert json.loads((restored / "RESTORED.json").read_text()) == recovery
        assert (rows(restored / "candidates.db"), rows(restored / "jobs.db")) == before
        after = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        plan = invoke(
            root,
            "workspace",
            "retention-plan",
            str(backup),
            "--sha256",
            digest,
            "--as-of",
            after,
            "--terminal-before",
            after,
        )
        assert sorted(r["action"] for r in plan["jobs"]) == [
            "RETAIN",
            "REVIEW_ARCHIVAL",
            "REVIEW_ARCHIVAL",
        ]
        assert plan["deletion_performed"] is False and plan["capacity_reclaimed"] == 0
        invoke(root, "workspace", "backup", str(database), str(jp), str(backup), expected=3)
        invoke(
            root, "workspace", "restore", str(backup), str(restored), "--sha256", digest, expected=3
        )
        completed = invoke(
            root,
            "jobs",
            "run",
            str(restored / "jobs.db"),
            queued.job_id,
            "--database",
            str(restored / "candidates.db"),
            "--revision",
            "0",
        )
        assert completed["state"] == "SUCCEEDED" and completed["revision"] == 4
        result = invoke(root, "jobs", "result", str(restored / "jobs.db"), queued.job_id)
        summary = result["collections"][0]["evidence"][0]["value"]
        assert summary == {
            "total": 4,
            "passed": 3,
            "failures": 1,
            "errors": 0,
            "skipped": 0,
            "duration_seconds": 0.5,
        }
        assert result["collections"][0]["evidence"][0]["status"] == "failed"
        assert result["collections"][0]["artifacts"][0]["sha256"] == hashlib.sha256(XML).hexdigest()
        assert (rows(database), rows(jp)) == before
        invoke(root, "jobs", "enable-archiving", str(jp), json_output=False)
        archive_plan = root / "review.json"
        reviewed = invoke(
            root,
            "workspace",
            "plan-job-archive",
            str(database),
            str(jp),
            str(backup),
            done.job_id,
            "--sha256",
            digest,
            "--revision",
            "4",
            "--terminal-before",
            datetime.now(UTC).isoformat(),
            "--output",
            str(archive_plan),
        )
        archived = invoke(
            root,
            "workspace",
            "archive-job",
            str(database),
            str(jp),
            str(backup),
            str(archive_plan),
            "--confirm-plan",
            reviewed["plan_fingerprint"],
        )
        assert (
            invoke(
                root,
                "workspace",
                "archive-job",
                str(database),
                str(jp),
                str(backup),
                str(archive_plan),
                "--confirm-plan",
                reviewed["plan_fingerprint"],
            )
            == archived
        )
        assert invoke(root, "jobs", "archive-info", str(jp), done.job_id) == archived
        assert store.submit(request, application, key="smoke:complete").job_id == done.job_id
        retained = invoke(
            root, "workspace", "archived-result", str(backup), done.job_id, "--sha256", digest
        )
        assert retained["collections"][0]["evidence"][0]["value"] == summary
        assert retained["collections"][0]["evidence"][0]["status"] == "failed"
        assert rows(jp)["events"] == before[1]["events"]
        assert rows(database) == before[0]
        archived_backup = root / "archived-snapshot.zip"
        archive_meta = invoke(
            root, "workspace", "backup", str(database), str(jp), str(archived_backup)
        )
        assert archive_meta["external_archive_dependencies"] == [digest]
        assert archive_meta["archived_job_count"] == 1 and archive_meta["job_store_version"] == 4
        readiness_args = (
            "workspace",
            "recovery-check",
            str(archived_backup),
            "--sha256",
            archive_meta["sha256"],
        )
        missing = invoke(root, *readiness_args, expected=2)
        assert missing["status"] == "INCOMPLETE"
        assert missing["dependencies"][0]["status"] == "NOT_SUPPLIED"
        ready = invoke(root, *readiness_args, "--dependency", f"{digest}={backup}")
        assert ready["status"] == "READY" and ready["archived_job_count"] == 1
        assert ready["dependencies"][0]["result_payloads_verified"] == 1
        wrong = invoke(
            root, *readiness_args, "--dependency", f"{digest}={archived_backup}", expected=2
        )
        assert wrong["status"] == "INCOMPLETE"
        assert wrong["dependencies"][0]["error_code"] == "WORKSPACE_HASH_MISMATCH"
        from forgegate.recovery_models import build_recovery_handoff
        from forgegate.recovery_rehearsal import RecoveryRehearsalReceipt

        reviewed_bytes = (json.dumps(ready, indent=2) + "\n").encode()
        handoff = build_recovery_handoff(
            reviewed_bytes.decode(), hashlib.sha256(reviewed_bytes).hexdigest()
        )
        handoff_file = root / "reviewed-handoff.json"
        handoff_bytes = (handoff.model_dump_json(indent=2) + "\n").encode()
        handoff_file.write_bytes(handoff_bytes)
        rehearsal_target = root / "rehearsal-copy"
        rehearsal_args = (
            "workspace",
            "rehearse-recovery",
            str(archived_backup),
            str(rehearsal_target),
            str(handoff_file),
            "--handoff-sha256",
            hashlib.sha256(handoff_bytes).hexdigest(),
        )
        invoke(
            root, *rehearsal_args, expected=3, expected_error="REHEARSAL_DEPENDENCIES_INCOMPLETE"
        )
        assert not rehearsal_target.exists()
        rehearsal = invoke(root, *rehearsal_args, "--dependency", f"{digest}={backup}")
        verified_rehearsal = RecoveryRehearsalReceipt.model_validate(rehearsal)
        assert verified_rehearsal.status == "RESTORED_COPY_VERIFIED"
        assert json.loads((rehearsal_target / "REHEARSAL.json").read_bytes()) == rehearsal
        assert rows(rehearsal_target / "jobs.db") == rows(jp)
        assert rows(rehearsal_target / "candidates.db") == rows(database)
        invoke(root, *rehearsal_args, "--dependency", f"{digest}={backup}", expected=3)
        archive_restore = root / "recovered-archived"
        invoke(
            root,
            "workspace",
            "restore",
            str(archived_backup),
            str(archive_restore),
            "--sha256",
            archive_meta["sha256"],
        )
        assert rows(archive_restore / "jobs.db") == rows(jp)
        receipt = {
            "result": "PASS",
            "verification": "HOST_TEST_SYNTHETIC",
            "checks": [
                "cross_process_backup_verify_restore",
                "exact_all_table_readback",
                "three_job_states_eight_events",
                "required_archive_hash",
                "readiness_marker",
                "backup_and_restore_no_overwrite",
                "retention_plan_two_review_one_retain_no_delete",
                "restored_queued_job_foreground_execution",
                "expected_test_summary",
                "original_workspace_unchanged",
                "reviewed_archive_cli_and_exact_replay",
                "archival_preserves_events_candidate_and_request_key",
                "external_archived_result_exact_failure_summary",
                "v4_backup_dependencies_and_restore",
                "recovery_readiness_ready_missing_and_wrong_hash",
                "reviewed_rehearsal_fresh_check_exact_copy_and_final_receipt",
                "rehearsal_missing_dependency_and_existing_target_refusal",
                "temporary_cleanup",
            ],
            "backup_sha256": digest,
            "backup_size_bytes": receipt["size_bytes"],
            "manifest_fingerprint": receipt["manifest_fingerprint"],
            "expected_test_summary": summary,
            "recovery_readiness": ready,
            "recovery_rehearsal": rehearsal,
            "missing_dependency_readiness": missing,
            "wrong_dependency_readiness": wrong,
            "source_sha256": hashlib.sha256(XML).hexdigest(),
            "hardware_access": "NOT_PERFORMED",
            "browser_test": "NOT_PERFORMED",
            "production_recovery": "NOT_PERFORMED",
        }
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
