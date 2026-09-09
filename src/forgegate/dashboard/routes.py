from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, Query, Request, Response, status
from fastapi import Path as ApiPath
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import FileResponse, PlainTextResponse, RedirectResponse

from forgegate import __version__
from forgegate.api.auth import (
    ApiAuthChallenge,
    ApiAuthenticationError,
    ApiAuthenticator,
    ApiChallengeRequest,
    ApiPrincipal,
    ApiSessionCreateRequest,
)
from forgegate.application import (
    AuditEventQuery,
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    CandidateEvaluateCommand,
    CandidateEvaluationResult,
    CandidateQuery,
)
from forgegate.assurance import render_assurance_bundle_archive
from forgegate.attestations import ReleaseAttestation
from forgegate.audit import AuditEventPage
from forgegate.candidates import (
    CandidateDocument,
    CandidateEvidenceBinding,
    CandidateStoreError,
    CandidateTransitionResult,
    ReleaseCandidatePage,
)
from forgegate.candidates.models import CANDIDATE_ID_PATTERN
from forgegate.candidates.store import STORE_SCHEMA_VERSION
from forgegate.dashboard.assets import validate_dashboard_assets
from forgegate.dashboard.collection import (
    DashboardCollectionPreview,
    DashboardCollectionPreviewRequest,
    DashboardJUnitPreview,
    DashboardJUnitPreviewRequest,
    preview_collection,
    preview_junit,
)
from forgegate.dashboard.models import (
    DashboardActivationCompleted,
    DashboardActivationStart,
    DashboardActivationStatus,
    DashboardAssuranceExportRequest,
    DashboardCandidateAssuranceReview,
    DashboardLogoutResponse,
    DashboardOverview,
    DashboardPolicyChoice,
    DashboardPolicyChoices,
    DashboardPrincipal,
    DashboardRecoveryRehearsalReviewRequest,
    DashboardRecoveryReviewRequest,
    DashboardReplayExportRequest,
    DashboardSessionResponse,
)
from forgegate.dashboard.sessions import DashboardSessionManager
from forgegate.domain.models import SLUG_PATTERN
from forgegate.evidence_replay import EvidenceReplayError, render_evidence_replay
from forgegate.live_status import DisabledLiveStatusProvider, LiveStatusPage, LiveStatusProvider
from forgegate.projects import RegisteredProjectPage
from forgegate.recovery_models import RecoveryReadinessHandoff, build_recovery_handoff
from forgegate.recovery_rehearsal import RecoveryRehearsalReview, build_rehearsal_review

DASHBOARD_SESSION_COOKIE = "forgegate_dashboard"
DASHBOARD_ACTIVATION_COOKIE = "forgegate_dashboard_activation"
DASHBOARD_CSRF_HEADER = "X-ForgeGate-CSRF"
DASHBOARD_CSP = (
    "default-src 'none'; "
    "base-uri 'none'; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "img-src 'self' data:; "
    "manifest-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'"
)
ACTIVATION_CODE_PATTERN = r"^FG-[A-Z2-7]{5}-[A-Z2-7]{5}$"


def install_dashboard_routes(
    app: FastAPI,
    *,
    application: CandidateApplication,
    authenticator: ApiAuthenticator,
    session_manager: DashboardSessionManager | None = None,
    static_root: Path | None = None,
    live_status_provider: LiveStatusProvider | None = None,
    job_store_path: Path | None = None,
) -> DashboardSessionManager:
    manager = session_manager or DashboardSessionManager(authenticator)
    status_provider = live_status_provider or DisabledLiveStatusProvider()
    assets_root = static_root or Path(__file__).resolve().parent / "static"
    index_path = assets_root / "index.html"
    if not index_path.is_file():
        raise ValueError("packaged Dashboard index is missing")
    inventory = validate_dashboard_assets(assets_root)
    accepted_asset_paths = frozenset(asset.path for asset in inventory.assets)

    @app.middleware("http")
    async def dashboard_security_headers(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        if request.url.path == "/app" or request.url.path.startswith("/app/"):
            response.headers["Content-Security-Policy"] = DASHBOARD_CSP
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = (
                "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
            )
            if request.url.path.startswith("/app/api/"):
                response.headers["Cache-Control"] = "no-store"
                response.headers["Pragma"] = "no-cache"
            elif (
                request.url.path.startswith("/app/assets/")
                and response.status_code == status.HTTP_200_OK
            ):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/app", include_in_schema=False)
    def dashboard_redirect() -> RedirectResponse:
        return RedirectResponse(url="/app/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    @app.get("/app/", include_in_schema=False)
    def dashboard_index() -> FileResponse:
        return FileResponse(index_path, media_type="text/html; charset=utf-8")

    @app.get("/app/assets/{asset_name}", include_in_schema=False)
    def dashboard_asset(
        asset_name: Annotated[str, ApiPath(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")],
    ) -> Response:
        target = assets_root / "assets" / asset_name
        if f"assets/{asset_name}" not in accepted_asset_paths or not target.is_file():
            return PlainTextResponse("Not found", status_code=status.HTTP_404_NOT_FOUND)
        return FileResponse(target)

    @app.post(
        "/app/api/activations",
        response_model=DashboardActivationStart,
        status_code=status.HTTP_201_CREATED,
        operation_id="startDashboardActivation",
        include_in_schema=False,
    )
    def start_dashboard_activation(
        request: Request,
        response: Response,
    ) -> DashboardActivationStart:
        _require_same_origin(request, required=True)
        activation, browser_cookie = manager.start_activation()
        response.set_cookie(
            DASHBOARD_ACTIVATION_COOKIE,
            browser_cookie,
            max_age=max(1, int((activation.expires_at - datetime.now(UTC)).total_seconds())),
            httponly=True,
            secure=False,
            samesite="strict",
            path="/app",
        )
        return activation

    @app.post(
        "/app/api/activations/{activation_code}/challenge",
        response_model=ApiAuthChallenge,
        status_code=status.HTTP_201_CREATED,
        operation_id="issueDashboardActivationChallenge",
        include_in_schema=False,
    )
    def issue_dashboard_activation_challenge(
        request: Request,
        activation_code: Annotated[str, ApiPath(pattern=ACTIVATION_CODE_PATTERN)],
        command: ApiChallengeRequest,
    ) -> ApiAuthChallenge:
        _require_same_origin(request, required=False)
        return manager.issue_challenge(activation_code, command)

    @app.post(
        "/app/api/activations/{activation_code}/complete",
        response_model=DashboardActivationCompleted,
        status_code=status.HTTP_201_CREATED,
        operation_id="completeDashboardActivation",
        include_in_schema=False,
    )
    def complete_dashboard_activation(
        request: Request,
        activation_code: Annotated[str, ApiPath(pattern=ACTIVATION_CODE_PATTERN)],
        command: ApiSessionCreateRequest,
    ) -> DashboardActivationCompleted:
        _require_same_origin(request, required=False)
        return manager.complete_activation(activation_code, command)

    @app.get(
        "/app/api/activation",
        response_model=DashboardActivationStatus,
        operation_id="pollDashboardActivation",
        include_in_schema=False,
    )
    def poll_dashboard_activation(
        request: Request,
        response: Response,
    ) -> DashboardActivationStatus:
        _require_same_origin(request, required=False)
        result, dashboard_cookie = manager.poll_activation(
            request.cookies.get(DASHBOARD_ACTIVATION_COOKIE)
        )
        if dashboard_cookie is not None and result.principal is not None:
            response.set_cookie(
                DASHBOARD_SESSION_COOKIE,
                dashboard_cookie,
                max_age=max(
                    1,
                    int((result.principal.expires_at - datetime.now(UTC)).total_seconds()),
                ),
                httponly=True,
                secure=False,
                samesite="strict",
                path="/app",
            )
        return result

    @app.get(
        "/app/api/session",
        response_model=DashboardSessionResponse,
        operation_id="getDashboardSession",
        include_in_schema=False,
    )
    def get_dashboard_session(request: Request) -> DashboardSessionResponse:
        _require_same_origin(request, required=False)
        return manager.session_response(request.cookies.get(DASHBOARD_SESSION_COOKIE))

    @app.delete(
        "/app/api/session",
        response_model=DashboardLogoutResponse,
        operation_id="endDashboardSession",
        include_in_schema=False,
    )
    def end_dashboard_session(
        request: Request,
        response: Response,
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> DashboardLogoutResponse:
        _require_same_origin(request, required=True)
        result = manager.logout(
            request.cookies.get(DASHBOARD_SESSION_COOKIE),
            csrf_token,
        )
        response.delete_cookie(DASHBOARD_SESSION_COOKIE, path="/app")
        response.delete_cookie(DASHBOARD_ACTIVATION_COOKIE, path="/app")
        return result

    @app.get(
        "/app/api/overview",
        response_model=DashboardOverview,
        operation_id="getDashboardOverview",
        include_in_schema=False,
    )
    def dashboard_overview(request: Request) -> DashboardOverview:
        _require_same_origin(request, required=False)
        principal = _dashboard_principal(manager, request)
        return DashboardOverview(
            forgegate_version=__version__,
            database_schema_version=STORE_SCHEMA_VERSION,
            hardware_access=status_provider.hardware_access,
            principal=DashboardPrincipal.from_api(principal),
            limitations=(
                "Request success is not an engineering release decision.",
                "Artifact integrity does not establish producer authenticity.",
                (
                    "Read-only telemetry is live status only; no command, physical "
                    "measurement validation, or release evidence is produced."
                    if status_provider.hardware_access == "READ_ONLY_TELEMETRY"
                    else "No hardware access or physical measurement is performed."
                ),
                "The service is not approved for non-loopback or production deployment.",
            ),
        )

    @app.post(
        "/app/api/recovery-review",
        response_model=RecoveryReadinessHandoff,
        operation_id="reviewDashboardRecoveryReadiness",
        include_in_schema=False,
    )
    def review_dashboard_recovery_readiness(
        request: Request,
        command: DashboardRecoveryReviewRequest,
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> RecoveryReadinessHandoff:
        _require_same_origin(request, required=True)
        stored, principal = manager.session(request.cookies.get(DASHBOARD_SESSION_COOKIE))
        request.state.authenticated_principal = principal
        manager.require_csrf(stored, csrf_token)
        if principal.role.value != "operator":
            raise ApiAuthenticationError(
                "API_ROLE_FORBIDDEN",
                "operator role required for recovery report review",
                status_code=403,
            )
        try:
            return build_recovery_handoff(command.document, command.expected_sha256)
        except (ValueError, UnicodeError) as exc:
            raise CandidateStoreError(
                "DASHBOARD_RECOVERY_REPORT_INVALID",
                "recovery readiness report failed strict validation",
            ) from exc

    @app.post(
        "/app/api/recovery-rehearsal-review",
        response_model=RecoveryRehearsalReview,
        operation_id="reviewDashboardRecoveryRehearsal",
        include_in_schema=False,
    )
    def review_dashboard_recovery_rehearsal(
        request: Request,
        command: DashboardRecoveryRehearsalReviewRequest,
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> RecoveryRehearsalReview:
        _require_same_origin(request, required=True)
        stored, principal = manager.session(request.cookies.get(DASHBOARD_SESSION_COOKIE))
        request.state.authenticated_principal = principal
        manager.require_csrf(stored, csrf_token)
        if principal.role.value != "operator":
            raise ApiAuthenticationError(
                "API_ROLE_FORBIDDEN",
                "operator role required for recovery rehearsal review",
                status_code=403,
            )
        try:
            return build_rehearsal_review(command.document, command.expected_sha256)
        except (ValueError, UnicodeError) as exc:
            raise CandidateStoreError(
                "DASHBOARD_RECOVERY_REHEARSAL_INVALID",
                "recovery rehearsal receipt failed strict validation",
            ) from exc

    @app.get(
        "/app/api/live-status",
        response_model=LiveStatusPage,
        operation_id="getDashboardLiveStatus",
        include_in_schema=False,
    )
    def dashboard_live_status(request: Request) -> LiveStatusPage:
        _require_same_origin(request, required=False)
        _dashboard_principal(manager, request)
        return status_provider.snapshot()

    @app.get(
        "/app/api/projects",
        response_model=RegisteredProjectPage,
        operation_id="listDashboardProjects",
        include_in_schema=False,
    )
    def dashboard_projects(
        request: Request,
        after_project_id: str | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> RegisteredProjectPage:
        _require_same_origin(request, required=False)
        principal = _dashboard_principal(manager, request)
        authorized_ids = tuple(
            project_id
            for project_id in principal.project_ids
            if after_project_id is None or project_id > after_project_id
        )
        projects = []
        for project_id in authorized_ids:
            try:
                projects.append(application.get_project(project_id))
            except CandidateStoreError as exc:
                if exc.code != "STORE_PROJECT_NOT_FOUND":
                    raise
            if len(projects) > limit:
                break
        visible = tuple(projects[:limit])
        return RegisteredProjectPage(
            projects=visible,
            next_after_project_id=visible[-1].project_id if visible else None,
            has_more=len(projects) > limit,
        )

    @app.get(
        "/app/api/projects/{project_id}/candidates",
        response_model=ReleaseCandidatePage,
        operation_id="listDashboardCandidates",
        include_in_schema=False,
    )
    def dashboard_candidates(
        request: Request,
        project_id: str,
        after_candidate_id: str | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> ReleaseCandidatePage:
        _require_same_origin(request, required=False)
        principal = _dashboard_principal(manager, request)
        authenticator.require_project(principal, project_id)
        return application.list_candidates(
            CandidateQuery(
                project_id=project_id,
                after_candidate_id=after_candidate_id,
                limit=limit,
            )
        )

    @app.post(
        "/app/api/candidates",
        response_model=CandidateDocument,
        status_code=status.HTTP_201_CREATED,
        operation_id="createDashboardCandidate",
        include_in_schema=False,
    )
    def create_dashboard_candidate(
        request: Request,
        command: CandidateCreateCommand,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> CandidateDocument:
        _require_same_origin(request, required=True)
        stored, principal = manager.session(request.cookies.get(DASHBOARD_SESSION_COOKIE))
        request.state.authenticated_principal = principal
        manager.require_csrf(stored, csrf_token)
        authenticator.require_project(principal, command.project_id, write=True)
        return application.create_candidate(
            command,
            idempotency_key=idempotency_key,
            actor=principal.audit_actor(),
        )

    @app.post(
        "/app/api/candidates/{candidate_id}/transitions",
        response_model=CandidateTransitionResult,
        operation_id="advanceDashboardCandidate",
        include_in_schema=False,
    )
    def advance_dashboard_candidate(
        request: Request,
        candidate_id: str,
        command: CandidateAdvanceCommand,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> CandidateTransitionResult:
        principal = _dashboard_write_principal(
            manager,
            authenticator,
            application,
            request,
            candidate_id,
            csrf_token,
        )
        return application.advance_candidate(
            candidate_id,
            command,
            idempotency_key=idempotency_key,
            actor=principal.audit_actor(),
        )

    @app.post(
        "/app/api/candidates/{candidate_id}/junit-preview",
        response_model=DashboardJUnitPreview,
        operation_id="previewDashboardCandidateJUnit",
        include_in_schema=False,
    )
    def preview_dashboard_candidate_junit(
        request: Request,
        candidate_id: Annotated[str, ApiPath(pattern=CANDIDATE_ID_PATTERN)],
        command: DashboardJUnitPreviewRequest,
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> DashboardJUnitPreview:
        validate_preview(request, candidate_id, command, csrf_token)
        return preview_junit(candidate_id, command)

    @app.post(
        "/app/api/candidates/{candidate_id}/collection-preview",
        response_model=DashboardCollectionPreview,
        operation_id="previewDashboardCandidateCollection",
        include_in_schema=False,
    )
    def preview_dashboard_candidate_collection(
        request: Request,
        candidate_id: Annotated[str, ApiPath(pattern=CANDIDATE_ID_PATTERN)],
        command: DashboardCollectionPreviewRequest,
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> DashboardCollectionPreview:
        validate_preview(request, candidate_id, command, csrf_token)
        return preview_collection(candidate_id, command)

    def validate_preview(
        request: Request,
        candidate_id: str,
        command: DashboardJUnitPreviewRequest | DashboardCollectionPreviewRequest,
        csrf_token: str | None,
    ) -> None:
        _dashboard_write_principal(
            manager, authenticator, application, request, candidate_id, csrf_token
        )
        candidate = application.get_candidate(candidate_id)
        if candidate.revision != command.expected_revision:
            raise CandidateStoreError("STORE_REVISION_CONFLICT", "reload candidate before preview")
        if candidate.status != "COLLECTING" or (
            application.get_history(candidate_id).evidence_binding is not None
        ):
            raise CandidateStoreError(
                "STORE_REVISION_CONFLICT", "preview requires an unbound COLLECTING candidate"
            )
        if candidate.commit_sha != command.reported_commit:
            raise CandidateStoreError(
                "STORE_REVISION_CONFLICT", "reported commit does not match the selected candidate"
            )

    @app.post(
        "/app/api/candidates/{candidate_id}/evidence",
        response_model=CandidateEvidenceBinding,
        operation_id="bindDashboardCandidateEvidence",
        include_in_schema=False,
    )
    def bind_dashboard_candidate_evidence(
        request: Request,
        candidate_id: str,
        command: CandidateBindEvidenceCommand,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> CandidateEvidenceBinding:
        principal = _dashboard_write_principal(
            manager,
            authenticator,
            application,
            request,
            candidate_id,
            csrf_token,
        )
        return application.bind_evidence(
            candidate_id,
            command,
            idempotency_key=idempotency_key,
            actor=principal.audit_actor(),
        )

    @app.post(
        "/app/api/candidates/{candidate_id}/evaluate",
        response_model=CandidateEvaluationResult,
        operation_id="evaluateDashboardCandidate",
        include_in_schema=False,
    )
    def evaluate_dashboard_candidate(
        request: Request,
        candidate_id: str,
        command: CandidateEvaluateCommand,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> CandidateEvaluationResult:
        principal = _dashboard_write_principal(
            manager,
            authenticator,
            application,
            request,
            candidate_id,
            csrf_token,
        )
        return application.evaluate_candidate(
            candidate_id,
            command,
            idempotency_key=idempotency_key,
            actor=principal.audit_actor(),
        )

    @app.post(
        "/app/api/candidates/{candidate_id}/attestation",
        response_model=ReleaseAttestation,
        operation_id="attestDashboardCandidate",
        include_in_schema=False,
    )
    def attest_dashboard_candidate(
        request: Request,
        candidate_id: str,
        command: CandidateAttestCommand,
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> ReleaseAttestation:
        principal = _dashboard_write_principal(
            manager,
            authenticator,
            application,
            request,
            candidate_id,
            csrf_token,
        )
        return application.attest_candidate(
            candidate_id,
            command,
            actor=principal.audit_actor(),
        )

    @app.get(
        "/app/api/candidates/{candidate_id}",
        response_model=CandidateDocument,
        operation_id="getDashboardCandidate",
        include_in_schema=False,
    )
    def get_dashboard_candidate(request: Request, candidate_id: str) -> CandidateDocument:
        _require_same_origin(request, required=False)
        principal = _dashboard_principal(manager, request)
        candidate = application.get_candidate(candidate_id)
        authenticator.require_project(principal, candidate.project_id)
        return candidate

    @app.get(
        "/app/api/candidates/{candidate_id}/policy-choices",
        response_model=DashboardPolicyChoices,
        operation_id="listDashboardCandidatePolicyChoices",
        include_in_schema=False,
    )
    def get_dashboard_policy_choices(request: Request, candidate_id: str) -> DashboardPolicyChoices:
        _require_same_origin(request, required=False)
        principal = _dashboard_principal(manager, request)
        candidate = application.get_candidate(candidate_id)
        authenticator.require_project(principal, candidate.project_id, write=True)
        materials = application.reusable_policy_materials(candidate_id)
        return DashboardPolicyChoices(
            candidate_id=candidate_id,
            choices=[DashboardPolicyChoice(material=item) for item in materials[:10]],
            truncated=len(materials) > 10,
        )

    @app.get(
        "/app/api/candidates/{candidate_id}/assurance-review",
        response_model=DashboardCandidateAssuranceReview,
        operation_id="getDashboardCandidateAssuranceReview",
        include_in_schema=False,
    )
    def get_dashboard_candidate_assurance_review(
        request: Request,
        candidate_id: str,
    ) -> DashboardCandidateAssuranceReview:
        _require_same_origin(request, required=False)
        principal = _dashboard_principal(manager, request)
        history = application.get_history(candidate_id)
        authenticator.require_project(principal, history.candidate.project_id)
        evaluation = application.get_evaluation(candidate_id)
        try:
            attestation = application.get_attestation(candidate_id)
        except CandidateStoreError as exc:
            if exc.code != "STORE_ATTESTATION_NOT_FOUND":
                raise
            attestation = None
        assurance_bundle = None
        if (
            history.evidence_binding is not None
            and history.policy_material is not None
            and attestation is not None
        ):
            assurance_bundle = application.get_assurance_bundle(candidate_id)
        return DashboardCandidateAssuranceReview(
            candidate=history.candidate,
            transitions=history.transitions,
            evidence_binding_required=history.evidence_binding_required,
            evidence_binding=history.evidence_binding,
            policy_material_required=history.policy_material_required,
            policy_material=history.policy_material,
            policy_evaluation=evaluation,
            attestation=attestation,
            assurance_bundle_id=(None if assurance_bundle is None else assurance_bundle.bundle_id),
            assurance=None if assurance_bundle is None else assurance_bundle.assurance,
            verification_scope=(
                None if assurance_bundle is None else assurance_bundle.verification_scope
            ),
            source_artifact_bytes=(
                None if assurance_bundle is None else assurance_bundle.source_artifact_bytes
            ),
            limitations=(
                "Opening this review validates stored documents; source replay export "
                "separately reparses selected reports.",
                "Artifact hashes establish retained-byte integrity, not producer authenticity.",
                (
                    "Source artifact bytes are referenced but are not embedded in this "
                    "review response."
                ),
                "An unsigned local decision is not deployment approval or hardware validation.",
            ),
        )

    @app.post(
        "/app/api/candidates/{candidate_id}/assurance-export",
        response_class=Response,
        operation_id="exportDashboardCandidateAssurance",
        include_in_schema=False,
        responses={
            status.HTTP_200_OK: {
                "description": "Deterministic portable assurance ZIP",
                "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
            }
        },
    )
    def export_dashboard_candidate_assurance(
        request: Request,
        candidate_id: str,
        command: DashboardAssuranceExportRequest,
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> Response:
        _dashboard_write_principal(
            manager,
            authenticator,
            application,
            request,
            candidate_id,
            csrf_token,
        )
        candidate = application.get_candidate(candidate_id)
        if candidate.revision != command.expected_revision:
            raise CandidateStoreError(
                "STORE_REVISION_CONFLICT",
                "candidate revision changed before assurance export",
            )
        bundle = application.get_assurance_bundle(candidate_id)
        if bundle.bundle_id != command.expected_bundle_id:
            raise CandidateStoreError(
                "STORE_REVISION_CONFLICT",
                "assurance bundle identity changed before export",
            )
        archive = render_assurance_bundle_archive(bundle)
        filename = f"assurance-{bundle.bundle_id.removeprefix('sha256:')}.zip"
        return Response(
            content=archive,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-ForgeGate-Assurance-Bundle": bundle.bundle_id,
            },
        )

    @app.post(
        "/app/api/candidates/{candidate_id}/evidence-replay-export",
        response_class=Response,
        operation_id="exportDashboardEvidenceReplay",
        include_in_schema=False,
        responses={
            200: {
                "description": "Verified private source replay ZIP",
                "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
            }
        },
    )
    def export_dashboard_evidence_replay(
        request: Request,
        candidate_id: str,
        command: DashboardReplayExportRequest,
        csrf_token: Annotated[str | None, Header(alias=DASHBOARD_CSRF_HEADER)] = None,
    ) -> Response:
        _dashboard_write_principal(
            manager, authenticator, application, request, candidate_id, csrf_token
        )
        candidate = application.get_candidate(candidate_id)
        bundle = application.get_assurance_bundle(candidate_id)
        if (
            candidate.revision != command.expected_revision
            or bundle.bundle_id != command.expected_bundle_id
        ):
            raise CandidateStoreError(
                "STORE_REVISION_CONFLICT", "Reload the candidate before exporting."
            )
        try:
            filename, archive = render_evidence_replay(
                bundle,
                {
                    item.sha256: base64.b64decode(item.content_base64, validate=True)
                    for item in command.files
                },
            )
        except (EvidenceReplayError, ValueError) as exc:
            raise CandidateStoreError(
                getattr(exc, "code", "REPLAY_INVALID"),
                "Source reports could not reproduce the retained candidate; "
                "check the complete original selection.",
            ) from exc
        return Response(
            content=archive,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-ForgeGate-Assurance-Bundle": bundle.bundle_id,
                "X-ForgeGate-Replay-Archive": filename,
                "X-ForgeGate-Archive-SHA256": hashlib.sha256(archive).hexdigest(),
            },
        )

    @app.get(
        "/app/api/audit-events",
        response_model=AuditEventPage,
        operation_id="listDashboardAuditEvents",
        include_in_schema=False,
    )
    def dashboard_audit_events(
        request: Request,
        project_id: Annotated[str, Query(pattern=SLUG_PATTERN)],
        after_sequence: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        candidate_id: Annotated[str | None, Query(pattern=CANDIDATE_ID_PATTERN)] = None,
    ) -> AuditEventPage:
        _require_same_origin(request, required=False)
        principal = _dashboard_principal(manager, request)
        authenticator.require_project(principal, project_id, audit=True)
        return application.query_audit_events(
            AuditEventQuery(
                after_sequence=after_sequence,
                limit=limit,
                project_id=project_id,
                candidate_id=candidate_id,
            )
        )

    from forgegate.dashboard.jobs import install_job_routes

    install_job_routes(
        app,
        application=application,
        authenticator=authenticator,
        manager=manager,
        store_path=job_store_path,
    )
    app.state.dashboard_session_manager = manager
    app.state.dashboard_static_root = assets_root
    app.state.dashboard_live_status_provider = status_provider
    return manager


def _dashboard_principal(manager: DashboardSessionManager, request: Request) -> ApiPrincipal:
    _, principal = manager.session(request.cookies.get(DASHBOARD_SESSION_COOKIE))
    request.state.authenticated_principal = principal
    return principal


def _dashboard_write_principal(
    manager: DashboardSessionManager,
    authenticator: ApiAuthenticator,
    application: CandidateApplication,
    request: Request,
    candidate_id: str,
    csrf_token: str | None,
) -> ApiPrincipal:
    _require_same_origin(request, required=True)
    stored, principal = manager.session(request.cookies.get(DASHBOARD_SESSION_COOKIE))
    request.state.authenticated_principal = principal
    manager.require_csrf(stored, csrf_token)
    candidate = application.get_candidate(candidate_id)
    authenticator.require_project(principal, candidate.project_id, write=True)
    return principal


def _require_same_origin(request: Request, *, required: bool) -> None:
    origin = request.headers.get("Origin")
    if origin is None:
        if required:
            raise ApiAuthenticationError(
                "DASHBOARD_ORIGIN_REQUIRED",
                "browser mutation requires the exact local Origin",
                status_code=403,
            )
        return
    host = request.headers.get("Host")
    if host is None or origin != f"{request.url.scheme}://{host}":
        raise ApiAuthenticationError(
            "DASHBOARD_ORIGIN_INVALID",
            "request Origin does not match the local Dashboard origin",
            status_code=403,
        )


__all__ = [
    "DASHBOARD_ACTIVATION_COOKIE",
    "DASHBOARD_CSP",
    "DASHBOARD_CSRF_HEADER",
    "DASHBOARD_SESSION_COOKIE",
    "install_dashboard_routes",
]
