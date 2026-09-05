from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from forgegate import __version__
from forgegate.api import ApiAuthenticator, create_api_app
from forgegate.identity import (
    IdentityRole,
    TrustedIdentity,
    create_signing_identity,
    create_trust_store,
)


def create_dashboard_openapi() -> dict[str, Any]:
    """Build the deterministic, non-served contract for the Dashboard BFF."""
    identity = create_signing_identity(
        display_name="ForgeGate Dashboard contract identity",
        public_key=bytes(range(32)),
    )
    trust_store = create_trust_store(
        (
            TrustedIdentity(
                identity=identity,
                roles=(IdentityRole.OPERATOR,),
                project_ids=("contract-project",),
            ),
        )
    )
    app = create_api_app(
        Path("forgegate-dashboard-openapi-contract.db"),
        authenticator=ApiAuthenticator(trust_store),
        contract_only=True,
        dashboard=True,
    )
    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/app/api/")
    ]
    previous = tuple(route.include_in_schema for route in routes)
    try:
        for route in routes:
            route.include_in_schema = True
        return get_openapi(
            title="ForgeGate Dashboard BFF",
            version=__version__,
            openapi_version="3.1.0",
            summary="Same-origin local Dashboard boundary",
            description=(
                "Build-time contract only. The BFF uses an opaque HttpOnly Dashboard "
                "cookie plus exact Origin and anti-CSRF checks; this document is not "
                "served as interactive documentation."
            ),
            routes=routes,
        )
    finally:
        for route, include in zip(routes, previous, strict=True):
            route.include_in_schema = include


__all__ = ["create_dashboard_openapi"]
