import os
import stat
from pathlib import Path

import yaml
from pydantic import ValidationError

from forgegate.assembly import EvidenceBundleAssembly
from forgegate.assurance import AssuranceBundle, AssuranceBundleManifest
from forgegate.attestations import ReleaseAttestation
from forgegate.bootstrap import InitializationReport
from forgegate.bounded_parsing import StructureLimitError, enforce_yaml_structure_limits
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
from forgegate.plugins import (
    PluginDiscoveryReport,
    PluginManifest,
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
from forgegate.projects import ProjectProfileRevision
from forgegate.workspace_init_models import WorkspaceInitializationReport

# A policy-material envelope can contain one 1 MiB policy twice: exact base64
# bytes plus its strict parsed document. Match the local REST request boundary.
MAX_CONFIG_BYTES = 4 * 1024 * 1024
MAX_CONFIG_NODES = 250_000
MAX_CONFIG_DEPTH = 64
type SupportedConfig = (
    ProjectConfig
    | WorkspaceInitializationReport
    | InitializationReport
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
    | PluginRunPlan
    | PluginRunRecord
    | PluginRunPage
    | PluginRunReceipt
    | PluginProtocolMessage
    | PluginRunTransition
    | PluginRunResult
    | WindowsSandboxCapabilityReport
)

SCHEMA_MODELS: dict[str, type[SupportedConfig]] = {
    "forgegate.workspace-initialization.v1": WorkspaceInitializationReport,
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
    "forgegate.plugin-run-plan.v1": PluginRunPlan,
    "forgegate.plugin-run-record.v1": PluginRunRecord,
    "forgegate.plugin-run-page.v1": PluginRunPage,
    "forgegate.plugin-run-receipt.v1": PluginRunReceipt,
    "forgegate.plugin-protocol-message.v1": PluginProtocolMessage,
    "forgegate.plugin-run-transition.v1": PluginRunTransition,
    "forgegate.plugin-run-result.v1": PluginRunResult,
    "forgegate.windows-plugin-sandbox-capability.v1": WindowsSandboxCapabilityReport,
}


class ConfigLoadError(ValueError):
    """A safe, user-facing configuration loading failure."""


def load_config(path: Path) -> SupportedConfig:
    requested = path.expanduser()
    if requested.is_symlink() or not requested.is_file():
        raise ConfigLoadError("cannot access configuration: path must be a regular file")
    descriptor: int | None = None
    try:
        descriptor = os.open(requested, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ConfigLoadError("cannot access configuration: path must be a regular file")
            if before.st_size > MAX_CONFIG_BYTES:
                raise ConfigLoadError(f"configuration exceeds {MAX_CONFIG_BYTES} byte limit")
            payload = handle.read(MAX_CONFIG_BYTES + 1)
            after = os.fstat(handle.fileno())
    except ConfigLoadError:
        raise
    except OSError as exc:
        raise ConfigLoadError(f"cannot access configuration: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(payload) > MAX_CONFIG_BYTES:
        raise ConfigLoadError(f"configuration exceeds {MAX_CONFIG_BYTES} byte limit")
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(payload) != before.st_size
    ):
        raise ConfigLoadError("configuration changed while being read")

    try:
        text = payload.decode("utf-8", errors="strict")
        enforce_yaml_structure_limits(
            text,
            max_nodes=MAX_CONFIG_NODES,
            max_depth=MAX_CONFIG_DEPTH,
        )
        raw = yaml.load(text, Loader=_UniqueKeySafeLoader)
    except StructureLimitError as exc:
        raise ConfigLoadError(str(exc)) from exc
    except (UnicodeError, yaml.YAMLError, RecursionError) as exc:
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


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key: {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)
