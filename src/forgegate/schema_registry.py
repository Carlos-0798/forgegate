from pydantic import BaseModel

from forgegate.assembly import EvidenceBundleAssembly
from forgegate.assurance import AssuranceBundle, AssuranceBundleManifest
from forgegate.attestations import ReleaseAttestation
from forgegate.audit import AuditActor, AuditEvent, AuditEventPage
from forgegate.bootstrap import InitializationReport
from forgegate.candidates import CandidateEvidenceBinding
from forgegate.candidates.models import (
    CandidateTransition,
    CandidateTransitionResult,
    ProfileBoundReleaseCandidate,
    ReleaseCandidate,
    ReleaseCandidatePage,
)
from forgegate.collection_jobs import (
    CollectionJobRecord,
    CollectionJobRequest,
    CollectionJobResult,
    LegacyCollectionJobRecord,
)
from forgegate.collectors.analog_validation import AFE_RESULT_JSON_SCHEMA
from forgegate.collectors.benchmark import BENCHMARK_JSON_SCHEMA
from forgegate.collectors.msp430_validation import MSP430_REPORT_JSON_SCHEMA
from forgegate.domain.models import EvidenceBundle, PolicyConfig, ProjectConfig
from forgegate.github_actions import GitHubActionReport
from forgegate.identity import AssuranceSignature, SigningIdentity, TrustStore
from forgegate.plugins import (
    PluginDiscoveryReport,
    PluginManifest,
    PluginOutputDocument,
    PluginProtocolMessage,
    PluginRunPage,
    PluginRunPlan,
    PluginRunReceipt,
    PluginRunRecord,
    PluginRunResult,
    PluginRunTransition,
    WindowsSandboxCapabilityReport,
)
from forgegate.policy import PolicyMaterial
from forgegate.policy.models import PolicyEvaluation, ProfileAuthorizedPolicyEvaluation
from forgegate.projects import (
    ProjectProfilePage,
    ProjectProfileRevision,
    RegisteredProject,
    RegisteredProjectPage,
)
from forgegate.security_events import ApiSecurityEvent, ApiSecurityEventPage
from forgegate.workspace_backups import WorkspaceBackupManifest

SCHEMAS: dict[str, type[BaseModel]] = {
    "forgegate.workspace-backup.v1": WorkspaceBackupManifest,
    "forgegate.collection-job-request.v1": CollectionJobRequest,
    "forgegate.collection-job.v1": LegacyCollectionJobRecord,
    "forgegate.collection-job.v2": CollectionJobRecord,
    "forgegate.collection-job-result.v1": CollectionJobResult,
    "forgegate.assurance-bundle.v1": AssuranceBundle,
    "forgegate.assurance-bundle-manifest.v1": AssuranceBundleManifest,
    "forgegate.assurance-signature.v1": AssuranceSignature,
    "forgegate.signing-identity.v1": SigningIdentity,
    "forgegate.trust-store.v1": TrustStore,
    "forgegate.project.v1": ProjectConfig,
    "forgegate.initialization-report.v1": InitializationReport,
    "forgegate.policy.v1": PolicyConfig,
    "forgegate.evidence-bundle.v1": EvidenceBundle,
    "forgegate.evidence-bundle-assembly.v1": EvidenceBundleAssembly,
    "forgegate.policy-evaluation.v1": PolicyEvaluation,
    "forgegate.policy-evaluation.v2": ProfileAuthorizedPolicyEvaluation,
    "forgegate.policy-material.v1": PolicyMaterial,
    "forgegate.release-candidate.v1": ReleaseCandidate,
    "forgegate.release-candidate.v2": ProfileBoundReleaseCandidate,
    "forgegate.release-candidate-page.v1": ReleaseCandidatePage,
    "forgegate.candidate-transition.v1": CandidateTransition,
    "forgegate.candidate-transition-result.v1": CandidateTransitionResult,
    "forgegate.candidate-evidence-binding.v1": CandidateEvidenceBinding,
    "forgegate.release-attestation.v1": ReleaseAttestation,
    "forgegate.registered-project.v1": RegisteredProject,
    "forgegate.registered-project-page.v1": RegisteredProjectPage,
    "forgegate.project-profile-revision.v1": ProjectProfileRevision,
    "forgegate.project-profile-page.v1": ProjectProfilePage,
    "forgegate.audit-event.v1": AuditEvent,
    "forgegate.audit-event-page.v1": AuditEventPage,
    "forgegate.audit-actor.v1": AuditActor,
    "forgegate.api-security-event.v1": ApiSecurityEvent,
    "forgegate.api-security-event-page.v1": ApiSecurityEventPage,
    "forgegate.github-action-report.v1": GitHubActionReport,
    "forgegate.plugin-manifest.v1": PluginManifest,
    "forgegate.plugin-discovery.v1": PluginDiscoveryReport,
    "forgegate.plugin-run-plan.v1": PluginRunPlan,
    "forgegate.plugin-run-record.v1": PluginRunRecord,
    "forgegate.plugin-run-page.v1": PluginRunPage,
    "forgegate.plugin-output.v1": PluginOutputDocument,
    "forgegate.plugin-protocol-message.v1": PluginProtocolMessage,
    "forgegate.plugin-run-transition.v1": PluginRunTransition,
    "forgegate.plugin-run-result.v1": PluginRunResult,
    "forgegate.plugin-run-receipt.v1": PluginRunReceipt,
    "forgegate.windows-plugin-sandbox-capability.v1": WindowsSandboxCapabilityReport,
}

ARTIFACT_SCHEMAS: dict[str, dict[str, object]] = {
    "analog-validation.result-export.v1": AFE_RESULT_JSON_SCHEMA,
    "forgegate.benchmark.v1": BENCHMARK_JSON_SCHEMA,
    "forgegate.msp430-validation-report.v1": MSP430_REPORT_JSON_SCHEMA,
}


def schema_filename(schema_version: str) -> str:
    return f"{schema_version}.schema.json"
