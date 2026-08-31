from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from forgegate.candidates import CandidateStoreError, SQLiteCandidateRepository, create_candidate
from forgegate.candidates.models import ReleaseCandidate, ReleaseCandidatePage
from forgegate.candidates.store import (
    AUDIT_STORE_SCHEMA_NAME,
    AUDIT_STORE_SCHEMA_VERSION,
    STORE_SCHEMA_VERSION,
)
from forgegate.domain.models import ProjectConfig
from forgegate.projects import RegisteredProjectPage

REGISTERED_AT = datetime(2026, 8, 31, 14, 0, tzinfo=UTC)
CREATED_AT = datetime(2026, 8, 31, 15, 0, tzinfo=UTC)


def project_config(
    project_id: str,
    *,
    tracks: dict[str, dict[str, str]] | None = None,
) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "schema_version": "forgegate.project.v1",
            "project": {
                "id": project_id,
                "name": project_id.replace("-", " ").title(),
                "repository": f"https://example.invalid/{project_id}",
                "default_branch": "main",
            },
            "release_tracks": tracks or {"pull_request": {"policy": "policies/pull-request.yaml"}},
            "collectors": [{"type": "junit", "path": "artifacts/junit.xml"}],
            "outputs": {
                "json": "build/forgegate/attestation.json",
                "markdown": "build/forgegate/summary.md",
            },
        }
    )


def candidate(
    project_id: str,
    *,
    version: str = "1.0.0",
    release_track: str = "pull-request",
    created_at: datetime = CREATED_AT,
) -> ReleaseCandidate:
    return create_candidate(
        project_id=project_id,
        version=version,
        commit_sha="a" * 40,
        source_branch="main",
        release_track=release_track,
        created_at=created_at,
    )


def register(
    repository: SQLiteCandidateRepository,
    project_id: str,
    *,
    tracks: dict[str, dict[str, str]] | None = None,
) -> None:
    repository.register_project(
        project_config(project_id, tracks=tracks),
        registered_at=REGISTERED_AT,
        idempotency_key=f"project:register:{project_id}",
    )


def test_new_candidate_authority_normalizes_tracks_and_fails_closed(tmp_path: Path) -> None:
    repository = SQLiteCandidateRepository(tmp_path / "forgegate.db")
    repository.initialize()

    unregistered = candidate("missing-api")
    with pytest.raises(CandidateStoreError, match="STORE_PROJECT_NOT_FOUND"):
        repository.create_for_registered_project(
            unregistered,
            idempotency_key="candidate:create:missing-project",
        )

    register(repository, "sample-api")
    normalized = candidate("sample-api", release_track="pull_request")
    assert normalized.release_track == "pull-request"
    stored = repository.create_for_registered_project(
        normalized,
        idempotency_key="candidate:create:authorized",
    )
    assert stored == repository.get(stored.candidate_id)

    missing_track = candidate("sample-api", version="2.0.0", release_track="production")
    with pytest.raises(CandidateStoreError, match="STORE_RELEASE_TRACK_NOT_FOUND"):
        repository.create_for_registered_project(
            missing_track,
            idempotency_key="candidate:create:missing-track",
        )

    noncanonical_payload = normalized.model_dump(mode="json")
    noncanonical_payload.update(
        candidate_id="cand-" + "1" * 24,
        release_track="pull_request",
    )
    noncanonical = ReleaseCandidate.model_validate(noncanonical_payload)
    with pytest.raises(CandidateStoreError, match="STORE_RELEASE_TRACK_NONCANONICAL"):
        repository.create_for_registered_project(
            noncanonical,
            idempotency_key="candidate:create:noncanonical",
        )

    register(
        repository,
        "ambiguous-api",
        tracks={
            "pull_request": {"policy": "policies/one.yaml"},
            "pull-request": {"policy": "policies/two.yaml"},
        },
    )
    with pytest.raises(CandidateStoreError, match="STORE_RELEASE_TRACK_AMBIGUOUS"):
        repository.create_for_registered_project(
            candidate("ambiguous-api"),
            idempotency_key="candidate:create:ambiguous",
        )


def test_legacy_candidate_reads_remain_available_without_registration(tmp_path: Path) -> None:
    repository = SQLiteCandidateRepository(tmp_path / "forgegate.db")
    repository.initialize()
    legacy = candidate("legacy-api")
    repository.create(legacy, idempotency_key="candidate:create:legacy")

    assert repository.get(legacy.candidate_id) == legacy
    with pytest.raises(CandidateStoreError, match="STORE_PROJECT_NOT_FOUND"):
        repository.candidates("legacy-api")


def test_project_and_candidate_discovery_pages_are_bounded_and_stable(tmp_path: Path) -> None:
    repository = SQLiteCandidateRepository(tmp_path / "forgegate.db")
    repository.initialize()
    for project_id in ("sample-api", "alpha-api", "beta-api"):
        register(repository, project_id)

    first_projects = repository.projects(limit=1)
    second_projects = repository.projects(
        after_project_id=first_projects.next_after_project_id,
        limit=1,
    )
    final_projects = repository.projects(after_project_id="sample-api", limit=1)
    assert [project.project_id for project in first_projects.projects] == ["alpha-api"]
    assert [project.project_id for project in second_projects.projects] == ["beta-api"]
    assert first_projects.has_more is second_projects.has_more is True
    assert final_projects.projects == () and final_projects.has_more is False

    sample_candidates = [
        candidate("sample-api", version="1.0.0"),
        candidate("sample-api", version="2.0.0", created_at=CREATED_AT + timedelta(minutes=1)),
    ]
    stored_candidates = []
    for index, draft in enumerate(sample_candidates, start=1):
        stored_candidates.append(
            repository.create_for_registered_project(
                draft,
                idempotency_key=f"candidate:create:sample:{index:03d}",
            )
        )
    repository.create_for_registered_project(
        candidate("beta-api"),
        idempotency_key="candidate:create:beta:001",
    )

    expected = sorted(item.candidate_id for item in stored_candidates)
    first_candidates = repository.candidates("sample-api", limit=1)
    second_candidates = repository.candidates(
        "sample-api",
        after_candidate_id=first_candidates.next_after_candidate_id,
        limit=1,
    )
    empty_candidates = repository.candidates(
        "sample-api",
        after_candidate_id=second_candidates.next_after_candidate_id,
        limit=1,
    )
    assert [item.candidate_id for item in first_candidates.candidates] == expected[:1]
    assert [item.candidate_id for item in second_candidates.candidates] == expected[1:]
    assert first_candidates.has_more is True and second_candidates.has_more is False
    assert empty_candidates.candidates == () and empty_candidates.has_more is False

    with pytest.raises(CandidateStoreError, match="STORE_PROJECT_CURSOR_INVALID"):
        repository.projects(after_project_id="INVALID")
    with pytest.raises(CandidateStoreError, match="STORE_PROJECT_LIMIT_INVALID"):
        repository.projects(limit=0)
    with pytest.raises(CandidateStoreError, match="STORE_PROJECT_ID_INVALID"):
        repository.candidates("INVALID")
    with pytest.raises(CandidateStoreError, match="STORE_CANDIDATE_CURSOR_INVALID"):
        repository.candidates("sample-api", after_candidate_id="invalid")
    with pytest.raises(CandidateStoreError, match="STORE_CANDIDATE_LIMIT_INVALID"):
        repository.candidates("sample-api", limit=201)


def test_discovery_page_models_reject_scope_order_and_cursor_mismatch(tmp_path: Path) -> None:
    repository = SQLiteCandidateRepository(tmp_path / "forgegate.db")
    repository.initialize()
    register(repository, "alpha-api")
    register(repository, "beta-api")
    alpha = repository.get_project("alpha-api")
    beta = repository.get_project("beta-api")

    with pytest.raises(ValidationError, match="unique increasing project IDs"):
        RegisteredProjectPage(
            projects=(beta, alpha),
            next_after_project_id="alpha-api",
            has_more=False,
        )
    with pytest.raises(ValidationError, match="next_after_project_id"):
        RegisteredProjectPage(projects=(alpha,), next_after_project_id=None, has_more=False)
    with pytest.raises(ValidationError, match="empty project page"):
        RegisteredProjectPage(projects=(), next_after_project_id=None, has_more=True)

    alpha_candidate = candidate("alpha-api")
    beta_candidate = candidate("beta-api")
    with pytest.raises(ValidationError, match="another project"):
        ReleaseCandidatePage(
            project_id="alpha-api",
            candidates=(beta_candidate,),
            next_after_candidate_id=beta_candidate.candidate_id,
            has_more=False,
        )
    with pytest.raises(ValidationError, match="unique increasing candidate IDs"):
        ReleaseCandidatePage(
            project_id="alpha-api",
            candidates=(alpha_candidate, alpha_candidate),
            next_after_candidate_id=alpha_candidate.candidate_id,
            has_more=False,
        )
    with pytest.raises(ValidationError, match="next_after_candidate_id"):
        ReleaseCandidatePage(
            project_id="alpha-api",
            candidates=(alpha_candidate,),
            next_after_candidate_id=None,
            has_more=False,
        )
    with pytest.raises(ValidationError, match="empty candidate page"):
        ReleaseCandidatePage(
            project_id="alpha-api",
            candidates=(),
            next_after_candidate_id=None,
            has_more=True,
        )


def test_v4_migration_adds_discovery_index_without_replaying_audit(tmp_path: Path) -> None:
    repository = SQLiteCandidateRepository(tmp_path / "forgegate.db")
    repository.initialize()
    register(repository, "sample-api")
    event_count = len(repository.audit_events().events)

    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DROP TABLE candidate_profile_bindings")
        connection.execute("DROP TABLE project_revision_idempotency_records")
        connection.execute("DROP TABLE project_profile_heads")
        connection.execute("DROP TABLE project_profiles")
        connection.execute("DROP INDEX candidates_project_candidate")
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_name'",
            (AUDIT_STORE_SCHEMA_NAME,),
        )
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_version'",
            (str(AUDIT_STORE_SCHEMA_VERSION),),
        )
        connection.execute(f"PRAGMA user_version = {AUDIT_STORE_SCHEMA_VERSION}")

    migrated = SQLiteCandidateRepository(repository.database_path)
    with pytest.raises(CandidateStoreError, match="STORE_MIGRATION_REQUIRED"):
        migrated.initialize()
    migrated.migrate()
    migrated.migrate()

    assert len(migrated.audit_events().events) == event_count
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == STORE_SCHEMA_VERSION
        index_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'candidates_project_candidate'"
        ).fetchone()[0]
    assert "project_id, candidate_id" in index_sql
