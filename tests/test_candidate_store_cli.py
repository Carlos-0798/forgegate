from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from forgegate.cli import app

runner = CliRunner()


def _create_command(
    database: Path,
    *,
    include_key: bool = True,
    created_at: str = "2026-08-31T12:00:00Z",
) -> list[str]:
    command = [
        "candidate",
        "create",
        "--project",
        "sample-api",
        "--version",
        "1.2.0",
        "--commit",
        "a" * 40,
        "--created-at",
        created_at,
        "--database",
        str(database),
    ]
    if include_key:
        command.extend(["--idempotency-key", "create:cli-sample-01"])
    return command


def test_candidate_store_cli_create_advance_show_history_and_replay(tmp_path: Path) -> None:
    database = tmp_path / "forgegate.db"
    initialized = runner.invoke(app, ["candidate", "init-store", str(database)])
    created = runner.invoke(app, _create_command(database))
    replay = runner.invoke(app, _create_command(database))

    assert initialized.exit_code == 0
    assert "INITIALIZED" in initialized.stdout
    assert created.exit_code == replay.exit_code == 0
    draft = json.loads(created.stdout)
    assert json.loads(replay.stdout) == draft

    candidate_id = draft["candidate_id"]
    shown = runner.invoke(app, ["candidate", "show", str(database), candidate_id])
    advanced = runner.invoke(
        app,
        [
            "candidate",
            "advance",
            str(database),
            candidate_id,
            "--to",
            "COLLECTING",
            "--expected-revision",
            "0",
            "--occurred-at",
            "2026-08-31T12:01:00Z",
            "--idempotency-key",
            "advance:cli-sample-01",
            "--reason",
            "begin collection",
        ],
    )
    advanced_replay = runner.invoke(
        app,
        [
            "candidate",
            "advance",
            str(database),
            candidate_id,
            "--to",
            "COLLECTING",
            "--expected-revision",
            "0",
            "--occurred-at",
            "2026-08-31T12:01:00Z",
            "--idempotency-key",
            "advance:cli-sample-01",
            "--reason",
            "begin collection",
        ],
    )
    history = runner.invoke(app, ["candidate", "history", str(database), candidate_id])

    assert shown.exit_code == 0
    assert json.loads(shown.stdout) == draft
    assert advanced.exit_code == advanced_replay.exit_code == 0
    transition_result = json.loads(advanced.stdout)
    assert json.loads(advanced_replay.stdout) == transition_result
    assert transition_result["candidate"]["revision"] == 1
    assert history.exit_code == 0
    history_payload = json.loads(history.stdout)
    assert history_payload["candidate"] == transition_result["candidate"]
    assert history_payload["transitions"] == [transition_result["transition"]]


def test_candidate_store_cli_terminal_transition_loads_evaluation(
    tmp_path: Path, repository_root: Path
) -> None:
    database = tmp_path / "forgegate.db"
    runner.invoke(app, ["candidate", "init-store", str(database)])
    created = runner.invoke(app, _create_command(database, created_at="2026-08-30T12:00:00Z"))
    candidate_id = json.loads(created.stdout)["candidate_id"]
    for revision, (status, timestamp) in enumerate(
        (
            ("COLLECTING", "2026-08-30T12:01:00Z"),
            ("READY", "2026-08-30T12:02:00Z"),
            ("EVALUATING", "2026-08-30T12:03:00Z"),
        )
    ):
        result = runner.invoke(
            app,
            [
                "candidate",
                "advance",
                str(database),
                candidate_id,
                "--to",
                status,
                "--expected-revision",
                str(revision),
                "--occurred-at",
                timestamp,
                "--idempotency-key",
                f"advance:cli-phase-{revision}",
            ],
        )
        assert result.exit_code == 0

    wrong_document = runner.invoke(
        app,
        [
            "candidate",
            "advance",
            str(database),
            candidate_id,
            "--to",
            "PASS",
            "--expected-revision",
            "3",
            "--occurred-at",
            "2026-08-30T21:00:00Z",
            "--idempotency-key",
            "advance:cli-terminal-bad",
            "--evaluation",
            str(repository_root / "examples/sample-python-api/evidence/pass-bundle.json"),
        ],
    )
    terminal = runner.invoke(
        app,
        [
            "candidate",
            "advance",
            str(database),
            candidate_id,
            "--to",
            "PASS",
            "--expected-revision",
            "3",
            "--occurred-at",
            "2026-08-30T21:00:00Z",
            "--idempotency-key",
            "advance:cli-terminal-001",
            "--evaluation",
            str(repository_root / "tests/golden/policy_pass.json"),
        ],
    )

    assert wrong_document.exit_code == 3
    assert "evaluation path must contain" in wrong_document.output
    assert terminal.exit_code == 0
    assert json.loads(terminal.stdout)["candidate"]["status"] == "PASS"


def test_candidate_store_cli_error_contracts(tmp_path: Path) -> None:
    database = tmp_path / "forgegate.db"
    idempotency_without_database = runner.invoke(
        app,
        [
            "candidate",
            "create",
            "--project",
            "sample-api",
            "--version",
            "1.2.0",
            "--commit",
            "a" * 40,
            "--created-at",
            "2026-08-31T12:00:00Z",
            "--idempotency-key",
            "create:unused-0001",
        ],
    )
    missing_store = runner.invoke(app, _create_command(database))
    runner.invoke(app, ["candidate", "init-store", str(database)])
    missing_key = runner.invoke(app, _create_command(database, include_key=False))
    created = runner.invoke(app, _create_command(database))
    candidate_id = json.loads(created.stdout)["candidate_id"]
    invalid_time = runner.invoke(
        app,
        [
            "candidate",
            "advance",
            str(database),
            candidate_id,
            "--to",
            "COLLECTING",
            "--expected-revision",
            "0",
            "--occurred-at",
            "not-a-timestamp",
            "--idempotency-key",
            "advance:invalid-time",
        ],
    )
    missing_candidate = "cand-" + "0" * 24
    show_missing = runner.invoke(app, ["candidate", "show", str(database), missing_candidate])
    history_missing = runner.invoke(app, ["candidate", "history", str(database), missing_candidate])

    assert idempotency_without_database.exit_code == 3
    assert "--idempotency-key requires --database" in idempotency_without_database.output
    assert missing_store.exit_code == 3
    assert "STORE_NOT_INITIALIZED" in missing_store.output
    assert missing_key.exit_code == 3
    assert "--database requires --idempotency-key" in missing_key.output
    assert invalid_time.exit_code == 3
    assert "Invalid isoformat string" in invalid_time.output
    assert show_missing.exit_code == history_missing.exit_code == 3
    assert "STORE_CANDIDATE_NOT_FOUND" in show_missing.output
    assert "STORE_CANDIDATE_NOT_FOUND" in history_missing.output


def test_candidate_store_init_cli_reports_path_errors(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["candidate", "init-store", str(tmp_path / "missing" / "forgegate.db")]
    )
    assert result.exit_code == 3
    assert "STORE_PARENT_MISSING" in result.output
