from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from forgegate.domain.models import StrictModel

ASSET_INVENTORY_FILENAME = "asset-inventory.json"
ASSET_PATH_PATTERN = re.compile(
    r"^(?:\.vite|assets)/[A-Za-z0-9][A-Za-z0-9._/-]{0,240}$"
    r"|^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$"
)
HASHED_ASSET_PATTERN = re.compile(r"^assets/[A-Za-z0-9_-]+-[A-Za-z0-9_-]{8,}\.(?:css|js)$")


class DashboardAsset(StrictModel):
    path: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=1, le=4 * 1024 * 1024)

    @field_validator("path")
    @classmethod
    def path_must_be_safe(cls, value: str) -> str:
        if ASSET_PATH_PATTERN.fullmatch(value) is None or ".." in Path(value).parts:
            raise ValueError("Dashboard asset path must be a safe relative path")
        return value


class DashboardAssetInventory(StrictModel):
    schema_version: Literal["forgegate.dashboard-asset-inventory.v1"] = (
        "forgegate.dashboard-asset-inventory.v1"
    )
    assets: tuple[DashboardAsset, ...] = Field(min_length=4, max_length=100)

    @field_validator("assets")
    @classmethod
    def assets_must_be_canonical(
        cls,
        value: tuple[DashboardAsset, ...],
    ) -> tuple[DashboardAsset, ...]:
        paths = tuple(asset.path for asset in value)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("Dashboard assets must use unique canonical path order")
        if "index.html" not in paths or ".vite/manifest.json" not in paths:
            raise ValueError("Dashboard inventory must include index and Vite manifest")
        if not any(HASHED_ASSET_PATTERN.fullmatch(path) for path in paths):
            raise ValueError("Dashboard inventory must include content-hashed assets")
        return value


def build_dashboard_asset_inventory(static_root: Path) -> DashboardAssetInventory:
    root = static_root.resolve(strict=True)
    assets: list[DashboardAsset] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.name == ASSET_INVENTORY_FILENAME:
            continue
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        assets.append(
            DashboardAsset(
                path=relative,
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
            )
        )
    # WindowsPath ordering is case-insensitive; the portable contract is not.
    return DashboardAssetInventory(assets=tuple(sorted(assets, key=lambda asset: asset.path)))


def write_dashboard_asset_inventory(static_root: Path) -> Path:
    inventory = build_dashboard_asset_inventory(static_root)
    target = static_root / ASSET_INVENTORY_FILENAME
    payload = json.dumps(inventory.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    target.write_bytes(payload.encode("utf-8"))
    return target


def validate_dashboard_assets(static_root: Path) -> DashboardAssetInventory:
    target = static_root / ASSET_INVENTORY_FILENAME
    try:
        raw = target.read_bytes()
        if not 1 <= len(raw) <= 64 * 1024:
            raise ValueError("Dashboard asset inventory has an invalid byte size")
        inventory = DashboardAssetInventory.model_validate_json(raw)
    except (OSError, ValueError) as exc:
        raise ValueError("Dashboard asset inventory is missing or invalid") from exc
    observed = build_dashboard_asset_inventory(static_root)
    if observed != inventory:
        raise ValueError("Dashboard packaged assets do not match the committed inventory")
    return inventory


__all__ = [
    "ASSET_INVENTORY_FILENAME",
    "DashboardAsset",
    "DashboardAssetInventory",
    "build_dashboard_asset_inventory",
    "validate_dashboard_assets",
    "write_dashboard_asset_inventory",
]
