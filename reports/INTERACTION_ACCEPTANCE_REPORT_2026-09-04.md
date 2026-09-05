# Interaction acceptance report

- Date: 2026-09-04
- Product: ForgeGate `0.1.0a1`
- Source: local `codex/interaction-acceptance` branch based on private `main`
  checkpoint `690123efcba79a699f356a73a557f804a8267ec9`
- Host evidence: Windows 11, Python 3.12.10
- Evidence level: `LOCAL_HOST_TEST`
- Hardware access: `NOT_PERFORMED`
- Remote publication status: not pushed by this report

## Outcome

**PASS for the implemented CLI and authenticated loopback REST interaction
surfaces.** All 33 deterministic interaction checks matched their expected
outputs. Full development verification and clean-install release smoke also
passed after the interaction checker was added to the accepted verification
entry point.

This is a local software checkpoint. It is not browser-dashboard, hardware,
network-deployment, production, or general third-party-plugin evidence.

## Improvements completed

- Added `tools/interaction_smoke.py`, a reproducible expected-versus-actual
  checker using only the committed generic sample plus temporary test state.
- Covered project validation and the complete `PASS`, `FAIL`, `REVIEW`, and
  `ERROR` decision/exit-code contract.
- Exercised a real ephemeral Ed25519 challenge signature and Bearer session,
  authenticated project registration, exact idempotent replay/readback, and
  strict unknown-field rejection.
- Integrated the interaction checker into `tools/verify.py` and required its
  presence in the source-distribution manifest check.
- Corrected recruiter-facing documentation to the accepted private `main`
  checkpoint `690123e` and GitHub Actions run `33839976122`.
- Clarified that the Alpha has no graphical dashboard and deliberately disables
  Swagger UI and ReDoc; its supported product surfaces are CLI and authenticated
  loopback REST, with a committed OpenAPI contract.

## Expected-versus-actual samples

| Surface | Case | Expected | Actual |
|---|---|---:|---:|
| CLI | valid generic project | exit `0`, `VALID` | matched |
| CLI | PASS decision | `PASS`, exit `0`, `RULE_SATISFIED` | matched |
| CLI | FAIL decision | `FAIL`, exit `1`, `RULE_NOT_SATISFIED` | matched |
| CLI | missing mandatory evidence | `REVIEW`, exit `2`, `EVIDENCE_MISSING` | matched |
| CLI | unevaluable expression | `ERROR`, exit `3`, `EVALUATION_ERROR` | matched |
| REST | health and supplied request ID | `200`, v1/0.1.0a1, echoed ID | matched |
| REST | `/docs` and `/redoc` | `404` / `404` | matched |
| REST | protected route without session | `401`, `API_AUTHENTICATION_REQUIRED` | matched |
| REST | challenge and signed session | `201` / `201` | matched |
| REST | register, replay, read | `201` / `201` / `200`, identical body | matched |
| REST | unknown request field | `422`, `API_REQUEST_VALIDATION_FAILED` | matched |

The smoke report records 33 individual checks because several rows above
contain multiple independently compared status, body, reason, correlation, or
exit-code values. No private key or Bearer token is printed or retained.

## Live listener check

The production `forgegate serve` command was started on `127.0.0.1:8765` with
an ephemeral trust store. Direct HTTP requests to the actual listener returned:

- `/healthz`: HTTP `200`, `status=ok`, API `v1`, ForgeGate `0.1.0a1`, store
  `forgegate.candidate-store.v8`, and the supplied `X-Request-ID`;
- `/docs`: HTTP `404`;
- `/redoc`: HTTP `404`;
- `/v1/projects` without a session: HTTP `401`,
  `API_AUTHENTICATION_REQUIRED`, and `WWW-Authenticate: Bearer`.

The in-app browser controller attempted both `127.0.0.1` and `localhost` but
reported `ERR_BLOCKED_BY_CLIENT` before it could expose an inspectable page.
The server did receive successful health requests, and the direct listener
results above independently establish the application responses. This client
restriction is not counted as a ForgeGate pass or failure.

## Regression and packaging evidence

| Gate | Result |
|---|---|
| Dependency consistency | PASS — no broken requirements |
| Ruff lint and format | PASS |
| mypy strict | PASS — 76 source/tool files |
| pytest | PASS — 780 passed, 3 skipped because Windows symlink creation is unavailable |
| Branch-aware coverage | PASS — 95.01% across 8,959 statements and 2,520 branches |
| Interaction smoke | PASS — 33/33 expected outputs |
| JSON Schema and OpenAPI drift | PASS |
| Source distribution and wheel | PASS — built, inspected, and clean-installed |
| Clean installed workflows | PASS — core, API contract, collectors, candidate lifecycle, bundle, plugin discovery/uninstall |
| Dependency advisory audit | PASS — no known advisory in resolved registry dependencies; editable ForgeGate excluded |
| Repository/privacy scan | PASS — no configured private email, private key, GitHub token, or retained Bearer-token pattern |

The three skipped tests remain the previously disclosed host-capability cases;
they are not newly introduced failures. The standard release smoke does not run
the live Podman hostile-plugin fixture, so the separate retained Windows
plugin evidence remains the authority for that claim.

## Remaining boundaries

- A graphical dashboard is intentionally outside the current Alpha scope; no
  UI screen was invented or treated as implemented.
- Swagger UI and ReDoc remain disabled. Consumers use the drift-checked OpenAPI
  JSON and authenticated API clients.
- The API remains loopback-only and lacks TLS, hostile-local-user defense, and
  durable/distributed sessions.
- No MSP430, serial port, programmer, firmware, AFE hardware, or physical
  measurement was accessed.
- These local changes require a separate explicit push/PR authorization before
  they appear in the private GitHub repository.
