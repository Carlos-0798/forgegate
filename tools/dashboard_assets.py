from __future__ import annotations

import argparse
from pathlib import Path

from forgegate.dashboard.assets import (
    validate_dashboard_assets,
    write_dashboard_asset_inventory,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = REPOSITORY_ROOT / "src" / "forgegate" / "dashboard" / "static"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or verify the Dashboard asset inventory")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        target = write_dashboard_asset_inventory(STATIC_ROOT)
        print(f"Dashboard asset inventory written: {target.relative_to(REPOSITORY_ROOT)}")
        return
    inventory = validate_dashboard_assets(STATIC_ROOT)
    print(f"Dashboard asset inventory: PASS ({len(inventory.assets)} files)")


if __name__ == "__main__":
    main()
