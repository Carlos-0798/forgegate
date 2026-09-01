from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from forgegate.application import (
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    CandidateEvaluateCommand,
    ProjectRegisterCommand,
)
from forgegate.candidates import CandidateStoreError, SQLiteCandidateRepository
from forgegate.candidates.store import (
    PROFILE_STORE_SCHEMA_NAME,
    PROFILE_STORE_SCHEMA_VERSION,
    STORE_SCHEMA_VERSION,
)
from forgegate.config import load_config
from forgegate.domain.enums import CandidateStatus
from forgegate.domain.models import ArtifactReference, ProjectConfig
from forgegate.policy import PolicyMaterial, create_policy_material, evaluate_policy_material
from forgegate.policy.materials import (
    MAX_POLICY_BYTES,
    decode_policy_content,
    parse_policy_bytes,
    policy_media_type,
)

CREATED = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def _application(
    tmp_path: Path,
    repository_root: Path,
) -> tuple[CandidateApplication, str]:
    application = CandidateApplication.for_database(tmp_path / "forgegate.db")
    application.initialize()
    project = load_config(repository_root / "examples/sample-python-api/forgegate.yaml")
    assert isinstance(project, ProjectConfig)
    application.register_project(
        ProjectRegisterCommand(
            config=project,
            registered_at=datetime(2026, 8, 30, 11, 59, tzinfo=UTC),
        ),
        idempotency_key="project:policy-material-setup",
    )
    candidate = application.create_candidate(
        CandidateCreateCommand(
            project_id="sample-api",
            version="1.2.0",
            commit_sha="a" * 40,
            source_branch="main",
            release_track="pull-request",
            created_at=CREATED,
        ),
        idempotency_key="candidate:policy-material-setup",
    )
    return application, candidate.candidate_id


def _advance_to_evaluating(
    application: CandidateApplication,
    candidate_id: str,
    repository_root: Path,
) -> None:
    application.advance_candidate(
        candidate_id,
        CandidateAdvanceCommand(
            to_status=CandidateStatus.COLLECTING,
            expected_revision=0,
            occurred_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
        ),
        idempotency_key="advance:policy-material-collecting",
    )
    assembly = load_config(repository_root / "tests/golden/evidence_bundle_assembly.json")
    application.bind_evidence(
        candidate_id,
        CandidateBindEvidenceCommand(
            assembly=assembly,
            bound_at=datetime(2026, 8, 30, 20, 31, tzinfo=UTC),
        ),
        idempotency_key="binding:policy-material",
    )
    for revision, target, timestamp in (
        (1, CandidateStatus.READY, datetime(2026, 8, 30, 20, 32, tzinfo=UTC)),
        (2, CandidateStatus.EVALUATING, datetime(2026, 8, 30, 20, 33, tzinfo=UTC)),
    ):
        application.advance_candidate(
            candidate_id,
            CandidateAdvanceCommand(
                to_status=target,
                expected_revision=revision,
                occurred_at=timestamp,
            ),
            idempotency_key=f"advance:policy-material-{target.value.lower()}",
        )


def test_materialization_retains_exact_profile_authorized_bytes(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _application(tmp_path, repository_root)
    project_root = repository_root / "examples/sample-python-api"

    material = application.materialize_policy(candidate_id, project_root)
    source = project_root / "policies/pull-request.yaml"
    content = source.read_bytes()

    assert material.schema_version == "forgegate.policy-material.v1"
    assert material.artifact.path_or_uri == "policies/pull-request.yaml"
    assert material.artifact.media_type == "application/yaml"
    assert material.artifact.size_bytes == len(content)
    assert material.artifact.sha256 == hashlib.sha256(content).hexdigest()
    assert decode_policy_content(material.content_base64) == content
    assert material.policy == load_config(source)
    assert PolicyMaterial.model_validate(material.model_dump(mode="json")) == material

    alternate_root = tmp_path / "alternate-project"
    alternate_policy = alternate_root / "policies/pull-request.yaml"
    alternate_policy.parent.mkdir(parents=True)
    alternate_policy.write_bytes(content + b"\n")
    semantically_equal = application.materialize_policy(candidate_id, alternate_root)

    assert semantically_equal.policy == material.policy
    assert semantically_equal.material_id != material.material_id
    assert semantically_equal.artifact.sha256 != material.artifact.sha256


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("material_id", "sha256:" + "0" * 64, "material_id"),
        ("content_base64", "e30=", "artifact size"),
        (
            "artifact",
            {
                "path_or_uri": "policies/pull-request.yaml",
                "media_type": "application/yaml",
                "sha256": "0" * 64,
                "size_bytes": 1,
            },
            "artifact size",
        ),
    ],
)
def test_policy_material_rejects_detached_identity_or_bytes(
    tmp_path: Path,
    repository_root: Path,
    field: str,
    replacement: object,
    message: str,
) -> None:
    application, candidate_id = _application(tmp_path, repository_root)
    material = application.materialize_policy(
        candidate_id,
        repository_root / "examples/sample-python-api",
    )
    payload = material.model_dump(mode="json")
    payload[field] = replacement

    with pytest.raises(ValidationError, match=message):
        PolicyMaterial.model_validate(payload)


def test_policy_material_rejects_noncanonical_base64_and_duplicate_yaml() -> None:
    with pytest.raises(ValueError, match="canonical base64"):
        decode_policy_content("%%%%")
    with pytest.raises(ValueError, match="canonical base64"):
        decode_policy_content("Zh==")

    duplicate = b"""\
schema_version: forgegate.policy.v1
name: pull-request
name: production
rules:
  - id: tests
    claim: tests.pass
    evidence_kind: test.summary
    operator: equals
    expected: 0
"""
    with pytest.raises(ValueError, match="duplicate key"):
        parse_policy_bytes(duplicate)


def test_policy_material_parser_and_metadata_fail_closed(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _application(tmp_path, repository_root)
    material = application.materialize_policy(
        candidate_id,
        repository_root / "examples/sample-python-api",
    )
    base = material.model_dump(mode="json")

    mutations = (
        (
            {"artifact": {**base["artifact"], "media_type": "application/octet-stream"}},
            "media type",
        ),
        (
            {"artifact": {**base["artifact"], "path_or_uri": "C:/policy.yaml"}},
            "must be relative",
        ),
        (
            {"artifact": {**base["artifact"], "path_or_uri": "policies/../policy.yaml"}},
            "without traversal",
        ),
        (
            {"artifact": {**base["artifact"], "sha256": "0" * 64}},
            "SHA-256",
        ),
        (
            {
                "policy": {
                    **base["policy"],
                    "rules": [
                        {**base["policy"]["rules"][0], "expected": "detached"},
                        *base["policy"]["rules"][1:],
                    ],
                }
            },
            "embedded policy",
        ),
        ({"policy_fingerprint": "sha256:" + "0" * 64}, "policy_fingerprint"),
    )
    for updates, message in mutations:
        with pytest.raises(ValidationError, match=message):
            PolicyMaterial.model_validate({**base, **updates})

    with pytest.raises(ValueError, match="byte limit"):
        parse_policy_bytes(b"x" * (MAX_POLICY_BYTES + 1))
    with pytest.raises(ValueError, match="UTF-8"):
        parse_policy_bytes(b"\xff")
    with pytest.raises(ValueError, match="cannot parse"):
        parse_policy_bytes(b"schema_version: [unterminated")
    with pytest.raises(ValueError, match="root must be a mapping"):
        parse_policy_bytes(b"- list")
    with pytest.raises(ValueError, match=r"must contain forgegate\.policy\.v1"):
        parse_policy_bytes(b"schema_version: forgegate.policy.v2")
    with pytest.raises(ValueError, match="unhashable key"):
        parse_policy_bytes(b"? [a, b]\n: value")

    assert policy_media_type("policy.JSON") == "application/json"
    assert policy_media_type("policy.yml") == "application/yaml"
    with pytest.raises(ValueError, match="must end"):
        policy_media_type("policy.txt")

    production = (
        repository_root / "examples/sample-python-api/policies/production.yaml"
    ).read_bytes()
    production_reference = ArtifactReference(
        path_or_uri="policies/production.yaml",
        media_type="application/yaml",
        sha256=hashlib.sha256(production).hexdigest(),
        size_bytes=len(production),
    )
    with pytest.raises(ValidationError, match="policy name"):
        create_policy_material(
            project_id=material.project_id,
            project_profile_id=material.project_profile_id,
            project_profile_version=material.project_profile_version,
            release_track="pull_request",
            artifact=production_reference,
            content=production,
        )


def test_product_candidate_requires_material_and_retains_v2_evaluation_atomically(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _application(tmp_path, repository_root)
    _advance_to_evaluating(application, candidate_id, repository_root)
    material = application.materialize_policy(
        candidate_id,
        repository_root / "examples/sample-python-api",
    )
    evaluated_at = datetime(2026, 8, 30, 21, 0, tzinfo=UTC)

    with pytest.raises(CandidateStoreError, match="STORE_POLICY_MATERIAL_REQUIRED"):
        application.evaluate_candidate(
            candidate_id,
            CandidateEvaluateCommand(
                policy=material.policy,
                expected_revision=3,
                evaluated_at=evaluated_at,
            ),
            idempotency_key="evaluate:legacy-policy-rejected",
        )

    command = CandidateEvaluateCommand(
        policy_material=material,
        expected_revision=3,
        evaluated_at=evaluated_at,
        reason="evaluate exact profile-authorized bytes",
    )
    result = application.evaluate_candidate(
        candidate_id,
        command,
        idempotency_key="evaluate:material-pass",
    )
    replay = application.evaluate_candidate(
        candidate_id,
        command,
        idempotency_key="evaluate:material-pass",
    )
    history = application.get_history(candidate_id)

    assert result == replay
    assert result.evaluation.schema_version == "forgegate.policy-evaluation.v2"
    assert result.evaluation.policy_material_id == material.material_id
    assert result.evaluation.policy_artifact_sha256 == material.artifact.sha256
    assert result.transition.candidate.status is CandidateStatus.PASS
    assert history.policy_material_required is True
    assert history.policy_material == material == application.get_policy_material(candidate_id)


@pytest.mark.parametrize(
    "checkpoint",
    [
        "after_policy_material_insert",
        "after_transition_append",
        "after_current_update",
        "after_idempotency_insert",
    ],
)
def test_policy_material_terminal_write_rolls_back_as_one_transaction(
    tmp_path: Path,
    repository_root: Path,
    checkpoint: str,
) -> None:
    application, candidate_id = _application(tmp_path, repository_root)
    _advance_to_evaluating(application, candidate_id, repository_root)
    material = application.materialize_policy(
        candidate_id,
        repository_root / "examples/sample-python-api",
    )
    evaluated_at = datetime(2026, 8, 30, 21, 0, tzinfo=UTC)
    binding = application.get_evidence(candidate_id)
    evaluation = evaluate_policy_material(
        material,
        binding.assembly.bundle,
        evaluated_at=evaluated_at,
    )

    def fail(name: str, _connection: sqlite3.Connection) -> None:
        if name == checkpoint:
            raise RuntimeError("injected policy-material transaction failure")

    failing = SQLiteCandidateRepository(
        application.repository.database_path,
        _failure_injector=fail,
    )
    with pytest.raises(RuntimeError, match="injected policy-material transaction failure"):
        failing.advance(
            candidate_id,
            CandidateStatus.PASS,
            expected_revision=3,
            occurred_at=evaluated_at,
            idempotency_key="evaluate:material-rollback",
            evaluation=evaluation,
            policy_material=material,
        )

    assert application.get_candidate(candidate_id).status is CandidateStatus.EVALUATING
    assert application.repository.evaluation(candidate_id) is None
    with pytest.raises(CandidateStoreError, match="STORE_POLICY_MATERIAL_NOT_FOUND"):
        application.get_policy_material(candidate_id)


def test_v6_migration_does_not_fabricate_historical_policy_material(
    tmp_path: Path,
    repository_root: Path,
) -> None:
    application, candidate_id = _application(tmp_path, repository_root)
    database = application.repository.database_path
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DROP TABLE api_security_events")
        connection.execute("DROP TRIGGER candidates_policy_material_requirement_guard_update")
        connection.execute("DROP TABLE candidate_policy_materials")
        connection.execute("ALTER TABLE candidates DROP COLUMN policy_material_required")
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_name'",
            (PROFILE_STORE_SCHEMA_NAME,),
        )
        connection.execute(
            "UPDATE forgegate_metadata SET value = ? WHERE key = 'schema_version'",
            (str(PROFILE_STORE_SCHEMA_VERSION),),
        )
        connection.execute(f"PRAGMA user_version = {PROFILE_STORE_SCHEMA_VERSION}")

    migrated = SQLiteCandidateRepository(database)
    migrated.migrate()
    history = migrated.history(candidate_id)

    assert history.policy_material_required is False
    assert history.policy_material is None
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == STORE_SCHEMA_VERSION

    later = CandidateApplication(migrated).create_candidate(
        CandidateCreateCommand(
            project_id="sample-api",
            version="1.2.1",
            commit_sha="b" * 40,
            source_branch="main",
            release_track="pull-request",
            created_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
        ),
        idempotency_key="candidate:post-v7-migration",
    )
    assert migrated.history(later.candidate_id).policy_material_required is True
