import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from forgegate.assembly import EvidenceBundleAssembly
from forgegate.candidates import create_candidate, transition_candidate
from forgegate.candidates.evidence_binding import (
    CandidateEvidenceBinding,
    binding_identity,
    create_candidate_evidence_binding,
)
from forgegate.canonical import sha256_fingerprint
from forgegate.domain.enums import CandidateStatus

CREATED = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
BOUND_AT = datetime(2026, 8, 30, 20, 31, tzinfo=UTC)


def assembly(repository_root: Path) -> EvidenceBundleAssembly:
    return EvidenceBundleAssembly.model_validate_json(
        (repository_root / "tests/golden/evidence_bundle_assembly.json").read_text(encoding="utf-8")
    )


def candidate(commit: str = "a" * 40):
    draft = create_candidate(
        project_id="sample-api",
        version="1.2.0",
        commit_sha=commit,
        source_branch="main",
        release_track="pull-request",
        created_at=CREATED,
    )
    return transition_candidate(
        draft,
        CandidateStatus.COLLECTING,
        occurred_at=CREATED + timedelta(minutes=1),
    ).candidate


def test_binding_is_deterministic_and_matches_its_identity(repository_root: Path) -> None:
    evidence_assembly = assembly(repository_root)
    first = create_candidate_evidence_binding(candidate(), evidence_assembly, bound_at=BOUND_AT)
    second = create_candidate_evidence_binding(candidate(), evidence_assembly, bound_at=BOUND_AT)

    assert first == second
    assert first.candidate.status is CandidateStatus.COLLECTING
    assert first.candidate_fingerprint == sha256_fingerprint(
        first.candidate.model_dump(mode="json")
    )
    assert first.assembly_fingerprint == sha256_fingerprint(first.assembly.model_dump(mode="json"))
    assert first.binding_id == sha256_fingerprint(
        binding_identity(
            first.bound_at,
            first.candidate,
            first.candidate_fingerprint,
            first.assembly,
            first.assembly_fingerprint,
        )
    )
    golden = json.loads(
        (repository_root / "tests/golden/candidate_evidence_binding.json").read_text(
            encoding="utf-8"
        )
    )
    assert first.model_dump(mode="json") == golden


def test_binding_rejects_wrong_candidate_commit_and_time(repository_root: Path) -> None:
    evidence_assembly = assembly(repository_root)
    with pytest.raises(ValidationError, match="assembly commit does not match"):
        create_candidate_evidence_binding(candidate("b" * 40), evidence_assembly, bound_at=BOUND_AT)
    with pytest.raises(ValidationError, match="cannot precede assembly generation"):
        create_candidate_evidence_binding(
            candidate(), evidence_assembly, bound_at=CREATED + timedelta(minutes=2)
        )
    with pytest.raises(ValueError, match="UTC offset"):
        create_candidate_evidence_binding(
            candidate(), evidence_assembly, bound_at=datetime(2026, 8, 30, 20, 31)
        )


def test_binding_requires_collecting_revision_one_candidate(repository_root: Path) -> None:
    evidence_assembly = assembly(repository_root)
    collecting = candidate()
    ready = transition_candidate(
        collecting,
        CandidateStatus.READY,
        occurred_at=BOUND_AT,
    ).candidate
    with pytest.raises(ValidationError, match="revision-one COLLECTING"):
        create_candidate_evidence_binding(ready, evidence_assembly, bound_at=BOUND_AT)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("candidate_fingerprint", "sha256:" + "0" * 64, "candidate_fingerprint"),
        ("assembly_fingerprint", "sha256:" + "0" * 64, "assembly_fingerprint"),
        ("binding_id", "sha256:" + "0" * 64, "binding_id"),
    ],
)
def test_binding_detects_content_fingerprint_tampering(
    repository_root: Path, field: str, value: str, match: str
) -> None:
    valid = create_candidate_evidence_binding(
        candidate(), assembly(repository_root), bound_at=BOUND_AT
    )
    payload = valid.model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValidationError, match=match):
        CandidateEvidenceBinding.model_validate(payload)


def test_binding_model_rejects_naive_or_regressed_timestamp(repository_root: Path) -> None:
    valid = create_candidate_evidence_binding(
        candidate(), assembly(repository_root), bound_at=BOUND_AT
    )
    payload = valid.model_dump(mode="json")
    naive = deepcopy(payload)
    naive["bound_at"] = "2026-08-30T20:31:00"
    with pytest.raises(ValidationError, match="UTC offset"):
        CandidateEvidenceBinding.model_validate(naive)

    regressed = json.loads(json.dumps(payload))
    regressed["bound_at"] = "2026-08-30T12:00:00Z"
    with pytest.raises(ValidationError, match="candidate timestamp"):
        CandidateEvidenceBinding.model_validate(regressed)
