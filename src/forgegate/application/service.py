from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forgegate.application.models import CandidateCreateCommand, CandidateHistoryView
from forgegate.attestations import ReleaseAttestation
from forgegate.candidates import (
    CandidateEvidenceBinding,
    ReleaseCandidate,
    SQLiteCandidateRepository,
    create_candidate,
)


@dataclass(frozen=True)
class CandidateApplication:
    repository: SQLiteCandidateRepository

    @classmethod
    def for_database(cls, database: Path) -> CandidateApplication:
        return cls(SQLiteCandidateRepository(database))

    def initialize(self) -> None:
        self.repository.initialize()

    @staticmethod
    def preview_candidate(command: CandidateCreateCommand) -> ReleaseCandidate:
        return create_candidate(
            project_id=command.project_id,
            version=command.version,
            commit_sha=command.commit_sha,
            source_branch=command.source_branch,
            release_track=command.release_track,
            created_at=command.created_at,
        )

    def create_candidate(
        self,
        command: CandidateCreateCommand,
        *,
        idempotency_key: str,
    ) -> ReleaseCandidate:
        candidate = self.preview_candidate(command)
        return self.repository.create(candidate, idempotency_key=idempotency_key)

    def get_candidate(self, candidate_id: str) -> ReleaseCandidate:
        return self.repository.get(candidate_id)

    def get_history(self, candidate_id: str) -> CandidateHistoryView:
        return CandidateHistoryView.from_history(self.repository.history(candidate_id))

    def get_evidence(self, candidate_id: str) -> CandidateEvidenceBinding:
        return self.repository.get_evidence_binding(candidate_id)

    def get_attestation(self, candidate_id: str) -> ReleaseAttestation:
        return self.repository.get_attestation(candidate_id)


__all__ = ["CandidateApplication"]
