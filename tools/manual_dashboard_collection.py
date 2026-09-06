"""Prepare an isolated synthetic fixture; never open hardware or start a server."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateCreateCommand,
    ProjectRegisterCommand,
)
from forgegate.config import load_config
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import ProjectConfig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new isolated fixture directory")
    parser.add_argument(
        "--multi-report", action="store_true", help="use synthetic test + coverage policy"
    )
    args = parser.parse_args()
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1] / (
        "examples/dashboard-multi-report" if args.multi_report else "examples/dashboard-junit"
    )
    application = CandidateApplication.for_database(output / "forgegate.db")
    application.initialize()
    now = datetime.now(UTC)
    config = load_config(root / "forgegate.yaml")
    if not isinstance(config, ProjectConfig):
        raise ValueError("fixture configuration must be a project")
    application.register_project(
        ProjectRegisterCommand(config=config, registered_at=now),
        idempotency_key="junit-fixture:register",
    )
    for name in ("pass", "fail", "warning", "rejected"):
        candidate = application.create_candidate(
            CandidateCreateCommand(
                project_id="sample-api",
                version=f"junit-{name}-fixture",
                commit_sha="a" * 40,
                release_track="pull-request",
                created_at=now,
            ),
            idempotency_key=f"junit-fixture:{name}",
        )
        application.advance_candidate(
            candidate.candidate_id,
            CandidateAdvanceCommand(
                to_status=CandidateStatus.COLLECTING, expected_revision=0, occurred_at=now
            ),
            idempotency_key=f"junit-fixture:{name}:collecting",
        )
        material = application.materialize_policy(candidate.candidate_id, root)
        (output / f"{name}-policy-material.json").write_text(
            material.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        print(f"{name}: {candidate.candidate_id}")
    print("SYNTHETIC fixture only; no identity generated, server started, or hardware accessed.")


if __name__ == "__main__":
    main()
