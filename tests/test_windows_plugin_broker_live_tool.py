from __future__ import annotations

import hashlib
import json
from pathlib import Path

from forgegate.canonical import canonical_json
from forgegate.plugins import PluginRunReceipt, PluginRunState

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LIVE_EVIDENCE = REPOSITORY_ROOT / "reports" / "PHASE_20_WINDOWS_PLUGIN_BROKER_LIVE_EVIDENCE.json"


def test_committed_production_broker_evidence_is_complete_and_path_free() -> None:
    raw = LIVE_EVIDENCE.read_bytes()
    document = json.loads(raw)
    verification_id = document.pop("verification_id")

    assert (
        verification_id == "sha256:" + hashlib.sha256(canonical_json(document).encode()).hexdigest()
    )
    assert document["production_broker_verified"] is True
    assert document["forgegate_installation"] == "CLEAN_WHEEL"
    assert document["advertised_isolation_tier"] == "SANDBOXED"
    assert document["evidence_level"] == "LOCAL_HOST_TEST"
    assert document["hardware_access"] == "NOT_PERFORMED"
    assert len(document["checks"]) == 13
    assert all(check["passed"] is True for check in document["checks"])

    receipt = PluginRunReceipt.model_validate(document["receipt"])
    assert receipt.result.status is PluginRunState.SUCCEEDED
    assert receipt.accepted_outputs_registered is True
    assert receipt.cleanup.container_removed is True
    assert receipt.cleanup.staging_removed is True
    assert receipt.execution.stdout_bytes == receipt.execution.stderr_bytes == 0

    assert b"C:\\" not in raw
    assert b"AppData" not in raw
    assert b"24046" not in raw
    assert b"@" not in raw
    assert b"token" not in raw.lower()
