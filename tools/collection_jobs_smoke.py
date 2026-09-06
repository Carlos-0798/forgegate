"""Cross-process, artifact-only job acceptance; works with a clean installed wheel."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateCreateCommand,
    ProjectRegisterCommand,
)
from forgegate.config import load_config
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import ProjectConfig

ROOT = Path(__file__).resolve().parents[1]
XML = b'<testsuite tests="4" failures="1" errors="0" skipped="0" time="0.5"/>'


def invoke(root: Path, *args: str, expected: int = 0) -> dict[str, Any] | list[Any]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, "-m", "forgegate", "jobs", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != expected:
        raise RuntimeError("job smoke command failed; no private command/output echoed")
    value: dict[str, Any] | list[Any] = json.loads(completed.stdout)
    return value


def main() -> int:
    # Each CLI invocation is a NEW process. No service, network or device is used.
    with tempfile.TemporaryDirectory(prefix="forgegate-jobs-") as directory:
        root = Path(directory)
        database = root / "candidates.db"
        store = root / "jobs.db"
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
                version="durable-job-smoke",
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
        history = application.get_history(candidate.candidate_id)
        from forgegate.collection_jobs import CollectionJobStore

        CollectionJobStore(store).initialize()
        request = root / "request.json"
        request.write_text(
            json.dumps(
                {
                    "schema_version": "forgegate.collection-job-request.v1",
                    "candidate_id": candidate.candidate_id,
                    "collection": {
                        "expected_revision": 1,
                        "reported_commit": "a" * 40,
                        "reports": [
                            {
                                "format": "junit",
                                "content_base64": base64.b64encode(XML).decode("ascii"),
                                "source_tool": "synthetic-job-smoke",
                                "source_version": "1",
                                "collected_at": now.isoformat(),
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        submitted = invoke(
            root,
            "submit",
            str(store),
            str(request),
            "--database",
            str(database),
            "--key",
            "smoke:one",
        )
        assert isinstance(submitted, dict) and submitted["state"] == "QUEUED"
        job_id = str(submitted["job_id"])
        assert invoke(root, "show", str(store), job_id) == submitted
        assert (
            invoke(
                root,
                "submit",
                str(store),
                str(request),
                "--database",
                str(database),
                "--key",
                "smoke:one",
            )
            == submitted
        )
        finished = invoke(
            root, "run", str(store), job_id, "--database", str(database), "--revision", "0"
        )
        assert isinstance(finished, dict) and finished["state"] == "SUCCEEDED"
        result = invoke(root, "result", str(store), job_id)
        assert isinstance(result, dict)
        summary = result["collections"][0]["evidence"][0]["value"]
        assert summary["total"] == 4 and summary["failures"] == 1
        artifact = result["collections"][0]["artifacts"][0]
        assert artifact["sha256"] == hashlib.sha256(XML).hexdigest()
        assert result["assembly"] == invoke(root, "result", str(store), job_id, "--assembly")
        assert application.get_history(candidate.candidate_id) == history
        cancelled = invoke(
            root,
            "submit",
            str(store),
            str(request),
            "--database",
            str(database),
            "--key",
            "smoke:cancel",
        )
        assert isinstance(cancelled, dict)
        cancelled = invoke(root, "cancel", str(store), str(cancelled["job_id"]), "--revision", "0")
        assert isinstance(cancelled, dict) and cancelled["state"] == "CANCELLED"
        assert len(invoke(root, "list", str(store))) == 2
        receipt = {
            "schema_version": "forgegate.collection-job-smoke.v1",
            "result": "PASS",
            "verification": "HOST_TEST_SYNTHETIC",
            "checks": [
                "cross_process_queued_read",
                "idempotent_replay",
                "foreground_completion",
                "exact_source_sha256",
                "expected_test_summary",
                "exact_assembly_export",
                "candidate_history_unchanged",
                "explicit_cancel",
                "list_retained_jobs",
                "temporary_store_cleanup",
            ],
            "expected_test_summary": {"total": 4, "failures": 1},
            "source_sha256": hashlib.sha256(XML).hexdigest(),
            "job_completion_is_policy_pass": False,
            "hardware_access": "NOT_PERFORMED",
            "browser_test": "NOT_PERFORMED",
        }
    # Emit PASS only after TemporaryDirectory has actually closed/removed the stores.
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
