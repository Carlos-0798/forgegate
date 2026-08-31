from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forgegate import __version__
from forgegate.application.models import (
    AuditEventQuery,
    CandidateAdvanceCommand,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    CandidateEvaluateCommand,
    CandidateEvaluationResult,
    CandidateHistoryView,
    CandidateQuery,
    ProjectQuery,
    ProjectRegisterCommand,
)
from forgegate.attestations import ReleaseAttestation
from forgegate.audit import AuditEventPage
from forgegate.candidates import (
    CandidateEvidenceBinding,
    CandidateLifecycleError,
    ReleaseCandidate,
    ReleaseCandidatePage,
    SQLiteCandidateRepository,
    create_candidate,
)
from forgegate.candidates.models import CandidateTransitionResult
from forgegate.domain.enums import CandidateStatus, Decision
from forgegate.policy import PolicyEvaluation, evaluate_policy
from forgegate.projects import RegisteredProject, RegisteredProjectPage

DECISION_STATUS = {
    Decision.PASS: CandidateStatus.PASS,
    Decision.FAIL: CandidateStatus.FAIL,
    Decision.REVIEW: CandidateStatus.REVIEW,
    Decision.ERROR: CandidateStatus.ERROR,
}


@dataclass(frozen=True)
class CandidateApplication:
    repository: SQLiteCandidateRepository

    @classmethod
    def for_database(cls, database: Path) -> CandidateApplication:
        return cls(SQLiteCandidateRepository(database))

    def initialize(self) -> None:
        self.repository.initialize()

    def register_project(
        self,
        command: ProjectRegisterCommand,
        *,
        idempotency_key: str,
    ) -> RegisteredProject:
        return self.repository.register_project(
            command.config,
            registered_at=command.registered_at,
            idempotency_key=idempotency_key,
        )

    def get_project(self, project_id: str) -> RegisteredProject:
        return self.repository.get_project(project_id)

    def list_projects(self, query: ProjectQuery) -> RegisteredProjectPage:
        return self.repository.projects(
            after_project_id=query.after_project_id,
            limit=query.limit,
        )

    def query_audit_events(self, query: AuditEventQuery) -> AuditEventPage:
        return self.repository.audit_events(
            after_sequence=query.after_sequence,
            limit=query.limit,
            project_id=query.project_id,
            candidate_id=query.candidate_id,
        )

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
        return self.repository.create_for_registered_project(
            candidate,
            idempotency_key=idempotency_key,
        )

    def get_candidate(self, candidate_id: str) -> ReleaseCandidate:
        return self.repository.get(candidate_id)

    def list_candidates(self, query: CandidateQuery) -> ReleaseCandidatePage:
        return self.repository.candidates(
            query.project_id,
            after_candidate_id=query.after_candidate_id,
            limit=query.limit,
        )

    def advance_candidate(
        self,
        candidate_id: str,
        command: CandidateAdvanceCommand,
        *,
        idempotency_key: str,
        evaluation: PolicyEvaluation | None = None,
    ) -> CandidateTransitionResult:
        return self.repository.advance(
            candidate_id,
            command.to_status,
            expected_revision=command.expected_revision,
            occurred_at=command.occurred_at,
            idempotency_key=idempotency_key,
            reason=command.reason,
            evaluation=evaluation,
        )

    def bind_evidence(
        self,
        candidate_id: str,
        command: CandidateBindEvidenceCommand,
        *,
        idempotency_key: str,
    ) -> CandidateEvidenceBinding:
        return self.repository.bind_evidence(
            candidate_id,
            command.assembly,
            bound_at=command.bound_at,
            idempotency_key=idempotency_key,
        )

    def evaluate_candidate(
        self,
        candidate_id: str,
        command: CandidateEvaluateCommand,
        *,
        idempotency_key: str,
    ) -> CandidateEvaluationResult:
        binding = self.repository.get_evidence_binding(candidate_id)
        try:
            evaluation = evaluate_policy(
                command.policy,
                binding.assembly.bundle,
                evaluated_at=command.evaluated_at,
            )
        except ValueError as exc:
            raise CandidateLifecycleError(
                "CANDIDATE_POLICY_EVALUATION_INVALID",
                str(exc),
            ) from exc
        transition = self.repository.advance(
            candidate_id,
            DECISION_STATUS[evaluation.decision],
            expected_revision=command.expected_revision,
            occurred_at=command.evaluated_at,
            idempotency_key=idempotency_key,
            reason=command.reason,
            evaluation=evaluation,
        )
        return CandidateEvaluationResult(evaluation=evaluation, transition=transition)

    def attest_candidate(
        self,
        candidate_id: str,
        command: CandidateAttestCommand,
    ) -> ReleaseAttestation:
        return self.repository.attest(
            candidate_id,
            issued_at=command.issued_at,
            generator_version=__version__,
        )

    def get_history(self, candidate_id: str) -> CandidateHistoryView:
        return CandidateHistoryView.from_history(self.repository.history(candidate_id))

    def get_evidence(self, candidate_id: str) -> CandidateEvidenceBinding:
        return self.repository.get_evidence_binding(candidate_id)

    def get_attestation(self, candidate_id: str) -> ReleaseAttestation:
        return self.repository.get_attestation(candidate_id)


__all__ = ["DECISION_STATUS", "CandidateApplication"]
