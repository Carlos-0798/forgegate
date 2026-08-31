from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, Query, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from forgegate import __version__
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
    ProjectQuery,
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

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    400: {"model": ApiErrorResponse, "description": "Invalid request"},
    404: {"model": ApiErrorResponse, "description": "Candidate resource not found"},
    409: {"model": ApiErrorResponse, "description": "Request conflicts with durable state"},
    413: {"model": ApiErrorResponse, "description": "Request body exceeds local API limit"},
    422: {"model": ApiErrorResponse, "description": "Strict request validation failed"},
    500: {"model": ApiErrorResponse, "description": "Fail-closed internal error"},
    503: {"model": ApiErrorResponse, "description": "Candidate store unavailable"},
}


def create_api_app(
    database: Path,
    *,
    application: CandidateApplication | None = None,
) -> FastAPI:
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
        lifespan=lifespan,
    )
    app.state.candidate_application = candidate_application

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
    ) -> RegisteredProject:
        return candidate_application.register_project(
            command,
            idempotency_key=idempotency_key,
        )

    @app.get(
        "/v1/projects",
        response_model=RegisteredProjectPage,
        operation_id="listProjects",
        tags=["projects"],
        responses=ERROR_RESPONSES,
    )
    def list_projects_endpoint(
        after_project_id: str | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> RegisteredProjectPage:
        return candidate_application.list_projects(
            ProjectQuery(after_project_id=after_project_id, limit=limit)
        )

    @app.get(
        "/v1/projects/{project_id}",
        response_model=RegisteredProject,
        operation_id="getProject",
        tags=["projects"],
        responses=ERROR_RESPONSES,
    )
    def get_project_endpoint(project_id: str) -> RegisteredProject:
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
    ) -> ProjectProfileRevision:
        return candidate_application.revise_project(
            project_id,
            command,
            idempotency_key=idempotency_key,
        )

    @app.get(
        "/v1/projects/{project_id}/profile",
        response_model=ProjectProfileDocument,
        operation_id="getCurrentProjectProfile",
        tags=["projects"],
        responses=ERROR_RESPONSES,
    )
    def get_current_project_profile_endpoint(project_id: str) -> ProjectProfileDocument:
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
        after_profile_version: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> ProjectProfilePage:
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
        after_candidate_id: str | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> ReleaseCandidatePage:
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
        after_sequence: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        project_id: str | None = None,
        candidate_id: str | None = None,
    ) -> AuditEventPage:
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
    ) -> CandidateDocument:
        return candidate_application.create_candidate(
            command,
            idempotency_key=idempotency_key,
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
    ) -> CandidateTransitionResult:
        return candidate_application.advance_candidate(
            candidate_id,
            command,
            idempotency_key=idempotency_key,
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
    ) -> CandidateEvidenceBinding:
        return candidate_application.bind_evidence(
            candidate_id,
            command,
            idempotency_key=idempotency_key,
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
    ) -> CandidateEvaluationResult:
        return candidate_application.evaluate_candidate(
            candidate_id,
            command,
            idempotency_key=idempotency_key,
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
    ) -> ReleaseAttestation:
        return candidate_application.attest_candidate(candidate_id, command)

    @app.get(
        "/v1/candidates/{candidate_id}",
        response_model=CandidateDocument,
        operation_id="getCandidate",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def get_candidate_endpoint(candidate_id: str) -> CandidateDocument:
        return candidate_application.get_candidate(candidate_id)

    @app.get(
        "/v1/candidates/{candidate_id}/history",
        response_model=CandidateHistoryView,
        operation_id="getCandidateHistory",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def get_candidate_history_endpoint(candidate_id: str) -> CandidateHistoryView:
        return candidate_application.get_history(candidate_id)

    @app.get(
        "/v1/candidates/{candidate_id}/evidence",
        response_model=CandidateEvidenceBinding,
        operation_id="getCandidateEvidence",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def get_candidate_evidence_endpoint(candidate_id: str) -> CandidateEvidenceBinding:
        return candidate_application.get_evidence(candidate_id)

    @app.get(
        "/v1/candidates/{candidate_id}/policy",
        response_model=PolicyMaterial,
        operation_id="getCandidatePolicyMaterial",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def get_candidate_policy_material_endpoint(candidate_id: str) -> PolicyMaterial:
        """Return exact profile-authorized policy material retained at evaluation."""
        return candidate_application.get_policy_material(candidate_id)

    @app.get(
        "/v1/candidates/{candidate_id}/attestation",
        response_model=ReleaseAttestation,
        operation_id="getCandidateAttestation",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def get_candidate_attestation_endpoint(candidate_id: str) -> ReleaseAttestation:
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
