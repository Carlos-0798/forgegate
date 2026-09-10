"""Small, path-free first-use receipt models; no workspace I/O or application imports."""

from typing import Literal

from pydantic import Field

from forgegate.domain.models import SLUG_PATTERN, StrictModel


class WorkspaceDemoCase(StrictModel):
    candidate_id: str = Field(pattern=r"^cand-[0-9a-f]{24}$")
    version: Literal["synthetic-demo-pass", "synthetic-demo-fail"]
    decision: Literal["PASS", "FAIL"]
    evidence_origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    verification_level: Literal["declared"] = "declared"


class WorkspaceInitializationReport(StrictModel):
    """Path-free setup receipt. Private key material is deliberately absent."""

    schema_version: Literal["forgegate.workspace-initialization.v1"] = (
        "forgegate.workspace-initialization.v1"
    )
    status: Literal["INITIALIZED"] = "INITIALIZED"
    project_id: str = Field(pattern=SLUG_PATTERN)
    operator_identity_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    demo_cases: tuple[WorkspaceDemoCase, ...] = Field(default=(), max_length=2)
    instructions: Literal["START_HERE.md"] = "START_HERE.md"
    private_key: Literal["operator-key.pem"] = "operator-key.pem"
    service: Literal["NOT_STARTED"] = "NOT_STARTED"
    browser_session: Literal["NOT_ACTIVATED"] = "NOT_ACTIVATED"
    hardware_access: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
