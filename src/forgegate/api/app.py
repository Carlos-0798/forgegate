from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from forgegate import __version__
from forgegate.api.models import ApiError, ApiErrorResponse, HealthResponse
from forgegate.application import (
    CandidateApplication,
    CandidateCreateCommand,
    CandidateHistoryView,
)
from forgegate.attestations import ReleaseAttestation
from forgegate.candidates import (
    CandidateEvidenceBinding,
    CandidateLifecycleError,
    CandidateStoreError,
    ReleaseCandidate,
)

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    400: {"model": ApiErrorResponse, "description": "Invalid request"},
    404: {"model": ApiErrorResponse, "description": "Candidate resource not found"},
    409: {"model": ApiErrorResponse, "description": "Request conflicts with durable state"},
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
        summary="Local release-assurance candidate API",
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
            "candidate input failed strict domain validation",
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
        "/v1/candidates",
        response_model=ReleaseCandidate,
        status_code=status.HTTP_201_CREATED,
        operation_id="createCandidate",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def create_candidate_endpoint(
        command: CandidateCreateCommand,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> ReleaseCandidate:
        return candidate_application.create_candidate(
            command,
            idempotency_key=idempotency_key,
        )

    @app.get(
        "/v1/candidates/{candidate_id}",
        response_model=ReleaseCandidate,
        operation_id="getCandidate",
        tags=["candidates"],
        responses=ERROR_RESPONSES,
    )
    def get_candidate_endpoint(candidate_id: str) -> ReleaseCandidate:
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


__all__ = ["REQUEST_ID_PATTERN", "create_api_app"]
