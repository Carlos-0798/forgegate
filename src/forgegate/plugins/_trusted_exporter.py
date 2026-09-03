"""Bounded container-side exporter for broker-owned plugin output.

This module is copied into the disposable sandbox next to the trusted runner.
It validates the output tree before emitting a deterministic tar stream and
uses only the Python standard library.
"""

from __future__ import annotations

import io
import os
import stat
import sys
import tarfile
from pathlib import Path

OUTPUT_ROOT = Path("/forgegate/output")
ALLOWED_DIRECTORIES = frozenset({"protocol", "evidence"})
ALLOWED_PROTOCOL_FILES = frozenset({"ready.json", "terminal.json"})


def _read_stable_regular(path: Path, remaining: int) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size < 0 or before.st_size > remaining:
            raise ValueError("invalid output file")
        content = bytearray()
        while chunk := os.read(descriptor, min(64 * 1024, remaining - len(content) + 1)):
            content.extend(chunk)
            if len(content) > remaining:
                raise ValueError("output byte limit exceeded")
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) or len(content) != after.st_size:
            raise ValueError("output changed while being read")
        return bytes(content)
    finally:
        os.close(descriptor)


def _collect(max_bytes: int, max_entries: int) -> tuple[tuple[str, bytes], ...]:
    root_status = os.lstat(OUTPUT_ROOT)
    if not stat.S_ISDIR(root_status.st_mode):
        raise ValueError("invalid output root")
    names: list[tuple[str, Path]] = []
    entries = 0
    for directory_entry in sorted(os.scandir(OUTPUT_ROOT), key=lambda item: item.name):
        entries += 1
        if entries > max_entries or directory_entry.name not in ALLOWED_DIRECTORIES:
            raise ValueError("invalid output directory")
        if not directory_entry.is_dir(follow_symlinks=False):
            raise ValueError("invalid output directory")
        directory = Path(directory_entry.path)
        for file_entry in sorted(os.scandir(directory), key=lambda item: item.name):
            entries += 1
            if entries > max_entries or not file_entry.is_file(follow_symlinks=False):
                raise ValueError("invalid output entry")
            if directory_entry.name == "protocol" and file_entry.name not in ALLOWED_PROTOCOL_FILES:
                raise ValueError("unexpected protocol output")
            names.append((f"{directory_entry.name}/{file_entry.name}", Path(file_entry.path)))
    content: list[tuple[str, bytes]] = []
    observed = 0
    for name, path in names:
        value = _read_stable_regular(path, max_bytes - observed)
        observed += len(value)
        content.append((name, value))
    return tuple(content)


def _write_archive(files: tuple[tuple[str, bytes], ...]) -> None:
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|", format=tarfile.PAX_FORMAT) as archive:
        for directory in sorted({name.split("/", maxsplit=1)[0] for name, _ in files}):
            member = tarfile.TarInfo(directory)
            member.type = tarfile.DIRTYPE
            member.mode = 0o500
            member.mtime = 0
            archive.addfile(member)
        for name, content in files:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            member.mode = 0o400
            member.mtime = 0
            archive.addfile(member, io.BytesIO(content))


def main() -> int:
    try:
        if len(sys.argv) != 3:
            raise ValueError("invalid exporter arguments")
        max_bytes = int(sys.argv[1])
        max_entries = int(sys.argv[2])
        if max_bytes < 1 or max_entries < 1:
            raise ValueError("invalid exporter limits")
        _write_archive(_collect(max_bytes, max_entries))
    except (OSError, ValueError, tarfile.TarError):
        print("bounded output export failed", file=sys.stderr)
        return 65
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
