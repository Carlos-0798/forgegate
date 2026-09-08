import hashlib
import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import forgegate.recovery_rehearsal as rehearsal
from forgegate.canonical import canonical_json
from forgegate.cli import app
from forgegate.recovery_models import build_recovery_handoff
from forgegate.recovery_readiness import check_recovery_readiness
from forgegate.workspace_backups import WorkspaceBackupError, backup_workspace
from tests import test_collection_jobs as jobs
from tests.test_recovery_readiness import archived
from tests.test_workspace_backups import _tables


@pytest.fixture
def fixture(tmp_path, repository_root):
    return jobs.fixture.__wrapped__(tmp_path, repository_root)


def handoff_for(root, digest, mappings, tmp_path):
    report = check_recovery_readiness(root, expected_sha256=digest, dependencies=mappings)
    raw = (report.model_dump_json(indent=2) + "\n").encode()
    handoff = build_recovery_handoff(raw.decode(), hashlib.sha256(raw).hexdigest())
    path = tmp_path / "handoff.json"
    path.write_bytes((handoff.model_dump_json(indent=2) + "\n").encode())
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def setup(fixture, tmp_path, state="SUCCEEDED"):
    root, digest, original, old_digest, record, _ = archived(fixture, tmp_path, state)
    mappings = {old_digest: original}
    handoff, handoff_hash = handoff_for(root, digest, mappings, tmp_path)
    return root, mappings, handoff, handoff_hash, record


def run(root, mappings, handoff, digest, destination):
    return rehearsal.rehearse_recovery(
        root, destination, handoff, handoff_sha256=digest, dependencies=mappings
    )


@pytest.mark.parametrize("state", ["SUCCEEDED", "CANCELLED"])
def test_complete_exact_copy_history_and_no_source_changes(fixture, tmp_path, state):
    root, mappings, handoff, digest, record = setup(fixture, tmp_path, state)
    sources = [root, *mappings.values(), handoff, fixture[1].path, tmp_path / "candidates.db"]
    before = [p.read_bytes() for p in sources]
    destination = tmp_path / "new directory"
    receipt = run(root, mappings, handoff, digest, destination)
    assert receipt.status == "RESTORED_COPY_VERIFIED"
    assert receipt.handoff_sha256 == digest
    assert receipt.rechecked_readiness.dependencies[0].job_ids == [record.job_id]
    assert receipt.rechecked_readiness.dependencies[0].result_payloads_verified == (
        state == "SUCCEEDED"
    )
    assert receipt.archived_payloads == "VERIFIED_EXTERNAL_NOT_REHYDRATED"
    assert _tables(destination / "jobs.db") == _tables(fixture[1].path)
    assert _tables(destination / "candidates.db") == _tables(tmp_path / "candidates.db")
    assert [p.read_bytes() for p in sources] == before
    assert (
        rehearsal.RecoveryRehearsalReceipt.model_validate_json(
            (destination / "REHEARSAL.json").read_bytes()
        )
        == receipt
    )
    assert not (destination / "RESTORED.json").exists()
    assert str(tmp_path) not in receipt.model_dump_json()
    assert (
        receipt.job_store.sha256
        == hashlib.sha256((destination / "jobs.db").read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("v4", [False, True])
def test_empty_v3_v4_rehearsal(fixture, tmp_path, v4):
    if v4:
        fixture[1].enable_archiving()
    root = tmp_path / "root.zip"
    meta = backup_workspace(tmp_path / "candidates.db", fixture[1].path, root)
    handoff, digest = handoff_for(root, meta["sha256"], {}, tmp_path)
    receipt = run(root, {}, handoff, digest, tmp_path / "copy")
    assert receipt.rechecked_readiness.archived_job_count == 0


@pytest.mark.parametrize(
    "kind",
    [
        "blocked",
        "missing",
        "wrong_dependency",
        "unused",
        "root_changed",
        "review_mismatch",
        "handoff_hash",
        "hash_invalid",
        "oversize",
        "duplicate",
        "nan",
        "utf8",
        "invalid",
        "depth",
        "missing_handoff",
        "directory",
        "file",
        "parent",
    ],
)
def test_refuse_before_destination_creation(fixture, tmp_path, kind):
    root, mappings, handoff, digest, _ = setup(fixture, tmp_path)
    destination = tmp_path / "copy"
    if kind == "blocked":
        handoff, digest = handoff_for(
            root, hashlib.sha256(root.read_bytes()).hexdigest(), {}, tmp_path
        )
    elif kind == "missing":
        mappings = {}
    elif kind == "wrong_dependency":
        mappings = dict.fromkeys(mappings, root)
    elif kind == "unused":
        mappings["0" * 64] = root
    elif kind == "root_changed":
        root.write_bytes(b"changed")
    elif kind == "review_mismatch":
        document = json.loads(handoff.read_bytes())
        document["readiness"]["manifest_fingerprint"] = "sha256:" + "0" * 64
        raw = canonical_json(document["readiness"])
        document = build_recovery_handoff(raw, hashlib.sha256(raw.encode()).hexdigest())
        handoff.write_bytes(document.model_dump_json().encode())
    elif kind == "handoff_hash":
        digest = "0" * 64
    elif kind == "hash_invalid":
        digest = "invalid"
    elif kind == "oversize":
        handoff.write_bytes(b" " * (rehearsal.MAX_HANDOFF_BYTES + 1))
    elif kind in {"duplicate", "nan", "utf8", "invalid", "depth"}:
        handoff.write_bytes(
            {
                "duplicate": b'{"x":1,"x":2}',
                "nan": b'{"x":NaN}',
                "utf8": b"\xff",
                "invalid": b"{}",
                "depth": b"[" * 30 + b"]" * 30,
            }[kind]
        )
    elif kind == "missing_handoff":
        handoff = tmp_path / "absent.json"
    elif kind == "directory":
        destination.mkdir()
        (destination / "owner.txt").write_bytes(b"keep")
    elif kind == "file":
        destination.write_bytes(b"keep")
    else:
        destination = tmp_path / "absent" / "copy"
    if kind in {"review_mismatch", "oversize", "duplicate", "nan", "utf8", "invalid", "depth"}:
        digest = hashlib.sha256(handoff.read_bytes()).hexdigest()
    with pytest.raises(WorkspaceBackupError):
        run(root, mappings, handoff, digest, destination)
    if kind == "directory":
        assert list(destination.iterdir()) == [destination / "owner.txt"]
    elif kind == "file":
        assert destination.read_bytes() == b"keep"
    else:
        assert not destination.exists()


@pytest.mark.parametrize("kind", ["copy", "readback", "hash", "publish", "deadline"])
def test_partial_failure_never_publishes_completion(fixture, tmp_path, monkeypatch, kind):
    root, mappings, handoff, digest, _ = setup(fixture, tmp_path)
    destination = tmp_path / "copy"
    if kind == "copy":
        monkeypatch.setattr(
            rehearsal,
            "_stream",
            lambda *args: rehearsal.SnapshotMember(sha256="0" * 64, size_bytes=1),
        )
    elif kind == "readback":
        monkeypatch.setattr(rehearsal, "_inspect_pair", lambda *args: {})
    elif kind == "hash":
        monkeypatch.setattr(rehearsal, "_hash", lambda *args: None)
    elif kind == "publish":

        def fail(*args):
            raise OSError("private detail must not escape")

        monkeypatch.setattr(rehearsal.os, "link", fail)
    else:
        real = rehearsal._inspect_pair

        def expire(path, deadline):
            value = real(path, deadline)
            monkeypatch.setattr(
                rehearsal,
                "_check_time",
                lambda _: rehearsal._require(False, "WORKSPACE_DEADLINE_EXCEEDED"),
            )
            return value

        monkeypatch.setattr(rehearsal, "_inspect_pair", expire)
    with pytest.raises(WorkspaceBackupError) as caught:
        run(root, mappings, handoff, digest, destination)
    assert "private detail" not in str(caught.value)
    assert destination.is_dir() and not (destination / "REHEARSAL.json").exists()
    monkeypatch.undo()
    with pytest.raises(WorkspaceBackupError, match="DESTINATION_EXISTS"):
        run(root, mappings, handoff, digest, destination)


def test_deadline_covers_prechecks(fixture, tmp_path, monkeypatch):
    root, mappings, handoff, digest, _ = setup(fixture, tmp_path)
    monkeypatch.setattr(rehearsal, "_deadline", lambda _: time.monotonic() - 1)
    with pytest.raises(WorkspaceBackupError, match="DEADLINE"):
        run(root, mappings, handoff, digest, tmp_path / "copy")
    assert not (tmp_path / "copy").exists()


def test_post_commit_cleanup_failure_still_returns_receipt(fixture, tmp_path, monkeypatch):
    root, mappings, handoff, digest, _ = setup(fixture, tmp_path)
    original = Path.unlink

    def fail_pending(path, *args, **kwargs):
        if path.name == ".REHEARSAL.pending":
            raise OSError("cleanup denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_pending)
    receipt = run(root, mappings, handoff, digest, tmp_path / "copy")
    assert receipt.status == "RESTORED_COPY_VERIFIED"
    assert (tmp_path / "copy/REHEARSAL.json").is_file()


@pytest.mark.parametrize(
    "kind", ["identity", "time", "naive", "blocked", "readiness", "boundary", "member", "count"]
)
def test_receipt_rejects_incoherent_claims(fixture, tmp_path, kind):
    root, mappings, handoff, digest, _ = setup(fixture, tmp_path)
    receipt = run(root, mappings, handoff, digest, tmp_path / "copy").model_dump(mode="json")
    if kind == "identity":
        receipt["rehearsal_id"] = "sha256:" + "0" * 64
    elif kind in {"time", "naive"}:
        receipt["completed_at"] = "2000-01-01T00:00:00" + ("Z" if kind == "time" else "")
    elif kind == "blocked":
        blocked, _ = handoff_for(root, hashlib.sha256(root.read_bytes()).hexdigest(), {}, tmp_path)
        receipt["handoff"] = json.loads(blocked.read_bytes())
    elif kind == "readiness":
        receipt["rechecked_readiness"]["manifest_fingerprint"] = "sha256:" + "0" * 64
    elif kind == "member":
        receipt["job_store"]["sha256"] = "0" * 64
    elif kind == "count":
        receipt["post_restore_job_count"] = 0
    else:
        receipt["producer_authenticity"] = "VERIFIED"
    with pytest.raises(ValidationError):
        rehearsal.RecoveryRehearsalReceipt.model_validate(receipt)


def test_cli_success_and_no_overwrite(fixture, tmp_path):
    root, mappings, handoff, digest, _ = setup(fixture, tmp_path)
    destination = tmp_path / "CLI copy"
    args = [
        "workspace",
        "rehearse-recovery",
        str(root),
        str(destination),
        str(handoff),
        "--handoff-sha256",
        digest,
    ]
    for key, path in mappings.items():
        args += ["--dependency", f"{key}={path}"]
    runner = CliRunner()
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "RESTORED_COPY_VERIFIED"
    result = runner.invoke(app, args)
    assert result.exit_code == 3 and "DESTINATION_EXISTS" in result.output
    assert str(tmp_path) not in result.output
