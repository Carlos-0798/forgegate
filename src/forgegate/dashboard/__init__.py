from forgegate.dashboard.assets import (
    DashboardAsset,
    DashboardAssetInventory,
    build_dashboard_asset_inventory,
    validate_dashboard_assets,
    write_dashboard_asset_inventory,
)
from forgegate.dashboard.models import (
    DashboardActivationCompleted,
    DashboardActivationStart,
    DashboardActivationStatus,
    DashboardCandidateAssuranceReview,
    DashboardLogoutResponse,
    DashboardOverview,
    DashboardPrincipal,
    DashboardSessionResponse,
)
from forgegate.dashboard.sessions import DashboardSessionManager

_ROUTE_EXPORTS = {
    "DASHBOARD_ACTIVATION_COOKIE",
    "DASHBOARD_CSP",
    "DASHBOARD_CSRF_HEADER",
    "DASHBOARD_SESSION_COOKIE",
    "install_dashboard_routes",
}


def __getattr__(name: str) -> object:
    """Keep route exports public without importing the application graph eagerly."""
    if name not in _ROUTE_EXPORTS:
        raise AttributeError(name)
    from forgegate.dashboard import routes

    return getattr(routes, name)


__all__ = [
    "DASHBOARD_ACTIVATION_COOKIE",
    "DASHBOARD_CSP",
    "DASHBOARD_CSRF_HEADER",
    "DASHBOARD_SESSION_COOKIE",
    "DashboardActivationCompleted",
    "DashboardActivationStart",
    "DashboardActivationStatus",
    "DashboardAsset",
    "DashboardAssetInventory",
    "DashboardCandidateAssuranceReview",
    "DashboardLogoutResponse",
    "DashboardOverview",
    "DashboardPrincipal",
    "DashboardSessionManager",
    "DashboardSessionResponse",
    "build_dashboard_asset_inventory",
    "install_dashboard_routes",
    "validate_dashboard_assets",
    "write_dashboard_asset_inventory",
]
