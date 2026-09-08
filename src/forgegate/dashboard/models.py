from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import ConfigDict, Field

from forgegate.api.auth import ApiPrincipal
from forgegate.attestations import ReleaseAttestation
from forgegate.candidates import CandidateDocument, CandidateEvidenceBinding
from forgegate.candidates.models import CandidateTransition
from forgegate.domain.models import SLUG_PATTERN, StrictModel
from forgegate.policy import PolicyEvaluationDocument, PolicyMaterial

MAX_DASHBOARD_RECOVERY_REPORT_BYTES = 256 * 1024
MAX_DASHBOARD_RECOVERY_RECEIPT_BYTES = 1024 * 1024


class DashboardPrincipal(StrictModel):
    session_id: str = Field(pattern=r"^sess-[0-9a-f]{32}$")
    identity_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    display_name: str = Field(min_length=1, max_length=120)
    role: Literal["operator", "producer"]
    project_ids: tuple[str, ...] = Field(min_length=1, max_length=100)
    trust_store_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authenticated_at: datetime
    expires_at: datetime

    @classmethod
    def from_api(cls, principal: ApiPrincipal) -> Self:
        return cls(
            session_id=principal.session_id,
            identity_id=principal.identity.identity_id,
            display_name=principal.identity.display_name,
            role=principal.role.value,
            project_ids=principal.project_ids,
            trust_store_id=principal.trust_store_id,
            authenticated_at=principal.authenticated_at,
            expires_at=principal.expires_at,
        )


class DashboardActivationStart(StrictModel):
    schema_version: Literal["forgegate.dashboard-activation-start.v1"] = (
        "forgegate.dashboard-activation-start.v1"
    )
    activation_code: str = Field(pattern=r"^FG-[A-Z2-7]{5}-[A-Z2-7]{5}$")
    expires_at: datetime
    poll_after_seconds: int = Field(default=1, ge=1, le=5)


class DashboardActivationStatus(StrictModel):
    schema_version: Literal["forgegate.dashboard-activation-status.v1"] = (
        "forgegate.dashboard-activation-status.v1"
    )
    status: Literal["PENDING", "CHALLENGE_ISSUED", "AUTHENTICATED"]
    expires_at: datetime
    principal: DashboardPrincipal | None = None
    csrf_token: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")


class DashboardActivationCompleted(StrictModel):
    schema_version: Literal["forgegate.dashboard-activation-completed.v1"] = (
        "forgegate.dashboard-activation-completed.v1"
    )
    status: Literal["AUTHENTICATED"] = "AUTHENTICATED"
    principal: DashboardPrincipal
    browser_delivery: Literal["PENDING_BROWSER_POLL"] = "PENDING_BROWSER_POLL"


class DashboardSessionResponse(StrictModel):
    schema_version: Literal["forgegate.dashboard-session.v1"] = "forgegate.dashboard-session.v1"
    status: Literal["AUTHENTICATED"] = "AUTHENTICATED"
    principal: DashboardPrincipal
    csrf_token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class DashboardOverview(StrictModel):
    schema_version: Literal["forgegate.dashboard-overview.v1"] = "forgegate.dashboard-overview.v1"
    forgegate_version: str
    api_version: Literal["v1"] = "v1"
    database_schema_version: int = Field(ge=1)
    deployment: Literal["loopback-local"] = "loopback-local"
    hardware_access: Literal["NOT_PERFORMED", "READ_ONLY_TELEMETRY"] = "NOT_PERFORMED"
    limitations: tuple[str, ...] = Field(min_length=1, max_length=20)
    principal: DashboardPrincipal


class DashboardLogoutResponse(StrictModel):
    schema_version: Literal["forgegate.dashboard-logout.v1"] = "forgegate.dashboard-logout.v1"
    status: Literal["SESSION_ENDED"] = "SESSION_ENDED"
    session_id: str = Field(pattern=r"^sess-[0-9a-f]{32}$")


class DashboardCandidateProject(StrictModel):
    project_id: str = Field(pattern=SLUG_PATTERN)


class DashboardCandidateAssuranceReview(StrictModel):
    schema_version: Literal["forgegate.dashboard-candidate-assurance-review.v1"] = (
        "forgegate.dashboard-candidate-assurance-review.v1"
    )
    candidate: CandidateDocument
    transitions: tuple[CandidateTransition, ...]
    evidence_binding_required: bool
    evidence_binding: CandidateEvidenceBinding | None
    policy_material_required: bool
    policy_material: PolicyMaterial | None
    policy_evaluation: PolicyEvaluationDocument | None
    attestation: ReleaseAttestation | None
    assurance_bundle_id: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    assurance: Literal["unsigned_local"] | None = None
    verification_scope: Literal["retained_documents_and_embedded_policy_bytes"] | None = None
    source_artifact_bytes: Literal["not_embedded"] | None = None
    limitations: tuple[str, ...] = Field(min_length=1, max_length=20)


class DashboardAssuranceExportRequest(StrictModel):
    expected_revision: int = Field(ge=0)
    expected_bundle_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class DashboardRecoveryReviewRequest(StrictModel):
    # The source hash covers the imported UTF-8 bytes. Preserve surrounding
    # whitespace so validation sees exactly what the browser hashed.
    model_config = ConfigDict(str_strip_whitespace=False)

    document: str = Field(min_length=1, max_length=MAX_DASHBOARD_RECOVERY_REPORT_BYTES)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DashboardRecoveryRehearsalReviewRequest(StrictModel):
    model_config = ConfigDict(str_strip_whitespace=False)

    document: str = Field(min_length=1, max_length=MAX_DASHBOARD_RECOVERY_RECEIPT_BYTES)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


__all__ = [
    "DashboardActivationCompleted",
    "DashboardActivationStart",
    "DashboardActivationStatus",
    "DashboardAssuranceExportRequest",
    "DashboardCandidateAssuranceReview",
    "DashboardCandidateProject",
    "DashboardLogoutResponse",
    "DashboardOverview",
    "DashboardPrincipal",
    "DashboardRecoveryRehearsalReviewRequest",
    "DashboardRecoveryReviewRequest",
    "DashboardSessionResponse",
]
