from pydantic import BaseModel

from forgegate.assembly import EvidenceBundleAssembly
from forgegate.attestations import ReleaseAttestation
from forgegate.audit import AuditEvent, AuditEventPage
from forgegate.candidates import CandidateEvidenceBinding
from forgegate.candidates.models import (
    CandidateTransition,
    CandidateTransitionResult,
    ReleaseCandidate,
    ReleaseCandidatePage,
)
from forgegate.collectors.analog_validation import AFE_RESULT_JSON_SCHEMA
from forgegate.collectors.benchmark import BENCHMARK_JSON_SCHEMA
from forgegate.domain.models import EvidenceBundle, PolicyConfig, ProjectConfig
from forgegate.policy.models import PolicyEvaluation
from forgegate.projects import RegisteredProject, RegisteredProjectPage

SCHEMAS: dict[str, type[BaseModel]] = {
    "forgegate.project.v1": ProjectConfig,
    "forgegate.policy.v1": PolicyConfig,
    "forgegate.evidence-bundle.v1": EvidenceBundle,
    "forgegate.evidence-bundle-assembly.v1": EvidenceBundleAssembly,
    "forgegate.policy-evaluation.v1": PolicyEvaluation,
    "forgegate.release-candidate.v1": ReleaseCandidate,
    "forgegate.release-candidate-page.v1": ReleaseCandidatePage,
    "forgegate.candidate-transition.v1": CandidateTransition,
    "forgegate.candidate-transition-result.v1": CandidateTransitionResult,
    "forgegate.candidate-evidence-binding.v1": CandidateEvidenceBinding,
    "forgegate.release-attestation.v1": ReleaseAttestation,
    "forgegate.registered-project.v1": RegisteredProject,
    "forgegate.registered-project-page.v1": RegisteredProjectPage,
    "forgegate.audit-event.v1": AuditEvent,
    "forgegate.audit-event-page.v1": AuditEventPage,
}

ARTIFACT_SCHEMAS: dict[str, dict[str, object]] = {
    "analog-validation.result-export.v1": AFE_RESULT_JSON_SCHEMA,
    "forgegate.benchmark.v1": BENCHMARK_JSON_SCHEMA,
}


def schema_filename(schema_version: str) -> str:
    return f"{schema_version}.schema.json"
