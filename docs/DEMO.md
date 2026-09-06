# Reproducible CLI walkthrough

This walkthrough records a small, reviewer-friendly ForgeGate path using only
committed generic fixtures. It is intended to make the README demonstration
independently reproducible, not to replace the full verification suite.

## Evidence boundary

- Remote presentation baseline: `690123efcba79a699f356a73a557f804a8267ec9`
- Reproduced: 2026-09-04
- Host: Windows 11
- Python: 3.12.10
- Evidence level: `LOCAL_HOST_TEST`
- Hardware/device access: none
- Analog measurement: none
- Production deployment: none

The README terminal image is a formatted excerpt of the output below. The
commands and values have not been substituted with results from another
project.

## 1. Validate the generic project contract

Run from the repository root after environment setup:

```powershell
.\.venv\Scripts\python.exe -m forgegate validate-config `
  examples\sample-python-api\forgegate.yaml
```

Exact output:

```text
VALID forgegate.project.v1: examples\sample-python-api\forgegate.yaml
```

This proves that the committed generic project document satisfies the current
ForgeGate model. It does not run tests, collect evidence, or make a release
decision.

## 2. Evaluate the committed PASS fixture

```powershell
.\.venv\Scripts\python.exe -m forgegate evaluate-policy `
  examples\sample-python-api\policies\pull-request.yaml `
  examples\sample-python-api\evidence\pass-bundle.json `
  --evaluated-at 2026-08-30T21:00:00Z
```

Exact output:

```json
{
  "schema_version": "forgegate.policy-evaluation.v1",
  "evaluation_id": "sha256:4ca0363cda7045ad855461a93f122d66561f5bd1017b68fa3cdb3c486cd8eb98",
  "policy_name": "pull-request",
  "policy_fingerprint": "sha256:26de07d5718ca9d55362a958791d98993d6dc79ea244f48c003e32bd3a4f0f3d",
  "evidence_fingerprint": "sha256:9fb8fb19e9a44e4c830b7060bf4824231affbbcf56c43f097fe6c53a492ca861",
  "candidate_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "evaluated_at": "2026-08-30T21:00:00Z",
  "decision": "PASS",
  "rule_results": [
    {
      "rule_id": "tests-pass",
      "claim": "tests.required-pass",
      "decision": "PASS",
      "mandatory": true,
      "evidence_kind": "test.summary",
      "aggregation": "value",
      "operator": "equals",
      "expected": 0,
      "actual": 0,
      "evidence_ids": [
        "test-summary-d5babd93ca28025f"
      ],
      "reason_code": "RULE_SATISFIED",
      "explanation": "Eligible evidence satisfies the policy expression.",
      "remediation_hint": null
    }
  ],
  "evaluated_evidence_ids": [
    "test-summary-d5babd93ca28025f"
  ]
}
```

The command returns exit code `0`. The PASS applies only to this committed
generic policy/evidence fixture at the explicit timestamp. ForgeGate does not
rerun the producer's tests or authenticate the producer while evaluating it.

## 3. Run the interaction acceptance matrix

```powershell
.\.venv\Scripts\python.exe tools\interaction_smoke.py
```

The command creates an ephemeral Ed25519 operator identity and temporary
SQLite database, then compares 33 expected and actual outcomes:

| Surface | Samples | Expected result |
|---|---|---|
| CLI | project validation | exit `0`, `VALID` output |
| CLI | PASS / FAIL / REVIEW / ERROR | decisions and exits `0` / `1` / `2` / `3` |
| REST | health and request correlation | HTTP `200`, exact API/product metadata, echoed request ID |
| REST | Swagger UI and ReDoc | HTTP `404`; deliberately disabled, not a missing dashboard |
| REST | unauthenticated read | HTTP `401`, `API_AUTHENTICATION_REQUIRED` |
| REST | challenge and session | HTTP `201` after a real Ed25519 signature exchange |
| REST | project registration, replay, read | `201` / `201` / `200`, identical documents |
| REST | unknown request field | HTTP `422`, `API_REQUEST_VALIDATION_FAILED` |

Successful output ends with `result: PASS`, `33` passed, `0` failed,
`LOCAL_HOST_TEST`, and `hardware_access: NOT_PERFORMED`. The report never
prints the generated private key or Bearer token, retains neither, and deletes
the temporary database when the process exits.

## 4. Run the accepted quality gates

```powershell
.\.venv\Scripts\python.exe tools\verify.py
.\.venv\Scripts\python.exe tools\release_smoke.py
```

These are the same repository entry points executed by the current CI
workflow. The hosted jobs do not execute the local Podman/WSL2 hostile fixtures.
Current results and exceptions belong in the
[verification matrix](VERIFICATION_MATRIX.md), not in this walkthrough.

## 5. Open the authenticated local Dashboard

Prerequisite: an initialized database containing at least one registered
project, plus an owner-managed `forgegate.trust-store.v1`, matching public
identity document, and existing Ed25519 private key. Keep these files under an
ignored local directory such as `work/`; never commit the private key.

```powershell
.\.venv\Scripts\forgegate.exe dashboard `
  --database work\forgegate.db `
  --trust-store work\trust-store.json
```

Open the printed loopback `/app/` URL, choose **Start local activation**, then
approve its short code from a second terminal:

```powershell
.\.venv\Scripts\forgegate.exe dashboard-activate FG-ABCDE-FGHJK `
  --server http://127.0.0.1:8000 `
  --identity work\operator-identity.json `
  --private-key work\operator-private-key.pem `
  --role operator `
  --project sample-api
```

Use the exact origin printed on the page, including any non-default port such
as 8131. Run from the environment containing ForgeGate and replace all local
identity/key/role/project placeholders. The displayed one-time code expires;
generate a fresh code if the page reports expiry. Failed requests have an
explicit manual retry; a returned Retry-After delay never auto-submits.

The page exposes Overview, Devices (when explicitly configured), Projects,
Candidates, Evidence, Decision, and Assurance. Operators can review and confirm
the implemented candidate workflow and portable ZIP download; collection,
plugins, and administration remain separate CLI/API work or planned gates.
Keep the service process running while using the page. A browser bookmark does
not start ForgeGate; `ERR_CONNECTION_REFUSED` means the local service must be
checked and started, not that internet access or private-key entry is needed.
Stop the first terminal process explicitly when finished. The current
manual test boundary is retained in the
[Dashboard acceptance matrix](DASHBOARD_ACCEPTANCE_MATRIX.md).

## Deeper workflows

- [Candidate lifecycle](architecture/CANDIDATE_LIFECYCLE.md)
- [Evidence assembly](architecture/EVIDENCE_BUNDLE_ASSEMBLY.md)
- [Portable assurance bundles](architecture/PORTABLE_ASSURANCE_BUNDLES.md)
- [Authenticated local API](architecture/AUTHENTICATED_LOCAL_API.md)
- [Authenticated local Dashboard](architecture/LOCAL_WEB_DASHBOARD.md)
- [GitHub Actions gate](architecture/GITHUB_ACTIONS_GATE.md)
- [Windows plugin sandbox](architecture/WINDOWS_PLUGIN_SANDBOX.md)
- [Plugin operator workflow](architecture/PLUGIN_OPERATOR_WORKFLOW.md)

Commands involving signing keys, trust stores, or live plugin execution should
be run only after reading the corresponding security and architecture boundary.
