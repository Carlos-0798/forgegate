"""Seed a new private synthetic job workspace; no service, network, or device access."""

from __future__ import annotations

import argparse
import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

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
from forgegate.identity import (
    IdentityRole,
    TrustedIdentity,
    create_signing_identity,
    create_trust_store,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="New private directory; contains an ephemeral test key"
    )
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=False)
    now = datetime.now(UTC)
    application = CandidateApplication.for_database(output / "candidates.db")
    application.initialize()
    config = load_config(
        Path(__file__).resolve().parents[1] / "examples/dashboard-multi-report/forgegate.yaml"
    )
    assert isinstance(config, ProjectConfig)
    application.register_project(
        ProjectRegisterCommand(config=config, registered_at=now), idempotency_key="jobs:project"
    )
    candidate = application.create_candidate(
        CandidateCreateCommand(
            project_id="sample-api",
            version="synthetic-job-management",
            commit_sha="a" * 40,
            release_track="pull-request",
            created_at=now,
        ),
        idempotency_key="jobs:candidate",
    )
    application.advance_candidate(
        candidate.candidate_id,
        CandidateAdvanceCommand(
            to_status=CandidateStatus.COLLECTING, expected_revision=0, occurred_at=now
        ),
        idempotency_key="jobs:collecting",
    )
    store = CollectionJobStore(output / "jobs.db")
    store.initialize()
    manifest = {}
    samples = {
        "queued": b'<testsuite tests="4" failures="1" errors="0" skipped="0" time="0.5"/>',
        "complete": b'<testsuite tests="4" failures="1" errors="0" skipped="0" time="0.5"/>',
        "warning": b'<testsuite tests="2"><testcase name="x"/></testsuite>',
        "rejected": b"<!DOCTYPE x><testsuite/>",
        "running": b'<testsuite tests="4" failures="0" errors="0" skipped="0" time="0.5"/>',
        "expired": b'<testsuite tests="4" failures="0" errors="0" skipped="0" time="0.5"/>',
    }
    for name, content in samples.items():
        request = CollectionJobRequest.model_validate(
            {
                "candidate_id": candidate.candidate_id,
                "collection": {
                    "expected_revision": 1,
                    "reported_commit": "a" * 40,
                    "reports": [
                        {
                            "format": "junit",
                            "content_base64": base64.b64encode(content).decode(),
                            "source_tool": "synthetic-browser-fixture",
                            "source_version": "1",
                            "collected_at": now,
                        }
                    ],
                },
            }
        )
        if name == "expired":
            # Deliberately stale synthetic lease, not an observed process crash.
            with patch("forgegate.collection_jobs._now", return_value=now - timedelta(minutes=10)):
                job = store.submit(request, application, key=f"fixture:{name}")
                store.claim(job.job_id, 0)
        else:
            job = store.submit(request, application, key=f"fixture:{name}")
            if name in {"complete", "warning", "rejected"}:
                store.run(job.job_id, 0, application)
            if name == "running":
                store.claim(job.job_id, 0)
        manifest[name] = job.job_id
        if name == "queued":
            for index in range(21):
                store.submit(request, application, key=f"padding:{index}")
    private_key = Ed25519PrivateKey.generate()
    identity = create_signing_identity(
        display_name="Synthetic job operator",
        public_key=private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ),
    )
    trust = create_trust_store(
        (
            TrustedIdentity(
                identity=identity,
                roles=(IdentityRole.OPERATOR, IdentityRole.PRODUCER),
                project_ids=("sample-api",),
            ),
        )
    )
    (output / "operator-key.pem").write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    (output / "identity.json").write_text(identity.model_dump_json(indent=2), encoding="utf-8")
    (output / "trust.json").write_text(trust.model_dump_json(indent=2), encoding="utf-8")
    (output / "fixture.json").write_text(
        json.dumps(
            {
                "candidate_id": candidate.candidate_id,
                "jobs": manifest,
                "evidence": "SYNTHETIC_HOST_ONLY",
                "expired_lease": "SEEDED_NOT_OBSERVED_CRASH",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Created 27 synthetic jobs and an ephemeral test identity; no service or device started.")


if __name__ == "__main__":
    main()
