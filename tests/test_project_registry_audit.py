from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from typer.testing import CliRunner

from forgegate.api import create_api_app
from forgegate.audit import AuditEvent, AuditEventPage, AuditEventType, create_audit_event
from forgegate.candidates import CandidateStoreError, SQLiteCandidateRepository, create_candidate
from forgegate.candidates.store import (
    BINDING_STORE_SCHEMA_NAME,
    BINDING_STORE_SCHEMA_VERSION,
    STORE_SCHEMA_VERSION,
)
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.cli import app
from forgegate.config import load_config
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import ProjectConfig
from forgegate.policy import evaluate_policy
from forgegate.projects import RegisteredProject, create_registered_project

runner = CliRunner()
REGISTERED_AT = datetime(2026, 8, 31, 14, 0, tzinfo=UTC)
CREATED_AT = datetime(2026, 8, 31, 15, 0, tzinfo=UTC)


def project_config(repository_root: Path) -> ProjectConfig:
    config = load_config(repository_root / "examples/sample-python-api/forgegate.yaml")
    assert isinstance(config, ProjectConfig)
    return config


def initialized_repository(tmp_path: Path) -> SQLiteCandidateRepository:
    repository = SQLiteCandidateRepository(tmp_path / "forgegate.db")
    repository.initialize()
    return repository


def test_registered_project_and_audit_models_fail_closed(repository_root: Path) -> None:
    config = project_config(repository_root)
    registration = create_registered_project(config, registered_at=REGISTERED_AT)

    assert registration.project_id == "sample-api"
    assert registration.registered_at == REGISTERED_AT
    assert registration.config_fingerprint == sha256_fingerprint(config.model_dump(mode="json"))
    assert RegisteredProject.model_validate_json(registration.model_dump_json()) == registration

    with pytest.raises(ValueError, match="registered_at must include"):
        create_registered_project(config, registered_at=datetime(2026, 8, 31, 14, 0))

    invalid = registration.model_dump(mode="json")
    invalid["config_fingerprint"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="config_fingerprint"):
        RegisteredProject.model_validate(invalid)
    naive_registration = registration.model_dump(mode="json")
    naive_registration["registered_at"] = "2026-08-31T14:00:00"
    with pytest.raises(ValidationError, match="registered_at must include"):
        RegisteredProject.model_validate(naive_registration)
    mismatched_project = registration.model_dump(mode="json")
    mismatched_project["project_id"] = "other-api"
    with pytest.raises(ValidationError, match="project_id must match"):
        RegisteredProject.model_validate(mismatched_project)
    mismatched_identity = registration.model_dump(mode="json")
    mismatched_identity["registration_id"] = "sha256:" + "9" * 64
    with pytest.raises(ValidationError, match="registration_id"):
        RegisteredProject.model_validate(mismatched_identity)

    event = create_audit_event(
        sequence=1,
        event_type=AuditEventType.PROJECT_REGISTERED,
        occurred_at=REGISTERED_AT,
        project_id="sample-api",
        candidate_id=None,
        subject_schema_version=registration.schema_version,
        subject_id=registration.registration_id,
        subject_fingerprint=sha256_fingerprint(registration.model_dump(mode="json")),
    )
    assert AuditEvent.model_validate_json(event.model_dump_json()) == event
    assert AuditEventPage(events=(event,), next_after_sequence=1, has_more=False).events == (event,)

    event_payload = event.model_dump(mode="json")
    event_payload["event_id"] = "sha256:" + "1" * 64
    with pytest.raises(ValidationError, match="event_id"):
        AuditEvent.model_validate(event_payload)
    naive_event = event.model_dump(mode="json")
    naive_event["occurred_at"] = "2026-08-31T14:00:00"
    with pytest.raises(ValidationError, match="occurred_at must include"):
        AuditEvent.model_validate(naive_event)
    project_event_with_candidate = event.model_dump(mode="json")
    project_event_with_candidate["candidate_id"] = "cand-" + "0" * 24
    with pytest.raises(ValidationError, match="cannot reference a candidate"):
        AuditEvent.model_validate(project_event_with_candidate)

    candidate_event = event.model_dump(mode="json")
    candidate_event.update(
        event_type="candidate.created",
        event_id="sha256:" + "2" * 64,
    )
    with pytest.raises(ValidationError, match="candidate_id"):
        AuditEvent.model_validate(candidate_event)

    with pytest.raises(ValidationError, match="next_after_sequence"):
        AuditEventPage(events=(event,), next_after_sequence=None, has_more=False)
    with pytest.raises(ValidationError, match="unique increasing"):
        AuditEventPage(events=(event, event), next_after_sequence=1, has_more=False)
    with pytest.raises(ValidationError, match="empty audit page"):
        AuditEventPage(events=(), next_after_sequence=None, has_more=True)


def test_project_registration_replay_conflict_and_corruption(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    repository = initialized_repository(tmp_path)
    config = project_config(repository_root)

    stored = repository.register_project(
        config,
        registered_at=REGISTERED_AT,
        idempotency_key="project:register:001",
    )
    replay = repository.register_project(
        config,
        registered_at=REGISTERED_AT,
        idempotency_key="project:register:001",
    )
    second_key = repository.register_project(
        config,
        registered_at=REGISTERED_AT,
        idempotency_key="project:register:002",
    )

    assert stored == replay == second_key == repository.get_project("sample-api")
    assert len(repository.audit_events().events) == 1

    with pytest.raises(CandidateStoreError, match="STORE_IDEMPOTENCY_CONFLICT"):
        repository.register_project(
            config,
            registered_at=datetime(2026, 8, 31, 14, 1, tzinfo=UTC),
            idempotency_key="project:register:001",
        )
    with pytest.raises(CandidateStoreError, match="STORE_PROJECT_CONFLICT"):
        repository.register_project(
            config,
            registered_at=datetime(2026, 8, 31, 14, 1, tzinfo=UTC),
            idempotency_key="project:register:003",
        )
    with pytest.raises(CandidateStoreError, match="STORE_IDEMPOTENCY_KEY_INVALID"):
        repository.register_project(config, registered_at=REGISTERED_AT, idempotency_key="bad")
    with pytest.raises(CandidateStoreError, match="STORE_PROJECT_NOT_FOUND"):
        repository.get_project("missing-project")

    with sqlite3.connect(repository.database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE projects SET profile_version = 2")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("DELETE FROM project_idempotency_records")

    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("DROP TRIGGER projects_guard_update")
        connection.execute(
            "UPDATE projects SET project_json = ? WHERE project_id = 'sample-api'",
            (canonical_json({"invalid": True}),),
        )
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        repository.get_project("sample-api")


def test_audit_pagination_filters_replay_and_corruption(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    repository = initialized_repository(tmp_path)
    repository.register_project(
        project_config(repository_root),
        registered_at=REGISTERED_AT,
        idempotency_key="project:register:001",
    )
    candidate = create_candidate(
        project_id="sample-api",
        version="1.2.0",
        commit_sha="a" * 40,
        source_branch="main",
        release_track="pull-request",
        created_at=CREATED_AT,
    )
    repository.create(candidate, idempotency_key="candidate:create:001")
    repository.create(candidate, idempotency_key="candidate:create:001")
    repository.advance(
        candidate.candidate_id,
        CandidateStatus.COLLECTING,
        expected_revision=0,
        occurred_at=datetime(2026, 8, 31, 15, 1, tzinfo=UTC),
        idempotency_key="candidate:advance:001",
    )

    first = repository.audit_events(limit=1)
    second = repository.audit_events(after_sequence=first.next_after_sequence or 0, limit=1)
    final = repository.audit_events(after_sequence=second.next_after_sequence or 0, limit=1)
    project_events = repository.audit_events(project_id="sample-api")
    candidate_events = repository.audit_events(candidate_id=candidate.candidate_id)
    empty = repository.audit_events(after_sequence=final.next_after_sequence or 0)

    assert first.has_more is True
    assert second.has_more is True
    assert final.has_more is False
    assert [event.event_type for event in project_events.events] == [
        AuditEventType.PROJECT_REGISTERED,
        AuditEventType.CANDIDATE_CREATED,
        AuditEventType.CANDIDATE_TRANSITIONED,
    ]
    assert [event.event_type for event in candidate_events.events] == [
        AuditEventType.CANDIDATE_CREATED,
        AuditEventType.CANDIDATE_TRANSITIONED,
    ]
    assert empty.events == () and empty.next_after_sequence is None

    with pytest.raises(CandidateStoreError, match="STORE_AUDIT_CURSOR_INVALID"):
        repository.audit_events(after_sequence=-1)
    with pytest.raises(CandidateStoreError, match="STORE_AUDIT_LIMIT_INVALID"):
        repository.audit_events(limit=201)

    with sqlite3.connect(repository.database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM audit_events")
        connection.execute("DROP TRIGGER audit_events_guard_update")
        connection.execute("UPDATE audit_events SET subject_id = 'tampered' WHERE sequence = 1")
    with pytest.raises(CandidateStoreError, match="STORE_CORRUPT"):
        repository.audit_events(limit=1)


def test_v3_migration_backfills_complete_audit_chain(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    repository = initialized_repository(tmp_path)
    assembly = load_config(repository_root / "tests/golden/evidence_bundle_assembly.json")
    policy = load_config(repository_root / "examples/sample-python-api/policies/pull-request.yaml")
    candidate = create_candidate(
        project_id="sample-api",
        version="1.2.0",
        commit_sha="a" * 40,
        source_branch="main",
        release_track="pull-request",
        created_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
    )
    candidate = repository.create(candidate, idempotency_key="candidate:create:001")
    evaluation = evaluate_policy(
        policy,
        assembly.bundle,
        evaluated_at=datetime(2026, 8, 30, 21, 0, tzinfo=UTC),
    )
    candidate = repository.advance(
        candidate.candidate_id,
        CandidateStatus.COLLECTING,
        expected_revision=0,
        occurred_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
        idempotency_key="candidate:advance:001",
    ).candidate
    repository.bind_evidence(
        candidate.candidate_id,
        assembly,
        bound_at=datetime(2026, 8, 30, 20, 31, tzinfo=UTC),
        idempotency_key="candidate:binding:001",
    )
    for index, (target, timestamp) in enumerate(
        (
            (CandidateStatus.READY, datetime(2026, 8, 30, 20, 32, tzinfo=UTC)),
            (CandidateStatus.EVALUATING, datetime(2026, 8, 30, 20, 33, tzinfo=UTC)),
        ),
        start=2,
    ):
        candidate = repository.advance(
            candidate.candidate_id,
            target,
            expected_revision=candidate.revision,
            occurred_at=timestamp,
            idempotency_key=f"candidate:advance:00{index}",
        ).candidate
    candidate = repository.advance(
        candidate.candidate_id,
        CandidateStatus.PASS,
        expected_revision=3,
        occurred_at=datetime(2026, 8, 30, 21, 0, tzinfo=UTC),
        idempotency_key="candidate:advance:004",
        evaluation=evaluation,
    ).candidate
    repository.attest(
        candidate.candidate_id,
        issued_at=datetime(2026, 8, 30, 22, 0, tzinfo=UTC),
        generator_version="0.1.0.dev14",
    )

    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DROP TRIGGER candidates_policy_material_requirement_guard_update")
        connection.execute("DROP TABLE candidate_policy_materials")
        connection.execute("ALTER TABLE candidates DROP COLUMN policy_material_required")
        connection.execute("DROP TABLE candidate_profile_bindings")
        connection.execute("DROP TABLE project_revision_idempotency_records")
        connection.execute("DROP TABLE project_profile_heads")
        connection.execute("DROP TABLE project_profiles")
        connection.execute("DROP INDEX candidates_project_candidate")
        connection.execute("DROP TABLE audit_events")
        connection.execute("DROP TABLE project_idempotency_records")
        connection.execute("DROP TABLE projects")
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_name'",
            (BINDING_STORE_SCHEMA_NAME,),
        )
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_version'",
            (str(BINDING_STORE_SCHEMA_VERSION),),
        )
        connection.execute(f"PRAGMA user_version = {BINDING_STORE_SCHEMA_VERSION}")

    migrated = SQLiteCandidateRepository(repository.database_path)
    with pytest.raises(CandidateStoreError, match="STORE_MIGRATION_REQUIRED"):
        migrated.initialize()
    migrated.migrate()
    migrated.migrate()

    events = migrated.audit_events().events
    assert [event.event_type for event in events] == [
        AuditEventType.CANDIDATE_CREATED,
        AuditEventType.CANDIDATE_TRANSITIONED,
        AuditEventType.EVIDENCE_BOUND,
        AuditEventType.CANDIDATE_TRANSITIONED,
        AuditEventType.CANDIDATE_TRANSITIONED,
        AuditEventType.CANDIDATE_TRANSITIONED,
        AuditEventType.EVALUATION_RECORDED,
        AuditEventType.ATTESTATION_RECORDED,
    ]
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == STORE_SCHEMA_VERSION


def test_project_and_audit_api_contract(tmp_path: Path, repository_root: Path) -> None:
    config = project_config(repository_root)
    payload = {
        "config": config.model_dump(mode="json", by_alias=True),
        "registered_at": "2026-08-31T14:00:00Z",
    }
    with TestClient(
        create_api_app(tmp_path / "forgegate.db"), base_url="http://127.0.0.1"
    ) as client:
        missing_key = client.post("/v1/projects", json=payload)
        unauthorized_candidate = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "candidate:api:unregistered"},
            json={
                "project_id": "sample-api",
                "version": "1.2.0",
                "commit_sha": "a" * 40,
                "source_branch": "main",
                "release_track": "pull-request",
                "created_at": "2026-08-31T15:00:00Z",
            },
        )
        created = client.post(
            "/v1/projects",
            headers={"Idempotency-Key": "project:api:001"},
            json=payload,
        )
        replay = client.post(
            "/v1/projects",
            headers={"Idempotency-Key": "project:api:001"},
            json=payload,
        )
        shown = client.get("/v1/projects/sample-api")
        projects = client.get("/v1/projects", params={"limit": 1})
        candidate = client.post(
            "/v1/candidates",
            headers={"Idempotency-Key": "candidate:api:authorized"},
            json={
                "project_id": "sample-api",
                "version": "1.2.0",
                "commit_sha": "a" * 40,
                "source_branch": "main",
                "release_track": "pull_request",
                "created_at": "2026-08-31T15:00:00Z",
            },
        )
        candidates = client.get(
            "/v1/projects/sample-api/candidates",
            params={"limit": 1},
        )
        missing = client.get("/v1/projects/missing-project")
        missing_candidates = client.get("/v1/projects/missing-project/candidates")
        audit = client.get("/v1/audit-events", params={"project_id": "sample-api", "limit": 1})
        bad_limit = client.get("/v1/audit-events", params={"limit": 0})
        bad_candidate = client.get("/v1/audit-events", params={"candidate_id": "bad"})
        conflict = client.post(
            "/v1/projects",
            headers={"Idempotency-Key": "project:api:002"},
            json={**payload, "registered_at": "2026-08-31T14:01:00Z"},
        )

    assert missing_key.status_code == 422
    assert unauthorized_candidate.status_code == 404
    assert created.status_code == replay.status_code == 201
    assert created.json() == replay.json() == shown.json()
    assert projects.status_code == candidates.status_code == 200
    assert candidate.status_code == 201
    assert projects.json()["projects"] == [created.json()]
    assert candidates.json()["candidates"] == [candidate.json()]
    assert candidate.json()["release_track"] == "pull-request"
    assert missing.status_code == 404
    assert missing_candidates.status_code == 404
    assert audit.status_code == 200
    assert audit.json()["events"][0]["event_type"] == "project.registered"
    assert bad_limit.status_code == bad_candidate.status_code == 422
    assert conflict.status_code == 409


def test_project_and_audit_cli_contract(tmp_path: Path, repository_root: Path) -> None:
    database = tmp_path / "forgegate.db"
    config_path = repository_root / "examples/sample-python-api/forgegate.yaml"
    candidate_path = repository_root / "examples/sample-python-api/candidates/draft.json"
    assert runner.invoke(app, ["candidate", "init-store", str(database)]).exit_code == 0

    unauthorized = runner.invoke(
        app,
        [
            "candidate",
            "create",
            "--project",
            "sample-api",
            "--version",
            "1.2.0",
            "--commit",
            "a" * 40,
            "--created-at",
            "2026-08-31T15:00:00Z",
            "--database",
            str(database),
            "--idempotency-key",
            "candidate:cli:unregistered",
        ],
    )

    register = runner.invoke(
        app,
        [
            "project",
            "register",
            str(database),
            str(config_path),
            "--registered-at",
            "2026-08-31T14:00:00Z",
            "--idempotency-key",
            "project:cli:001",
        ],
    )
    show = runner.invoke(app, ["project", "show", str(database), "sample-api"])
    projects = runner.invoke(app, ["project", "list", str(database), "--limit", "1"])
    candidate = runner.invoke(
        app,
        [
            "candidate",
            "create",
            "--project",
            "sample-api",
            "--version",
            "1.2.0",
            "--commit",
            "a" * 40,
            "--created-at",
            "2026-08-31T15:00:00Z",
            "--track",
            "pull_request",
            "--database",
            str(database),
            "--idempotency-key",
            "candidate:cli:authorized",
        ],
    )
    candidates = runner.invoke(
        app,
        ["candidate", "list", str(database), "--project", "sample-api", "--limit", "1"],
    )
    invalid_projects = runner.invoke(
        app,
        ["project", "list", str(database), "--after-project", "INVALID"],
    )
    missing_project_candidates = runner.invoke(
        app,
        ["candidate", "list", str(database), "--project", "missing-project"],
    )
    audit = runner.invoke(
        app,
        ["audit", "events", str(database), "--project", "sample-api", "--limit", "1"],
    )
    wrong_type = runner.invoke(
        app,
        [
            "project",
            "register",
            str(database),
            str(candidate_path),
            "--registered-at",
            "2026-08-31T14:00:00Z",
            "--idempotency-key",
            "project:cli:002",
        ],
    )
    missing = runner.invoke(app, ["project", "show", str(database), "missing-project"])
    invalid_audit = runner.invoke(
        app,
        ["audit", "events", str(database), "--project", "INVALID"],
    )

    assert unauthorized.exit_code == 3 and "STORE_PROJECT_NOT_FOUND" in unauthorized.output
    assert register.exit_code == show.exit_code == projects.exit_code == 0
    assert candidate.exit_code == candidates.exit_code == audit.exit_code == 0
    assert json.loads(register.stdout) == json.loads(show.stdout)
    assert json.loads(projects.stdout)["projects"] == [json.loads(register.stdout)]
    assert json.loads(candidates.stdout)["candidates"] == [json.loads(candidate.stdout)]
    assert json.loads(candidate.stdout)["release_track"] == "pull-request"
    assert invalid_projects.exit_code == 3 and "validation error" in invalid_projects.output
    assert missing_project_candidates.exit_code == 3
    assert "STORE_PROJECT_NOT_FOUND" in missing_project_candidates.output
    assert json.loads(audit.stdout)["events"][0]["event_type"] == "project.registered"
    assert wrong_type.exit_code == 3 and "forgegate.project.v1" in wrong_type.output
    assert missing.exit_code == 3 and "STORE_PROJECT_NOT_FOUND" in missing.output
    assert invalid_audit.exit_code == 3 and "validation error" in invalid_audit.output
