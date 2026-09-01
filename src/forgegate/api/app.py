from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Query, Request, status
from fastapi import Path as ApiPath
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from forgegate import __version__
from forgegate.api.auth import (
    ApiAuthChallenge,
    ApiAuthenticationError,
    ApiAuthenticator,
    ApiChallengeRequest,
    ApiPrincipal,
    ApiSessionCreateRequest,
    ApiSessionResponse,
    ApiSessionRevocationResponse,
    ApiTrustStoreReloadResponse,
)
from forgegate.api.models import ApiError, ApiErrorResponse, HealthResponse
from forgegate.application import (
    AuditEventQuery,
    CandidateAdvanceCommand,
    CandidateApplication,
    CandidateAttestCommand,
    CandidateBindEvidenceCommand,
    CandidateCreateCommand,
    CandidateEvaluateCommand,
    CandidateEvaluationResult,
    CandidateHistoryView,
    CandidateQuery,
    ProjectProfileQuery,
    ProjectRegisterCommand,
    ProjectReviseCommand,
)
from forgegate.attestations import ReleaseAttestation
from forgegate.audit import AuditEventPage
from forgegate.candidates import (
    CandidateDocument,
    CandidateEvidenceBinding,
    CandidateLifecycleError,
    CandidateStoreError,
    ReleaseCandidatePage,
)
from forgegate.candidates.models import CandidateTransitionResult
from forgegate.network import is_loopback_host
from forgegate.policy import PolicyMaterial
from forgegate.projects import (
    ProjectProfileDocument,
    ProjectProfilePage,
    ProjectProfileRevision,
    RegisteredProject,
    RegisteredProjectPage,
)

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
MAX_REQUEST_BODY_BYTES = 4 * 1024 * 1024
BEARER_SCHEME = HTTPBearer(auto_error=False)

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    400: {"model": ApiErrorResponse, "description": "Invalid request"},
    401: {"model": ApiErrorResponse, "description": "Authentication required or invalid"},
    403: {"model": ApiErrorResponse, "description": "Authenticated identity is not authorized"},
    404: {"model": ApiErrorResponse, "description": "Candidate resource not found"},
    409: {"model": ApiErrorResponse, "description": "Request conflicts with durable state"},
    413: {"model": ApiErrorResponse, "description": "Request body exceeds local API limit"},
    429: {"model": ApiErrorResponse, "description": "Authentication rate limit exceeded"},
    422: {"model": ApiErrorResponse, "description": "Strict request validation failed"},
    500: {"model": ApiErrorResponse, "description": "Fail-closed internal error"},
    503: {"model": ApiErrorResponse, "description": "Candidate store unavailable"},
}


def authenticated_principal_dependency(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER_SCHEME)],
) -> ApiPrincipal:
    authenticator = getattr(request.app.state, "authenticator", None)
    if not isinstance(authenticator, ApiAuthenticator):
        raise ApiAuthenticationError(
            "API_AUTHENTICATOR_UNAVAILABLE",
            "runtime authenticator is unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    authorization = (
        f"{credentials.scheme} {credentials.credentials}" if credentials is not None else None
    )
    return authenticator.authenticate(authorization)


def create_api_app(
    database: Path,
    *,
    application: CandidateApplication | None = None,
    authenticator: ApiAuthenticator | None = None,
    contract_only: bool = False,
) -> FastAPI:
    if authenticator is None and not contract_only:
        raise ValueError("authenticated API construction requires an ApiAuthenticator")
    candidate_application = application or CandidateApplication.for_database(database)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        candidate_application.initialize()
        yield

    app = FastAPI(
        title="ForgeGate Local API",
        summary="Local release-assurance project and candidate API",
        version=__version__,
        openapi_version="3.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.candidate_application = candidate_application
    app.state.authenticator = authenticator

    def require_project(
        principal: ApiPrincipal,
        project_id: str,
        *,
        write: bool = False,
        audit: bool = False,
    ) -> None:
        assert authenticator is not None
        authenticator.require_project(principal, project_id, write=write, audit=audit)

    def require_candidate(
        principal: ApiPrincipal,
        candidate_id: str,
        *,
        write: bool = False,
    ) -> CandidateDocument:
        candidate = candidate_application.get_candidate(candidate_id)
        require_project(principal, candidate.project_id, write=write)
        return candidate

    @app.middleware("http")
    async def correlation_id_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        supplied = request.headers.get("X-Request-ID")
        request_id = supplied or _new_request_id()
        if not REQUEST_ID_PATTERN.fullmatch(request_id):
            replacement = _new_request_id()
            return _error_response(
                status.HTTP_400_BAD_REQUEST,
                "API_REQUEST_ID_INVALID",
                "X-Request-ID must be 8-128 safe identifier characters",
                replacement,
            )
        request.state.request_id = request_id
        if not is_loopback_host(request.url.hostname):
            return _error_response(
                status.HTTP_400_BAD_REQUEST,
                "API_HOST_INVALID",
                "Host must identify localhost or a loopback IP address",
                request_id,
            )
        content_length = request.headers.get("Content-Length")
        if content_length is not None:
            try:
                body_length = int(content_length)
            except ValueError:
                return _error_response(
                    status.HTTP_400_BAD_REQUEST,
                    "API_CONTENT_LENGTH_INVALID",
                    "Content-Length must be a non-negative integer",
                    request_id,
                )
            if body_length < 0:
                return _error_response(
                    status.HTTP_400_BAD_REQUEST,
                    "API_CONTENT_LENGTH_INVALID",
                    "Content-Length must be a non-negative integer",
                    request_id,
                )
            if body_length > MAX_REQUEST_BODY_BYTES:
                return _error_response(
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    "API_BODY_TOO_LARGE",
                    "request body exceeds the 4 MiB local API limit",
                    request_id,
                )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(CandidateStoreError)
    async def candidate_store_error_handler(
        request: Request,
        exc: CandidateStoreError,
    ) -> JSONResponse:
        return _error_response(
            _store_error_status(exc.code),
            exc.code,
            _error_message(exc.code, str(exc)),
            _request_id(request),
        )

    @app.exception_handler(ApiAuthenticationError)
    async def authentication_error_handler(
        request: Request,
        exc: ApiAuthenticationError,
    ) -> JSONResponse:
        response = _error_response(
            exc.status_code,
            exc.code,
            _error_message(exc.code, str(exc)),
            _request_id(request),
        )
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            response.headers["WWW-Authenticate"] = "Bearer"
        if exc.retry_after_seconds is not None:
            response.headers["Retry-After"] = str(exc.retry_after_seconds)
        return response

    @app.exception_handler(CandidateLifecycleError)
    async def candidate_lifecycle_error_handler(
        request: Request,
        exc: CandidateLifecycleError,
    ) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            exc.code,
            _error_message(exc.code, str(exc)),
            _request_id(request),
        )

    @app.exception_handler(ValidationError)
    async def pydantic_error_handler(request: Request, _: ValidationError) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "API_DOMAIN_VALIDATION_FAILED",
            "request input failed strict domain validation",
            _request_id(request),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        _: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "API_REQUEST_VALIDATION_FAILED",
            "request path, headers, or body failed strict validation",
            _request_id(request),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, _: Exception) -> JSONResponse:
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "API_INTERNAL_ERROR",
            "request failed closed; inspect local service logs",
            _request_id(request),
        )

    @app.get(
        "/healthz",
        response_model=HealthResponse,
        operation_id="getHealth",
        tags=["system"],
    )
    def health() -> HealthResponse:
        return HealthResponse(forgegate_version=__version__)

    @app.post(
        "/v1/auth/challenges",
        response_model=ApiAuthChallenge,
        status_code=status.HTTP_201_CREATED,
        operation_id="createApiAuthChallenge",
        tags=["authentication"],
        responses=ERROR_RESPONSES,
    )
    def create_auth_challenge_endpoint(command: ApiChallengeRequest) -> ApiAuthChallenge:
        if authenticator is None:
            raise ApiAuthenticationError(
                "API_AUTHENTICATOR_UNAVAILABLE",
                "runtime authenticator is unavailable",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return authenticator.issue_challenge(command)

    @app.post(
        "/v1/auth/sessions",
        response_model=ApiSessionResponse,
        status_code=status.HTTP_201_CREATED,
        operation_id="createApiSession",
        tags=["authentication"],
        responses=ERROR_RESPONSES,
    )
    def create_auth_session_endpoint(command: ApiSessionCreateRequest) -> ApiSessionResponse:
        if authenticator is None:
            raise ApiAuthenticationError(
                "API_AUTHENTICATOR_UNAVAILABLE",
                "runtime authenticator is unavailable",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return authenticator.create_session(command)

    @app.delete(
        "/v1/auth/session",
        response_model=ApiSessionRevocationResponse,
        operation_id="logoutApiSession",
        tags=["authentication"],
        responses=ERROR_RESPONSES,
    )
    def logout_auth_session_endpoint(
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> ApiSessionRevocationResponse:
        assert authenticator is not None
        return authenticator.logout(principal)

    @app.delete(
        "/v1/auth/sessions/{session_id}",
        response_model=ApiSessionRevocationResponse,
        operation_id="revokeApiSession",
        tags=["authentication"],
        responses=ERROR_RESPONSES,
    )
    def revoke_auth_session_endpoint(
        session_id: Annotated[str, ApiPath(pattern=r"^sess-[0-9a-f]{32}$")],
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> ApiSessionRevocationResponse:
        assert authenticator is not None
        return authenticator.revoke_session(principal, session_id)

    @app.post(
        "/v1/auth/trust-store/reload",
        response_model=ApiTrustStoreReloadResponse,
        operation_id="reloadApiTrustStore",
        tags=["authentication"],
        responses=ERROR_RESPONSES,
    )
    def reload_api_trust_store_endpoint(
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> ApiTrustStoreReloadResponse:
        assert authenticator is not None
        return authenticator.reload_trust_store(principal)

    @app.post(
        "/v1/projects",
        response_model=RegisteredProject,
        status_code=status.HTTP_201_CREATED,
        operation_id="registerProject",
        tags=["projects"],
        responses=ERROR_RESPONSES,
    )
    def register_project_endpoint(
        command: ProjectRegisterCommand,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> RegisteredProject:
        require_project(principal, command.config.project.id, write=True)
        return candidate_application.register_project(
            command,
            idempotency_key=idempotency_key,
            actor=principal.audit_actor(),
        )

    @app.get(
        "/v1/projects",
        response_model=RegisteredProjectPage,
        operation_id="listProjects",
        tags=["projects"],
        responses=ERROR_RESPONSES,
    )
    def list_projects_endpoint(
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
        after_project_id: str | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> RegisteredProjectPage:
        authorized_ids = tuple(
            project_id
            for project_id in principal.project_ids
            if after_project_id is None or project_id > after_project_id
        )
        projects: list[RegisteredProject] = []
        for project_id in authorized_ids:
            try:
                projects.append(candidate_application.get_project(project_id))
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
        "/v1/projects/{project_id}",
        response_model=RegisteredProject,
        operation_id="getProject",
        tags=["projects"],
        responses=ERROR_RESPONSES,
    )
    def get_project_endpoint(
        project_id: str,
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> RegisteredProject:
        require_project(principal, project_id)
        return candidate_application.get_project(project_id)

    @app.post(
        "/v1/projects/{project_id}/revisions",
        response_model=ProjectProfileRevision,
        status_code=status.HTTP_201_CREATED,
        operation_id="reviseProjectProfile",
        tags=["projects"],
        responses=ERROR_RESPONSES,
    )
    def revise_project_profile_endpoint(
        project_id: str,
        command: ProjectReviseCommand,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> ProjectProfileRevision:
        require_project(principal, project_id, write=True)
        return candidate_application.revise_project(
            project_id,
            command,
            idempotency_key=idempotency_key,
            actor=principal.audit_actor(),
        )

    @app.get(
        "/v1/projects/{project_id}/profile",
        response_model=ProjectProfileDocument,
        operation_id="getCurrentProjectProfile",
        tags=["projects"],
        responses=ERROR_RESPONSES,
    )
    def get_current_project_profile_endpoint(
        project_id: str,
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> ProjectProfileDocument:
        require_project(principal, project_id)
        return candidate_application.get_current_project_profile(project_id)

    @app.get(
        "/v1/projects/{project_id}/revisions",
        response_model=ProjectProfilePage,
        operation_id="listProjectProfileRevisions",
        tags=["projects"],
        responses=ERROR_RESPONSES,
    )
    def list_project_profile_revisions_endpoint(
        project_id: str,
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
        after_profile_version: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> ProjectProfilePage:
        require_project(principal, project_id)
        return candidate_application.list_project_profiles(
            ProjectProfileQuery(
                project_id=project_id,
                after_profile_version=after_profile_version,
                limit=limit,
            )
        )

    @app.get(
        "/v1/projects/{project_id}/candidates",
        response_model=ReleaseCandidatePage,
        operation_id="listProjectCandidates",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def list_project_candidates_endpoint(
        project_id: str,
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
        after_candidate_id: str | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> ReleaseCandidatePage:
        require_project(principal, project_id)
        return candidate_application.list_candidates(
            CandidateQuery(
                project_id=project_id,
                after_candidate_id=after_candidate_id,
                limit=limit,
            )
        )

    @app.get(
        "/v1/audit-events",
        response_model=AuditEventPage,
        operation_id="queryAuditEvents",
        tags=["audit"],
        responses=ERROR_RESPONSES,
    )
    def query_audit_events_endpoint(
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
        project_id: str,
        after_sequence: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        candidate_id: str | None = None,
    ) -> AuditEventPage:
        require_project(principal, project_id, audit=True)
        return candidate_application.query_audit_events(
            AuditEventQuery(
                after_sequence=after_sequence,
                limit=limit,
                project_id=project_id,
                candidate_id=candidate_id,
            )
        )

    @app.post(
        "/v1/candidates",
        response_model=CandidateDocument,
        status_code=status.HTTP_201_CREATED,
        operation_id="createCandidate",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def create_candidate_endpoint(
        command: CandidateCreateCommand,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> CandidateDocument:
        require_project(principal, command.project_id, write=True)
        return candidate_application.create_candidate(
            command,
            idempotency_key=idempotency_key,
            actor=principal.audit_actor(),
        )

    @app.post(
        "/v1/candidates/{candidate_id}/transitions",
        response_model=CandidateTransitionResult,
        operation_id="advanceCandidate",
        tags=["candidate commands"],
        responses=ERROR_RESPONSES,
    )
    def advance_candidate_endpoint(
        candidate_id: str,
        command: CandidateAdvanceCommand,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> CandidateTransitionResult:
        require_candidate(principal, candidate_id, write=True)
        return candidate_application.advance_candidate(
            candidate_id,
            command,
            idempotency_key=idempotency_key,
            actor=principal.audit_actor(),
        )

    @app.post(
        "/v1/candidates/{candidate_id}/evidence",
        response_model=CandidateEvidenceBinding,
        operation_id="bindCandidateEvidence",
        tags=["candidate commands"],
        responses=ERROR_RESPONSES,
    )
    def bind_candidate_evidence_endpoint(
        candidate_id: str,
        command: CandidateBindEvidenceCommand,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> CandidateEvidenceBinding:
        require_candidate(principal, candidate_id, write=True)
        return candidate_application.bind_evidence(
            candidate_id,
            command,
            idempotency_key=idempotency_key,
            actor=principal.audit_actor(),
        )

    @app.post(
        "/v1/candidates/{candidate_id}/evaluate",
        response_model=CandidateEvaluationResult,
        operation_id="evaluateCandidate",
        tags=["candidate commands"],
        responses=ERROR_RESPONSES,
    )
    def evaluate_candidate_endpoint(
        candidate_id: str,
        command: CandidateEvaluateCommand,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> CandidateEvaluationResult:
        require_candidate(principal, candidate_id, write=True)
        return candidate_application.evaluate_candidate(
            candidate_id,
            command,
            idempotency_key=idempotency_key,
            actor=principal.audit_actor(),
        )

    @app.post(
        "/v1/candidates/{candidate_id}/attestation",
        response_model=ReleaseAttestation,
        operation_id="attestCandidate",
        tags=["candidate commands"],
        responses=ERROR_RESPONSES,
    )
    def attest_candidate_endpoint(
        candidate_id: str,
        command: CandidateAttestCommand,
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> ReleaseAttestation:
        require_candidate(principal, candidate_id, write=True)
        return candidate_application.attest_candidate(
            candidate_id,
            command,
            actor=principal.audit_actor(),
        )

    @app.get(
        "/v1/candidates/{candidate_id}",
        response_model=CandidateDocument,
        operation_id="getCandidate",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def get_candidate_endpoint(
        candidate_id: str,
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> CandidateDocument:
        return require_candidate(principal, candidate_id)

    @app.get(
        "/v1/candidates/{candidate_id}/history",
        response_model=CandidateHistoryView,
        operation_id="getCandidateHistory",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def get_candidate_history_endpoint(
        candidate_id: str,
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> CandidateHistoryView:
        require_candidate(principal, candidate_id)
        return candidate_application.get_history(candidate_id)

    @app.get(
        "/v1/candidates/{candidate_id}/evidence",
        response_model=CandidateEvidenceBinding,
        operation_id="getCandidateEvidence",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def get_candidate_evidence_endpoint(
        candidate_id: str,
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> CandidateEvidenceBinding:
        require_candidate(principal, candidate_id)
        return candidate_application.get_evidence(candidate_id)

    @app.get(
        "/v1/candidates/{candidate_id}/policy",
        response_model=PolicyMaterial,
        operation_id="getCandidatePolicyMaterial",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def get_candidate_policy_material_endpoint(
        candidate_id: str,
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> PolicyMaterial:
        """Return exact profile-authorized policy material retained at evaluation."""
        require_candidate(principal, candidate_id)
        return candidate_application.get_policy_material(candidate_id)

    @app.get(
        "/v1/candidates/{candidate_id}/attestation",
        response_model=ReleaseAttestation,
        operation_id="getCandidateAttestation",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def get_candidate_attestation_endpoint(
        candidate_id: str,
        principal: Annotated[ApiPrincipal, Depends(authenticated_principal_dependency)],
    ) -> ReleaseAttestation:
        require_candidate(principal, candidate_id)
        return candidate_application.get_attestation(candidate_id)

    return app


def _new_request_id() -> str:
    return "req-" + uuid.uuid4().hex


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else _new_request_id()


def _error_response(status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    payload = ApiErrorResponse(
        error=ApiError(code=code, message=message, request_id=request_id)
    ).model_dump(mode="json")
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers={"X-Request-ID": request_id},
    )


def _error_message(code: str, rendered: str) -> str:
    prefix = f"{code}: "
    return rendered.removeprefix(prefix)


def _store_error_status(code: str) -> int:
    if code.endswith("_NOT_FOUND"):
        return status.HTTP_404_NOT_FOUND
    if code in {
        "STORE_CANDIDATE_CONFLICT",
        "STORE_PROJECT_CONFLICT",
        "STORE_PROJECT_PROFILE_VERSION_CONFLICT",
        "STORE_ATTESTATION_CONFLICT",
        "STORE_EVIDENCE_BINDING_CONFLICT",
        "STORE_EVALUATION_CONFLICT",
        "STORE_IDEMPOTENCY_CONFLICT",
        "STORE_REVISION_CONFLICT",
    }:
        return status.HTTP_409_CONFLICT
    if code in {"STORE_BUSY", "STORE_MIGRATION_REQUIRED", "STORE_NOT_INITIALIZED"}:
        return status.HTTP_503_SERVICE_UNAVAILABLE
    if code in {
        "STORE_CORRUPT",
        "STORE_NOT_FORGEGATE",
        "STORE_SCHEMA_UNSUPPORTED",
    }:
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    return status.HTTP_400_BAD_REQUEST


__all__ = ["MAX_REQUEST_BODY_BYTES", "REQUEST_ID_PATTERN", "create_api_app"]
