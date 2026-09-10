import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import forgegate.adoption_inventory as ai
import forgegate.adoption_preflight as ap
from forgegate.adoption_models import (
    AdoptionDifference,
    WorkspaceAdoptionPreflight,
)
from forgegate.application import CandidateAttestCommand, CandidateEvaluateCommand
from forgegate.cli import app
from forgegate.collection_jobs import CollectionJobStore
from forgegate.recovery_rehearsal import rehearse_recovery
from forgegate.security_events import ApiSecurityEventType
from forgegate.workspace_backups import WorkspaceBackupError, backup_workspace
from tests import test_collection_jobs as jobs
from tests.test_policy_materialization import _advance_to_evaluating, _application
from tests.test_recovery_rehearsal import handoff_for, setup


@pytest.fixture
def fixture(tmp_path, repository_root):
    return jobs.fixture.__wrapped__(tmp_path, repository_root)


def prepare(fixture, tmp_path, v4=False):
    if v4:
        fixture[1].enable_archiving()
    root = tmp_path / "target.zip"
    digest = backup_workspace(tmp_path / "candidates.db", fixture[1].path, root)["sha256"]
    handoff, hhash = handoff_for(root, digest, {}, tmp_path)
    target = tmp_path / "cold copy"
    rehearse_recovery(root, target, handoff, handoff_sha256=hhash, dependencies={})
    receipt_hash = hashlib.sha256((target / "REHEARSAL.json").read_bytes()).hexdigest()
    return root, target, digest, receipt_hash


def check(inputs, **kwargs):
    root, target, digest, receipt_hash = inputs
    return ap.preflight_adoption(
        root, root, target, source_sha256=digest, receipt_sha256=receipt_hash, **kwargs
    )


@pytest.mark.parametrize("v4", [False, True])
def test_match_exact_readonly_and_contract(fixture, tmp_path, v4):
    inputs = prepare(fixture, tmp_path, v4)
    tracked = [inputs[0], *inputs[1].iterdir(), fixture[1].path, tmp_path / "candidates.db"]
    before = {p: p.read_bytes() for p in tracked}
    report = check(inputs)
    assert report.comparison == "MATCH"
    assert report.differences_total == 0 and report.next_offset is None
    assert len(report.tables) == 20
    assert not report.adoption_authorized and not report.live_workspace_changed
    assert report.live_source_state == "NOT_CHECKED"
    assert str(tmp_path) not in report.model_dump_json()
    assert "project:jobs" not in report.model_dump_json()
    assert report == WorkspaceAdoptionPreflight.model_validate_json(report.model_dump_json())
    assert {p: p.read_bytes() for p in tracked} == before
    assert {p.name for p in inputs[1].iterdir()} == {"REHEARSAL.json", "candidates.db", "jobs.db"}


def test_difference_paging_and_schema_only_difference(fixture, tmp_path):
    inputs = prepare(fixture, tmp_path)
    application, store, request = fixture
    store.submit(request, application, key="new-source-job")
    source = tmp_path / "source.zip"
    digest = backup_workspace(tmp_path / "candidates.db", store.path, source)["sha256"]
    first = ap.preflight_adoption(
        source, inputs[0], inputs[1], source_sha256=digest, receipt_sha256=inputs[3], limit=1
    )
    second = ap.preflight_adoption(
        source,
        inputs[0],
        inputs[1],
        source_sha256=digest,
        receipt_sha256=inputs[3],
        limit=1,
        offset=1,
    )
    assert first.comparison == "DIFFERENT" and first.differences_total == 2
    assert first.next_offset == 1 and second.next_offset is None
    assert first.comparison_id == second.comparison_id
    assert first.report_id != second.report_id
    assert all(d.kind == "SOURCE_ONLY" for d in first.differences + second.differences)
    assert {d.table for d in first.differences + second.differences} == {"jobs.events", "jobs.jobs"}


@pytest.mark.parametrize(
    "kind",
    [
        "source_hash",
        "receipt_hash",
        "receipt_invalid",
        "receipt_missing",
        "candidate_changed",
        "jobs_missing",
        "wal",
        "shm",
        "journal",
        "hardlink",
        "receipt_oversize",
        "offset",
        "limit",
        "timeout",
        "unused_dependency",
    ],
)
def test_refusals_preserve_inputs(fixture, tmp_path, kind):
    inputs = list(prepare(fixture, tmp_path))
    kwargs = {}
    if kind == "source_hash":
        inputs[2] = "0" * 64
    elif kind == "receipt_hash":
        inputs[3] = "0" * 64
    elif kind == "receipt_invalid":
        (inputs[1] / "REHEARSAL.json").write_bytes(b"{}")
        inputs[3] = hashlib.sha256(b"{}").hexdigest()
    elif kind == "receipt_missing":
        (inputs[1] / "REHEARSAL.json").unlink()
    elif kind == "candidate_changed":
        with (inputs[1] / "candidates.db").open("ab") as stream:
            stream.write(b"changed")
    elif kind == "jobs_missing":
        (inputs[1] / "jobs.db").unlink()
    elif kind in {"wal", "shm", "journal"}:
        (inputs[1] / f"candidates.db-{kind}").write_bytes(b"owner")
    elif kind == "hardlink":
        os.link(inputs[1] / "jobs.db", tmp_path / "alias.db")
    elif kind == "receipt_oversize":
        (inputs[1] / "REHEARSAL.json").write_bytes(b" " * (ap.MAX_RECOVERY_RECEIPT_BYTES + 1))
    elif kind == "offset":
        kwargs["offset"] = 1
    elif kind == "limit":
        kwargs["limit"] = 0
    elif kind == "timeout":
        kwargs["timeout_seconds"] = float("nan")
    elif kind == "unused_dependency":
        kwargs["source_dependencies"] = {inputs[2]: inputs[0]}
    tracked = [p for p in inputs[1].iterdir() if p.is_file()]
    before = {p: p.read_bytes() for p in tracked}
    with pytest.raises(WorkspaceBackupError):
        check(inputs, **kwargs)
    assert {p: p.read_bytes() for p in tracked} == before


@pytest.mark.parametrize(
    "kind", ["trigger", "extra_table", "audit", "replay", "candidate", "profile"]
)
def test_unreferenced_corruption_rejected(fixture, tmp_path, kind):
    inputs = prepare(fixture, tmp_path)
    source = tmp_path / "bad-source.zip"
    with closing(sqlite3.connect(tmp_path / "candidates.db")) as con:
        if kind == "trigger":
            con.execute("DROP TRIGGER audit_events_guard_delete")
            con.execute(
                "CREATE TRIGGER audit_events_guard_delete BEFORE DELETE ON audit_events "
                "BEGIN SELECT 1; END"
            )
        elif kind == "extra_table":
            con.execute("CREATE TABLE owner_extra (id TEXT PRIMARY KEY)")
        else:
            _table, trigger, query = {
                "audit": (
                    "audit_events",
                    "audit_events_guard_delete",
                    "DELETE FROM audit_events WHERE sequence=1",
                ),
                "replay": (
                    "idempotency_records",
                    "idempotency_records_guard_update",
                    "UPDATE idempotency_records SET recorded_at='bad'",
                ),
                "candidate": (
                    "candidates",
                    "candidates_guard_update",
                    "UPDATE candidates SET current_fingerprint='sha256:' || printf('%064d',0)",
                ),
                "profile": (
                    "project_profiles",
                    "project_profiles_guard_update",
                    "UPDATE project_profiles SET profile_fingerprint='sha256:' "
                    "|| printf('%064d',0)",
                ),
            }[kind]
            ddl = con.execute("SELECT sql FROM sqlite_master WHERE name=?", (trigger,)).fetchone()[
                0
            ]
            con.execute(f'DROP TRIGGER "{trigger}"')
            con.execute(query)
            con.execute(ddl)
        con.commit()
    # No jobs reference the candidate, so the earlier backup check is deliberately narrower.
    digest = backup_workspace(tmp_path / "candidates.db", fixture[1].path, source)["sha256"]
    with pytest.raises(WorkspaceBackupError):
        ap.preflight_adoption(
            source, inputs[0], inputs[1], source_sha256=digest, receipt_sha256=inputs[3]
        )


def test_archived_dependency_readback_and_missing_refusal(fixture, tmp_path):
    root, mapping, handoff, handoff_hash, _ = setup(fixture, tmp_path)
    target = tmp_path / "archived-copy"
    rehearse_recovery(root, target, handoff, handoff_sha256=handoff_hash, dependencies=mapping)
    digest = hashlib.sha256(root.read_bytes()).hexdigest()
    receipt_hash = hashlib.sha256((target / "REHEARSAL.json").read_bytes()).hexdigest()
    inputs = root, target, digest, receipt_hash
    report = check(inputs, source_dependencies=mapping, target_dependencies=mapping)
    assert (
        report.comparison == "MATCH"
        and report.archive_dependencies == "RECHECKED_EXTERNAL_NOT_REHYDRATED"
    )
    with pytest.raises(WorkspaceBackupError, match="ADOPTION_DEPENDENCIES_INCOMPLETE"):
        check(inputs)


def test_cli_exit_output_and_no_overwrite(fixture, tmp_path):
    inputs = prepare(fixture, tmp_path)
    command = [
        "workspace",
        "adoption-preflight",
        str(inputs[0]),
        str(inputs[0]),
        str(inputs[1]),
        "--source-sha256",
        inputs[2],
        "--receipt-sha256",
        inputs[3],
    ]
    runner = CliRunner()
    output = tmp_path / "report.json"
    result = runner.invoke(app, [*command, "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert result.output.encode() == output.read_bytes()
    old = output.read_bytes()
    result = runner.invoke(app, [*command, "--output", str(output)])
    assert result.exit_code == 3 and "RECOVERY_OUTPUT_EXISTS" in result.output
    assert output.read_bytes() == old
    result = runner.invoke(app, [*command, "--output", str(inputs[1] / "report.json")])
    assert result.exit_code == 3 and "ADOPTION_OUTPUT_IN_TARGET" in result.output


@pytest.mark.parametrize(
    "kind",
    ["identity", "timestamp", "total", "page", "comparison", "authority", "table", "unknown"],
)
def test_report_rejects_forged_fields(fixture, tmp_path, kind):
    report = check(prepare(fixture, tmp_path)).model_dump(mode="json")
    if kind == "identity":
        report["comparison_id"] = "sha256:" + "0" * 64
    elif kind == "timestamp":
        report["checked_at"] = "2026-09-08T00:00:00"
    elif kind == "total":
        report["differences_total"] = 1
    elif kind == "page":
        report["next_offset"] = 1
    elif kind == "comparison":
        report["comparison"] = "DIFFERENT"
    elif kind == "authority":
        report["adoption_authorized"] = True
    elif kind == "table":
        report["tables"][0]["source_rows"] += 1
    else:
        report["command"] = "switch"
    with pytest.raises(ValidationError):
        WorkspaceAdoptionPreflight.model_validate(report)


def test_bounds_before_domain_parse(fixture, tmp_path, monkeypatch):
    inputs = prepare(fixture, tmp_path)
    monkeypatch.setattr(ai, "MAX_INVENTORY_ROWS", 1)
    with pytest.raises(WorkspaceBackupError, match="ADOPTION_ROW_LIMIT"):
        check(inputs)


def test_target_changed_during_inspection(fixture, tmp_path, monkeypatch):
    inputs = prepare(fixture, tmp_path)
    original = ap.inventory

    def changed(*args):
        result = original(*args)
        (inputs[1] / "jobs.db-wal").write_bytes(b"changed")
        return result

    monkeypatch.setattr(ap, "inventory", changed)
    with pytest.raises(WorkspaceBackupError, match="ADOPTION_NOT_COLD"):
        check(inputs)


def test_complete_terminal_profile_revision_and_security_readback(tmp_path, repository_root):
    application, cid = _application(tmp_path, repository_root)
    _advance_to_evaluating(application, cid, repository_root)
    application.evaluate_candidate(
        cid,
        CandidateEvaluateCommand(
            policy_material=application.materialize_policy(
                cid, repository_root / "examples/sample-python-api"
            ),
            expected_revision=3,
            evaluated_at=datetime(2026, 8, 30, 21, tzinfo=UTC),
        ),
        idempotency_key="adoption:evaluate",
    )
    application.attest_candidate(
        cid, CandidateAttestCommand(issued_at=datetime(2026, 8, 30, 22, tzinfo=UTC))
    )
    repo = application.repository
    registration = repo.get_project("sample-api")
    repo.revise_project(
        "sample-api",
        registration.config,
        expected_profile_version=1,
        effective_at=datetime(2026, 9, 1, tzinfo=UTC),
        idempotency_key="adoption:revise",
    )
    repo.append_api_security_event(
        event_type=ApiSecurityEventType.AUTHENTICATION_REJECTED,
        occurred_at=datetime(2026, 9, 1, tzinfo=UTC),
        request_id="adoption-0001",
        outcome_code="API_AUTHENTICATION_REQUIRED",
    )
    jp = tmp_path / "jobs.db"
    CollectionJobStore(jp).initialize()
    root = tmp_path / "terminal.zip"
    digest = backup_workspace(tmp_path / "forgegate.db", jp, root)["sha256"]
    handoff, hhash = handoff_for(root, digest, {}, tmp_path)
    target = tmp_path / "terminal-cold"
    rehearse_recovery(root, target, handoff, handoff_sha256=hhash, dependencies={})
    report = check(
        (root, target, digest, hashlib.sha256((target / "REHEARSAL.json").read_bytes()).hexdigest())
    )
    assert report.comparison == "MATCH"
    counts = {t.table: t.source_rows for t in report.tables}
    assert counts["candidates.attestations"] == 1
    assert counts["candidates.project_profiles"] == 2
    assert counts["candidates.api_security_events"] == 1


def test_schema_only_difference(fixture, tmp_path):
    inputs = prepare(fixture, tmp_path)
    fixture[1].enable_archiving()
    source = tmp_path / "v4.zip"
    digest = backup_workspace(tmp_path / "candidates.db", fixture[1].path, source)["sha256"]
    report = ap.preflight_adoption(
        source, inputs[0], inputs[1], source_sha256=digest, receipt_sha256=inputs[3]
    )
    assert report.comparison == "DIFFERENT" and report.differences_total == 0
    assert report.source_inventory_fingerprint == report.target_inventory_fingerprint
    assert report.source_schema_fingerprint != report.target_schema_fingerprint


@pytest.mark.parametrize("reverse", [False, True])
def test_same_job_count_changed_records_and_both_directions(fixture, tmp_path, reverse):
    application, store, request = fixture
    record = store.submit(request, application, key="one")
    old = prepare(fixture, tmp_path)
    store.cancel(record.job_id, 0)
    newroot = tmp_path / "new.zip"
    digest = backup_workspace(tmp_path / "candidates.db", store.path, newroot)["sha256"]
    if reverse:
        handoff, hhash = handoff_for(newroot, digest, {}, tmp_path)
        target = tmp_path / "new-cold"
        rehearse_recovery(newroot, target, handoff, handoff_sha256=hhash, dependencies={})
        source, target_root, source_hash = old[0], newroot, old[2]
        receipt_hash = hashlib.sha256((target / "REHEARSAL.json").read_bytes()).hexdigest()
    else:
        source, target_root, target, source_hash, receipt_hash = (
            newroot,
            old[0],
            old[1],
            digest,
            old[3],
        )
    report = ap.preflight_adoption(
        source, target_root, target, source_sha256=source_hash, receipt_sha256=receipt_hash
    )
    by_table = {t.table: t for t in report.tables}
    assert by_table["jobs.jobs"].source_rows == by_table["jobs.jobs"].target_rows == 1
    assert by_table["jobs.jobs"].changed == 1
    assert {d.kind for d in report.differences} == {
        "CHANGED",
        "TARGET_ONLY" if reverse else "SOURCE_ONLY",
    }
    result = CliRunner().invoke(
        app,
        [
            "workspace",
            "adoption-preflight",
            str(source),
            str(target_root),
            str(target),
            "--source-sha256",
            source_hash,
            "--receipt-sha256",
            receipt_hash,
        ],
    )
    assert result.exit_code == 2 and json.loads(result.stdout)["comparison"] == "DIFFERENT"


@pytest.mark.parametrize("bound", ["MAX_CELL_BYTES", "MAX_INVENTORY_BYTES"])
def test_byte_bounds(fixture, tmp_path, monkeypatch, bound):
    inputs = prepare(fixture, tmp_path)
    monkeypatch.setattr(ai, bound, 1)
    with pytest.raises(WorkspaceBackupError, match="ADOPTION_BYTE_LIMIT"):
        check(inputs)


def test_deadline_and_sanitized_parser_failure(fixture, tmp_path, monkeypatch):
    inputs = prepare(fixture, tmp_path)

    def fail(*args):
        raise KeyError("private-source-path")

    monkeypatch.setattr(ap, "inspect_domain", fail)
    with pytest.raises(WorkspaceBackupError, match=r"^ADOPTION_DOMAIN_INVALID$"):
        check(inputs)


@pytest.mark.parametrize("payload", ['{"x":1,"x":2}', '{"x":NaN}', "[" * 45 + "]" * 45])
def test_bounded_json_before_reader(fixture, tmp_path, payload):
    inputs = prepare(fixture, tmp_path)
    with closing(sqlite3.connect(tmp_path / "candidates.db")) as con:
        ddl = con.execute(
            "SELECT sql FROM sqlite_master WHERE name='idempotency_records_guard_update'"
        ).fetchone()[0]
        con.execute("DROP TRIGGER idempotency_records_guard_update")
        con.execute("UPDATE idempotency_records SET response_json=?", (payload,))
        con.execute(ddl)
        con.commit()
    source = tmp_path / "corrupt-json.zip"
    digest = backup_workspace(tmp_path / "candidates.db", fixture[1].path, source)["sha256"]
    with pytest.raises(WorkspaceBackupError):
        ap.preflight_adoption(
            source, inputs[0], inputs[1], source_sha256=digest, receipt_sha256=inputs[3]
        )


@pytest.mark.parametrize("kind", ["missing", "same", "wrong_kind"])
def test_difference_contract_rejects_incoherence(kind):
    raw = {
        "table": "jobs.jobs",
        "key_fingerprint": "sha256:" + "0" * 64,
        "kind": "CHANGED",
        "source_fingerprint": "sha256:" + "1" * 64,
        "target_fingerprint": "sha256:" + "2" * 64,
    }
    if kind == "missing":
        raw["target_fingerprint"] = None
    elif kind == "same":
        raw["target_fingerprint"] = raw["source_fingerprint"]
    else:
        raw["kind"] = "SOURCE_ONLY"
    with pytest.raises(ValidationError):
        AdoptionDifference.model_validate(raw)
