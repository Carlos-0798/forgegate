"""Real isolated CLI startup/restart/correlation; no user service or hardware access."""

from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import IO

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from forgegate.candidates import SQLiteCandidateRepository
from forgegate.collection_jobs import CollectionJobStore
from forgegate.identity import (
    IdentityRole,
    IdentityStatus,
    TrustedIdentity,
    create_trust_store,
    derive_signing_identity,
)


def run() -> dict[str, object]:
    env = {key: value for key, value in os.environ.items() if key.upper() != "PYTHONPATH"}
    cases: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="forgegate-pair-") as directory:
        root = Path(directory).resolve(strict=True)
        candidate, jobs = root / "candidate.db", root / "jobs.db"
        SQLiteCandidateRepository(candidate).initialize()
        CollectionJobStore(jobs).initialize()
        trust = create_trust_store(
            (
                TrustedIdentity(
                    identity=derive_signing_identity(
                        Ed25519PrivateKey.generate(), display_name="pair-smoke"
                    ),
                    roles=(IdentityRole.OPERATOR,),
                    project_ids=("pair-smoke",),
                    status=IdentityStatus.ACTIVE,
                ),
            )
        )
        trust_path = root / "trust.json"
        trust_path.write_text(trust.model_dump_json(), encoding="utf-8")
        previous: dict[str, str] | None = None
        for attempt in range(2):
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            command = [
                sys.executable,
                "-m",
                "forgegate",
                "dashboard",
                "--existing-pair",
                "--database",
                str(candidate),
                "--job-store",
                str(jobs),
                "--trust-store",
                str(trust_path),
                "--port",
                str(port),
            ]
            process = subprocess.Popen(
                command,
                cwd=root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            messages: queue.Queue[str] = queue.Queue()
            assert process.stdout is not None
            stream = process.stdout

            def read_lines(
                source: IO[str] = stream,
                destination: queue.Queue[str] = messages,
            ) -> None:
                for line in source:
                    destination.put(line)

            reader = threading.Thread(target=read_lines, daemon=True)
            reader.start()
            try:
                deadline = time.monotonic() + 20
                receipt = None
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        line = messages.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if line.startswith("ForgeGate runtime: "):
                        receipt = json.loads(line.removeprefix("ForgeGate runtime: "))
                    if "Application startup complete" in line:
                        break
                if receipt is None or process.poll() is not None:
                    raise RuntimeError("PAIR_SMOKE_START_FAILED")
                check = [sys.executable, "-m", "forgegate", "dashboard-check", "--port", str(port)]

                def observe(
                    expected: dict[str, str],
                    check_command: list[str] = check,
                ) -> tuple[int, dict[str, object]]:
                    result = subprocess.run(
                        [
                            *check_command,
                            "--expected-runtime-id",
                            expected["runtime_id"],
                            "--expected-store-pair-id",
                            expected["store_pair_id"],
                        ],
                        cwd=root,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    return result.returncode, json.loads(result.stdout)

                code, report = observe(receipt)
                if code != 0 or report["runtime_correlation"] != "MATCH_NOT_AUTHENTICATED":
                    raise RuntimeError("PAIR_SMOKE_CORRELATION_FAILED")
                cases.append({"case": f"start_{attempt + 1}", "exit_code": code, **report})
                wrong = {**receipt, "store_pair_id": "0" * 32}
                code, report = observe(wrong)
                if code != 3 or report["status"] != "RUNTIME_IDENTITY_MISMATCH":
                    raise RuntimeError("PAIR_SMOKE_WRONG_PAIR_ACCEPTED")
                cases.append({"case": f"wrong_pair_{attempt + 1}", "exit_code": code, **report})
                if previous is not None:
                    if any(
                        previous[key] == receipt[key] for key in ("runtime_id", "store_pair_id")
                    ):
                        raise RuntimeError("PAIR_SMOKE_ID_REUSED")
                    code, report = observe(previous)
                    if code != 3 or report["status"] != "RUNTIME_IDENTITY_MISMATCH":
                        raise RuntimeError("PAIR_SMOKE_STALE_START_ACCEPTED")
                    cases.append({"case": "prior_start_refused", "exit_code": code, **report})
                previous = receipt
            finally:
                # Only the exact child Popen handle created above; no PID/port lookup.
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=15)
                reader.join(timeout=5)
                stream.close()
        missing = root / "missing.db"
        command[command.index("--database") + 1] = str(missing)
        refused = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=15)
        if refused.returncode != 3 or missing.exists():
            raise RuntimeError("PAIR_SMOKE_MISSING_STORE_CREATED")
        cases.append({"case": "missing_candidate_refused", "exit_code": 3, "created": False})
    return {
        "evidence": "LOCAL_HOST_TEST",
        "cases": cases,
        "hardware_access": "NOT_PERFORMED",
        "browser_interaction": "NOT_TESTED",
        "managed_process_ownership": "NOT_IMPLEMENTED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(), indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
