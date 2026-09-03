from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from forgegate.assembly import EvidenceBundleAssembly
from forgegate.canonical import canonical_json
from forgegate.collectors import CollectionResult
from forgegate.plugins import PluginRunPage, PluginRunReceipt, PluginRunRecord, PluginRunState
from forgegate.policy.models import PolicyEvaluation

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DISTRIBUTION = "forgegate-sample-collector-plugin"
PLUGIN_ID = "example.forgegate-sample-collector"
DEFAULT_EVIDENCE = REPOSITORY_ROOT / "reports/PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json"


class LiveBrokerVerificationError(RuntimeError):
    pass


def _run_cli(command: list[str], *, cwd: Path, expected: int = 0) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "forgegate", *command],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != expected:
        issue_code = None
        try:
            payload = json.loads(completed.stdout)
            issue_code = payload.get("result", {}).get("issue", {}).get("code")
        except (json.JSONDecodeError, AttributeError):
            pass
        if issue_code is None:
            match = re.search(r"\bPLUGIN_[A-Z_]+\b", completed.stdout + completed.stderr)
            issue_code = match.group(0) if match is not None else None
        detail = f" ({issue_code})" if isinstance(issue_code, str) else ""
        raise LiveBrokerVerificationError(
            f"CLI command returned {completed.returncode}, expected {expected}: "
            + " ".join(command[:3])
            + detail
        )
    return completed.stdout


def _path_free(root: Path, *payloads: str) -> bool:
    forbidden = str(root).replace("\\", "/").casefold()
    return all(forbidden not in payload.replace("\\", "/").casefold() for payload in payloads)


def verify_live_broker(
    *, evidence_path: Path = DEFAULT_EVIDENCE, podman: Path | None = None
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    planned_at = started_at.isoformat().replace("+00:00", "Z")
    input_payload = canonical_json(
        {
            "collected_at": planned_at,
            "commit_sha": "a" * 40,
        }
    ).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="forgegate-live-broker-") as raw_root:
        root = Path(raw_root)
        artifacts = root / "artifacts"
        state = root / "state"
        work = state / "work"
        outputs = state / "outputs"
        database = state / "plugin-runs.db"
        input_path = artifacts / "inputs/synthetic.json"
        input_path.parent.mkdir(parents=True)
        input_path.write_bytes(input_payload)

        run_command = [
            "plugins",
            "run",
            PLUGIN_ID,
            "--input",
            "inputs/synthetic.json=application/json",
            "--grant",
            "artifact-read",
            "--grant",
            "filesystem-write",
            "--sandbox-evidence",
            str(evidence_path.resolve(strict=True)),
            "--idempotency-key",
            "phase21:windows-alpha:success",
            "--planned-at",
            planned_at,
            "--database",
            str(database),
            "--root",
            str(artifacts),
            "--work-root",
            str(work),
            "--accepted-output-root",
            str(outputs),
        ]
        if podman is not None:
            run_command.extend(("--podman", str(podman.resolve(strict=True))))
        first_text = _run_cli(run_command, cwd=root)
        replay_text = _run_cli(run_command, cwd=root)
        receipt = PluginRunReceipt.model_validate_json(first_text)
        replay = PluginRunReceipt.model_validate_json(replay_text)
        if receipt.result.status is not PluginRunState.SUCCEEDED or receipt != replay:
            raise LiveBrokerVerificationError("operator CLI run or exact replay did not succeed")
        run_plan_id = receipt.result.run_plan.run_plan_id

        record_text = _run_cli(["plugins", "show", str(database), run_plan_id], cwd=root)
        record = PluginRunRecord.model_validate_json(record_text)
        page_text = _run_cli(
            ["plugins", "runs", str(database), "--limit", "100"],
            cwd=root,
        )
        page = PluginRunPage.model_validate_json(page_text)
        collection_text = _run_cli(
            [
                "plugins",
                "collect",
                str(database),
                run_plan_id,
                "--root",
                str(artifacts),
                "--accepted-output-root",
                str(outputs),
            ],
            cwd=root,
        )
        collection = CollectionResult.model_validate_json(collection_text)
        collection_path = artifacts / "plugin.collection.json"
        collection_path.write_text(collection_text, encoding="utf-8", newline="\n")
        generated_at = (started_at + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        assembly_text = _run_cli(
            [
                "assemble-evidence",
                "plugin.collection.json",
                "--root",
                str(artifacts),
                "--commit",
                "a" * 40,
                "--generated-at",
                generated_at,
            ],
            cwd=root,
        )
        assembly = EvidenceBundleAssembly.model_validate_json(assembly_text)
        assembly_path = artifacts / "plugin.assembly.json"
        assembly_path.write_text(assembly_text, encoding="utf-8", newline="\n")
        policy_path = root / "plugin-policy.yaml"
        policy_path.write_text(
            """schema_version: forgegate.policy.v1
name: plugin-smoke
rules:
  - id: plugin-output-present
    claim: plugin.output-present
    evidence_kind: sample.metric
    aggregation: count
    operator: greater_than_or_equal
    expected: 1
    mandatory: true
    require_presence: true
    on_missing: REVIEW
    minimum_trust: unsigned_local
    minimum_verification: declared
""",
            encoding="utf-8",
            newline="\n",
        )
        evaluation_text = _run_cli(
            [
                "evaluate-policy",
                str(policy_path),
                str(assembly_path),
                "--evaluated-at",
                generated_at,
            ],
            cwd=root,
        )
        evaluation = PolicyEvaluation.model_validate_json(evaluation_text)

        tampered_evidence = root / "tampered-sandbox-evidence.json"
        raw_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        raw_evidence["verification_id"] = "sha256:" + "0" * 64
        tampered_evidence.write_text(
            json.dumps(raw_evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        failed_time = (started_at + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        failed_command = list(run_command)
        failed_command[failed_command.index("--sandbox-evidence") + 1] = str(tampered_evidence)
        failed_command[failed_command.index("--idempotency-key") + 1] = (
            "phase21:windows-alpha:failure"
        )
        failed_command[failed_command.index("--planned-at") + 1] = failed_time
        failed_text = _run_cli(failed_command, cwd=root, expected=3)
        failed = PluginRunReceipt.model_validate_json(failed_text)
        failed_record_text = _run_cli(
            ["plugins", "show", str(database), failed.result.run_plan.run_plan_id],
            cwd=root,
        )
        failed_record = PluginRunRecord.model_validate_json(failed_record_text)
        _run_cli(
            [
                "plugins",
                "collect",
                str(database),
                failed.result.run_plan.run_plan_id,
                "--root",
                str(artifacts),
                "--accepted-output-root",
                str(outputs),
            ],
            cwd=root,
            expected=3,
        )
        final_page_text = _run_cli(
            ["plugins", "runs", str(database), "--limit", "100"],
            cwd=root,
        )
        final_page = PluginRunPage.model_validate_json(final_page_text)

        accepted = tuple(outputs.rglob("*.json"))
        if len(accepted) != 1:
            raise LiveBrokerVerificationError("broker did not register exactly one accepted output")
        output = json.loads(accepted[0].read_bytes())
        observations = output["evidence"]["value"]
        checks = {
            "input_read": observations.get("input_read") is True,
            "input_write_denied": observations.get("input_write_denied") is True,
            "root_write_denied": observations.get("root_write_denied") is True,
            "host_read_denied": observations.get("host_read_denied") is True,
            "network_denied": observations.get("network_denied") is True,
            "subprocess_denied": observations.get("subprocess_denied") is True,
            "environment_sanitized": observations.get("environment_keys")
            == ["FORGEGATE_RUN_PLAN_ID", "LC_CTYPE"],
            "protocol_complete": [item.kind.value for item in receipt.protocol_messages]
            == ["START", "READY", "RESULT"],
            "double_snapshot_validated": receipt.accepted_outputs_registered,
            "cleanup_verified": receipt.cleanup.container_removed
            and receipt.cleanup.staging_removed,
            "durable_replay_exact": replay.receipt_id == receipt.receipt_id,
            "durable_store_readback": record.receipt == receipt,
            "path_free_queries": _path_free(
                root,
                first_text,
                replay_text,
                record_text,
                page_text,
                final_page_text,
            ),
            "collection_boundary": collection.evidence == assembly.bundle.evidence,
            "low_trust_output": output["evidence"]["trust"] == "unsigned_local"
            and output["evidence"]["verification_level"] == "declared",
            "policy_chain_pass": evaluation.decision.value == "PASS",
            "failed_run_persisted": failed.result.status is PluginRunState.ERROR
            and failed_record.receipt == failed,
            "run_page_complete": len(final_page.runs) == 2 and len(page.runs) == 1,
        }

    report: dict[str, Any] = {
        "report_format": "forgegate.windows-alpha-plugin-chain-verification.v1",
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "plugin_distribution": PLUGIN_DISTRIBUTION,
        "plugin_id": PLUGIN_ID,
        "run_plan_id": receipt.result.run_plan.run_plan_id,
        "receipt": receipt.model_dump(mode="json"),
        "checks": [{"control": name, "passed": passed} for name, passed in sorted(checks.items())],
        "production_broker_verified": all(checks.values()),
        "advertised_isolation_tier": "SANDBOXED" if all(checks.values()) else "NONE",
        "evidence_level": "LOCAL_HOST_TEST",
        "hardware_access": "NOT_PERFORMED",
        "limitations": [
            "The executed plugin is the ForgeGate-owned generic package fixture.",
            "The accepted evidence remains unsigned_local and declared.",
            "Linux and macOS external-plugin execution remain unsupported.",
            "A PASS decision here covers only the generic plugin-chain smoke policy.",
        ],
    }
    report["verification_id"] = (
        "sha256:" + hashlib.sha256(canonical_json(report).encode("utf-8")).hexdigest()
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute the installed generic plugin through the Windows Alpha CLI chain."
    )
    parser.add_argument("--sandbox-evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--podman", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        report = verify_live_broker(
            evidence_path=arguments.sandbox_evidence,
            podman=arguments.podman,
        )
    except (LiveBrokerVerificationError, ValueError, OSError) as exc:
        print(f"Windows Alpha plugin-chain verification: ERROR ({exc})")
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if arguments.output is not None:
        arguments.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if report["production_broker_verified"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
