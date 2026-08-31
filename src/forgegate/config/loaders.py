from pathlib import Path

import yaml
from pydantic import ValidationError

from forgegate.candidates.models import (
    CandidateTransition,
    CandidateTransitionResult,
    ReleaseCandidate,
)
from forgegate.domain.models import EvidenceBundle, PolicyConfig, ProjectConfig
from forgegate.policy.models import PolicyEvaluation

MAX_CONFIG_BYTES = 1024 * 1024
type SupportedConfig = (
    ProjectConfig
    | PolicyConfig
    | EvidenceBundle
    | PolicyEvaluation
    | ReleaseCandidate
    | CandidateTransition
    | CandidateTransitionResult
)

SCHEMA_MODELS: dict[str, type[SupportedConfig]] = {
    "forgegate.project.v1": ProjectConfig,
    "forgegate.policy.v1": PolicyConfig,
    "forgegate.evidence-bundle.v1": EvidenceBundle,
    "forgegate.policy-evaluation.v1": PolicyEvaluation,
    "forgegate.release-candidate.v1": ReleaseCandidate,
    "forgegate.candidate-transition.v1": CandidateTransition,
    "forgegate.candidate-transition-result.v1": CandidateTransitionResult,
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
