from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from forgegate.plugins import WINDOWS_SANDBOX_PROBE_IMAGE, PluginResourceLimits
from tools import verify_windows_sandbox_live as live

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LIVE_EVIDENCE = REPOSITORY_ROOT / "reports" / "PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json"


def _limits(*, output_bytes: int = 1_024, file_count: int = 2) -> PluginResourceLimits:
    return PluginResourceLimits(
        startup_timeout_ms=1_000,
        total_timeout_ms=2_000,
        cpu_time_ms=1_000,
        memory_bytes=67_108_864,
        output_bytes=output_bytes,
        file_count=file_count,
        process_count=1,
        stdout_bytes=1_024,
        stderr_bytes=1_024,
    )


@pytest.mark.parametrize("payload", [b'{"key":1,"key":2}', b'{"value":NaN}'])
def test_strict_management_json_rejects_ambiguous_values(payload: bytes) -> None:
    with pytest.raises(live.LiveVerificationError):
        live._load_json_bytes(payload)


def test_output_summary_hashes_and_enforces_member_limit(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"a")
    (tmp_path / "b.txt").write_bytes(b"bb")
    (tmp_path / "c.txt").write_bytes(b"ccc")

    summary = live._summarize_outputs(tmp_path, _limits())

    assert summary.issue == "file-count"
    assert summary.total_bytes == 6
    assert summary.files[0] == (
        "a.txt",
        1,
        hashlib.sha256(b"a").hexdigest(),
    )


def test_output_summary_enforces_byte_limit(tmp_path: Path) -> None:
    (tmp_path / "large.bin").write_bytes(b"x" * 1_025)

    summary = live._summarize_outputs(tmp_path, _limits())

    assert summary.issue == "output-bytes"
    assert summary.total_bytes == 1_025


def test_image_identity_normalizes_podman_bare_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_id = "a" * 64
    digest = WINDOWS_SANDBOX_PROBE_IMAGE.rsplit("@", maxsplit=1)[-1]
    responses = iter(
        (
            live.CommandResult(0, b"", b""),
            live.CommandResult(
                0,
                json.dumps([{"Id": image_id, "Digest": digest}]).encode(),
                b"",
            ),
        )
    )
    monkeypatch.setattr(live, "_run_command", lambda *args, **kwargs: next(responses))

    assert live._image_identity(tmp_path / "podman.exe") == f"sha256:{image_id}"


def test_image_identity_rejects_digest_substitution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    responses = iter(
        (
            live.CommandResult(0, b"", b""),
            live.CommandResult(
                0,
                json.dumps([{"Id": "a" * 64, "Digest": "sha256:" + "b" * 64}]).encode(),
                b"",
            ),
        )
    )
    monkeypatch.setattr(live, "_run_command", lambda *args, **kwargs: next(responses))

    with pytest.raises(live.LiveVerificationError, match="unexpected digest"):
        live._image_identity(tmp_path / "podman.exe")


def test_committed_live_evidence_is_complete_content_derived_and_path_free() -> None:
    raw = LIVE_EVIDENCE.read_bytes()
    document = live._load_json_bytes(raw)
    assert isinstance(document, dict)
    verification_id = document.pop("verification_id")
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    assert verification_id == "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    assert document["backend_enforcement_verified"] is True
    assert document["external_plugin_execution"] == "PROHIBITED"
    assert document["advertised_isolation_tier"] == "NONE"
    assert len(document["checks"]) == 14
    assert all(check["passed"] is True for check in document["checks"])
    assert document["runtime_client_version"] == document["runtime_server_version"]
    assert b"C:\\" not in raw
    assert b"AppData" not in raw
