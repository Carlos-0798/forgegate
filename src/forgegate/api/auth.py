from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal, Never

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import Field, field_validator, model_validator

from forgegate.audit import AuditActor
from forgegate.canonical import canonical_json
from forgegate.domain.models import SLUG_PATTERN, StrictModel
from forgegate.identity import (
    IdentityRole,
    IdentityStatus,
    SigningIdentity,
    TrustedIdentity,
    TrustStore,
)
from forgegate.identity.models import decode_canonical_base64

API_CHALLENGE_DOMAIN = b"ForgeGate API session challenge v1\x00"
MAX_API_CHALLENGE_DOCUMENT_BYTES = 64 * 1024
DEFAULT_MAX_PENDING_CHALLENGES = 1000
DEFAULT_MAX_ACTIVE_SESSIONS = 1000
DEFAULT_CHALLENGE_RATE_LIMIT = 60
DEFAULT_SESSION_RATE_LIMIT = 60
DEFAULT_AUTH_FAILURE_RATE_LIMIT = 120
DEFAULT_RATE_LIMIT_WINDOW = timedelta(minutes=1)
ACCESS_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
IDENTITY_ID_PATTERN = r"^sha256:[0-9a-f]{64}$"
CHALLENGE_ID_PATTERN = r"^chal-[0-9a-f]{32}$"
SERVER_INSTANCE_ID_PATTERN = r"^api-[0-9a-f]{32}$"

ProjectId = Annotated[str, Field(pattern=SLUG_PATTERN)]


class ApiChallengeRequest(StrictModel):
    identity_id: str = Field(pattern=IDENTITY_ID_PATTERN)
    role: IdentityRole
    project_ids: tuple[ProjectId, ...] = Field(min_length=1, max_length=100)

    @field_validator("project_ids")
    @classmethod
    def projects_must_be_canonical(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(value)) or len(value) != len(set(value)):
            raise ValueError("project_ids must be unique and canonically ordered")
        return value


class ApiAuthChallenge(StrictModel):
    schema_version: Literal["forgegate.api-auth-challenge.v1"] = "forgegate.api-auth-challenge.v1"
    challenge_id: str = Field(pattern=CHALLENGE_ID_PATTERN)
    server_instance_id: str = Field(pattern=SERVER_INSTANCE_ID_PATTERN)
    trust_store_id: str = Field(pattern=IDENTITY_ID_PATTERN)
    identity_id: str = Field(pattern=IDENTITY_ID_PATTERN)
    role: IdentityRole
    project_ids: tuple[ProjectId, ...] = Field(min_length=1, max_length=100)
    nonce_base64: str = Field(min_length=44, max_length=44)
    issued_at: datetime
    expires_at: datetime

    @field_validator("project_ids")
    @classmethod
    def challenge_projects_must_be_canonical(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return ApiChallengeRequest.projects_must_be_canonical(value)

    @field_validator("issued_at", "expires_at")
    @classmethod
    def timestamps_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("API challenge timestamps must include a UTC offset")
        return value

    @model_validator(mode="after")
    def challenge_must_be_bounded(self) -> ApiAuthChallenge:
        decode_canonical_base64(
            self.nonce_base64,
            expected_length=32,
            field_name="nonce_base64",
        )
        lifetime = self.expires_at - self.issued_at
        if lifetime <= timedelta(0) or lifetime > timedelta(minutes=5):
            raise ValueError(
                "API challenge lifetime must be positive and no more than five minutes"
            )
        return self


class ApiSessionCreateRequest(StrictModel):
    challenge_id: str = Field(pattern=CHALLENGE_ID_PATTERN)
    signature_base64: str = Field(min_length=88, max_length=88)

    @field_validator("signature_base64")
    @classmethod
    def signature_must_be_canonical(cls, value: str) -> str:
        decode_canonical_base64(
            value,
            expected_length=64,
            field_name="signature_base64",
        )
        return value


class ApiSessionResponse(StrictModel):
    schema_version: Literal["forgegate.api-session.v1"] = "forgegate.api-session.v1"
    session_id: str = Field(pattern=r"^sess-[0-9a-f]{32}$")
    identity: SigningIdentity
    role: IdentityRole
    project_ids: tuple[ProjectId, ...] = Field(min_length=1, max_length=100)
    authenticated_at: datetime
    expires_at: datetime
    token_type: Literal["Bearer"] = "Bearer"
    access_token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class ApiSessionRevocationResponse(StrictModel):
    schema_version: Literal["forgegate.api-session-revocation.v1"] = (
        "forgegate.api-session-revocation.v1"
    )
    session_id: str = Field(pattern=r"^sess-[0-9a-f]{32}$")
    revoked_at: datetime
    reason: Literal["self_logout", "operator_revocation"]

    @field_validator("revoked_at")
    @classmethod
    def revoked_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("session revocation time must include a UTC offset")
        return value


class ApiTrustStoreReloadResponse(StrictModel):
    schema_version: Literal["forgegate.api-trust-store-reload.v1"] = (
        "forgegate.api-trust-store-reload.v1"
    )
    previous_trust_store_id: str = Field(pattern=IDENTITY_ID_PATTERN)
    trust_store_id: str = Field(pattern=IDENTITY_ID_PATTERN)
    reloaded_at: datetime
    discarded_challenges: int = Field(ge=0)
    revoked_sessions: int = Field(ge=0)
    retained_sessions: int = Field(ge=0)

    @field_validator("reloaded_at")
    @classmethod
    def reloaded_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("trust-store reload time must include a UTC offset")
        return value


class ApiAuthenticationError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 401,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.code = code
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class ApiPrincipal:
    session_id: str
    identity: SigningIdentity
    role: IdentityRole
    project_ids: tuple[str, ...]
    trust_store_id: str
    authenticated_at: datetime
    expires_at: datetime

    def audit_actor(self) -> AuditActor:
        return AuditActor(
            identity_id=self.identity.identity_id,
            display_name=self.identity.display_name,
            role=self.role.value,
            session_id=self.session_id,
            trust_store_id=self.trust_store_id,
            authenticated_at=self.authenticated_at,
        )


@dataclass(frozen=True)
class _StoredSession:
    token_digest: str
    principal: ApiPrincipal


@dataclass
class _RateWindow:
    started_at: datetime
    count: int


class ApiAuthenticator:
    def __init__(
        self,
        trust_store: TrustStore,
        *,
        challenge_ttl: timedelta = timedelta(seconds=60),
        session_ttl: timedelta = timedelta(minutes=15),
        max_pending_challenges: int = DEFAULT_MAX_PENDING_CHALLENGES,
        max_active_sessions: int = DEFAULT_MAX_ACTIVE_SESSIONS,
        challenge_rate_limit: int = DEFAULT_CHALLENGE_RATE_LIMIT,
        session_rate_limit: int = DEFAULT_SESSION_RATE_LIMIT,
        auth_failure_rate_limit: int = DEFAULT_AUTH_FAILURE_RATE_LIMIT,
        rate_limit_window: timedelta = DEFAULT_RATE_LIMIT_WINDOW,
        trust_store_loader: Callable[[], TrustStore] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if challenge_ttl <= timedelta(0) or challenge_ttl > timedelta(minutes=5):
            raise ValueError("challenge TTL must be positive and no more than five minutes")
        if session_ttl <= timedelta(0) or session_ttl > timedelta(hours=1):
            raise ValueError("session TTL must be positive and no more than one hour")
        if not 1 <= max_pending_challenges <= 10_000:
            raise ValueError("max pending challenges must be between 1 and 10000")
        if not 1 <= max_active_sessions <= 10_000:
            raise ValueError("max active sessions must be between 1 and 10000")
        for name, value in (
            ("challenge rate limit", challenge_rate_limit),
            ("session rate limit", session_rate_limit),
            ("authentication failure rate limit", auth_failure_rate_limit),
        ):
            if not 1 <= value <= 10_000:
                raise ValueError(f"{name} must be between 1 and 10000")
        if rate_limit_window < timedelta(seconds=1) or rate_limit_window > timedelta(hours=1):
            raise ValueError("rate-limit window must be between one second and one hour")
        self._trust_store = trust_store
        self._challenge_ttl = challenge_ttl
        self._session_ttl = session_ttl
        self._max_pending_challenges = max_pending_challenges
        self._max_active_sessions = max_active_sessions
        self._challenge_rate_limit = challenge_rate_limit
        self._session_rate_limit = session_rate_limit
        self._auth_failure_rate_limit = auth_failure_rate_limit
        self._rate_limit_window = rate_limit_window
        self._trust_store_loader = trust_store_loader
        self._clock = clock or (lambda: datetime.now(UTC))
        self._server_instance_id = "api-" + secrets.token_hex(16)
        self._challenges: dict[str, ApiAuthChallenge] = {}
        self._sessions: dict[str, _StoredSession] = {}
        self._rate_windows: dict[str, _RateWindow] = {}
        self._lock = threading.RLock()

    @property
    def trust_store_id(self) -> str:
        with self._lock:
            return self._trust_store.trust_store_id

    def consume_endpoint_request(self, endpoint: Literal["challenge", "session"]) -> None:
        """Count an HTTP authentication request before body-model validation."""
        limit = self._challenge_rate_limit if endpoint == "challenge" else self._session_rate_limit
        self._consume_rate(endpoint, limit, self._now())

    def issue_challenge(
        self,
        request: ApiChallengeRequest,
        *,
        endpoint_rate_checked: bool = False,
    ) -> ApiAuthChallenge:
        now = self._now()
        if not endpoint_rate_checked:
            self._consume_rate("challenge", self._challenge_rate_limit, now)
        with self._lock:
            self._purge_expired(now)
            try:
                trusted = self._authorize_identity_in(
                    self._trust_store,
                    request.identity_id,
                    request.role,
                    request.project_ids,
                )
            except ApiAuthenticationError as exc:
                raise ApiAuthenticationError(
                    "API_CHALLENGE_AUTHORITY_DENIED",
                    "identity or requested session authority is denied",
                ) from exc
            if len(self._challenges) >= self._max_pending_challenges:
                raise ApiAuthenticationError(
                    "API_CHALLENGE_CAPACITY_REACHED",
                    "pending challenge capacity is exhausted",
                    status_code=503,
                )
            challenge = ApiAuthChallenge(
                challenge_id="chal-" + secrets.token_hex(16),
                server_instance_id=self._server_instance_id,
                trust_store_id=self._trust_store.trust_store_id,
                identity_id=trusted.identity.identity_id,
                role=request.role,
                project_ids=request.project_ids,
                nonce_base64=base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
                issued_at=now,
                expires_at=now + self._challenge_ttl,
            )
            self._challenges[challenge.challenge_id] = challenge
        return challenge

    def create_session(
        self,
        request: ApiSessionCreateRequest,
        *,
        endpoint_rate_checked: bool = False,
    ) -> ApiSessionResponse:
        now = self._now()
        if not endpoint_rate_checked:
            self._consume_rate("session", self._session_rate_limit, now)
        with self._lock:
            self._purge_expired(now)
            challenge = self._challenges.pop(request.challenge_id, None)
        if challenge is None:
            raise ApiAuthenticationError(
                "API_CHALLENGE_INVALID",
                "challenge is unknown, expired, or already consumed",
            )
        trusted = self._authorize_identity(
            challenge.identity_id, challenge.role, challenge.project_ids
        )
        public_key = Ed25519PublicKey.from_public_bytes(
            decode_canonical_base64(
                trusted.identity.public_key_base64,
                expected_length=32,
                field_name="public_key_base64",
            )
        )
        signature = decode_canonical_base64(
            request.signature_base64,
            expected_length=64,
            field_name="signature_base64",
        )
        try:
            public_key.verify(signature, api_challenge_payload(challenge))
        except (InvalidSignature, ValueError) as exc:
            raise ApiAuthenticationError(
                "API_CHALLENGE_SIGNATURE_INVALID",
                "Ed25519 challenge signature verification failed",
            ) from exc
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        principal = ApiPrincipal(
            session_id="sess-" + secrets.token_hex(16),
            identity=trusted.identity,
            role=challenge.role,
            project_ids=challenge.project_ids,
            trust_store_id=self._trust_store.trust_store_id,
            authenticated_at=now,
            expires_at=now + self._session_ttl,
        )
        with self._lock:
            self._purge_expired(now)
            current_trusted = self._authorize_identity_in(
                self._trust_store,
                challenge.identity_id,
                challenge.role,
                challenge.project_ids,
            )
            if current_trusted.identity != trusted.identity:
                raise ApiAuthenticationError(
                    "API_CHALLENGE_INVALID",
                    "challenge identity no longer matches the trust record",
                )
            if len(self._sessions) >= self._max_active_sessions:
                raise ApiAuthenticationError(
                    "API_SESSION_CAPACITY_REACHED",
                    "active session capacity is exhausted",
                    status_code=503,
                )
            self._sessions[digest] = _StoredSession(token_digest=digest, principal=principal)
        return ApiSessionResponse(
            session_id=principal.session_id,
            identity=principal.identity,
            role=principal.role,
            project_ids=principal.project_ids,
            authenticated_at=principal.authenticated_at,
            expires_at=principal.expires_at,
            access_token=token,
        )

    def authenticate(self, authorization: str | None) -> ApiPrincipal:
        if authorization is None or not authorization.startswith("Bearer "):
            self._raise_auth_failure(
                "API_AUTHENTICATION_REQUIRED",
                "a ForgeGate Bearer session is required",
            )
        token = authorization.removeprefix("Bearer ")
        if ACCESS_TOKEN_PATTERN.fullmatch(token) is None:
            self._raise_auth_failure(
                "API_SESSION_INVALID",
                "Bearer session token is invalid",
            )
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        now = self._now()
        with self._lock:
            self._purge_expired(now)
            stored = self._sessions.get(digest)
        if stored is None or not hmac.compare_digest(stored.token_digest, digest):
            self._raise_auth_failure(
                "API_SESSION_INVALID",
                "Bearer session token is invalid or expired",
                now=now,
            )
        principal = stored.principal
        trusted = self._authorize_identity(
            principal.identity.identity_id,
            principal.role,
            principal.project_ids,
        )
        if trusted.identity != principal.identity:
            raise ApiAuthenticationError(
                "API_SESSION_INVALID",
                "session identity no longer matches the trust record",
            )
        return principal

    def logout(self, principal: ApiPrincipal) -> ApiSessionRevocationResponse:
        return self._remove_session(
            principal,
            principal.session_id,
            reason="self_logout",
            require_operator=False,
        )

    def revoke_session(
        self,
        principal: ApiPrincipal,
        session_id: str,
    ) -> ApiSessionRevocationResponse:
        return self._remove_session(
            principal,
            session_id,
            reason="operator_revocation",
            require_operator=True,
        )

    def reload_trust_store(self, principal: ApiPrincipal) -> ApiTrustStoreReloadResponse:
        with self._lock:
            self._require_matching_principal(self._trust_store, principal)
            if principal.role is not IdentityRole.OPERATOR:
                raise ApiAuthenticationError(
                    "API_TRUST_STORE_RELOAD_FORBIDDEN",
                    "operator role is required for trust-store reload",
                    status_code=403,
                )
        if self._trust_store_loader is None:
            raise ApiAuthenticationError(
                "API_TRUST_STORE_RELOAD_UNAVAILABLE",
                "runtime trust-store reload is not configured",
                status_code=503,
            )
        try:
            new_store = self._trust_store_loader()
        except Exception as exc:
            raise ApiAuthenticationError(
                "API_TRUST_STORE_RELOAD_FAILED",
                "configured trust store could not be loaded and validated",
                status_code=503,
            ) from exc
        if not isinstance(new_store, TrustStore):
            raise ApiAuthenticationError(
                "API_TRUST_STORE_RELOAD_FAILED",
                "configured trust-store loader returned an invalid document",
                status_code=503,
            )
        now = self._now()
        with self._lock:
            self._purge_expired(now)
            previous = self._trust_store
            self._require_matching_principal(previous, principal)
            all_projects = self._trust_store_projects(previous) | self._trust_store_projects(
                new_store
            )
            if not all_projects.issubset(principal.project_ids):
                raise ApiAuthenticationError(
                    "API_TRUST_STORE_RELOAD_FORBIDDEN",
                    "operator session must cover every project in the current and new trust stores",
                    status_code=403,
                )
            self._require_matching_principal(new_store, principal)
            if new_store.trust_store_id == previous.trust_store_id:
                return ApiTrustStoreReloadResponse(
                    previous_trust_store_id=previous.trust_store_id,
                    trust_store_id=new_store.trust_store_id,
                    reloaded_at=now,
                    discarded_challenges=0,
                    revoked_sessions=0,
                    retained_sessions=len(self._sessions),
                )
            discarded_challenges = len(self._challenges)
            self._challenges.clear()
            retained: dict[str, _StoredSession] = {}
            for digest, stored in self._sessions.items():
                try:
                    self._require_matching_principal(new_store, stored.principal)
                except ApiAuthenticationError:
                    continue
                retained[digest] = stored
            revoked_sessions = len(self._sessions) - len(retained)
            self._sessions = retained
            self._trust_store = new_store
            return ApiTrustStoreReloadResponse(
                previous_trust_store_id=previous.trust_store_id,
                trust_store_id=new_store.trust_store_id,
                reloaded_at=now,
                discarded_challenges=discarded_challenges,
                revoked_sessions=revoked_sessions,
                retained_sessions=len(retained),
            )

    def require_project(
        self,
        principal: ApiPrincipal,
        project_id: str,
        *,
        write: bool = False,
        audit: bool = False,
    ) -> None:
        if project_id not in principal.project_ids:
            raise ApiAuthenticationError(
                "API_PROJECT_FORBIDDEN",
                "session is not authorized for the requested project",
                status_code=403,
            )
        if (write or audit) and principal.role is not IdentityRole.OPERATOR:
            raise ApiAuthenticationError(
                "API_ROLE_FORBIDDEN",
                "operator role is required for this operation",
                status_code=403,
            )

    def require_global_security_audit(self, principal: ApiPrincipal) -> None:
        """Require an active operator session covering the whole current trust store."""
        with self._lock:
            self._require_matching_principal(self._trust_store, principal)
            all_projects = self._trust_store_projects(self._trust_store)
            if principal.role is not IdentityRole.OPERATOR or not all_projects.issubset(
                principal.project_ids
            ):
                raise ApiAuthenticationError(
                    "API_SECURITY_AUDIT_FORBIDDEN",
                    "global operator authority is required for API security-event access",
                    status_code=403,
                )

    def _authorize_identity(
        self,
        identity_id: str,
        role: IdentityRole,
        project_ids: tuple[str, ...],
    ) -> TrustedIdentity:
        with self._lock:
            return self._authorize_identity_in(self._trust_store, identity_id, role, project_ids)

    @staticmethod
    def _authorize_identity_in(
        trust_store: TrustStore,
        identity_id: str,
        role: IdentityRole,
        project_ids: tuple[str, ...],
    ) -> TrustedIdentity:
        trusted = next(
            (item for item in trust_store.identities if item.identity.identity_id == identity_id),
            None,
        )
        if trusted is None or trusted.status is not IdentityStatus.ACTIVE:
            raise ApiAuthenticationError(
                "API_IDENTITY_DENIED",
                "identity is not active in the configured trust store",
            )
        if role not in trusted.roles:
            raise ApiAuthenticationError(
                "API_ROLE_DENIED",
                "identity is not trusted for the requested role",
                status_code=403,
            )
        if not set(project_ids).issubset(trusted.project_ids):
            raise ApiAuthenticationError(
                "API_PROJECT_DENIED",
                "identity is not trusted for every requested project",
                status_code=403,
            )
        return trusted

    def _require_matching_principal(
        self,
        trust_store: TrustStore,
        principal: ApiPrincipal,
    ) -> TrustedIdentity:
        trusted = self._authorize_identity_in(
            trust_store,
            principal.identity.identity_id,
            principal.role,
            principal.project_ids,
        )
        if trusted.identity != principal.identity:
            raise ApiAuthenticationError(
                "API_SESSION_INVALID",
                "session identity no longer matches the trust record",
            )
        return trusted

    def _remove_session(
        self,
        principal: ApiPrincipal,
        session_id: str,
        *,
        reason: Literal["self_logout", "operator_revocation"],
        require_operator: bool,
    ) -> ApiSessionRevocationResponse:
        now = self._now()
        with self._lock:
            self._purge_expired(now)
            self._require_matching_principal(self._trust_store, principal)
            if require_operator and principal.role is not IdentityRole.OPERATOR:
                raise ApiAuthenticationError(
                    "API_ROLE_FORBIDDEN",
                    "operator role is required for session revocation",
                    status_code=403,
                )
            found = next(
                (
                    (digest, stored)
                    for digest, stored in self._sessions.items()
                    if stored.principal.session_id == session_id
                ),
                None,
            )
            if found is None:
                raise ApiAuthenticationError(
                    "API_SESSION_NOT_FOUND",
                    "session is unavailable or outside the caller's authority",
                    status_code=404,
                )
            digest, stored = found
            target = stored.principal
            if reason == "self_logout":
                authorized = target == principal
            else:
                authorized = set(target.project_ids).issubset(principal.project_ids)
            if not authorized:
                raise ApiAuthenticationError(
                    "API_SESSION_NOT_FOUND",
                    "session is unavailable or outside the caller's authority",
                    status_code=404,
                )
            del self._sessions[digest]
        return ApiSessionRevocationResponse(
            session_id=session_id,
            revoked_at=now,
            reason=reason,
        )

    def _raise_auth_failure(
        self,
        code: str,
        message: str,
        *,
        now: datetime | None = None,
    ) -> Never:
        self._consume_rate(
            "authentication_failure",
            self._auth_failure_rate_limit,
            now or self._now(),
        )
        raise ApiAuthenticationError(code, message)

    def _consume_rate(self, scope: str, limit: int, now: datetime) -> None:
        with self._lock:
            window = self._rate_windows.get(scope)
            if window is None or now >= window.started_at + self._rate_limit_window:
                self._rate_windows[scope] = _RateWindow(started_at=now, count=1)
                return
            if window.count >= limit:
                retry_after = max(
                    1,
                    math.ceil((window.started_at + self._rate_limit_window - now).total_seconds()),
                )
                raise ApiAuthenticationError(
                    "API_AUTH_RATE_LIMITED",
                    "in-process authentication request limit exceeded",
                    status_code=429,
                    retry_after_seconds=retry_after,
                )
            window.count += 1

    @staticmethod
    def _trust_store_projects(trust_store: TrustStore) -> set[str]:
        return {
            project_id for trusted in trust_store.identities for project_id in trusted.project_ids
        }

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("authentication clock must return a timezone-aware timestamp")
        return value.astimezone(UTC)

    def _purge_expired(self, now: datetime) -> None:
        self._challenges = {
            key: value for key, value in self._challenges.items() if value.expires_at > now
        }
        self._sessions = {
            key: value for key, value in self._sessions.items() if value.principal.expires_at > now
        }


def api_challenge_payload(challenge: ApiAuthChallenge) -> bytes:
    return API_CHALLENGE_DOMAIN + canonical_json(challenge.model_dump(mode="json")).encode("utf-8")


def sign_api_challenge(
    challenge: ApiAuthChallenge,
    *,
    identity: SigningIdentity,
    private_key: Ed25519PrivateKey,
) -> ApiSessionCreateRequest:
    public_bytes = private_key.public_key().public_bytes_raw()
    expected = base64.b64encode(public_bytes).decode("ascii")
    if identity.identity_id != challenge.identity_id or identity.public_key_base64 != expected:
        raise ApiAuthenticationError(
            "API_CHALLENGE_IDENTITY_MISMATCH",
            "private key and identity must match the challenged identity",
            status_code=400,
        )
    signature = private_key.sign(api_challenge_payload(challenge))
    return ApiSessionCreateRequest(
        challenge_id=challenge.challenge_id,
        signature_base64=base64.b64encode(signature).decode("ascii"),
    )


def load_api_challenge(path: Path) -> ApiAuthChallenge:
    requested = path.expanduser()
    if requested.is_symlink() or not requested.is_file():
        raise ApiAuthenticationError(
            "API_CHALLENGE_DOCUMENT_INVALID",
            "challenge document must be a regular file",
            status_code=400,
        )
    try:
        size = requested.stat().st_size
        if size == 0 or size > MAX_API_CHALLENGE_DOCUMENT_BYTES:
            raise ApiAuthenticationError(
                "API_CHALLENGE_DOCUMENT_INVALID",
                "challenge document has an invalid byte size",
                status_code=400,
            )
        payload = requested.read_bytes()
    except ApiAuthenticationError:
        raise
    except OSError as exc:
        raise ApiAuthenticationError(
            "API_CHALLENGE_DOCUMENT_IO",
            f"cannot read challenge document: {exc}",
            status_code=400,
        ) from exc
    if len(payload) != size:
        raise ApiAuthenticationError(
            "API_CHALLENGE_DOCUMENT_CHANGED",
            "challenge document changed while reading",
            status_code=400,
        )
    try:
        raw = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        return ApiAuthChallenge.model_validate(raw)
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ApiAuthenticationError(
            "API_CHALLENGE_DOCUMENT_INVALID",
            f"cannot parse strict challenge JSON: {exc}",
            status_code=400,
        ) from exc


def _unique_object(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value is not allowed: {value}")


__all__ = [
    "API_CHALLENGE_DOMAIN",
    "ApiAuthChallenge",
    "ApiAuthenticationError",
    "ApiAuthenticator",
    "ApiChallengeRequest",
    "ApiPrincipal",
    "ApiSessionCreateRequest",
    "ApiSessionResponse",
    "ApiSessionRevocationResponse",
    "ApiTrustStoreReloadResponse",
    "api_challenge_payload",
    "load_api_challenge",
    "sign_api_challenge",
]
