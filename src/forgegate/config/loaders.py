from pathlib import Path

import yaml
from pydantic import ValidationError

from forgegate.assembly import EvidenceBundleAssembly
from forgegate.assurance import AssuranceBundle, AssuranceBundleManifest
from forgegate.attestations import ReleaseAttestation
from forgegate.candidates import CandidateEvidenceBinding
from forgegate.candidates.models import (
    CandidateTransition,
    CandidateTransitionResult,
    ProfileBoundReleaseCandidate,
    ReleaseCandidate,
)
from forgegate.domain.models import EvidenceBundle, PolicyConfig, ProjectConfig
from forgegate.github_actions import GitHubActionReport
from forgegate.identity import AssuranceSignature, SigningIdentity, TrustStore
from forgegate.plugins import PluginDiscoveryReport, PluginManifest
from forgegate.policy import PolicyMaterial
from forgegate.policy.models import PolicyEvaluation, ProfileAuthorizedPolicyEvaluation
from forgegate.projects import ProjectProfileRevision

# A policy-material envelope can contain one 1 MiB policy twice: exact base64
# bytes plus its strict parsed document. Match the local REST request boundary.
MAX_CONFIG_BYTES = 4 * 1024 * 1024
type SupportedConfig = (
    ProjectConfig
    | PolicyConfig
    | EvidenceBundle
    | EvidenceBundleAssembly
    | PolicyEvaluation
    | ProfileAuthorizedPolicyEvaluation
    | PolicyMaterial
    | ReleaseCandidate
    | ProfileBoundReleaseCandidate
    | CandidateTransition
    | CandidateTransitionResult
    | CandidateEvidenceBinding
    | ReleaseAttestation
    | ProjectProfileRevision
    | AssuranceBundle
    | AssuranceBundleManifest
    | AssuranceSignature
    | SigningIdentity
    | TrustStore
    | GitHubActionReport
    | PluginManifest
    | PluginDiscoveryReport
)

SCHEMA_MODELS: dict[str, type[SupportedConfig]] = {
    "forgegate.project.v1": ProjectConfig,
    "forgegate.policy.v1": PolicyConfig,
    "forgegate.evidence-bundle.v1": EvidenceBundle,
    "forgegate.evidence-bundle-assembly.v1": EvidenceBundleAssembly,
    "forgegate.policy-evaluation.v1": PolicyEvaluation,
    "forgegate.policy-evaluation.v2": ProfileAuthorizedPolicyEvaluation,
    "forgegate.policy-material.v1": PolicyMaterial,
    "forgegate.release-candidate.v1": ReleaseCandidate,
    "forgegate.release-candidate.v2": ProfileBoundReleaseCandidate,
    "forgegate.candidate-transition.v1": CandidateTransition,
    "forgegate.candidate-transition-result.v1": CandidateTransitionResult,
    "forgegate.candidate-evidence-binding.v1": CandidateEvidenceBinding,
    "forgegate.release-attestation.v1": ReleaseAttestation,
    "forgegate.project-profile-revision.v1": ProjectProfileRevision,
    "forgegate.assurance-bundle.v1": AssuranceBundle,
    "forgegate.assurance-bundle-manifest.v1": AssuranceBundleManifest,
    "forgegate.assurance-signature.v1": AssuranceSignature,
    "forgegate.signing-identity.v1": SigningIdentity,
    "forgegate.trust-store.v1": TrustStore,
    "forgegate.github-action-report.v1": GitHubActionReport,
    "forgegate.plugin-manifest.v1": PluginManifest,
    "forgegate.plugin-discovery.v1": PluginDiscoveryReport,
}


class ConfigLoadError(ValueError):
    """A safe, user-facing configuration loading failure."""


def load_config(path: Path) -> SupportedConfig:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ConfigLoadError(f"cannot access configuration: {exc}") from exc
    if size > MAX_CONFIG_BYTES:
        raise ConfigLoadError(f"configuration exceeds {MAX_CONFIG_BYTES} byte limit")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigLoadError(f"cannot parse configuration: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigLoadError("configuration root must be a mapping")
    schema_version = raw.get("schema_version")
    if not isinstance(schema_version, str):
        raise ConfigLoadError("schema_version is required and must be a string")
    model = SCHEMA_MODELS.get(schema_version)
    if model is None:
        raise ConfigLoadError(f"unsupported schema_version: {schema_version}")
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ConfigLoadError(str(exc)) from exc
