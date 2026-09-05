"""Loopback-only presentation harness for manual Dashboard error-state checks.

This tool deliberately injects responses only for generic ``ui-error-*``
candidate versions. It is acceptance tooling, not a production failure switch.
"""

from __future__ import annotations

import argparse
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from forgegate.api import ApiAuthenticator, create_api_app
from forgegate.application import CandidateApplication
from forgegate.identity import TrustStore, load_identity_document


@dataclass(frozen=True)
class FaultPresentation:
    status: int
    code: str
    message: str
    retry_after: int | None = None


FAULT_PRESENTATIONS = {
    "ui-error-409": FaultPresentation(
        409,
        "STORE_IDEMPOTENCY_CONFLICT",
        "idempotency key was reused with a different request",
    ),
    "ui-error-413": FaultPresentation(
        413,
        "API_BODY_TOO_LARGE",
        "request body exceeds the 4 MiB local API limit",
    ),
    "ui-error-429": FaultPresentation(
        429,
        "API_AUTH_RATE_LIMITED",
        "authentication request rate limit exceeded",
        retry_after=3,
    ),
    "ui-error-500": FaultPresentation(
        500,
        "API_INTERNAL_ERROR",
        "request failed closed; inspect local service logs",
    ),
}


def create_fault_presentation_app(database: Path, trust_store_path: Path) -> FastAPI:
    """Create the real Dashboard with an isolated candidate-write fault layer."""
    document = load_identity_document(trust_store_path)
    if not isinstance(document, TrustStore):
        raise ValueError("--trust-store must contain forgegate.trust-store.v1")
    application = CandidateApplication.for_database(database)
    application.initialize()
    app = create_api_app(
        database,
        application=application,
        authenticator=ApiAuthenticator(document, session_ttl=timedelta(minutes=15)),
        dashboard=True,
    )

    async def inject_candidate_fault(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method != "POST" or request.url.path != "/app/api/candidates":
            return await call_next(request)
        body = await request.body()
        fault = next(
            (
                presentation
                for version, presentation in FAULT_PRESENTATIONS.items()
                if f'"version":"{version}"'.encode() in body
            ),
            None,
        )
        if fault is None:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "MANUAL_FAULT_SAMPLE_REQUIRED",
                        "message": "use one documented ui-error-* version in this manual harness",
                        "request_id": "manual-browser-fault-invalid",
                    }
                },
            )
        request_id = f"manual-browser-fault-{fault.status}"
        headers = {"X-Request-ID": request_id}
        if fault.retry_after is not None:
            headers["Retry-After"] = str(fault.retry_after)
        return JSONResponse(
            status_code=fault.status,
            content={
                "error": {
                    "code": fault.code,
                    "message": fault.message,
                    "request_id": request_id,
                }
            },
            headers=headers,
        )

    app.add_middleware(BaseHTTPMiddleware, dispatch=inject_candidate_fault)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve the loopback-only Dashboard manual error-presentation harness."
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--trust-store", required=True, type=Path)
    parser.add_argument("--port", default=8131, type=int)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    print("TEST_ONLY_FAULT_PRESENTATION_HARNESS; no failure-path authenticity claim")
    uvicorn.run(
        create_fault_presentation_app(args.database, args.trust_store),
        host="127.0.0.1",
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
