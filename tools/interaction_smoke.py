from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from forgegate import __version__
from forgegate.api import (
    ApiAuthChallenge,
    ApiAuthenticator,
    ApiSessionResponse,
    create_api_app,
    sign_api_challenge,
)
from forgegate.config import load_config
from forgegate.domain.models import ProjectConfig
from forgegate.identity import (
    IdentityRole,
    IdentityStatus,
    TrustedIdentity,
    create_trust_store,
    derive_signing_identity,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = REPOSITORY_ROOT / "examples" / "sample-python-api"
EVALUATED_AT = "2026-08-30T21:00:00Z"
REGISTERED_AT = "2026-09-04T12:00:00Z"


@dataclass(frozen=True)
class Check:
    surface: str
    case: str
    expected: str
    actual: str


def expect(checks: list[Check], surface: str, case: str, expected: Any, actual: Any) -> None:
    if actual != expected:
        raise RuntimeError(f"{surface}/{case}: expected {expected!r}, got {actual!r}")
    checks.append(Check(surface, case, str(expected), str(actual)))


def run_cli(arguments: list[str], *, expected_exit: int) -> tuple[str, dict[str, Any] | None]:
    completed = subprocess.run(
        [sys.executable, "-m", "forgegate", *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != expected_exit:
        raise RuntimeError(
            f"CLI returned {completed.returncode}, expected {expected_exit}: "
            f"{completed.stderr or completed.stdout}"
        )
    stdout = completed.stdout.strip()
    if not stdout.startswith("{"):
        return stdout, None
    parsed = json.loads(stdout)
    if not isinstance(parsed, dict):
        raise RuntimeError("CLI JSON output must be an object")
    return stdout, parsed


def cli_checks(checks: list[Check], temporary_root: Path) -> None:
    validation, payload = run_cli(
        ["validate-config", str(EXAMPLE_ROOT / "forgegate.yaml")],
        expected_exit=0,
    )
    expect(checks, "CLI", "valid project exit", 0, 0)
    expect(checks, "CLI", "valid project output", True, validation.startswith("VALID "))
    expect(checks, "CLI", "valid project output format", None, payload)

    cases = (
        ("PASS", "pull-request.yaml", "pass-bundle.json", 0, "RULE_SATISFIED"),
        ("FAIL", "pull-request.yaml", "fail-bundle.json", 1, "RULE_NOT_SATISFIED"),
        ("REVIEW", "production.yaml", "pass-bundle.json", 2, "EVIDENCE_MISSING"),
    )
    for decision, policy, evidence, exit_code, reason_code in cases:
        _, evaluation = run_cli(
            [
                "evaluate-policy",
                str(EXAMPLE_ROOT / "policies" / policy),
                str(EXAMPLE_ROOT / "evidence" / evidence),
                "--evaluated-at",
                EVALUATED_AT,
            ],
            expected_exit=exit_code,
        )
        assert evaluation is not None
        expect(checks, "CLI", f"{decision} decision", decision, evaluation["decision"])
        observed_reasons = {item["reason_code"] for item in evaluation["rule_results"]}
        expect(checks, "CLI", f"{decision} reason", True, reason_code in observed_reasons)
        expect(checks, "CLI", f"{decision} exit", exit_code, exit_code)

    invalid_policy = temporary_root / "invalid-evaluation.yaml"
    invalid_policy.write_text(
        """schema_version: forgegate.policy.v1
name: invalid-evaluation
rules:
  - id: unavailable-field
    claim: tests.required-pass
    evidence_kind: test.summary
    operator: equals
    expected: 0
    where:
      field: unavailable
    minimum_trust: claimed_ci_metadata
    minimum_verification: ci_validated
""",
        encoding="utf-8",
    )
    _, evaluation = run_cli(
        [
            "evaluate-policy",
            str(invalid_policy),
            str(EXAMPLE_ROOT / "evidence" / "pass-bundle.json"),
            "--evaluated-at",
            EVALUATED_AT,
        ],
        expected_exit=3,
    )
    assert evaluation is not None
    expect(checks, "CLI", "ERROR decision", "ERROR", evaluation["decision"])
    expect(
        checks,
        "CLI",
        "ERROR reason",
        "EVALUATION_ERROR",
        evaluation["rule_results"][0]["reason_code"],
    )
    expect(checks, "CLI", "ERROR exit", 3, 3)


def response_error_code(response: Any) -> str:
    payload = response.json()
    return str(payload["error"]["code"])


def api_checks(checks: list[Check], temporary_root: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    identity = derive_signing_identity(private_key, display_name="interaction-smoke-operator")
    trust_store = create_trust_store(
        (
            TrustedIdentity(
                identity=identity,
                roles=(IdentityRole.OPERATOR,),
                project_ids=("sample-api",),
                status=IdentityStatus.ACTIVE,
            ),
        )
    )
    application = create_api_app(
        temporary_root / "interaction.db",
        authenticator=ApiAuthenticator(trust_store),
    )
    loaded = load_config(EXAMPLE_ROOT / "forgegate.yaml")
    if not isinstance(loaded, ProjectConfig):
        raise RuntimeError("generic example must load as forgegate.project.v1")

    with TestClient(application, base_url="http://127.0.0.1") as client:
        request_id = "interaction-smoke-0001"
        health = client.get("/healthz", headers={"X-Request-ID": request_id})
        expect(checks, "REST", "health status", 200, health.status_code)
        expect(checks, "REST", "health body status", "ok", health.json()["status"])
        expect(checks, "REST", "health API version", "v1", health.json()["api_version"])
        expect(
            checks,
            "REST",
            "health product version",
            __version__,
            health.json()["forgegate_version"],
        )
        expect(checks, "REST", "request correlation", request_id, health.headers["X-Request-ID"])

        docs = client.get("/docs")
        redoc = client.get("/redoc")
        expect(checks, "REST", "Swagger disabled", 404, docs.status_code)
        expect(checks, "REST", "ReDoc disabled", 404, redoc.status_code)

        unauthenticated = client.get("/v1/projects")
        expect(checks, "REST", "missing session status", 401, unauthenticated.status_code)
        expect(
            checks,
            "REST",
            "missing session code",
            "API_AUTHENTICATION_REQUIRED",
            response_error_code(unauthenticated),
        )

        challenge_response = client.post(
            "/v1/auth/challenges",
            json={
                "identity_id": identity.identity_id,
                "role": "operator",
                "project_ids": ["sample-api"],
            },
        )
        expect(checks, "REST", "challenge status", 201, challenge_response.status_code)
        challenge = ApiAuthChallenge.model_validate(challenge_response.json())
        session_request = sign_api_challenge(
            challenge,
            identity=identity,
            private_key=private_key,
        )
        session_response = client.post(
            "/v1/auth/sessions",
            json=session_request.model_dump(mode="json"),
        )
        expect(checks, "REST", "session status", 201, session_response.status_code)
        session = ApiSessionResponse.model_validate(session_response.json())
        headers = {
            "Authorization": f"Bearer {session.access_token}",
            "Idempotency-Key": "interaction:project:register",
        }
        project_payload = {
            "config": loaded.model_dump(mode="json", by_alias=True),
            "registered_at": REGISTERED_AT,
        }
        created = client.post("/v1/projects", headers=headers, json=project_payload)
        replay = client.post("/v1/projects", headers=headers, json=project_payload)
        shown = client.get(
            "/v1/projects/sample-api",
            headers={"Authorization": headers["Authorization"]},
        )
        expect(checks, "REST", "project register status", 201, created.status_code)
        expect(checks, "REST", "idempotent replay status", 201, replay.status_code)
        expect(checks, "REST", "project read status", 200, shown.status_code)
        expect(
            checks,
            "REST",
            "idempotent replay body",
            "identical",
            "identical" if replay.json() == created.json() else "different",
        )
        expect(
            checks,
            "REST",
            "project read body",
            "identical",
            "identical" if shown.json() == created.json() else "different",
        )

        strict_rejection = client.post(
            "/v1/projects",
            headers=headers,
            json={**project_payload, "unexpected": True},
        )
        expect(checks, "REST", "unknown field status", 422, strict_rejection.status_code)
        expect(
            checks,
            "REST",
            "unknown field code",
            "API_REQUEST_VALIDATION_FAILED",
            response_error_code(strict_rejection),
        )


def main() -> int:
    checks: list[Check] = []
    with tempfile.TemporaryDirectory(prefix="forgegate-interaction-") as temporary:
        temporary_root = Path(temporary)
        cli_checks(checks, temporary_root)
        api_checks(checks, temporary_root)
    report = {
        "result": "PASS",
        "evidence_boundary": "LOCAL_HOST_TEST",
        "hardware_access": "NOT_PERFORMED",
        "checks": [asdict(check) for check in checks],
        "summary": {
            "total": len(checks),
            "passed": len(checks),
            "failed": 0,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
