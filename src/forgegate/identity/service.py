from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import ValidationError

from forgegate.assurance import AssuranceBundle, render_assurance_bundle_json
from forgegate.canonical import canonical_json, sha256_fingerprint
from forgegate.identity.models import (
    AssuranceSignature,
    IdentityRole,
    IdentityStatus,
    SigningIdentity,
    TrustStore,
    create_signing_identity,
    decode_canonical_base64,
    signature_statement,
)

SIGNATURE_DOMAIN = b"ForgeGate assurance signature v1\x00"
MAX_PRIVATE_KEY_BYTES = 64 * 1024
MAX_IDENTITY_DOCUMENT_BYTES = 1024 * 1024
type IdentityDocument = SigningIdentity | TrustStore | AssuranceSignature

IDENTITY_DOCUMENT_MODELS: dict[str, type[SigningIdentity | TrustStore | AssuranceSignature]] = {
    "forgegate.signing-identity.v1": SigningIdentity,
    "forgegate.trust-store.v1": TrustStore,
    "forgegate.assurance-signature.v1": AssuranceSignature,
}


class IdentityError(RuntimeError):
    """Stable identity, signing, or trust-verification failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class AuthenticatedAssurance:
    bundle_id: str
    candidate_id: str
    project_id: str
    identity_id: str
    display_name: str
    role: IdentityRole
    trust_store_id: str


def load_ed25519_private_key(path: Path) -> Ed25519PrivateKey:
    requested = path.expanduser()
    if requested.is_symlink() or not requested.is_file():
        raise IdentityError("IDENTITY_PRIVATE_KEY_INVALID", "private key must be a regular file")
    try:
        size = requested.stat().st_size
        if size == 0 or size > MAX_PRIVATE_KEY_BYTES:
            raise IdentityError(
                "IDENTITY_PRIVATE_KEY_INVALID", "private key has an invalid byte size"
            )
        payload = requested.read_bytes()
    except IdentityError:
        raise
    except OSError as exc:
        raise IdentityError("IDENTITY_PRIVATE_KEY_IO", f"cannot read private key: {exc}") from exc
    if len(payload) != size:
        raise IdentityError("IDENTITY_PRIVATE_KEY_CHANGED", "private key changed while reading")
    try:
        key = serialization.load_pem_private_key(payload, password=None)
    except (TypeError, ValueError) as exc:
        raise IdentityError(
            "IDENTITY_PRIVATE_KEY_INVALID",
            "private key must be an unencrypted PKCS8 Ed25519 PEM",
        ) from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise IdentityError("IDENTITY_PRIVATE_KEY_INVALID", "private key is not Ed25519")
    return key


def load_identity_document(path: Path) -> IdentityDocument:
    requested = path.expanduser()
    if requested.is_symlink() or not requested.is_file():
        raise IdentityError("IDENTITY_DOCUMENT_INVALID", "identity document must be a regular file")
    try:
        size = requested.stat().st_size
        if size == 0 or size > MAX_IDENTITY_DOCUMENT_BYTES:
            raise IdentityError(
                "IDENTITY_DOCUMENT_INVALID", "identity document has an invalid byte size"
            )
        payload = requested.read_bytes()
    except IdentityError:
        raise
    except OSError as exc:
        raise IdentityError(
            "IDENTITY_DOCUMENT_IO", f"cannot read identity document: {exc}"
        ) from exc
    if len(payload) != size:
        raise IdentityError("IDENTITY_DOCUMENT_CHANGED", "identity document changed while reading")
    try:
        raw = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise IdentityError(
            "IDENTITY_DOCUMENT_INVALID", f"cannot parse strict UTF-8 JSON: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise IdentityError("IDENTITY_DOCUMENT_INVALID", "identity document root must be an object")
    schema_version = raw.get("schema_version")
    model = (
        IDENTITY_DOCUMENT_MODELS.get(schema_version) if isinstance(schema_version, str) else None
    )
    if model is None:
        raise IdentityError("IDENTITY_DOCUMENT_INVALID", "unsupported identity schema_version")
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise IdentityError("IDENTITY_DOCUMENT_INVALID", str(exc)) from exc


def derive_signing_identity(
    private_key: Ed25519PrivateKey, *, display_name: str
) -> SigningIdentity:
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return create_signing_identity(display_name=display_name, public_key=public_key)


def create_assurance_signature(
    bundle: AssuranceBundle,
    *,
    signer: SigningIdentity,
    role: IdentityRole,
    signed_at: datetime,
    private_key: Ed25519PrivateKey,
) -> AssuranceSignature:
    derived = derive_signing_identity(private_key, display_name=signer.display_name)
    if derived != signer:
        raise IdentityError(
            "IDENTITY_PRIVATE_KEY_MISMATCH",
            "private key does not match the declared signing identity",
        )
    bundle_bytes = render_assurance_bundle_json(bundle).encode("utf-8")
    statement: dict[str, object] = {
        "bundle_id": bundle.bundle_id,
        "bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(),
        "signer": signer.model_dump(mode="json"),
        "role": role.value,
        "signed_at": signed_at.isoformat(),
    }
    signature = private_key.sign(_signature_payload(statement))
    return AssuranceSignature(
        signature_id=sha256_fingerprint(statement),
        bundle_id=bundle.bundle_id,
        bundle_sha256=hashlib.sha256(bundle_bytes).hexdigest(),
        signer=signer,
        role=role,
        signed_at=signed_at,
        signature_base64=base64.b64encode(signature).decode("ascii"),
    )


def verify_assurance_signature(
    bundle: AssuranceBundle,
    signature: AssuranceSignature,
    trust_store: TrustStore,
) -> AuthenticatedAssurance:
    bundle_bytes = render_assurance_bundle_json(bundle).encode("utf-8")
    if (
        signature.bundle_id != bundle.bundle_id
        or signature.bundle_sha256 != hashlib.sha256(bundle_bytes).hexdigest()
    ):
        raise IdentityError(
            "IDENTITY_BUNDLE_MISMATCH", "signature does not cover this assurance bundle"
        )
    public_key_bytes = decode_canonical_base64(
        signature.signer.public_key_base64,
        expected_length=32,
        field_name="public_key_base64",
    )
    signature_bytes = decode_canonical_base64(
        signature.signature_base64,
        expected_length=64,
        field_name="signature_base64",
    )
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
            signature_bytes,
            _signature_payload(signature_statement(signature)),
        )
    except (InvalidSignature, ValueError) as exc:
        raise IdentityError(
            "IDENTITY_SIGNATURE_INVALID", "Ed25519 signature verification failed"
        ) from exc
    trusted = next(
        (
            item
            for item in trust_store.identities
            if item.identity.identity_id == signature.signer.identity_id
        ),
        None,
    )
    if trusted is None:
        raise IdentityError("IDENTITY_NOT_TRUSTED", "signer is absent from the trust store")
    if trusted.identity != signature.signer:
        raise IdentityError(
            "IDENTITY_TRUST_RECORD_MISMATCH", "signer metadata differs from the trust record"
        )
    if trusted.status is IdentityStatus.REVOKED:
        raise IdentityError("IDENTITY_REVOKED", "signer is revoked by the trust store")
    if signature.role not in trusted.roles:
        raise IdentityError("IDENTITY_ROLE_DENIED", "signer is not trusted for the claimed role")
    project_id = bundle.attestation.candidate.project_id
    if project_id not in trusted.project_ids:
        raise IdentityError("IDENTITY_PROJECT_DENIED", "signer is not trusted for this project")
    return AuthenticatedAssurance(
        bundle_id=bundle.bundle_id,
        candidate_id=bundle.attestation.candidate.candidate_id,
        project_id=project_id,
        identity_id=signature.signer.identity_id,
        display_name=signature.signer.display_name,
        role=signature.role,
        trust_store_id=trust_store.trust_store_id,
    )


def _signature_payload(statement: dict[str, object]) -> bytes:
    return SIGNATURE_DOMAIN + canonical_json(statement).encode("utf-8")


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
    "AuthenticatedAssurance",
    "IdentityError",
    "create_assurance_signature",
    "derive_signing_identity",
    "load_ed25519_private_key",
    "load_identity_document",
    "verify_assurance_signature",
]
