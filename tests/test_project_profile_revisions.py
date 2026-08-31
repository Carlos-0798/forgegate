from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from forgegate.api import create_api_app
from forgegate.audit import AuditEventType
from forgegate.candidates import (
    CandidateStoreError,
    ProfileBoundReleaseCandidate,
    ReleaseCandidate,
    SQLiteCandidateRepository,
    create_candidate,
)
from forgegate.candidates.store import (
    DISCOVERY_STORE_SCHEMA_NAME,
    DISCOVERY_STORE_SCHEMA_VERSION,
    STORE_SCHEMA_VERSION,
)
from forgegate.cli import app
from forgegate.domain.models import ProjectConfig
from forgegate.projects import ProjectProfileRevision, RegisteredProject

runner = CliRunner()
REGISTERED_AT = datetime(2026, 8, 31, 14, 0, tzinfo=UTC)


def project_config(project_id: str, *tracks: str) -> ProjectConfig:
    release_tracks = {
        track.replace("-", "_"): {"policy": f"policies/{track}.yaml"} for track in tracks
    }
    return ProjectConfig.model_validate(
        {
            "schema_version": "forgegate.project.v1",
            "project": {
                "id": project_id,
                "name": project_id.replace("-", " ").title(),
                "repository": f"https://example.invalid/{project_id}",
                "default_branch": "main",
            },
            "release_tracks": release_tracks,
            "collectors": [{"type": "junit", "path": "artifacts/junit.xml"}],
            "outputs": {
                "json": "build/forgegate/attestation.json",
                "markdown": "build/forgegate/summary.md",
            },
        }
    )


def draft(track: str, *, created_at: datetime) -> ReleaseCandidate:
    return create_candidate(
        project_id="sample-api",
        version="1.2.0",
        commit_sha="a" * 40,
        source_branch="main",
        release_track=track,
        created_at=created_at,
    )


def initialized_repository(tmp_path: Path) -> SQLiteCandidateRepository:
    repository = SQLiteCandidateRepository(tmp_path / "forgegate.db")
    repository.initialize()
    repository.register_project(
        project_config("sample-api", "pull-request"),
        registered_at=REGISTERED_AT,
        idempotency_key="project:register:sample-api",
    )
    return repository


def test_profile_revisions_bind_only_later_candidates_and_preserve_replay(
    tmp_path: Path,
) -> None:
    repository = initialized_repository(tmp_path)
    first_draft = draft(
        "pull-request",
        created_at=datetime(2026, 8, 31, 15, 0, tzinfo=UTC),
    )
    first = repository.create_for_registered_project(
        first_draft,
        idempotency_key="candidate:create:profile-one",
    )
    assert isinstance(first, ProfileBoundReleaseCandidate)
    assert first.project_profile_version == 1

    second = repository.revise_project(
        "sample-api",
        project_config("sample-api", "production"),
        expected_profile_version=1,
        effective_at=datetime(2026, 8, 31, 16, 0, tzinfo=UTC),
        idempotency_key="project:revise:production",
    )
    replay = repository.revise_project(
        "sample-api",
        project_config("sample-api", "production"),
        expected_profile_version=1,
        effective_at=datetime(2026, 8, 31, 16, 0, tzinfo=UTC),
        idempotency_key="project:revise:production",
    )
    assert second == replay == repository.get_current_project_profile("sample-api")
    assert second.previous_profile_id == first.project_profile_id

    assert (
        repository.create_for_registered_project(
            first_draft,
            idempotency_key="candidate:create:profile-one",
        )
        == first
    )
    with pytest.raises(CandidateStoreError, match="STORE_RELEASE_TRACK_NOT_FOUND"):
        repository.create_for_registered_project(
            draft(
                "pull-request",
                created_at=datetime(2026, 8, 31, 17, 0, tzinfo=UTC),
            ),
            idempotency_key="candidate:create:removed-track",
        )

    later = repository.create_for_registered_project(
        draft("production", created_at=datetime(2026, 8, 31, 17, 0, tzinfo=UTC)),
        idempotency_key="candidate:create:profile-two",
    )
    assert isinstance(later, ProfileBoundReleaseCandidate)
    assert (later.project_profile_id, later.project_profile_version) == (
        second.revision_id,
        2,
    )
    assert repository.get(first.candidate_id) == first

    profiles = repository.project_profiles("sample-api")
    assert [profile.profile_version for profile in profiles.profiles] == [1, 2]
    assert isinstance(profiles.profiles[0], RegisteredProject)
    assert isinstance(profiles.profiles[1], ProjectProfileRevision)
    assert [event.event_type for event in repository.audit_events().events] == [
        AuditEventType.PROJECT_REGISTERED,
        AuditEventType.CANDIDATE_CREATED,
        AuditEventType.PROJECT_PROFILE_REVISED,
        AuditEventType.CANDIDATE_CREATED,
    ]


def test_project_revision_rejects_stale_cas_time_regression_and_key_reuse(
    tmp_path: Path,
) -> None:
    repository = initialized_repository(tmp_path)
    revision = repository.revise_project(
        "sample-api",
        project_config("sample-api", "production"),
        expected_profile_version=1,
        effective_at=datetime(2026, 8, 31, 16, 0, tzinfo=UTC),
        idempotency_key="project:revise:guarded",
    )

    with pytest.raises(CandidateStoreError, match="STORE_PROJECT_PROFILE_VERSION_CONFLICT"):
        repository.revise_project(
            "sample-api",
            project_config("sample-api", "pull-request"),
            expected_profile_version=1,
            effective_at=datetime(2026, 8, 31, 17, 0, tzinfo=UTC),
            idempotency_key="project:revise:stale",
        )
    with pytest.raises(CandidateStoreError, match="STORE_PROJECT_PROFILE_TIME_REGRESSION"):
        repository.revise_project(
            "sample-api",
            project_config("sample-api", "pull-request"),
            expected_profile_version=revision.profile_version,
            effective_at=datetime(2026, 8, 31, 15, 59, tzinfo=UTC),
            idempotency_key="project:revise:time-regression",
        )
    with pytest.raises(CandidateStoreError, match="STORE_IDEMPOTENCY_CONFLICT"):
        repository.revise_project(
            "sample-api",
            project_config("sample-api", "production"),
            expected_profile_version=2,
            effective_at=datetime(2026, 8, 31, 17, 0, tzinfo=UTC),
            idempotency_key="project:revise:guarded",
        )


def test_profile_binding_corruption_fails_closed(tmp_path: Path) -> None:
    repository = initialized_repository(tmp_path)
    candidate = repository.create_for_registered_project(
        draft("pull-request", created_at=datetime(2026, 8, 31, 15, 0, tzinfo=UTC)),
        idempotency_key="candidate:create:corruption",
    )
    with sqlite3.connect(repository.database_path) as connection:
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
            "AND name = 'candidate_profile_bindings_guard_delete'"
        ).fetchone()[0]
        connection.execute("DROP TRIGGER candidate_profile_bindings_guard_delete")
        connection.execute(
            "DELETE FROM candidate_profile_bindings WHERE candidate_id = ?",
            (candidate.candidate_id,),
        )
        connection.execute(trigger_sql)

    with pytest.raises(
        CandidateStoreError,
        match="profile-bound candidate is missing its durable binding",
    ):
        repository.get(candidate.candidate_id)


def test_v5_migration_backfills_registration_profiles_without_fabricating_candidate_links(
    tmp_path: Path,
) -> None:
    repository = initialized_repository(tmp_path)
    legacy = draft("pull-request", created_at=datetime(2026, 8, 31, 15, 0, tzinfo=UTC))
    repository.create(legacy, idempotency_key="candidate:create:legacy-v5")
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DROP TRIGGER candidates_policy_material_requirement_guard_update")
        connection.execute("DROP TABLE candidate_policy_materials")
        connection.execute("ALTER TABLE candidates DROP COLUMN policy_material_required")
        connection.execute("DROP TABLE candidate_profile_bindings")
        connection.execute("DROP TABLE project_revision_idempotency_records")
        connection.execute("DROP TABLE project_profile_heads")
        connection.execute("DROP TABLE project_profiles")
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_name'",
            (DISCOVERY_STORE_SCHEMA_NAME,),
        )
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_version'",
            (str(DISCOVERY_STORE_SCHEMA_VERSION),),
        )
        connection.execute(f"PRAGMA user_version = {DISCOVERY_STORE_SCHEMA_VERSION}")

    migrated = SQLiteCandidateRepository(repository.database_path)
    with pytest.raises(CandidateStoreError, match="STORE_MIGRATION_REQUIRED"):
        migrated.initialize()
    migrated.migrate()

    current = migrated.get_current_project_profile("sample-api")
    assert isinstance(current, RegisteredProject)
    assert migrated.get(legacy.candidate_id) == legacy
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == STORE_SCHEMA_VERSION
        binding_count = connection.execute(
            "SELECT COUNT(*) FROM candidate_profile_bindings"
        ).fetchone()[0]
        assert binding_count == 0


def test_project_revision_api_and_cli_contracts(tmp_path: Path) -> None:
    database = tmp_path / "forgegate.db"
    initial = project_config("sample-api", "pull-request")
    revised = project_config("sample-api", "production")
    with TestClient(create_api_app(database), base_url="http://127.0.0.1") as client:
        registered = client.post(
            "/v1/projects",
            headers={"Idempotency-Key": "project:api:register"},
            json={
                "config": initial.model_dump(mode="json", by_alias=True),
                "registered_at": "2026-08-31T14:00:00Z",
            },
        )
        created = client.post(
            "/v1/projects/sample-api/revisions",
            headers={"Idempotency-Key": "project:api:revise"},
            json={
                "config": revised.model_dump(mode="json", by_alias=True),
                "expected_profile_version": 1,
                "effective_at": "2026-08-31T16:00:00Z",
            },
        )
        current = client.get("/v1/projects/sample-api/profile")
        history = client.get("/v1/projects/sample-api/revisions")

    assert registered.status_code == created.status_code == 201
    assert current.status_code == history.status_code == 200
    assert current.json() == created.json()
    assert [profile["profile_version"] for profile in history.json()["profiles"]] == [1, 2]

    shown = runner.invoke(app, ["project", "current", str(database), "sample-api"])
    listed = runner.invoke(app, ["project", "history", str(database), "sample-api"])
    assert shown.exit_code == listed.exit_code == 0
    assert json.loads(shown.stdout) == current.json()
    assert json.loads(listed.stdout) == history.json()

    third_config = project_config("sample-api", "pull-request", "production")
    third_config_path = tmp_path / "third-profile.json"
    third_config_path.write_text(
        json.dumps(third_config.model_dump(mode="json", by_alias=True)),
        encoding="utf-8",
    )
    revised_by_cli = runner.invoke(
        app,
        [
            "project",
            "revise",
            str(database),
            "sample-api",
            str(third_config_path),
            "--expected-profile-version",
            "2",
            "--effective-at",
            "2026-08-31T17:00:00Z",
            "--idempotency-key",
            "project:cli:revise",
        ],
    )
    assert revised_by_cli.exit_code == 0, revised_by_cli.output
    assert json.loads(revised_by_cli.stdout)["profile_version"] == 3
