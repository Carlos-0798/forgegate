from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

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


class ApiAuthenticationError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 401) -> None:
        self.code = code
        self.status_code = status_code
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


class ApiAuthenticator:
    def __init__(
        self,
        trust_store: TrustStore,
        *,
        challenge_ttl: timedelta = timedelta(seconds=60),
        session_ttl: timedelta = timedelta(minutes=15),
        max_pending_challenges: int = DEFAULT_MAX_PENDING_CHALLENGES,
        max_active_sessions: int = DEFAULT_MAX_ACTIVE_SESSIONS,
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
        self._trust_store = trust_store
        self._challenge_ttl = challenge_ttl
        self._session_ttl = session_ttl
        self._max_pending_challenges = max_pending_challenges
        self._max_active_sessions = max_active_sessions
        self._clock = clock or (lambda: datetime.now(UTC))
        self._server_instance_id = "api-" + secrets.token_hex(16)
        self._challenges: dict[str, ApiAuthChallenge] = {}
        self._sessions: dict[str, _StoredSession] = {}
        self._lock = threading.Lock()

    @property
    def trust_store_id(self) -> str:
        return self._trust_store.trust_store_id

    def issue_challenge(self, request: ApiChallengeRequest) -> ApiAuthChallenge:
        try:
            trusted = self._authorize_identity(
                request.identity_id,
                request.role,
                request.project_ids,
            )
        except ApiAuthenticationError as exc:
            raise ApiAuthenticationError(
                "API_CHALLENGE_AUTHORITY_DENIED",
                "identity or requested session authority is denied",
            ) from exc
        now = self._now()
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
        with self._lock:
            self._purge_expired(now)
            if len(self._challenges) >= self._max_pending_challenges:
                raise ApiAuthenticationError(
                    "API_CHALLENGE_CAPACITY_REACHED",
                    "pending challenge capacity is exhausted",
                    status_code=503,
                )
            self._challenges[challenge.challenge_id] = challenge
        return challenge

    def create_session(self, request: ApiSessionCreateRequest) -> ApiSessionResponse:
        now = self._now()
        with self._lock:
            self._purge_expired(now)
            challenge = self._challenges.pop(request.challenge_id, None)
        if challenge is None:
            raise ApiAuthenticationError(
                "API_CHALLENGE_INVALID",
                "challenge is unknown, expired, or already consumed",
            )
        trusted = self._authorize_identity(
            challenge.identity_id,
            challenge.role,
            challenge.project_ids,
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
            raise ApiAuthenticationError(
                "API_AUTHENTICATION_REQUIRED",
                "a ForgeGate Bearer session is required",
            )
        token = authorization.removeprefix("Bearer ")
        if ACCESS_TOKEN_PATTERN.fullmatch(token) is None:
            raise ApiAuthenticationError(
                "API_SESSION_INVALID",
                "Bearer session token is invalid",
            )
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        now = self._now()
        with self._lock:
            self._purge_expired(now)
            stored = self._sessions.get(digest)
        if stored is None or not hmac.compare_digest(stored.token_digest, digest):
            raise ApiAuthenticationError(
                "API_SESSION_INVALID",
                "Bearer session token is invalid or expired",
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

    def _authorize_identity(
        self,
        identity_id: str,
        role: IdentityRole,
        project_ids: tuple[str, ...],
    ) -> TrustedIdentity:
        trusted = next(
            (
                item
                for item in self._trust_store.identities
                if item.identity.identity_id == identity_id
            ),
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
    "api_challenge_payload",
    "load_api_challenge",
    "sign_api_challenge",
]
