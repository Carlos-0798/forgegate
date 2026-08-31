from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from forgegate.attestations.models import ReleaseAttestation
from forgegate.attestations.service import render_attestation_json, render_attestation_markdown


class AttestationPublishError(RuntimeError):
    """Stable output-publication failure for an attestation bundle."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class PublishedAttestation:
    directory: Path
    json_path: Path
    markdown_path: Path
    replayed: bool


def publish_attestation_bundle(
    attestation: ReleaseAttestation,
    output_root: Path,
) -> PublishedAttestation:
    requested_root = output_root.expanduser()
    if requested_root.is_symlink() or (requested_root.exists() and not requested_root.is_dir()):
        raise AttestationPublishError(
            "ATTESTATION_OUTPUT_ROOT_INVALID", "output root must be a non-symlink directory"
        )
    root = requested_root.resolve(strict=False)
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AttestationPublishError(
            "ATTESTATION_OUTPUT_IO", f"cannot create output root: {exc}"
        ) from exc
    directory_name = "attestation-" + attestation.attestation_id.removeprefix("sha256:")
    target = root / directory_name
    json_bytes = render_attestation_json(attestation).encode("utf-8")
    markdown_bytes = render_attestation_markdown(attestation).encode("utf-8")
    if target.exists():
        _verify_existing(target, json_bytes, markdown_bytes)
        return PublishedAttestation(
            directory=target,
            json_path=target / "attestation.json",
            markdown_path=target / "attestation.md",
            replayed=True,
        )
    try:
        staging = Path(tempfile.mkdtemp(prefix=".forgegate-attestation-", dir=root))
    except OSError as exc:
        raise AttestationPublishError(
            "ATTESTATION_OUTPUT_IO", f"cannot create staging directory: {exc}"
        ) from exc
    try:
        _write_file(staging / "attestation.json", json_bytes)
        _write_file(staging / "attestation.md", markdown_bytes)
        try:
            staging.replace(target)
        except OSError:
            if target.exists():
                _verify_existing(target, json_bytes, markdown_bytes)
                return PublishedAttestation(
                    directory=target,
                    json_path=target / "attestation.json",
                    markdown_path=target / "attestation.md",
                    replayed=True,
                )
            raise
    except AttestationPublishError:
        raise
    except OSError as exc:
        raise AttestationPublishError(
            "ATTESTATION_OUTPUT_IO", f"cannot publish attestation bundle: {exc}"
        ) from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return PublishedAttestation(
        directory=target,
        json_path=target / "attestation.json",
        markdown_path=target / "attestation.md",
        replayed=False,
    )


def _verify_existing(target: Path, json_bytes: bytes, markdown_bytes: bytes) -> None:
    if not target.is_dir() or target.is_symlink():
        raise AttestationPublishError(
            "ATTESTATION_OUTPUT_CONFLICT", "attestation output target is not a safe directory"
        )
    try:
        entries = {entry.name for entry in target.iterdir()}
    except OSError as exc:
        raise AttestationPublishError(
            "ATTESTATION_OUTPUT_IO", f"cannot inspect existing attestation bundle: {exc}"
        ) from exc
    if entries != {"attestation.json", "attestation.md"}:
        raise AttestationPublishError(
            "ATTESTATION_OUTPUT_CONFLICT", "existing attestation bundle has unexpected contents"
        )
    json_path = target / "attestation.json"
    markdown_path = target / "attestation.md"
    if (
        json_path.is_symlink()
        or markdown_path.is_symlink()
        or not json_path.is_file()
        or not markdown_path.is_file()
    ):
        raise AttestationPublishError(
            "ATTESTATION_OUTPUT_CONFLICT", "existing attestation files are not safe regular files"
        )
    try:
        matches = (
            json_path.read_bytes() == json_bytes and markdown_path.read_bytes() == markdown_bytes
        )
    except OSError as exc:
        raise AttestationPublishError(
            "ATTESTATION_OUTPUT_IO", f"cannot read existing attestation bundle: {exc}"
        ) from exc
    if not matches:
        raise AttestationPublishError(
            "ATTESTATION_OUTPUT_CONFLICT", "existing attestation bytes differ"
        )


def _write_file(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    except OSError as exc:
        raise AttestationPublishError(
            "ATTESTATION_OUTPUT_IO", f"cannot stage attestation file: {exc}"
        ) from exc
