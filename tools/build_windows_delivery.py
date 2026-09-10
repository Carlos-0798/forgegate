"""Build a Windows delivery wheel from its sdist, isolated from stale build trees."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from importlib.metadata import version
from pathlib import Path, PurePosixPath
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MAX_SDIST_MEMBERS = 10_000
MAX_SDIST_BYTES = 128 * 1024 * 1024
REQUIRED_WHEEL_MEMBERS = {
    "forgegate/cli.py",
    "forgegate/evidence_replay.py",
    "forgegate/evidence_replay_cli.py",
    "forgegate/dashboard/static/asset-inventory.json",
    "forgegate/dashboard/static/index.html",
}


class DeliveryBuildError(RuntimeError):
    pass


def _run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise DeliveryBuildError(f"Build subprocess failed with exit {completed.returncode}.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _one(directory: Path, pattern: str) -> Path:
    matches = list(directory.glob(pattern))
    if len(matches) != 1:
        raise DeliveryBuildError(f"Expected exactly one {pattern} build artifact.")
    return matches[0]


def _extract_sdist(sdist: Path, destination: Path) -> Path:
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > MAX_SDIST_MEMBERS:
            raise DeliveryBuildError("Source distribution contains too many members.")
        if sum(member.size for member in members if member.isfile()) > MAX_SDIST_BYTES:
            raise DeliveryBuildError("Source distribution exceeds the unpacked-size limit.")
        roots: set[str] = set()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise DeliveryBuildError("Source distribution contains an unsafe member path.")
            roots.add(path.parts[0])
            if member.issym() or member.islnk() or member.isdev():
                raise DeliveryBuildError("Source distribution contains links or device members.")
        if len(roots) != 1:
            raise DeliveryBuildError("Source distribution must have one root directory.")
        archive.extractall(destination, filter="data")
    source = destination / next(iter(roots))
    if not source.is_dir():
        raise DeliveryBuildError("Extracted source root is missing.")
    return source


def validate_delivery_wheel(wheel: Path) -> dict[str, int]:
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise DeliveryBuildError("Wheel contains duplicate members.")
            if not REQUIRED_WHEEL_MEMBERS.issubset(names):
                raise DeliveryBuildError("Wheel is missing required runtime members.")
            if any("/__pycache__/" in name or name.endswith((".pyc", ".pyo")) for name in names):
                raise DeliveryBuildError("Wheel contains Python build residue.")
            static_prefix = "forgegate/dashboard/static/"
            inventory_name = static_prefix + "asset-inventory.json"
            inventory = json.loads(archive.read(inventory_name))
            expected = {
                static_prefix + item["path"]: (item["sha256"], item["size_bytes"])
                for item in inventory["assets"]
            }
            actual = {
                name: archive.read(name)
                for name in names
                if name.startswith(static_prefix)
                and name != inventory_name
                and not name.endswith("/")
            }
            if set(actual) != set(expected):
                raise DeliveryBuildError("Wheel Dashboard assets differ from its inventory.")
            for name, payload in actual.items():
                digest, size = expected[name]
                if len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
                    raise DeliveryBuildError("Wheel Dashboard asset hash or size differs.")
    except (KeyError, OSError, TypeError, ValueError, zipfile.BadZipFile) as exc:
        raise DeliveryBuildError("Wheel structure or asset inventory is invalid.") from exc
    return {"dashboard_asset_count": len(actual), "wheel_member_count": len(names)}


def _git_source(repository_root: Path) -> tuple[str | None, str]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None, "SOURCE_CONTROL_UNAVAILABLE"
    return commit, "WORKING_TREE_WITH_CHANGES" if status else "CLEAN_COMMIT"


def build_windows_delivery(
    destination: Path,
    *,
    repository_root: Path = REPOSITORY_ROOT,
    python: Path = Path(sys.executable),
) -> dict[str, Any]:
    destination = destination.resolve(strict=False)
    for part in (destination, *destination.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise DeliveryBuildError("Delivery destination cannot contain links or junctions.")
    if destination.exists():
        raise FileExistsError("Delivery destination already exists; refusing to overwrite it.")
    with tempfile.TemporaryDirectory(prefix="forgegate-delivery-build-") as temporary:
        root = Path(temporary)
        sdist_output = root / "sdist"
        _run(
            [str(python), "-m", "build", "--sdist", "--outdir", str(sdist_output)],
            cwd=repository_root,
        )
        sdist = _one(sdist_output, "*.tar.gz")
        source = _extract_sdist(sdist, root / "source")
        wheel_output = root / "wheel"
        _run(
            [str(python), "-m", "build", "--wheel", "--outdir", str(wheel_output)],
            cwd=source,
        )
        wheel = _one(wheel_output, "*.whl")
        wheel_checks = validate_delivery_wheel(wheel)
        commit, source_state = _git_source(repository_root)
        receipt: dict[str, Any] = {
            "format": "forgegate.windows-delivery-build.v1",
            "product_version": version("forgegate"),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "source_commit": commit,
            "source_state": source_state,
            "construction": "wheel_built_from_generated_sdist_in_fresh_directory",
            "wheel": {
                "filename": wheel.name,
                "sha256": _sha256(wheel),
                "size_bytes": wheel.stat().st_size,
                **wheel_checks,
            },
            "sdist": {
                "filename": sdist.name,
                "sha256": _sha256(sdist),
                "size_bytes": sdist.stat().st_size,
            },
            "hardware_access": "NOT_PERFORMED",
            "publication": "NOT_PERFORMED",
        }
        destination.mkdir(parents=True, exist_ok=False)
        shutil.copy2(wheel, destination / wheel.name)
        shutil.copy2(sdist, destination / sdist.name)
        (destination / "build-receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a no-overwrite Windows delivery wheel from a fresh sdist tree."
    )
    parser.add_argument("destination", type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    try:
        receipt = build_windows_delivery(args.destination, python=args.python)
    except (DeliveryBuildError, FileExistsError, OSError) as exc:
        print(f"ForgeGate Windows delivery build refused: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print("ForgeGate Windows delivery build: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
