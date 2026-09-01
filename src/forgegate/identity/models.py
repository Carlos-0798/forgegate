from __future__ import annotations

import base64
import binascii
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from forgegate.canonical import sha256_fingerprint
from forgegate.domain.models import SHA256_PATTERN, SLUG_PATTERN, StrictModel

FINGERPRINT_PATTERN = r"^sha256:[0-9a-f]{64}$"
ED25519_PUBLIC_KEY_BYTES = 32
ED25519_SIGNATURE_BYTES = 64

ProjectId = Annotated[str, Field(pattern=SLUG_PATTERN)]


class IdentityRole(StrEnum):
    PRODUCER = "producer"
    OPERATOR = "operator"


class IdentityStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class SigningIdentity(StrictModel):
    schema_version: Literal["forgegate.signing-identity.v1"] = "forgegate.signing-identity.v1"
    identity_id: str = Field(pattern=FINGERPRINT_PATTERN)
    display_name: str = Field(min_length=1, max_length=120)
    algorithm: Literal["ed25519"] = "ed25519"
    public_key_base64: str = Field(min_length=44, max_length=44)

    @model_validator(mode="after")
    def identity_must_match_public_key(self) -> SigningIdentity:
        public_key = decode_canonical_base64(
            self.public_key_base64,
            expected_length=ED25519_PUBLIC_KEY_BYTES,
            field_name="public_key_base64",
        )
        expected = identity_fingerprint(self.algorithm, public_key)
        if self.identity_id != expected:
            raise ValueError("identity_id does not match the Ed25519 public key")
        return self


class TrustedIdentity(StrictModel):
    identity: SigningIdentity
    roles: tuple[IdentityRole, ...] = Field(min_length=1, max_length=2)
    project_ids: tuple[ProjectId, ...] = Field(min_length=1, max_length=100)
    status: IdentityStatus = IdentityStatus.ACTIVE

    @field_validator("roles")
    @classmethod
    def roles_must_be_unique_and_canonical(
        cls, value: tuple[IdentityRole, ...]
    ) -> tuple[IdentityRole, ...]:
        canonical = tuple(sorted(value, key=lambda item: item.value))
        if value != canonical or len(value) != len(set(value)):
            raise ValueError("trusted identity roles must be unique and canonically ordered")
        return value

    @field_validator("project_ids")
    @classmethod
    def projects_must_be_unique_and_canonical(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(value)) or len(value) != len(set(value)):
            raise ValueError("trusted project IDs must be unique and canonically ordered")
        return value


class TrustStore(StrictModel):
    schema_version: Literal["forgegate.trust-store.v1"] = "forgegate.trust-store.v1"
    trust_store_id: str = Field(pattern=FINGERPRINT_PATTERN)
    identities: tuple[TrustedIdentity, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def trust_store_must_be_canonical(self) -> TrustStore:
        identity_ids = tuple(item.identity.identity_id for item in self.identities)
        if identity_ids != tuple(sorted(identity_ids)) or len(identity_ids) != len(
            set(identity_ids)
        ):
            raise ValueError("trusted identities must have unique, canonical identity IDs")
        identity = self.model_dump(mode="json", exclude={"schema_version", "trust_store_id"})
        if self.trust_store_id != sha256_fingerprint(identity):
            raise ValueError("trust_store_id does not match trust-store content")
        return self


class AssuranceSignature(StrictModel):
    schema_version: Literal["forgegate.assurance-signature.v1"] = "forgegate.assurance-signature.v1"
    signature_id: str = Field(pattern=FINGERPRINT_PATTERN)
    bundle_id: str = Field(pattern=FINGERPRINT_PATTERN)
    bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    signer: SigningIdentity
    role: IdentityRole
    signed_at: datetime
    signature_base64: str = Field(min_length=88, max_length=88)

    @field_validator("signed_at")
    @classmethod
    def signed_time_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("signed_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def signature_document_must_be_canonical(self) -> AssuranceSignature:
        decode_canonical_base64(
            self.signature_base64,
            expected_length=ED25519_SIGNATURE_BYTES,
            field_name="signature_base64",
        )
        if self.signature_id != sha256_fingerprint(signature_statement(self)):
            raise ValueError("signature_id does not match the signed statement")
        return self


def identity_fingerprint(algorithm: str, public_key: bytes) -> str:
    return sha256_fingerprint(
        {
            "algorithm": algorithm,
            "public_key_base64": base64.b64encode(public_key).decode("ascii"),
        }
    )


def create_signing_identity(*, display_name: str, public_key: bytes) -> SigningIdentity:
    encoded = base64.b64encode(public_key).decode("ascii")
    return SigningIdentity(
        identity_id=identity_fingerprint("ed25519", public_key),
        display_name=display_name,
        public_key_base64=encoded,
    )


def create_trust_store(identities: tuple[TrustedIdentity, ...]) -> TrustStore:
    ordered = tuple(sorted(identities, key=lambda item: item.identity.identity_id))
    identity = {
        "identities": [item.model_dump(mode="json") for item in ordered],
    }
    return TrustStore(trust_store_id=sha256_fingerprint(identity), identities=ordered)


def signature_statement(signature: AssuranceSignature) -> dict[str, object]:
    return {
        "bundle_id": signature.bundle_id,
        "bundle_sha256": signature.bundle_sha256,
        "signer": signature.signer.model_dump(mode="json"),
        "role": signature.role.value,
        "signed_at": signature.signed_at.isoformat(),
    }


def decode_canonical_base64(value: str, *, expected_length: int, field_name: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{field_name} must be canonical base64") from exc
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError(f"{field_name} must be canonical base64")
    if len(decoded) != expected_length:
        raise ValueError(f"{field_name} has an invalid decoded length")
    return decoded


__all__ = [
    "AssuranceSignature",
    "IdentityRole",
    "IdentityStatus",
    "SigningIdentity",
    "TrustStore",
    "TrustedIdentity",
    "create_signing_identity",
    "create_trust_store",
    "decode_canonical_base64",
    "signature_statement",
]
