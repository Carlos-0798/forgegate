from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from forgegate.api.auth import (
    ApiAuthChallenge,
    ApiAuthenticationError,
    ApiAuthenticator,
    ApiChallengeRequest,
    ApiPrincipal,
    ApiSessionCreateRequest,
    ApiSessionResponse,
)
from forgegate.dashboard.models import (
    DashboardActivationCompleted,
    DashboardActivationStart,
    DashboardActivationStatus,
    DashboardLogoutResponse,
    DashboardPrincipal,
    DashboardSessionResponse,
)

ACTIVATION_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ234567"
DASHBOARD_COOKIE_PATTERN_LENGTH = 43


@dataclass
class _Activation:
    code_digest: str
    browser_digest: str
    expires_at: datetime
    challenge: ApiAuthChallenge | None = None
    completion_digest: str | None = None
    api_session: ApiSessionResponse | None = None
    dashboard_cookie: str | None = None
    csrf_token: str | None = None


@dataclass(frozen=True)
class _DashboardSession:
    cookie_digest: str
    api_access_token: str
    csrf_token: str
    principal: ApiPrincipal


class DashboardSessionManager:
    def __init__(
        self,
        authenticator: ApiAuthenticator,
        *,
        activation_ttl: timedelta = timedelta(seconds=60),
        max_pending_activations: int = 100,
        max_dashboard_sessions: int = 100,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if activation_ttl <= timedelta(0) or activation_ttl > timedelta(minutes=5):
            raise ValueError(
                "Dashboard activation TTL must be positive and no more than five minutes"
            )
        if not 1 <= max_pending_activations <= 1000:
            raise ValueError("max pending Dashboard activations must be between 1 and 1000")
        if not 1 <= max_dashboard_sessions <= 1000:
            raise ValueError("max Dashboard sessions must be between 1 and 1000")
        self._authenticator = authenticator
        self._activation_ttl = activation_ttl
        self._max_pending_activations = max_pending_activations
        self._max_dashboard_sessions = max_dashboard_sessions
        self._clock = clock or (lambda: datetime.now(UTC))
        self._activations_by_code: dict[str, _Activation] = {}
        self._activations_by_browser: dict[str, _Activation] = {}
        self._sessions: dict[str, _DashboardSession] = {}
        self._lock = threading.RLock()

    def start_activation(self) -> tuple[DashboardActivationStart, str]:
        now = self._now()
        with self._lock:
            self._purge(now)
            if len(self._activations_by_browser) >= self._max_pending_activations:
                raise ApiAuthenticationError(
                    "DASHBOARD_ACTIVATION_CAPACITY_REACHED",
                    "pending Dashboard activation capacity is exhausted",
                    status_code=503,
                )
            code = self._unique_code()
            browser_cookie = secrets.token_urlsafe(32)
            activation = _Activation(
                code_digest=_digest(code),
                browser_digest=_digest(browser_cookie),
                expires_at=now + self._activation_ttl,
            )
            self._activations_by_code[activation.code_digest] = activation
            self._activations_by_browser[activation.browser_digest] = activation
        return (
            DashboardActivationStart(
                activation_code=code,
                expires_at=activation.expires_at,
            ),
            browser_cookie,
        )

    def issue_challenge(
        self,
        activation_code: str,
        request: ApiChallengeRequest,
    ) -> ApiAuthChallenge:
        now = self._now()
        with self._lock:
            self._purge(now)
            activation = self._activation_for_code(activation_code)
            if activation.api_session is not None:
                raise ApiAuthenticationError(
                    "DASHBOARD_ACTIVATION_ALREADY_COMPLETED",
                    "Dashboard activation is already complete",
                    status_code=409,
                )
            if activation.challenge is not None:
                existing = activation.challenge
                if (
                    existing.identity_id,
                    existing.role,
                    existing.project_ids,
                ) == (request.identity_id, request.role, request.project_ids):
                    return existing
                raise ApiAuthenticationError(
                    "DASHBOARD_ACTIVATION_CONFLICT",
                    "Dashboard activation authority cannot be changed",
                    status_code=409,
                )
            challenge = self._authenticator.issue_challenge(request)
            activation.challenge = challenge
            return challenge

    def complete_activation(
        self,
        activation_code: str,
        request: ApiSessionCreateRequest,
    ) -> DashboardActivationCompleted:
        now = self._now()
        completion_digest = _digest(request.model_dump_json())
        with self._lock:
            self._purge(now)
            activation = self._activation_for_code(activation_code)
            if activation.challenge is None:
                raise ApiAuthenticationError(
                    "DASHBOARD_ACTIVATION_CHALLENGE_REQUIRED",
                    "Dashboard activation challenge has not been issued",
                    status_code=409,
                )
            if request.challenge_id != activation.challenge.challenge_id:
                raise ApiAuthenticationError(
                    "DASHBOARD_ACTIVATION_CHALLENGE_MISMATCH",
                    "signed challenge does not belong to this Dashboard activation",
                    status_code=409,
                )
            if activation.api_session is not None:
                if not hmac.compare_digest(
                    activation.completion_digest or "",
                    completion_digest,
                ):
                    raise ApiAuthenticationError(
                        "DASHBOARD_ACTIVATION_CONFLICT",
                        "completed Dashboard activation cannot accept a different signature",
                        status_code=409,
                    )
                principal = self._authenticator.authenticate(
                    f"Bearer {activation.api_session.access_token}"
                )
                return DashboardActivationCompleted(
                    principal=DashboardPrincipal.from_api(principal)
                )
            api_session = self._authenticator.create_session(request)
            activation.api_session = api_session
            activation.completion_digest = completion_digest
            return DashboardActivationCompleted(
                principal=DashboardPrincipal.from_api(
                    self._authenticator.authenticate(f"Bearer {api_session.access_token}")
                )
            )

    def poll_activation(
        self,
        browser_cookie: str | None,
    ) -> tuple[DashboardActivationStatus, str | None]:
        if browser_cookie is None:
            raise ApiAuthenticationError(
                "DASHBOARD_ACTIVATION_REQUIRED",
                "browser-bound Dashboard activation is required",
            )
        now = self._now()
        browser_digest = _digest(browser_cookie)
        with self._lock:
            self._purge(now)
            activation = self._activations_by_browser.get(browser_digest)
            if activation is None or not hmac.compare_digest(
                activation.browser_digest,
                browser_digest,
            ):
                raise ApiAuthenticationError(
                    "DASHBOARD_ACTIVATION_INVALID",
                    "Dashboard activation is unknown or expired",
                )
            if activation.api_session is None:
                return (
                    DashboardActivationStatus(
                        status=(
                            "CHALLENGE_ISSUED" if activation.challenge is not None else "PENDING"
                        ),
                        expires_at=activation.expires_at,
                    ),
                    None,
                )
            principal = self._authenticator.authenticate(
                f"Bearer {activation.api_session.access_token}"
            )
            if activation.dashboard_cookie is None:
                self._purge(now)
                if len(self._sessions) >= self._max_dashboard_sessions:
                    raise ApiAuthenticationError(
                        "DASHBOARD_SESSION_CAPACITY_REACHED",
                        "active Dashboard session capacity is exhausted",
                        status_code=503,
                    )
                dashboard_cookie = secrets.token_urlsafe(32)
                csrf_token = secrets.token_urlsafe(32)
                stored = _DashboardSession(
                    cookie_digest=_digest(dashboard_cookie),
                    api_access_token=activation.api_session.access_token,
                    csrf_token=csrf_token,
                    principal=principal,
                )
                self._sessions[stored.cookie_digest] = stored
                activation.dashboard_cookie = dashboard_cookie
                activation.csrf_token = csrf_token
                self._activations_by_code.pop(activation.code_digest, None)
            assert activation.dashboard_cookie is not None
            assert activation.csrf_token is not None
            return (
                DashboardActivationStatus(
                    status="AUTHENTICATED",
                    expires_at=activation.expires_at,
                    principal=DashboardPrincipal.from_api(principal),
                    csrf_token=activation.csrf_token,
                ),
                activation.dashboard_cookie,
            )

    def session(self, dashboard_cookie: str | None) -> tuple[_DashboardSession, ApiPrincipal]:
        if dashboard_cookie is None:
            raise ApiAuthenticationError(
                "DASHBOARD_AUTHENTICATION_REQUIRED",
                "an authenticated Dashboard session is required",
            )
        now = self._now()
        cookie_digest = _digest(dashboard_cookie)
        with self._lock:
            self._purge(now)
            stored = self._sessions.get(cookie_digest)
            if stored is None or not hmac.compare_digest(stored.cookie_digest, cookie_digest):
                raise ApiAuthenticationError(
                    "DASHBOARD_SESSION_INVALID",
                    "Dashboard session is invalid or expired",
                )
        try:
            principal = self._authenticator.authenticate(f"Bearer {stored.api_access_token}")
        except ApiAuthenticationError:
            with self._lock:
                self._sessions.pop(cookie_digest, None)
            raise
        return stored, principal

    def session_response(self, dashboard_cookie: str | None) -> DashboardSessionResponse:
        stored, principal = self.session(dashboard_cookie)
        return DashboardSessionResponse(
            principal=DashboardPrincipal.from_api(principal),
            csrf_token=stored.csrf_token,
        )

    def require_csrf(self, stored: _DashboardSession, supplied: str | None) -> None:
        if supplied is None or not hmac.compare_digest(stored.csrf_token, supplied):
            raise ApiAuthenticationError(
                "DASHBOARD_CSRF_INVALID",
                "Dashboard mutation requires the active anti-CSRF value",
                status_code=403,
            )

    def logout(
        self,
        dashboard_cookie: str | None,
        csrf_token: str | None,
    ) -> DashboardLogoutResponse:
        stored, principal = self.session(dashboard_cookie)
        self.require_csrf(stored, csrf_token)
        self._authenticator.logout(principal)
        with self._lock:
            self._sessions.pop(stored.cookie_digest, None)
        return DashboardLogoutResponse(session_id=principal.session_id)

    def _activation_for_code(self, activation_code: str) -> _Activation:
        code_digest = _digest(activation_code)
        activation = self._activations_by_code.get(code_digest)
        if activation is None or not hmac.compare_digest(activation.code_digest, code_digest):
            raise ApiAuthenticationError(
                "DASHBOARD_ACTIVATION_INVALID",
                "Dashboard activation code is unknown or expired",
            )
        return activation

    def _unique_code(self) -> str:
        for _ in range(20):
            raw = "".join(secrets.choice(ACTIVATION_CODE_ALPHABET) for _ in range(10))
            code = f"FG-{raw[:5]}-{raw[5:]}"
            if _digest(code) not in self._activations_by_code:
                return code
        raise ApiAuthenticationError(
            "DASHBOARD_ACTIVATION_CAPACITY_REACHED",
            "could not allocate a unique Dashboard activation code",
            status_code=503,
        )

    def _purge(self, now: datetime) -> None:
        expired_browser_keys = [
            key
            for key, activation in self._activations_by_browser.items()
            if activation.expires_at <= now
        ]
        for key in expired_browser_keys:
            activation = self._activations_by_browser.pop(key)
            self._activations_by_code.pop(activation.code_digest, None)
        expired_session_keys = [
            key for key, stored in self._sessions.items() if stored.principal.expires_at <= now
        ]
        for key in expired_session_keys:
            self._sessions.pop(key, None)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Dashboard clock must return a timezone-aware datetime")
        return now


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = ["DashboardSessionManager"]
