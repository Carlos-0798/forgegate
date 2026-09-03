from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Any


def _denied(operation: Any) -> bool:
    try:
        operation()
    except BaseException:
        return True
    return False


def plugin(request: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Generic hostile collector used only by the production broker test."""

    subject = request["inputs"][0]
    path = Path(subject["path"])
    content = path.read_bytes()
    source = json.loads(content.decode("utf-8"))
    network_denied = True
    connection = socket.socket()
    connection.settimeout(0.25)
    try:
        network_denied = connection.connect_ex(("1.1.1.1", 53)) != 0
    finally:
        connection.close()
    observations = {
        "input_read": hashlib.sha256(content).hexdigest() == subject["digest"].split(":", 1)[1],
        "input_write_denied": _denied(lambda: path.write_bytes(b"mutated")),
        "root_write_denied": _denied(lambda: Path("/forgegate-host-write").write_text("x")),
        "host_read_denied": _denied(lambda: Path("/mnt/c/Windows/win.ini").read_bytes()),
        "network_denied": network_denied,
        "subprocess_denied": _denied(
            lambda: subprocess.run(["/usr/local/bin/python", "-c", "pass"], check=False)
        ),
        "environment_keys": sorted(os.environ),
    }
    evidence = {
        "evidence_id": "plugin.sample.sandbox",
        "kind": "sample.metric",
        "scope": "generic-production-broker-fixture",
        "value": observations,
        "unit": None,
        "status": "observed",
        "source_tool": "forgegate-sample-collector",
        "source_version": "0.2.0",
        "execution_context": {
            "commit_sha": source["commit_sha"],
            "operating_system": "linux",
            "architecture": None,
            "runtime": "python-sandbox",
            "ci_provider": None,
            "ci_run_id": None,
            "tags": {"forgegate_plugin_protocol": "1"},
        },
        "artifact": {
            "path_or_uri": subject["name"],
            "media_type": subject["media_type"],
            "sha256": subject["digest"].split(":", 1)[1],
            "size_bytes": subject["size_bytes"],
        },
        "collected_at": source["collected_at"],
        "trust": "unsigned_local",
        "verification_level": "declared",
        "tags": {"fixture": "production-broker"},
    }
    return {"evidence": [evidence]}
