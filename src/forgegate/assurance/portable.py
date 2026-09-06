from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from forgegate.assurance.models import (
    AssuranceBundle,
    AssuranceBundleManifest,
    create_assurance_manifest,
)
from forgegate.bounded_parsing import enforce_json_structure_limits

ASSURANCE_BUNDLE_FILES = frozenset({"README.md", "assurance-bundle.json", "manifest.json"})
MAX_ASSURANCE_JSON_BYTES = 16 * 1024 * 1024
MAX_ASSURANCE_AUXILIARY_BYTES = 64 * 1024
MAX_ASSURANCE_JSON_NODES = 500_000
MAX_ASSURANCE_JSON_DEPTH = 64
MAX_ASSURANCE_ARCHIVE_BYTES = (
    MAX_ASSURANCE_JSON_BYTES + (2 * MAX_ASSURANCE_AUXILIARY_BYTES) + (16 * 1024)
)


class AssuranceBundleError(RuntimeError):
    """Stable portable-assurance publication or verification failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class PublishedAssuranceBundle:
    directory: Path
    bundle_path: Path
    readme_path: Path
    manifest_path: Path
    replayed: bool


@dataclass(frozen=True)
class VerifiedAssuranceBundle:
    directory: Path
    bundle: AssuranceBundle
    manifest: AssuranceBundleManifest


def render_assurance_bundle_json(bundle: AssuranceBundle) -> str:
    return json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def render_assurance_bundle_readme(bundle: AssuranceBundle) -> str:
    candidate = bundle.attestation.candidate
    evaluation = bundle.attestation.policy_evaluation
    assert evaluation is not None
    return "\n".join(
        (
            "# ForgeGate portable assurance bundle",
            "",
            f"- Bundle: `{bundle.bundle_id}`",
            f"- Project: `{candidate.project_id}`",
            f"- Candidate: `{candidate.candidate_id}`",
            f"- Version: `{candidate.version}`",
            f"- Commit: `{candidate.commit_sha}`",
            f"- Decision: **{evaluation.decision.value}**",
            f"- Assurance: `{bundle.assurance}`",
            "",
            "## Offline verification",
            "",
            "```text",
            "forgegate verify-assurance <this-directory>",
            "```",
            "",
            "The verifier checks exact directory contents, canonical file bytes, SHA-256",
            "manifest entries, all document identities, and cross-document associations.",
            "",
            "## Evidence boundary",
            "",
            "This unsigned local bundle embeds the frozen project profile, retained evidence",
            "binding, exact policy bytes, evaluation, lifecycle chain, and attestation. Source",
            "artifact bytes referenced by collector receipts are not embedded, so this bundle",
            "does not independently re-run collectors, authenticate producers, prove trusted",
            "time, or establish hardware, bench, field, or production verification.",
            "",
        )
    )


def render_assurance_bundle_archive(bundle: AssuranceBundle) -> bytes:
    """Render the canonical three-file bundle as a deterministic rootless ZIP."""
    output = BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in sorted(_canonical_assurance_files(bundle).items()):
            member = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            member.compress_type = zipfile.ZIP_STORED
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            archive.writestr(member, payload)
    rendered = output.getvalue()
    if len(rendered) > MAX_ASSURANCE_ARCHIVE_BYTES:
        raise AssuranceBundleError(
            "ASSURANCE_ARCHIVE_TOO_LARGE", "rendered assurance archive exceeds byte limit"
        )
    return rendered


def publish_assurance_bundle(
    bundle: AssuranceBundle,
    output_root: Path,
) -> PublishedAssuranceBundle:
    root = _prepare_output_root(output_root)
    expected = _canonical_assurance_files(bundle)
    target = root / ("assurance-" + bundle.bundle_id.removeprefix("sha256:"))
    if target.is_symlink():
        raise AssuranceBundleError(
            "ASSURANCE_OUTPUT_CONFLICT", "assurance output target is an unsafe symlink"
        )
    if target.exists():
        _verify_existing_bytes(target, expected)
        verify_assurance_bundle(target)
        return _published(target, replayed=True)
    try:
        staging = Path(tempfile.mkdtemp(prefix=".forgegate-assurance-", dir=root))
    except OSError as exc:
        raise AssuranceBundleError(
            "ASSURANCE_OUTPUT_IO", f"cannot create staging directory: {exc}"
        ) from exc
    try:
        for name, payload in expected.items():
            _write_file(staging / name, payload)
        try:
            staging.replace(target)
        except OSError:
            if target.exists():
                _verify_existing_bytes(target, expected)
                verify_assurance_bundle(target)
                return _published(target, replayed=True)
            raise
    except AssuranceBundleError:
        raise
    except OSError as exc:
        raise AssuranceBundleError(
            "ASSURANCE_OUTPUT_IO", f"cannot publish assurance bundle: {exc}"
        ) from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return _published(target, replayed=False)


def verify_assurance_bundle(directory: Path) -> VerifiedAssuranceBundle:
    target = directory.expanduser()
    if target.is_symlink() or not target.is_dir():
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_INVALID", "bundle path must be a non-symlink directory"
        )
    target = target.resolve(strict=True)
    entries = _safe_entries(target)
    if entries != ASSURANCE_BUNDLE_FILES:
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_CONTENTS_INVALID", "bundle directory has unexpected contents"
        )
    raw_bundle = _read_regular_file(target / "assurance-bundle.json", MAX_ASSURANCE_JSON_BYTES)
    raw_readme = _read_regular_file(target / "README.md", MAX_ASSURANCE_AUXILIARY_BYTES)
    raw_manifest = _read_regular_file(target / "manifest.json", MAX_ASSURANCE_AUXILIARY_BYTES)
    try:
        bundle = AssuranceBundle.model_validate(_strict_json(raw_bundle))
        manifest = AssuranceBundleManifest.model_validate(_strict_json(raw_manifest))
    except (ValidationError, ValueError) as exc:
        raise AssuranceBundleError("ASSURANCE_BUNDLE_DOCUMENT_INVALID", str(exc)) from exc
    if manifest.bundle_id != bundle.bundle_id:
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_MANIFEST_MISMATCH", "manifest bundle ID does not match bundle"
        )
    expected_name = "assurance-" + bundle.bundle_id.removeprefix("sha256:")
    if target.name != expected_name:
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_DIRECTORY_MISMATCH",
            "bundle directory name does not match content identity",
        )
    expected_bundle = render_assurance_bundle_json(bundle).encode("utf-8")
    expected_readme = render_assurance_bundle_readme(bundle).encode("utf-8")
    expected_manifest = create_assurance_manifest(
        bundle,
        bundle_json=expected_bundle,
        readme=expected_readme,
    )
    if (
        raw_bundle != expected_bundle
        or raw_readme != expected_readme
        or manifest != expected_manifest
        or raw_manifest != _render_manifest(expected_manifest).encode("utf-8")
    ):
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_BYTES_MISMATCH",
            "bundle files do not match canonical content and manifest",
        )
    return VerifiedAssuranceBundle(directory=target, bundle=bundle, manifest=manifest)


def _render_manifest(manifest: AssuranceBundleManifest) -> str:
    return json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def _canonical_assurance_files(bundle: AssuranceBundle) -> dict[str, bytes]:
    bundle_bytes = render_assurance_bundle_json(bundle).encode("utf-8")
    readme_bytes = render_assurance_bundle_readme(bundle).encode("utf-8")
    if len(bundle_bytes) > MAX_ASSURANCE_JSON_BYTES:
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_FILE_TOO_LARGE",
            "canonical assurance-bundle.json exceeds byte limit",
        )
    if len(readme_bytes) > MAX_ASSURANCE_AUXILIARY_BYTES:
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_FILE_TOO_LARGE",
            "canonical README.md exceeds byte limit",
        )
    manifest = create_assurance_manifest(
        bundle,
        bundle_json=bundle_bytes,
        readme=readme_bytes,
    )
    files = {
        "README.md": readme_bytes,
        "assurance-bundle.json": bundle_bytes,
        "manifest.json": _render_manifest(manifest).encode("utf-8"),
    }
    if len(files["manifest.json"]) > MAX_ASSURANCE_AUXILIARY_BYTES:
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_FILE_TOO_LARGE",
            "canonical manifest.json exceeds byte limit",
        )
    return files


def _prepare_output_root(output_root: Path) -> Path:
    requested = output_root.expanduser()
    if requested.is_symlink() or (requested.exists() and not requested.is_dir()):
        raise AssuranceBundleError(
            "ASSURANCE_OUTPUT_ROOT_INVALID", "output root must be a non-symlink directory"
        )
    root = requested.resolve(strict=False)
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AssuranceBundleError(
            "ASSURANCE_OUTPUT_IO", f"cannot create output root: {exc}"
        ) from exc
    return root


def _published(target: Path, *, replayed: bool) -> PublishedAssuranceBundle:
    return PublishedAssuranceBundle(
        directory=target,
        bundle_path=target / "assurance-bundle.json",
        readme_path=target / "README.md",
        manifest_path=target / "manifest.json",
        replayed=replayed,
    )


def _safe_entries(target: Path) -> frozenset[str]:
    try:
        return frozenset(entry.name for entry in target.iterdir())
    except OSError as exc:
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_IO", f"cannot inspect bundle directory: {exc}"
        ) from exc


def _verify_existing_bytes(target: Path, expected: dict[str, bytes]) -> None:
    if target.is_symlink() or not target.is_dir():
        raise AssuranceBundleError(
            "ASSURANCE_OUTPUT_CONFLICT", "assurance output target is not a safe directory"
        )
    if _safe_entries(target) != ASSURANCE_BUNDLE_FILES:
        raise AssuranceBundleError(
            "ASSURANCE_OUTPUT_CONFLICT", "existing assurance bundle has unexpected contents"
        )
    for name, payload in expected.items():
        path = target / name
        limit = (
            MAX_ASSURANCE_JSON_BYTES
            if name == "assurance-bundle.json"
            else MAX_ASSURANCE_AUXILIARY_BYTES
        )
        try:
            actual = _read_regular_file(path, limit)
        except AssuranceBundleError as exc:
            raise AssuranceBundleError("ASSURANCE_OUTPUT_CONFLICT", str(exc)) from exc
        if actual != payload:
            raise AssuranceBundleError(
                "ASSURANCE_OUTPUT_CONFLICT", "existing assurance bundle bytes differ"
            )


def _read_regular_file(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_FILE_INVALID",
            f"bundle member is not a safe regular file: {path.name}",
        )
    try:
        size = path.stat().st_size
        if size > limit:
            raise AssuranceBundleError(
                "ASSURANCE_BUNDLE_FILE_TOO_LARGE", f"bundle member exceeds byte limit: {path.name}"
            )
        payload = path.read_bytes()
    except AssuranceBundleError:
        raise
    except OSError as exc:
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_IO", f"cannot read bundle member {path.name}: {exc}"
        ) from exc
    if len(payload) != size:
        raise AssuranceBundleError(
            "ASSURANCE_BUNDLE_FILE_CHANGED", f"bundle member changed while reading: {path.name}"
        )
    return payload


def _strict_json(payload: bytes) -> dict[str, Any]:
    try:
        enforce_json_structure_limits(
            payload,
            max_nodes=MAX_ASSURANCE_JSON_NODES,
            max_depth=MAX_ASSURANCE_JSON_DEPTH,
        )
        text = payload.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: _reject_constant(value),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot parse strict UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("portable assurance document root must be an object")
    return value


def _unique_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value is not allowed: {value}")


def _write_file(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    except OSError as exc:
        raise AssuranceBundleError(
            "ASSURANCE_OUTPUT_IO", f"cannot stage assurance file: {exc}"
        ) from exc
