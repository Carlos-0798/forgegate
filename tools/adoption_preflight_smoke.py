"""Independent CLI snapshot comparison on synthetic private temporary stores."""

import argparse
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

from forgegate.adoption_models import WorkspaceAdoptionPreflight
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
from forgegate.recovery_models import build_recovery_handoff
from forgegate.recovery_readiness import check_recovery_readiness
from forgegate.workspace_backups import backup_workspace
from forgegate.workspace_cli import _write_new_report

REPO = Path(__file__).resolve().parents[1]


def run(root: Path, arguments: list[str], expected: int = 0) -> str:
    environment = {k: v for k, v in os.environ.items() if k.upper() != "PYTHONPATH"}
    completed = subprocess.run(
        [sys.executable, "-m", "forgegate", *arguments],
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != expected:
        raise RuntimeError(
            f"adoption smoke exit mismatch: expected {expected}, got {completed.returncode}"
        )
    return completed.stdout if expected != 3 else completed.stderr


def smoke() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="forgegate-adoption-smoke-") as temp:
        root = Path(temp).resolve(strict=True)
        cp, jp = root / "candidates.db", root / "jobs.db"
        application = CandidateApplication.for_database(cp)
        application.initialize()
        config = load_config(REPO / "examples/dashboard-multi-report/forgegate.yaml")
        assert isinstance(config, ProjectConfig)
        now = datetime(2026, 9, 8, tzinfo=UTC)
        application.register_project(
            ProjectRegisterCommand(config=config, registered_at=now),
            idempotency_key="adoption:project",
        )
        candidate = application.create_candidate(
            CandidateCreateCommand(
                project_id="sample-api",
                version="adoption-synthetic",
                commit_sha="a" * 40,
                release_track="pull-request",
                created_at=now,
            ),
            idempotency_key="adoption:candidate",
        )
        application.advance_candidate(
            candidate.candidate_id,
            CandidateAdvanceCommand(
                to_status=CandidateStatus.COLLECTING, expected_revision=0, occurred_at=now
            ),
            idempotency_key="adoption:collecting",
        )
        jobs = CollectionJobStore(jp)
        jobs.initialize()
        original = root / "original.zip"
        original_hash = backup_workspace(cp, jp, original)["sha256"]
        readiness = check_recovery_readiness(
            original, expected_sha256=original_hash, dependencies={}
        )
        content = readiness.model_dump_json()
        handoff = build_recovery_handoff(content, hashlib.sha256(content.encode()).hexdigest())
        handoff_file = root / "handoff.json"
        _write_new_report(handoff_file, handoff.model_dump_json().encode())
        target = root / "cold"
        run(
            root,
            [
                "workspace",
                "rehearse-recovery",
                str(original),
                str(target),
                str(handoff_file),
                "--handoff-sha256",
                hashlib.sha256(handoff_file.read_bytes()).hexdigest(),
            ],
        )
        marker_hash = hashlib.sha256((target / "REHEARSAL.json").read_bytes()).hexdigest()
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir()}
        command = [
            "workspace",
            "adoption-preflight",
            str(original),
            str(original),
            str(target),
            "--source-sha256",
            original_hash,
            "--receipt-sha256",
            marker_hash,
        ]
        match = WorkspaceAdoptionPreflight.model_validate_json(run(root, command))
        assert match.comparison == "MATCH" and not match.adoption_authorized
        request = CollectionJobRequest.model_validate(
            {
                "candidate_id": candidate.candidate_id,
                "collection": {
                    "expected_revision": 1,
                    "reported_commit": "a" * 40,
                    "reports": [
                        {
                            "format": "junit",
                            "content_base64": base64.b64encode(
                                b'<testsuite tests="4" failures="1" errors="0" skipped="0"/>'
                            ).decode(),
                            "source_tool": "synthetic",
                            "source_version": "1",
                            "collected_at": now,
                        }
                    ],
                },
            }
        )
        queued = jobs.submit(request, application, key="synthetic-new-job")
        newer = root / "newer.zip"
        newer_hash = backup_workspace(cp, jp, newer)["sha256"]
        changed = [
            "workspace",
            "adoption-preflight",
            str(newer),
            str(original),
            str(target),
            "--source-sha256",
            newer_hash,
            "--receipt-sha256",
            marker_hash,
        ]
        report = WorkspaceAdoptionPreflight.model_validate_json(run(root, changed, 2))
        assert report.differences_total == 2
        assert {d.table for d in report.differences} == {"jobs.jobs", "jobs.events"}
        assert jobs.show(queued.job_id).state == "QUEUED"
        bad = command.copy()
        bad[bad.index("--source-sha256") + 1] = "0" * 64
        error = run(root, bad, 3)
        assert "WORKSPACE_HASH_MISMATCH" in error
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir()}
        assert before == after and set(after) == {"candidates.db", "jobs.db", "REHEARSAL.json"}
        return {
            "result": "PASS",
            "evidence_boundary": "LOCAL_HOST_TEST",
            "fixture": "SYNTHETIC",
            "hardware_access": "NOT_PERFORMED",
            "live_workspace_changed": False,
            "independent_cli_exits": {"match": 0, "different": 2, "wrong_hash": 3},
            "expected_differences": 2,
            "actual_differences": report.differences_total,
            "cold_copy_bytes_preserved": before == after,
            "new_job_state": "QUEUED",
            "match_report": match.model_dump(mode="json"),
            "difference_report": report.model_dump(mode="json"),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = smoke()
    content = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.output is not None:
        _write_new_report(args.output, content)
    print(content.decode(), end="")
