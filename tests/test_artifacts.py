import hashlib
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from forgegate.artifacts import (
    ArtifactBoundaryError,
    ArtifactChangedError,
    ArtifactNotFoundError,
    ArtifactReadError,
    ArtifactRegistry,
    ArtifactTooLargeError,
)


def test_registry_hashes_and_retains_exact_bytes(tmp_path: Path) -> None:
    content = b"exact artifact bytes\r\n"
    (tmp_path / "report.xml").write_bytes(content)
    registry = ArtifactRegistry(tmp_path)

    artifact = registry.register("report.xml", media_type="application/xml")

    assert registry.root == tmp_path.resolve()
    assert registry.max_bytes == 8 * 1024 * 1024
    assert artifact.content == content
    assert artifact.reference.path_or_uri == "report.xml"
    assert artifact.reference.sha256 == hashlib.sha256(content).hexdigest()
    assert artifact.reference.size_bytes == len(content)


def test_repeated_registration_is_idempotent(tmp_path: Path) -> None:
    (tmp_path / "report.xml").write_bytes(b"stable")
    registry = ArtifactRegistry(tmp_path)

    first = registry.register("report.xml", media_type="application/xml")
    second = registry.register("report.xml", media_type="application/xml")

    assert second is first


def test_registered_path_cannot_change_bytes(tmp_path: Path) -> None:
    path = tmp_path / "report.xml"
    path.write_bytes(b"first")
    registry = ArtifactRegistry(tmp_path)
    registry.register("report.xml", media_type="application/xml")
    path.write_bytes(b"second")

    with pytest.raises(ArtifactChangedError, match="changed after registration"):
        registry.register("report.xml", media_type="application/xml")


def test_absolute_artifact_path_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "report.xml"
    path.write_bytes(b"content")
    registry = ArtifactRegistry(tmp_path)

    with pytest.raises(ArtifactBoundaryError, match="must be relative"):
        registry.register(path, media_type="application/xml")


@pytest.mark.parametrize("source", ["../report.xml", "nested/../../report.xml"])
def test_parent_traversal_is_rejected(tmp_path: Path, source: str) -> None:
    registry = ArtifactRegistry(tmp_path)
    with pytest.raises(ArtifactBoundaryError, match="parent traversal"):
        registry.register(source, media_type="application/xml")


def test_missing_artifact_is_rejected(tmp_path: Path) -> None:
    registry = ArtifactRegistry(tmp_path)
    with pytest.raises(ArtifactNotFoundError, match="does not exist"):
        registry.register("missing.xml", media_type="application/xml")


def test_directory_is_not_a_readable_artifact(tmp_path: Path) -> None:
    (tmp_path / "directory").mkdir()
    registry = ArtifactRegistry(tmp_path)
    with pytest.raises(ArtifactReadError, match=r"cannot read artifact|regular file"):
        registry.register("directory", media_type="application/xml")


def test_oversized_artifact_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "large.xml").write_bytes(b"x" * 11)
    registry = ArtifactRegistry(tmp_path, max_bytes=10)
    with pytest.raises(ArtifactTooLargeError, match="10 byte limit"):
        registry.register("large.xml", media_type="application/xml")


def test_registry_requires_positive_size_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        ArtifactRegistry(tmp_path, max_bytes=0)


def test_registry_root_must_exist(tmp_path: Path) -> None:
    with pytest.raises(ArtifactBoundaryError, match="does not exist"):
        ArtifactRegistry(tmp_path / "missing")


def test_registry_root_must_be_directory(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"content")
    with pytest.raises(ArtifactBoundaryError, match="must be a directory"):
        ArtifactRegistry(path)


def test_resolution_os_error_is_wrapped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = ArtifactRegistry(tmp_path)

    def fail_resolve(*_args: object, **_kwargs: object) -> Path:
        raise OSError("simulated resolution failure")

    monkeypatch.setattr(Path, "resolve", fail_resolve)
    with pytest.raises(ArtifactReadError, match="cannot resolve artifact"):
        registry.register("report.xml", media_type="application/xml")


def test_resolved_outside_path_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.xml"
    outside.write_bytes(b"outside")
    registry = ArtifactRegistry(root)
    monkeypatch.setattr(Path, "resolve", lambda *_args, **_kwargs: outside)

    with pytest.raises(ArtifactBoundaryError, match="outside"):
        registry.register("link.xml", media_type="application/xml")


def test_nonregular_fstat_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "report.xml").write_bytes(b"content")
    registry = ArtifactRegistry(tmp_path)
    fake = SimpleNamespace(st_mode=stat.S_IFDIR, st_size=7, st_mtime_ns=1)
    monkeypatch.setattr("forgegate.artifacts.os.fstat", lambda _fd: fake)

    with pytest.raises(ArtifactReadError, match="regular file"):
        registry.register("report.xml", media_type="application/xml")


def test_growth_beyond_limit_during_read_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "report.xml").write_bytes(b"x" * 11)
    registry = ArtifactRegistry(tmp_path, max_bytes=10)
    fake = SimpleNamespace(st_mode=stat.S_IFREG, st_size=1, st_mtime_ns=1)
    monkeypatch.setattr("forgegate.artifacts.os.fstat", lambda _fd: fake)

    with pytest.raises(ArtifactTooLargeError, match="10 byte limit"):
        registry.register("report.xml", media_type="application/xml")


def test_metadata_change_during_read_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "report.xml").write_bytes(b"abc")
    registry = ArtifactRegistry(tmp_path)
    snapshots = iter(
        [
            SimpleNamespace(st_mode=stat.S_IFREG, st_size=3, st_mtime_ns=1),
            SimpleNamespace(st_mode=stat.S_IFREG, st_size=3, st_mtime_ns=2),
        ]
    )
    monkeypatch.setattr("forgegate.artifacts.os.fstat", lambda _fd: next(snapshots))

    with pytest.raises(ArtifactChangedError, match="metadata changed"):
        registry.register("report.xml", media_type="application/xml")


def test_size_mismatch_during_read_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "report.xml").write_bytes(b"abc")
    registry = ArtifactRegistry(tmp_path)
    fake = SimpleNamespace(st_mode=stat.S_IFREG, st_size=4, st_mtime_ns=1)
    monkeypatch.setattr("forgegate.artifacts.os.fstat", lambda _fd: fake)

    with pytest.raises(ArtifactChangedError, match="size changed"):
        registry.register("report.xml", media_type="application/xml")


def test_symlink_escape_is_rejected_when_supported(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "report.xml").write_bytes(b"outside")
    link = root / "link.xml"
    try:
        link.symlink_to(outside / "report.xml")
    except OSError:
        pytest.skip("symlink creation is unavailable in this environment")

    registry = ArtifactRegistry(root)
    with pytest.raises(ArtifactBoundaryError, match="outside"):
        registry.register("link.xml", media_type="application/xml")
