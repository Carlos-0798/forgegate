from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from forgegate.domain.models import ArtifactReference

DEFAULT_MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024


class ArtifactError(ValueError):
    code = "ARTIFACT_ERROR"


class ArtifactBoundaryError(ArtifactError):
    code = "ARTIFACT_BOUNDARY"


class ArtifactNotFoundError(ArtifactError):
    code = "ARTIFACT_NOT_FOUND"


class ArtifactReadError(ArtifactError):
    code = "ARTIFACT_READ_ERROR"


class ArtifactTooLargeError(ArtifactError):
    code = "ARTIFACT_TOO_LARGE"


class ArtifactChangedError(ArtifactError):
    code = "ARTIFACT_CHANGED"


@dataclass(frozen=True, slots=True)
class RegisteredArtifact:
    reference: ArtifactReference
    content: bytes


class ArtifactRegistry:
    """Registers immutable artifact bytes inside one explicit filesystem root."""

    def __init__(self, root: Path, *, max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        try:
            resolved_root = root.resolve(strict=True)
        except OSError as exc:
            raise ArtifactBoundaryError("artifact root does not exist") from exc
        if not resolved_root.is_dir():
            raise ArtifactBoundaryError("artifact root must be a directory")
        self._root = resolved_root
        self._max_bytes = max_bytes
        self._by_path: dict[str, RegisteredArtifact] = {}

    @property
    def root(self) -> Path:
        return self._root

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    def register(self, source_path: str | Path, *, media_type: str) -> RegisteredArtifact:
        relative_path, resolved_path = self._resolve_source(source_path)
        content, size_bytes = self._read_stable_bytes(resolved_path)
        digest = hashlib.sha256(content).hexdigest()
        reference = ArtifactReference(
            path_or_uri=relative_path,
            media_type=media_type,
            sha256=digest,
            size_bytes=size_bytes,
        )
        registered = RegisteredArtifact(reference=reference, content=content)

        previous = self._by_path.get(relative_path)
        if previous is not None:
            if previous.reference.sha256 != digest or previous.reference.size_bytes != size_bytes:
                raise ArtifactChangedError(f"artifact changed after registration: {relative_path}")
            return previous
        self._by_path[relative_path] = registered
        return registered

    def _resolve_source(self, source_path: str | Path) -> tuple[str, Path]:
        requested = Path(source_path)
        if requested.is_absolute():
            raise ArtifactBoundaryError("artifact path must be relative to the registry root")
        if any(part == ".." for part in requested.parts):
            raise ArtifactBoundaryError("artifact path cannot contain parent traversal")
        try:
            resolved = (self._root / requested).resolve(strict=True)
        except FileNotFoundError as exc:
            raise ArtifactNotFoundError(f"artifact does not exist: {requested.as_posix()}") from exc
        except OSError as exc:
            raise ArtifactReadError(f"cannot resolve artifact: {requested.as_posix()}") from exc
        try:
            relative = resolved.relative_to(self._root).as_posix()
        except ValueError as exc:
            raise ArtifactBoundaryError("artifact resolves outside the registry root") from exc
        return relative, resolved

    def _read_stable_bytes(self, path: Path) -> tuple[bytes, int]:
        try:
            with path.open("rb") as handle:
                before = os.fstat(handle.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise ArtifactReadError("artifact must be a regular file")
                if before.st_size > self._max_bytes:
                    raise ArtifactTooLargeError(f"artifact exceeds {self._max_bytes} byte limit")

                chunks: list[bytes] = []
                observed = 0
                while chunk := handle.read(READ_CHUNK_BYTES):
                    observed += len(chunk)
                    if observed > self._max_bytes:
                        raise ArtifactTooLargeError(
                            f"artifact exceeds {self._max_bytes} byte limit"
                        )
                    chunks.append(chunk)
                after = os.fstat(handle.fileno())
        except ArtifactError:
            raise
        except OSError as exc:
            raise ArtifactReadError("cannot read artifact") from exc

        if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
            raise ArtifactChangedError("artifact metadata changed while it was being read")
        content = b"".join(chunks)
        if len(content) != before.st_size:
            raise ArtifactChangedError("artifact size changed while it was being read")
        return content, len(content)
