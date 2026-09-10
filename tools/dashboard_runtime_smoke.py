"""Actual loopback HTTP smoke with owned temporary servers; never access hardware."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from forgegate.api import ApiAuthenticator, create_api_app
from forgegate.dashboard.runtime import check_dashboard
from forgegate.identity import (
    IdentityRole,
    IdentityStatus,
    TrustedIdentity,
    create_trust_store,
    derive_signing_identity,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results: list[dict[str, object]] = []
    trust = create_trust_store(
        (
            TrustedIdentity(
                identity=derive_signing_identity(
                    Ed25519PrivateKey.generate(), display_name="runtime-smoke"
                ),
                roles=(IdentityRole.OPERATOR,),
                project_ids=("runtime-smoke",),
                status=IdentityStatus.ACTIVE,
            ),
        )
    )
    with tempfile.TemporaryDirectory(prefix="forgegate-runtime-") as temporary:
        root = Path(temporary).resolve(strict=True)
        for dashboard, expected in ((True, "DASHBOARD_REACHABLE"), (False, "DASHBOARD_HTTP_ERROR")):
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
                api = create_api_app(
                    root / f"{dashboard}.db",
                    authenticator=ApiAuthenticator(trust),
                    dashboard=dashboard,
                )
                server = uvicorn.Server(uvicorn.Config(api, log_level="error", access_log=False))
                thread = threading.Thread(
                    target=server.run, kwargs={"sockets": [listener]}, daemon=True
                )
                thread.start()
                try:
                    deadline = time.monotonic() + 10
                    while not server.started and thread.is_alive() and time.monotonic() < deadline:
                        time.sleep(0.02)
                    if not server.started:
                        raise RuntimeError("isolated runtime server did not start")
                    completed = subprocess.run(
                        [sys.executable, "-m", "forgegate", "dashboard-check", "--port", str(port)],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=False,
                    )
                    report = json.loads(completed.stdout)
                    if report["status"] != expected or completed.returncode != (
                        0 if dashboard else 3
                    ):
                        raise RuntimeError("installed diagnostic returned an unexpected result")
                    results.append({"case": "dashboard" if dashboard else "api_only", **report})
                finally:
                    # Stop only this in-process fixture, never a PID discovered on the host.
                    server.should_exit = True
                    thread.join(timeout=10)
                    if thread.is_alive():
                        raise RuntimeError("isolated runtime server failed to stop")
            stopped = check_dashboard(port=port).to_dict()
            if stopped["status"] != "CONNECTION_REFUSED":
                raise RuntimeError("stopped fixture was not reported as connection refused")
            results.append({"case": "stopped_dashboard" if dashboard else "stopped_api", **stopped})
    payload = (
        json.dumps(
            {
                "observed_at": datetime.now(UTC).isoformat(),
                "evidence": "LOCAL_HOST_TEST",
                "hardware_access": "NOT_PERFORMED",
                "cases": results,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if args.output:
        # Preserve previous evidence; never overwrite an existing receipt.
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
