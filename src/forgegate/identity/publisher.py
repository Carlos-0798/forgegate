from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from forgegate.identity.models import AssuranceSignature
from forgegate.identity.service import IdentityError


@dataclass(frozen=True)
class PublishedAssuranceSignature:
    path: Path
    replayed: bool


def render_assurance_signature_json(signature: AssuranceSignature) -> str:
    return json.dumps(signature.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def publish_assurance_signature(
    signature: AssuranceSignature, output_root: Path
) -> PublishedAssuranceSignature:
    requested = output_root.expanduser()
    if requested.is_symlink() or (requested.exists() and not requested.is_dir()):
        raise IdentityError(
            "IDENTITY_OUTPUT_ROOT_INVALID", "output root must be a non-symlink directory"
        )
    root = requested.resolve(strict=False)
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IdentityError("IDENTITY_OUTPUT_IO", f"cannot create output root: {exc}") from exc
    payload = render_assurance_signature_json(signature).encode("utf-8")
    target = root / (
        "assurance-signature-" + signature.signature_id.removeprefix("sha256:") + ".json"
    )
    if target.is_symlink():
        raise IdentityError("IDENTITY_OUTPUT_CONFLICT", "signature target is an unsafe symlink")
    if target.exists():
        if not _matches_existing_file(target, payload):
            raise IdentityError("IDENTITY_OUTPUT_CONFLICT", "existing signature bytes differ")
        return PublishedAssuranceSignature(path=target, replayed=True)
    staging: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=".forgegate-signature-", dir=root)
        staging = Path(name)
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        try:
            staging.replace(target)
        except OSError:
            if target.exists() and _matches_existing_file(target, payload):
                return PublishedAssuranceSignature(path=target, replayed=True)
            raise
    except IdentityError:
        raise
    except OSError as exc:
        raise IdentityError("IDENTITY_OUTPUT_IO", f"cannot publish signature: {exc}") from exc
    finally:
        if staging is not None and staging.exists():
            with suppress(OSError):
                staging.unlink()
    return PublishedAssuranceSignature(path=target, replayed=False)


def _matches_existing_file(path: Path, expected: bytes) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        return path.read_bytes() == expected
    except OSError as exc:
        raise IdentityError(
            "IDENTITY_OUTPUT_CONFLICT", "cannot verify existing signature bytes"
        ) from exc


__all__ = [
    "PublishedAssuranceSignature",
    "publish_assurance_signature",
    "render_assurance_signature_json",
]
