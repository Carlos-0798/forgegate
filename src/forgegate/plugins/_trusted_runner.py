"""Trusted container-side runner.

This module is copied as source into the disposable sandbox.  It intentionally
uses only the Python standard library and is never asked to import a plugin in
the ForgeGate core process.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

INPUT_ROOT = Path("/forgegate/input")
CONTROL_ROOT = Path("/forgegate/control")
OUTPUT_ROOT = Path("/forgegate/output")
PROTOCOL_ROOT = OUTPUT_ROOT / "protocol"
EVIDENCE_ROOT = OUTPUT_ROOT / "evidence"
EVIDENCE_ID = re.compile(r"^[a-z][a-z0-9._-]{1,127}$")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _write_exclusive(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)
        handle.flush()


def _message(
    *,
    run_plan_id: str,
    sequence: int,
    kind: str,
    output_set_id: str | None = None,
    issue_code: str | None = None,
) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "protocol_version": "1",
        "run_plan_id": run_plan_id,
        "sequence": sequence,
        "direction": "PLUGIN_TO_CORE",
        "kind": kind,
        "run_plan": None,
        "output_set_id": output_set_id,
        "issue": {"code": issue_code} if issue_code is not None else None,
    }
    return {
        "schema_version": "forgegate.plugin-protocol-message.v1",
        "message_id": _fingerprint(identity),
        **identity,
    }


def _write_terminal(message: dict[str, Any]) -> None:
    _write_exclusive(PROTOCOL_ROOT / "terminal.json", _canonical_bytes(message))
    time.sleep(3600)


def _fail(run_plan_id: str, code: str, *, sequence: int) -> None:
    try:
        _write_terminal(
            _message(
                run_plan_id=run_plan_id,
                sequence=sequence,
                kind="ERROR",
                issue_code=code,
            )
        )
    except BaseException:
        raise SystemExit(70) from None


def _load_start() -> tuple[dict[str, Any], dict[str, Any]]:
    raw = (CONTROL_ROOT / "start.json").read_bytes()
    if len(raw) > 1024 * 1024 or b"\x00" in raw:
        raise ValueError("invalid START message")
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict) or document.get("kind") != "START":
        raise ValueError("invalid START message")
    plan = document.get("run_plan")
    if not isinstance(plan, dict) or plan.get("run_plan_id") != document.get("run_plan_id"):
        raise ValueError("invalid run plan")
    return document, plan


def _plugin_request(plan: dict[str, Any]) -> dict[str, Any]:
    inputs = plan.get("inputs")
    if not isinstance(inputs, list):
        raise ValueError("invalid inputs")
    request_inputs: list[dict[str, Any]] = []
    for subject in inputs:
        if not isinstance(subject, dict) or not isinstance(subject.get("name"), str):
            raise ValueError("invalid input subject")
        request_inputs.append(
            {
                **subject,
                "path": str(INPUT_ROOT / subject["name"]),
            }
        )
    return {
        "protocol_version": "1",
        "run_plan_id": plan["run_plan_id"],
        "input_schema": plan["input_schema"],
        "inputs": request_inputs,
    }


def _load_callable(plan: dict[str, Any]) -> Any:
    value = plan["target"]["entry_point_value"]
    module_name, attribute = value.split(":", maxsplit=1)
    sys.path.insert(0, str(CONTROL_ROOT / "plugin"))
    module = importlib.import_module(module_name)
    callable_value = getattr(module, attribute)
    if not callable(callable_value):
        raise TypeError("plugin entry point is not callable")
    return callable_value


def _serialize_outputs(plan: dict[str, Any], response: Any) -> str:
    if not isinstance(response, dict) or set(response) != {"evidence"}:
        raise ValueError("plugin response shape is invalid")
    evidence_items = response["evidence"]
    if not isinstance(evidence_items, list) or not evidence_items:
        raise ValueError("plugin response requires evidence")
    limits = plan["resource_limits"]
    if len(evidence_items) > limits["file_count"]:
        raise ValueError("plugin response exceeds the file limit")
    validated: list[dict[str, Any]] = []
    total_bytes = 0
    seen: set[str] = set()
    for evidence in evidence_items:
        if not isinstance(evidence, dict):
            raise ValueError("plugin evidence must be an object")
        evidence_id = evidence.get("evidence_id")
        if not isinstance(evidence_id, str) or EVIDENCE_ID.fullmatch(evidence_id) is None:
            raise ValueError("plugin evidence ID is invalid")
        if evidence_id in seen:
            raise ValueError("plugin evidence IDs must be unique")
        seen.add(evidence_id)
        output_name = f"evidence/{evidence_id}.json"
        output_document = {
            "schema_version": "forgegate.plugin-output.v1",
            "run_plan_id": plan["run_plan_id"],
            "evidence": evidence,
        }
        content = _canonical_bytes(output_document)
        total_bytes += len(content)
        if total_bytes > limits["output_bytes"]:
            raise ValueError("plugin response exceeds the output byte limit")
        _write_exclusive(OUTPUT_ROOT / output_name, content)
        subject = {
            "name": output_name,
            "media_type": "application/vnd.forgegate.plugin-output+json",
            "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
        output_identity = {
            "subject": subject,
            "evidence_kind": evidence.get("kind"),
            "evidence_id": evidence_id,
            "validation": "CORE_REHASHED_AND_SCHEMA_VALIDATED",
        }
        validated.append({"output_id": _fingerprint(output_identity), **output_identity})
    validated.sort(
        key=lambda item: (
            item["subject"]["name"],
            item["subject"]["digest"],
            item["evidence_id"],
        )
    )
    return _fingerprint({"outputs": validated})


def main() -> int:
    try:
        _, plan = _load_start()
        run_plan_id = plan["run_plan_id"]
    except BaseException:
        return 64
    try:
        ready = _message(run_plan_id=run_plan_id, sequence=1, kind="READY")
        _write_exclusive(PROTOCOL_ROOT / "ready.json", _canonical_bytes(ready))
        plugin = _load_callable(plan)
        output_set_id = _serialize_outputs(plan, plugin(_plugin_request(plan)))
        _write_terminal(
            _message(
                run_plan_id=run_plan_id,
                sequence=2,
                kind="RESULT",
                output_set_id=output_set_id,
            )
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        _fail(run_plan_id, "PLUGIN_OUTPUT_INVALID", sequence=2)
    except BaseException:
        _fail(run_plan_id, "PLUGIN_EXIT_ERROR", sequence=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
