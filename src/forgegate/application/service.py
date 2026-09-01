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
    ProjectProfileQuery,
    ProjectQuery,
    ProjectRegisterCommand,
    ProjectReviseCommand,
)
from forgegate.artifacts import ArtifactRegistry
from forgegate.assurance import AssuranceBundle, create_assurance_bundle
from forgegate.attestations import ReleaseAttestation
from forgegate.audit import AuditActor, AuditEventPage
from forgegate.candidates import (
    CandidateDocument,
    CandidateEvidenceBinding,
    CandidateLifecycleError,
    ProfileBoundReleaseCandidate,
    ReleaseCandidate,
    ReleaseCandidatePage,
    SQLiteCandidateRepository,
    create_candidate,
)
from forgegate.candidates.models import CandidateTransitionResult
from forgegate.domain.enums import CandidateStatus, Decision
from forgegate.domain.models import canonical_release_track_name
from forgegate.policy import (
    PolicyEvaluationDocument,
    PolicyMaterial,
    create_policy_material,
    evaluate_policy,
    evaluate_policy_material,
)
from forgegate.policy.materials import MAX_POLICY_BYTES, policy_media_type
from forgegate.projects import (
    ProjectProfileDocument,
    ProjectProfilePage,
    ProjectProfileRevision,
    RegisteredProject,
    RegisteredProjectPage,
    profile_id,
)

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
        actor: AuditActor | None = None,
    ) -> RegisteredProject:
        return self.repository.register_project(
            command.config,
            registered_at=command.registered_at,
            idempotency_key=idempotency_key,
            actor=actor,
        )

    def get_project(self, project_id: str) -> RegisteredProject:
        return self.repository.get_project(project_id)

    def revise_project(
        self,
        project_id: str,
        command: ProjectReviseCommand,
        *,
        idempotency_key: str,
        actor: AuditActor | None = None,
    ) -> ProjectProfileRevision:
        return self.repository.revise_project(
            project_id,
            command.config,
            expected_profile_version=command.expected_profile_version,
            effective_at=command.effective_at,
            idempotency_key=idempotency_key,
            actor=actor,
        )

    def get_current_project_profile(self, project_id: str) -> ProjectProfileDocument:
        return self.repository.get_current_project_profile(project_id)

    def list_project_profiles(self, query: ProjectProfileQuery) -> ProjectProfilePage:
        return self.repository.project_profiles(
            query.project_id,
            after_profile_version=query.after_profile_version,
            limit=query.limit,
        )

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
        actor: AuditActor | None = None,
    ) -> CandidateDocument:
        candidate = self.preview_candidate(command)
        return self.repository.create_for_registered_project(
            candidate,
            idempotency_key=idempotency_key,
            actor=actor,
        )

    def get_candidate(self, candidate_id: str) -> CandidateDocument:
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
        evaluation: PolicyEvaluationDocument | None = None,
        actor: AuditActor | None = None,
    ) -> CandidateTransitionResult:
        return self.repository.advance(
            candidate_id,
            command.to_status,
            expected_revision=command.expected_revision,
            occurred_at=command.occurred_at,
            idempotency_key=idempotency_key,
            reason=command.reason,
            evaluation=evaluation,
            actor=actor,
        )

    def bind_evidence(
        self,
        candidate_id: str,
        command: CandidateBindEvidenceCommand,
        *,
        idempotency_key: str,
        actor: AuditActor | None = None,
    ) -> CandidateEvidenceBinding:
        return self.repository.bind_evidence(
            candidate_id,
            command.assembly,
            bound_at=command.bound_at,
            idempotency_key=idempotency_key,
            actor=actor,
        )

    def evaluate_candidate(
        self,
        candidate_id: str,
        command: CandidateEvaluateCommand,
        *,
        idempotency_key: str,
        actor: AuditActor | None = None,
    ) -> CandidateEvaluationResult:
        binding = self.repository.get_evidence_binding(candidate_id)
        try:
            evaluation: PolicyEvaluationDocument
            if command.policy_material is not None:
                evaluation = evaluate_policy_material(
                    command.policy_material,
                    binding.assembly.bundle,
                    evaluated_at=command.evaluated_at,
                )
            else:
                assert command.policy is not None
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
            policy_material=command.policy_material,
            actor=actor,
        )
        return CandidateEvaluationResult(
            evaluation=evaluation,
            transition=transition,
            policy_material=command.policy_material,
        )

    def materialize_policy(self, candidate_id: str, project_root: Path) -> PolicyMaterial:
        """Read only the policy path authorized by the candidate's frozen profile."""
        candidate = self.repository.get(candidate_id)
        if not isinstance(candidate, ProfileBoundReleaseCandidate):
            raise CandidateLifecycleError(
                "CANDIDATE_POLICY_PROFILE_REQUIRED",
                "legacy candidate has no frozen project profile for policy materialization",
            )
        profile = self.repository.get_project_profile(
            candidate.project_id,
            candidate.project_profile_version,
        )
        if profile_id(profile) != candidate.project_profile_id:
            raise CandidateLifecycleError(
                "CANDIDATE_POLICY_PROFILE_MISMATCH",
                "candidate profile identity does not match the durable profile",
            )
        matches = [
            (name, track)
            for name, track in profile.config.release_tracks.items()
            if canonical_release_track_name(name) == candidate.release_track
        ]
        if len(matches) != 1:
            raise CandidateLifecycleError(
                "CANDIDATE_POLICY_AUTHORITY_INVALID",
                "candidate release track does not resolve to exactly one profile policy",
            )
        _, track = matches[0]
        registered = ArtifactRegistry(project_root, max_bytes=MAX_POLICY_BYTES).register(
            track.policy,
            media_type=policy_media_type(track.policy),
        )
        try:
            return create_policy_material(
                project_id=candidate.project_id,
                project_profile_id=candidate.project_profile_id,
                project_profile_version=candidate.project_profile_version,
                release_track=candidate.release_track,
                artifact=registered.reference,
                content=registered.content,
            )
        except ValueError as exc:
            raise CandidateLifecycleError(
                "CANDIDATE_POLICY_MATERIAL_INVALID",
                str(exc),
            ) from exc

    def attest_candidate(
        self,
        candidate_id: str,
        command: CandidateAttestCommand,
        *,
        actor: AuditActor | None = None,
    ) -> ReleaseAttestation:
        return self.repository.attest(
            candidate_id,
            issued_at=command.issued_at,
            generator_version=__version__,
            actor=actor,
        )

    def get_history(self, candidate_id: str) -> CandidateHistoryView:
        return CandidateHistoryView.from_history(self.repository.history(candidate_id))

    def get_evidence(self, candidate_id: str) -> CandidateEvidenceBinding:
        return self.repository.get_evidence_binding(candidate_id)

    def get_policy_material(self, candidate_id: str) -> PolicyMaterial:
        return self.repository.get_policy_material(candidate_id)

    def get_attestation(self, candidate_id: str) -> ReleaseAttestation:
        return self.repository.get_attestation(candidate_id)

    def get_assurance_bundle(self, candidate_id: str) -> AssuranceBundle:
        candidate = self.repository.get(candidate_id)
        if not isinstance(candidate, ProfileBoundReleaseCandidate):
            raise CandidateLifecycleError(
                "CANDIDATE_ASSURANCE_PROFILE_REQUIRED",
                "portable assurance requires a profile-bound candidate",
            )
        try:
            return create_assurance_bundle(
                project_profile=self.repository.get_project_profile(
                    candidate.project_id,
                    candidate.project_profile_version,
                ),
                evidence_binding=self.repository.get_evidence_binding(candidate_id),
                policy_material=self.repository.get_policy_material(candidate_id),
                attestation=self.repository.get_attestation(candidate_id),
            )
        except ValueError as exc:
            raise CandidateLifecycleError(
                "CANDIDATE_ASSURANCE_INVALID",
                str(exc),
            ) from exc


__all__ = ["DECISION_STATUS", "CandidateApplication"]
