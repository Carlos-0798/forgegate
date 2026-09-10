import hashlib
import json
import zipfile

import pytest

from tools.build_windows_delivery import DeliveryBuildError, validate_delivery_wheel


def _wheel(tmp_path, *, extra=False, corrupt=False):
    path = tmp_path / "forgegate.whl"
    assets = {
        ".vite/manifest.json": b"{}",
        "assets/index-abcdefgh.js": b"script",
        "assets/index-abcdefgh.css": b"style",
        "index.html": b"<main></main>",
        "third-party-licenses.json": b"{}",
    }
    inventory = {
        "schema_version": "forgegate.dashboard-asset-inventory.v1",
        "assets": [
            {"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
            for name, raw in sorted(assets.items())
        ],
    }
    if corrupt:
        inventory["assets"][0]["sha256"] = "0" * 64
    with zipfile.ZipFile(path, "w") as archive:
        for required in [
            "forgegate/cli.py",
            "forgegate/evidence_replay.py",
            "forgegate/evidence_replay_cli.py",
        ]:
            archive.writestr(required, "")
        archive.writestr("forgegate/dashboard/static/asset-inventory.json", json.dumps(inventory))
        for name, raw in assets.items():
            archive.writestr(f"forgegate/dashboard/static/{name}", raw)
        if extra:
            archive.writestr("forgegate/dashboard/static/assets/stale-abcdefgh.js", b"stale")
    return path


def test_delivery_wheel_matches_exact_asset_inventory(tmp_path):
    checks = validate_delivery_wheel(_wheel(tmp_path))
    assert checks["dashboard_asset_count"] == 5


@pytest.mark.parametrize("change", ["extra", "corrupt"])
def test_delivery_wheel_refuses_stale_or_corrupt_assets(tmp_path, change):
    with pytest.raises(DeliveryBuildError):
        validate_delivery_wheel(
            _wheel(tmp_path, extra=change == "extra", corrupt=change == "corrupt")
        )
