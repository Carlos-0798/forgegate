from pydantic import BaseModel

from forgegate.domain.models import EvidenceBundle, PolicyConfig, ProjectConfig
from forgegate.policy.models import PolicyEvaluation

SCHEMAS: dict[str, type[BaseModel]] = {
    "forgegate.project.v1": ProjectConfig,
    "forgegate.policy.v1": PolicyConfig,
    "forgegate.evidence-bundle.v1": EvidenceBundle,
    "forgegate.policy-evaluation.v1": PolicyEvaluation,
}


def schema_filename(schema_version: str) -> str:
    return f"{schema_version}.schema.json"
