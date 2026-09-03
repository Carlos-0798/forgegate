# ForgeGate

ForgeGate is a local-first, evidence-aware release assurance platform under
active development. It is intended to normalize engineering evidence, evaluate
versioned release policies, and generate auditable release decisions.

[![CI](https://github.com/Carlos-0798/forgegate/actions/workflows/ci.yml/badge.svg)](https://github.com/Carlos-0798/forgegate/actions/workflows/ci.yml)

## Current status

**Phase 19 Windows sandbox controls verified with ForgeGate-owned hostile
fixtures; production external-plugin execution remains prohibited; not
production-ready.**

This private-development checkpoint provides a working Python 3.12 CLI and an
Ed25519-authenticated, project-authorized, loopback-only REST API. Its strongest
ForgeGate-owned evidence is local host testing; it contains no physical-device
verification or production-deployment claim.

## Architecture and workflow

```text
JUnit / coverage / SARIF / benchmark / optional Studio artifact
                              |
                              v
                  bounded evidence collectors
                              |
                              v
             audited, commit-bound evidence assembly
                              |
                              v
current immutable project profile -> profile-bound release candidate
                              |
                              v
                  persisted evidence binding
                              |
                              v
       exact profile-authorized policy material
                              |
                              v
                material-bound policy evaluation
                              |
                              v
        immutable transition history + unsigned local attestation
                              |
                              v
       content-addressed portable bundle + offline verification
                              |
                              v
 external trust store -> Ed25519 signer authentication sidecar
                              |
                              v
      one-time Ed25519 challenge -> short-lived local API session
                              |
                              v
 project/role authorization -> authenticated audit actor on writes
                              |
                              v
 logout / scoped revocation / fixed-path trust reload / bounded rate controls
                              |
                              v
 streamed body cap + separate bounded API security-event journal
                              |
                              v
 verified portable bundle + exact CI commit -> bounded GitHub Job Summary
                              |
                              v
 installed entry-point metadata -> bounded manifest compatibility report
                              |
                              v
 approved authority -> content-addressed run/protocol/state/result documents
                              |
                              v
 Windows Podman/WSL2 hostile control proof -> production broker still required
```

The core remains domain-neutral. Analog Validation Studio is consumed only
through a frozen JSON contract, while MSP430 support remains a planned optional
collector rather than a runtime or hardware dependency.

## Verified results

| Gate | Result | Evidence level |
|---|---|---|
| Python tests | 723 passed, 3 skipped because Windows symlink creation was unavailable | Local host test |
| Branch-aware coverage | 96.23% across 7,601 statements and 2,082 branches | Local host test |
| Static quality gates | Ruff, formatting, and strict mypy passed across 67 source/tool files | Local host test |
| Contracts | 36 document and 2 artifact JSON Schemas plus OpenAPI passed drift checks | Local host test |
| Packaging | sdist/wheel build and clean-environment install smoke passed | Local host test |
| Plugin discovery | 30 passed, 1 skipped; standalone wheel install/discover/uninstall passed | Local host test; code not loaded |
| Plugin execution documents | 7 focused model/identity/chain/loader tests passed | Local host test; no process started |
| Windows sandbox readiness | 20 focused probe/model/command/verifier tests passed; Podman client/server 5.8.6 match | Local host test; execution remains `PROHIBITED`, tier `NONE` |
| Windows sandbox enforcement | All 14 required controls passed fixed hostile fixtures; [raw evidence](reports/PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json) | Live local WSL2/Podman test; not an external-plugin or production-broker test |
| GitHub Actions | Phase 19 baseline passed `verify.py` and `release_smoke.py` on Windows, Ubuntu, and macOS; the generic composite Action smoke also passed | PASS — [run 33798778977](https://github.com/Carlos-0798/forgegate/actions/runs/33798778977); live Podman fixtures remain local-only evidence |
| Hardware/device behavior | Not exercised by ForgeGate | Out of scope |

## Key design decisions

- Evidence collection, policy evaluation, candidate transitions, and
  attestation are separate operations so a successful collector cannot silently
  become a release decision.
- SHA-256 identities establish byte integrity and association, not authenticity.
  A separate Ed25519 sidecar authenticates its signer only when an external
  trust store authorizes that exact key, role, and project.
- Candidate writes use caller-owned idempotency keys and optimistic revisions;
  persisted history is append-only.
- New persisted candidates bind the exact immutable project-profile ID/version
  that authorized creation; later revisions cannot reinterpret them.
- New terminal decisions retain the exact profile-authorized policy bytes and
  bind evaluation v2 to their material ID, SHA-256, and frozen profile.
- Portable exports bind the frozen profile, evidence binding, exact policy
  material, and attestation into deterministic bytes that verify without the
  source database or project tree.
- Project revisions are complete append-only replacements guarded by expected
  profile version and exact idempotency; legacy candidates remain readable
  without fabricated profile bindings.
- The REST API shares its application service with the CLI, accepts no local
  artifact-loader or output-directory path, requires a short-lived session
  authorized by an external trust store, and remains restricted to loopback.
- Producers are read-only; operators may write and query project-scoped audit
  history. Successful API writes retain a public authenticated actor but never
  a private key or Bearer token.
- Session logout, project-covering operator revocation, and fixed-startup-path
  trust reload are explicit memory-only controls. Process-global fixed-window
  authentication limits do not claim per-client network attribution.
- API security-control telemetry is a separate append-only SQLite v8 journal,
  bounded at 10,000 events by default and globally operator-readable. It stores
  no token, signature, body, private key, or arbitrary header and is not the
  release-state audit chain or a complete compliance log.
- The GitHub Actions bridge accepts only a strictly verified portable bundle,
  requires an exact complete candidate/CI commit match, writes bounded escaped
  summary/output files, and preserves 0/1/2/3 decision exits without requesting
  a token or calling GitHub APIs.
- Plugin discovery reads only distribution-listed bounded manifests, never
  imports entry-point modules, and reports compatibility separately from code
  execution or publisher trust.
- Initial external-plugin isolation is scoped to a Windows host using a local
  rootless Podman/WSL2 machine. Low-level controls passed fixed hostile
  fixtures, but no external plugin may run until the production broker,
  protocol, output validation, and durable audit path are implemented.
- Upstream AFE or future MSP430 results retain their original evidence level;
  ForgeGate does not relabel software or replay evidence as physical proof.

<details>
<summary>Detailed implemented capabilities</summary>

Implemented and host-verified in this checkpoint:

- strict, versioned project, policy, and evidence-bundle models;
- fail-closed configuration loading with a 4 MiB document limit and a separate
  1 MiB exact policy-material byte limit;
- explicit evidence trust and verification levels;
- guards that prevent a mandatory zero-count rule from passing without evidence;
- CLI commands for environment diagnosis, configuration validation, and schema export;
- generic sample configuration with no AFE or MSP430 dependency;
- documented optional compatibility boundaries for Analog Validation Studio and
  the MSP430 Equipment Health & Safety Controller;
- a root-confined artifact registry that captures exact bytes, size, media type,
  and SHA-256 identity;
- a bounded JUnit collector that emits normalized `test.summary` evidence plus
  explicit warnings or rejections;
- bounded Cobertura/coverage.py XML and LCOV collectors that emit line and
  branch coverage for repository, package, and module scopes;
- a bounded SARIF 2.1.0 collector that emits an explicit summary even when a
  successful scan contains zero results, plus one normalized record per finding;
- a strict ForgeGate-owned `forgegate.benchmark.v1` schema and bounded collector
  for metric value, unit, scope, baseline, and tolerance facts;
- `collect-junit`, `collect-coverage-xml`, `collect-lcov`, `collect-sarif`, and
  `collect-benchmark` CLI previews with deterministic golden-output coverage.
- deterministic evaluation at an explicit timestamp with trust, verification,
  age, presence, filter, aggregation, operator, and conflict semantics;
- a versioned machine-readable policy-evaluation result with stable input
  fingerprints, per-rule explanations, evidence references, and remediation;
- `evaluate-policy` with PASS/FAIL/REVIEW/ERROR exit codes 0/1/2/3 and generic
  committed PASS/FAIL examples;
- immutable release candidates with the exact DRAFT → COLLECTING → READY →
  EVALUATING → PASS/FAIL/REVIEW/ERROR state graph;
- deterministic candidate/transition identities, exact revisions, monotonic
  timestamps, immutable terminal states, and before/after fingerprints;
- mandatory policy-evaluation binding for PASS/FAIL/REVIEW terminal states;
- stateless `candidate create` and `candidate transition` CLI previews with
  committed structural and evaluation-bound Golden outputs;
- a local SQLite v8 candidate/project store with WAL, FULL synchronous durability,
  foreign keys, exact application/schema identity, and explicit transactions;
- canonical append-only candidate snapshots and transition events with an
  optimistic current-revision pointer and immutable idempotency responses;
- exact retry replay, conflicting-key rejection, stale-write protection,
  restart recovery, bounded writer contention, and audit-chain validation;
- persisted `candidate create`, `advance`, `show`, and `history` CLI paths;
- explicit validated v1/v2/v3/v4/v5-to-v6 migration, audit projection,
  registration-profile backfill, discovery indexing, and legacy evaluation
  backfill without candidate-profile fabrication;
- durable append-only policy evaluations and release attestations;
- self-validating `forgegate.release-attestation.v1` records containing the
  terminal candidate, transition chain, evaluation, and content fingerprints;
- deterministic JSON/Markdown rendering, atomic content-addressed publication,
  exact replay, and conflict rejection;
- persisted `candidate migrate-store`, `import-evaluation`, `attest`, and
  `show-attestation` CLI paths.
- an optional, artifact-only Analog Validation Studio `result-export.v1`
  collector with a committed consumer-side Schema mirror;
- strict TestRun, criteria, metric, point, limitation, and record-lineage
  validation without importing or running the upstream Studio;
- deterministic `analog-validation.run`, `.metric`, and `.criterion` evidence,
  with source-derived verification levels and no collector-owned release
  decision;
- automatic `BENCH_*` capping at `system_observed` because v1 does not require
  instrument identity or calibration provenance;
- `collect-analog-validation` CLI preview, compatibility fixture, Golden
  projection, adversarial tests, Schema drift gate, and installed-wheel smoke.
- strict, bounded collection-result JSON loading with referenced-artifact
  byte revalidation;
- `forgegate.evidence-bundle-assembly.v1` receipts preserving raw result
  hashes, normalized fingerprints, collector versions, artifacts, evidence
  IDs, and warnings;
- `assemble-evidence` with candidate-commit binding, duplicate/conflict gates,
  content-derived identity, and fail-closed warning handling;
- policy evaluation of either a direct evidence bundle or a validated assembly.
- a self-validating `forgegate.candidate-evidence-binding.v1` document covering
  the revision-one `COLLECTING` snapshot and complete audited assembly;
- immutable, idempotent SQLite binding persistence plus `bind-evidence` and
  `show-evidence` CLI paths;
- mandatory evidence binding and chronology gates before a new persisted
  candidate reaches `READY`;
- terminal evaluation enforcement against the bound assembly's nested
  evidence-bundle fingerprint, with non-fabricating v1/v2 migration semantics.
- a shared candidate application-service boundary used by both CLI and HTTP;
- a versioned FastAPI surface for health, idempotent candidate creation, and
  candidate/history/evidence/attestation reads;
- strict request models, structured error envelopes, caller-supplied or
  generated request correlation IDs, and sanitized unexpected failures;
- `serve` with mandatory loopback-only binding plus deterministic
  `export-openapi` and a committed OpenAPI 3.1 drift gate;
- API/CLI candidate-creation parity, durable SQLite readback integration, and
  installed-wheel OpenAPI smoke verification.
- idempotent, expected-revision REST transitions plus immutable audited
  assembly binding;
- REST policy evaluation that reads only the persisted binding, computes the
  decision, and atomically records the matching terminal transition;
- durable REST attestation creation without accepting a filesystem output
  path or publishing files;
- frozen-profile/material matching, loopback Host validation, and a declared
  4 MiB request-length guard;
- complete HTTP create → collect-state → bind → ready → evaluate → attest
  integration with exact replay and conflict tests.
- immutable project-profile registration with exact idempotent replay and
  canonical configuration identity;
- transactional append-only audit events for successful project/candidate
  lifecycle writes, including deterministic v3 history projection on migration;
- stable cursor pages with bounded project/candidate filtering through
  `project register/show`, `audit events`, and loopback REST endpoints.
- registered-project authority for every new application/CLI/REST candidate,
  including fail-closed normalized release-track resolution;
- bounded `project list` and project-scoped `candidate list` contracts through
  CLI and REST, backed by the SQLite v5 composite discovery index;
- `forgegate.project-profile-revision.v1`, bounded profile history, current
  profile reads, CAS/idempotent revision writes, and profile-revision audit
  events through the application, CLI, and REST boundaries;
- `forgegate.release-candidate.v2` with immutable profile ID/version binding,
  exact replay across later revisions, and track changes applied only to later
  candidates;
- explicit v1/v2/v3/v4/v5-to-v6 migration without replaying existing audit
  events or fabricating profile links for legacy candidates.
- self-validating policy-material documents retaining exact bytes, media type,
  size, SHA-256, parsed policy, profile/track authority, and content identity;
- material-bound policy-evaluation v2 plus SQLite v7 atomic persistence and
  non-fabricating v1-v6 migration semantics;
- `candidate materialize-policy`, `evaluate`, and `show-policy`, with path-free
  REST evaluation and policy-material readback.
- `forgegate.assurance-bundle.v1` and manifest contracts with deterministic,
  atomic, content-addressed directory publication;
- `candidate export-assurance` plus database-independent `verify-assurance`,
  strict canonical-byte checks, and explicit source-artifact limitations.
- strict `forgegate.signing-identity.v1`, `forgegate.trust-store.v1`, and
  `forgegate.assurance-signature.v1` contracts with key-derived identity and
  content-derived trust/signature IDs;
- domain-separated Ed25519 signatures over canonical Phase 11 bundle bytes,
  content-addressed signature publication, exact replay, and external
  trust-store verification for an authorized producer or operator role;
- strict bounded JSON identity loading plus `identity derive`, `identity trust`,
  `sign-assurance`, and `verify-assurance-signature` installed CLI paths.
- domain-separated, one-time Ed25519 API challenges bound to server instance,
  trust store, role, exact projects, nonce, and short server time window;
- bounded short-lived in-memory Bearer sessions that retain only token digests,
  expire on schedule or restart, and recheck active trust authority;
- exact project authorization with producer read-only and operator write/audit
  permissions, including filtered project discovery and mandatory project audit
  scope;
- authenticated `forgegate.audit-actor.v1` attribution on successful API writes
  inside the existing durable transaction, with no token or private-key
  persistence;
- required `serve --trust-store`, strict `identity sign-api-challenge`, two
  session-establishment endpoints, OpenAPI security declarations, adversarial
  tests, and clean-wheel session smoke.
- authenticated self-logout plus operator-only exact-session revocation whose
  target projects must all be inside the caller's session scope;
- explicit reload of only the trust-store path fixed at server startup, with
  old/new global project coverage, exact caller reauthorization, pending
  challenge invalidation, and incompatible-session removal;
- bounded fixed-window controls for valid challenge requests, session
  exchanges, and invalid Bearer attempts with `429` and `Retry-After`;
- lifecycle/reload/rate OpenAPI contracts, adversarial tests, and installed
  wheel smoke without remote-use claims.
- actual ASGI request-byte accounting up to the 4 MiB limit even when no
  `Content-Length` is supplied, plus challenge/session rate accounting before
  strict body-model validation;
- strict content-addressed `forgegate.api-security-event.v1` and bounded page
  contracts in a separate append-only SQLite table, explicit v7-to-v8
  migration, global-operator query API, saturation disclosure, privacy tests,
  and clean-wheel persistence smoke;
- best-effort retention of authentication rejection/rate-limit events and
  successful logout, scoped revocation, and trust reload, without changing the
  in-memory session or loopback-only deployment boundary.
- strict `forgegate.github-action-report.v1` binding a verified portable bundle
  and manifest to one exact complete CI commit and existing ForgeGate decision;
- `github-gate` with PASS/FAIL/REVIEW/ERROR exits 0/1/2/3, bounded escaped Job
  Summary rendering, schema-constrained outputs, unsafe-target rejection, and
  sanitized ERROR presentation;
- a token-free repository-local composite Action, canonical generic fixture,
  real workflow smoke job, Schema drift gate, adversarial tests, and installed-
  wheel verification without Checks/PR/Issue/Release API writes.
- strict content-derived `forgegate.plugin-manifest.v1` and
  `forgegate.plugin-discovery.v1` contracts for Plugin API v1;
- import-free `plugins list` enumeration with compatible, incompatible,
  invalid, and duplicate-ID conflict states plus sanitized issue codes;
- a separately buildable import-hostile generic plugin fixture and clean-wheel
  install/discover/uninstall smoke proving core operation without plugins.
- strict content-derived run-plan, protocol-message, transition, and terminal-
  result contracts with exact manifest authority, `SANDBOXED`-only planning,
  resource limits, stable issues, and complete state-chain validation; these
  are public documents, not an execution or isolation implementation.
- a content-derived Windows Podman/WSL2 capability report, strict shell-free
  digest-pinned container-create specification, and development-only live
  verifier whose 14 required controls passed ForgeGate-owned hostile fixtures;
  the production path still starts no external plugin.


</details>

## Quick start

```powershell
.\tools\setup_environment.ps1
.\.venv\Scripts\python.exe tools\verify.py
.\.venv\Scripts\python.exe tools\release_smoke.py
```

On Linux/macOS, run `./tools/setup_environment.sh`. The checked direct
dependency constraints keep local and CI quality-gate versions aligned while
the package retains compatible version ranges for downstream users.

See `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, and
`docs/VERIFICATION_MATRIX.md` before making capability claims.

Inspect installed plugin metadata without importing plugin code:

```powershell
.\.venv\Scripts\python.exe -m forgegate plugins list
```

Every result explicitly reports `execution=NOT_LOADED`. `COMPATIBLE` means only
that the strict manifest targets Plugin API v1; it is not approval to execute
the entry point and grants none of its declared permissions.

Inspect Windows sandbox prerequisites without loading a plugin or starting a
container:

```powershell
.\.venv\Scripts\python.exe -m forgegate plugins sandbox-status
```

`READY_FOR_ADVERSARIAL_VERIFICATION` is still non-executable readiness. On a
prepared developer host, rerun the fixed hostile fixtures with:

```powershell
.\.venv\Scripts\python.exe tools\verify_windows_sandbox_live.py
```

Even a passing development report keeps external execution `PROHIBITED` and
the advertised tier `NONE`; only the later production broker gate may change
those claims.

Start the local API against an existing or new local candidate database:

```powershell
.\.venv\Scripts\python.exe -m forgegate serve `
  --database work/forgegate.db `
  --trust-store work/trust-store.json `
  --host 127.0.0.1 --port 8000
```

The server accepts only `localhost` or a loopback IP, rejects a non-loopback
HTTP `Host`, and requires an external `forgegate.trust-store.v1`. Obtain a
one-time challenge from `/v1/auth/challenges`, sign its saved JSON with
`forgegate identity sign-api-challenge`, exchange the signature at
`/v1/auth/sessions`, and use the returned short-lived Bearer token. Candidate
creation, transition, evidence binding, and evaluation writes also require
`Idempotency-Key`; transitions and evaluation require `expected_revision`.
Attestation creation is content-deterministic and persists only to SQLite. The
API never accepts a path from which to load an assembly/artifact or an
attestation output directory; path metadata already inside a validated assembly
is not dereferenced. OpenAPI is available at `/openapi.json`, and the
committed copy can be regenerated with:

```powershell
.\.venv\Scripts\python.exe -m forgegate export-openapi `
  schemas/forgegate.openapi.v1.json
```

This API authenticates local callers and applies exact role/project authority,
supports self-logout, scoped operator revocation, explicit fixed-path trust
reload, parsing-independent authentication endpoint limits, and an actual
4 MiB request-byte cap. Global operators can inspect the separate bounded
`GET /v1/security-events` journal. The API still has no TLS, remote deployment
approval, hostile-local-user defense, durable/distributed sessions, managed
online revocation, or trusted time. It is not approved for LAN, internet,
shared-host, or production deployment.

Register and read one immutable project profile, then query its local audit
events:

```powershell
.\.venv\Scripts\python.exe -m forgegate project register `
  work/forgegate.db examples/sample-python-api/forgegate.yaml `
  --registered-at 2026-08-31T14:00:00Z `
  --idempotency-key project:sample-api:v1

.\.venv\Scripts\python.exe -m forgegate project show `
  work/forgegate.db sample-api

.\.venv\Scripts\python.exe -m forgegate project current `
  work/forgegate.db sample-api

.\.venv\Scripts\python.exe -m forgegate project history `
  work/forgegate.db sample-api --limit 100

.\.venv\Scripts\python.exe -m forgegate project list `
  work/forgegate.db --limit 100

.\.venv\Scripts\python.exe -m forgegate audit events `
  work/forgegate.db --project sample-api --limit 100
```

Audit sequences are stable cursors within one database lineage. The log covers
successful durable state changes; it is not an authenticated compliance log
and does not automatically ingest rejected requests or collector warnings.

Preview the first collection path without making a release decision:

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-junit artifacts/junit.xml `
  --root examples/sample-python-api `
  --commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa `
  --collected-at 2026-08-30T20:30:00Z `
  --source-tool pytest --source-version 8.4.2 `
  --trust claimed_ci_metadata --verification-level ci_validated
```

The command's `COMPLETE` status means collection completed; the evidence's
`passed` or `failed` status describes the tests. Policy evaluation is a separate
explicit action.

After saving one or more collection command JSON outputs beneath the same
artifact root, assemble them for one candidate:

```powershell
.\.venv\Scripts\python.exe -m forgegate assemble-evidence `
  work/junit.collection.json work/coverage.collection.json `
  --root examples/sample-python-api `
  --commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa `
  --generated-at 2026-08-30T20:31:00Z
```

The original artifacts must still match the references in every collection
result. Any warning rejects by default; `--retain-warnings` explicitly keeps
the warnings in the audited envelope. The resulting JSON can be passed directly
as the evidence argument to `evaluate-policy`.

Evaluate committed PASS and FAIL examples at a caller-supplied timestamp:

```powershell
.\.venv\Scripts\python.exe -m forgegate evaluate-policy `
  examples/sample-python-api/policies/pull-request.yaml `
  examples/sample-python-api/evidence/pass-bundle.json `
  --evaluated-at 2026-08-30T21:00:00Z
```

Exit code `0` means PASS, `1` FAIL, `2` REVIEW, and `3` ERROR. Configuration or
system errors also use `3`. The evaluator does not collect, rebuild, rerun, or
authenticate evidence while deciding.

Create a deterministic local DRAFT candidate and preview one legal structural
transition without persistence:

```powershell
.\.venv\Scripts\python.exe -m forgegate candidate create `
  --project sample-api --version 1.2.0 `
  --commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa `
  --created-at 2026-08-30T12:00:00Z

.\.venv\Scripts\python.exe -m forgegate candidate transition `
  examples/sample-python-api/candidates/draft.json `
  --to COLLECTING --occurred-at 2026-08-30T12:01:00Z
```

PASS/FAIL/REVIEW transitions additionally require `--evaluation` pointing to a
matching `forgegate.policy-evaluation.v1` document.

Initialize a local store, persist a profile-bound candidate, atomically advance
the expected revision, and read its validated audit history. Use the
`candidate_id` returned by persisted creation in later commands:

```powershell
New-Item -ItemType Directory -Force work | Out-Null
.\.venv\Scripts\python.exe -m forgegate candidate init-store work/forgegate.db

.\.venv\Scripts\python.exe -m forgegate candidate create `
  --project sample-api --version 1.2.0 `
  --commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa `
  --created-at 2026-08-31T15:00:00Z `
  --database work/forgegate.db `
  --idempotency-key create:sample-api-1.2.0

.\.venv\Scripts\python.exe -m forgegate candidate advance `
  work/forgegate.db <candidate_id-from-create> `
  --to COLLECTING --expected-revision 0 `
  --occurred-at 2026-08-31T15:01:00Z `
  --idempotency-key advance:sample-api-collecting

.\.venv\Scripts\python.exe -m forgegate candidate bind-evidence `
  work/forgegate.db <candidate_id-from-create> `
  work/evidence-assembly.json `
  --bound-at 2026-08-30T20:31:00Z `
  --idempotency-key bind-evidence:sample-api-1.2.0

.\.venv\Scripts\python.exe -m forgegate candidate show-evidence `
  work/forgegate.db <candidate_id-from-create>

.\.venv\Scripts\python.exe -m forgegate candidate list `
  work/forgegate.db --project sample-api --limit 100

.\.venv\Scripts\python.exe -m forgegate candidate history `
  work/forgegate.db <candidate_id-from-create>
```

Every persisted candidate creation first requires the current project profile
and a uniquely configured release track. Its v2 document records that exact
profile ID and version. Configuration keys such as `pull_request`
are matched to the canonical candidate/policy identity `pull-request`; an
ambiguous normalized configuration is rejected. Every persisted write requires
a caller-owned idempotency key. Exact retries
return the original response; reuse for different normalized input and stale
revisions fail closed. New v3 candidates cannot advance to `READY` before an
immutable binding is present, and the terminal evaluation must be produced from
that assembly's nested bundle. The database establishes local transaction
ordering, not producer authenticity or operator authorization.

After reaching PASS, FAIL, REVIEW, or ERROR, persist and publish a deterministic
attestation bundle:

```powershell
.\.venv\Scripts\python.exe -m forgegate candidate attest `
  work/forgegate.db <candidate_id-from-create> `
  --issued-at 2026-08-30T22:00:00Z `
  --output-root work/attestations

.\.venv\Scripts\python.exe -m forgegate candidate show-attestation `
  work/forgegate.db <candidate_id-from-create>
```

The bundle contains `attestation.json` and `attestation.md` beneath a directory
named from the attestation SHA-256. An exact rerun verifies and reuses those
bytes; ForgeGate does not overwrite a conflicting target. Database persistence
commits before filesystem publication, so an output failure is recovered by
rerunning the same command.

Export the complete retained assurance state and verify it without access to
the database or source project:

```powershell
.\.venv\Scripts\python.exe -m forgegate candidate export-assurance `
  work/forgegate.db <candidate_id-from-create> `
  --output-root work/assurance

.\.venv\Scripts\python.exe -m forgegate verify-assurance `
  work/assurance/assurance-<bundle-sha256>
```

The portable directory contains canonical `assurance-bundle.json`, `README.md`,
and `manifest.json`. It embeds the retained evidence binding and exact policy
bytes, but not the collector source-artifact bytes; offline verification proves
the internal document and byte associations, not producer identity or a fresh
collector/hardware run.

Drive a GitHub Actions job from that verified bundle and bind it to the exact CI
commit represented by the candidate:

```powershell
forgegate github-gate work/assurance/assurance-<bundle-sha256> `
  --expected-commit <complete-40-or-64-hex-ci-commit>
```

Inside GitHub Actions, the command appends a bounded escaped Job Summary and
stable outputs through `GITHUB_STEP_SUMMARY` and `GITHUB_OUTPUT`; the repository-
local `.github/actions/assurance-gate` composite Action wraps this command. For a
pull-request candidate built from the PR head, pass the head SHA rather than a
synthetic merge SHA. The bridge does not install ForgeGate, request a token,
call GitHub APIs, upload artifacts, rerun collectors, or authenticate the
workflow. `gate_status=VALID` describes bundle/commit validity and remains
separate from the PASS/FAIL/REVIEW/ERROR decision.

Authenticate the signer of those exact canonical bundle bytes against a
separately protected trust store:

```powershell
forgegate identity derive producer-key.pem --display-name sample-ci-producer `
  > work/signing-identity.json

forgegate identity trust work/signing-identity.json `
  --role producer --project sample-api > work/trust-store.json

forgegate sign-assurance work/assurance/assurance-<bundle-sha256> `
  work/signing-identity.json producer-key.pem `
  --role producer --signed-at 2026-08-31T23:00:00Z `
  --output-root work/signatures

forgegate verify-assurance-signature `
  work/assurance/assurance-<bundle-sha256> `
  work/signatures/assurance-signature-<signature-sha256>.json `
  work/trust-store.json
```

ForgeGate does not generate or retain private keys. The current CLI accepts an
existing unencrypted PKCS8 Ed25519 PEM and leaves key encryption, OS ACLs,
hardware-backed custody, trust-store distribution, and rotation to the operator.
The signature authenticates the bundle signer at verification time; it does not
authenticate the original source artifacts, establish trusted time, or change
the embedded bundle's `unsigned_local` evidence label.

For a schema-v1, v2, v3, v4, or v5 database, migration is explicit:

```powershell
.\.venv\Scripts\python.exe -m forgegate candidate migrate-store work/forgegate.db
```

Migration preserves existing candidates with no binding requirement; it does
not fabricate a historical assembly. If a v1 database already contains a
terminal candidate, it references but does not contain its original policy
evaluation. Import the exact original document with `candidate
import-evaluation` before attesting. ForgeGate verifies the evaluation ID,
commit, decision, and timestamp; it does not reconstruct or invent missing
evidence.

Coverage artifacts use the same provenance options:

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-coverage-xml `
  artifacts/coverage.xml --root examples/sample-python-api `
  --commit bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb `
  --collected-at 2026-08-30T22:00:00Z

.\.venv\Scripts\python.exe -m forgegate collect-lcov `
  artifacts/coverage.info --root examples/sample-python-api `
  --commit bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb `
  --collected-at 2026-08-30T22:00:00Z
```

Coverage percentages remain facts until a policy rule explicitly evaluates
them.

SARIF 2.1.0 collection reads scanner identity from the artifact:

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-sarif `
  artifacts/security.sarif --root examples/sample-python-api `
  --commit cccccccccccccccccccccccccccccccccccccccc `
  --collected-at 2026-08-30T23:00:00Z `
  --trust claimed_ci_metadata --verification-level ci_validated
```

A `COMPLETE` result means the artifact was collected successfully. Finding
levels, kinds, suppressions, and a zero-result summary remain evidence; the
collector does not issue a release decision.

Benchmark collection reads tool identity and metrics from the versioned
ForgeGate artifact:

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-benchmark `
  artifacts/benchmark.json --root examples/sample-python-api `
  --commit dddddddddddddddddddddddddddddddddddddddd `
  --collected-at 2026-08-31T00:00:00Z `
  --trust claimed_ci_metadata --verification-level ci_validated
```

Observed values, baselines, and absolute/percent tolerances remain facts. A
`COMPLETE` collection does not assert that performance is acceptable; only an
explicit matching policy rule can make that determination.

Collect an Analog Validation Studio structured result without importing its
runtime or touching a device:

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-analog-validation `
  artifacts/analog-validation-result.json `
  --root examples/sample-python-api `
  --commit 9ac23494b86212928185de9b0eef1c1a82a8c0ea `
  --collected-at 2026-08-31T13:00:00Z
```

`--commit` is the claimed Studio artifact-producing commit. ForgeGate derives
the verification level from `evidence_source`; there is intentionally no
verification-level override. A valid upstream `PASS` remains observed evidence
until a separate ForgeGate policy evaluates it.

## Repository layout

| Path | Purpose |
|---|---|
| `src/forgegate/` | Domain models, collectors, policy engine, plugin discovery and execution contracts, persistence, CLI, and REST API |
| `tests/` | Unit, adversarial, integration, Golden, and contract-drift tests |
| `schemas/` | Committed JSON Schema and OpenAPI contracts |
| `examples/` | Generic reproducible project, policies, evidence, and artifacts |
| `docs/` | Architecture, security, compatibility, status, roadmap, and verification records |
| `reports/` | Phase acceptance and environment-audit reports |
| `tools/` | Environment setup, full verification, and clean-install release smoke |

## Known limitations and product boundary

Not implemented yet:

- non-loopback or TLS-protected API deployment;
- HTTP artifact collection or filesystem publication;
- complete rejected-request ingestion, security/audit export and retention,
  production Windows broker/runner authorization, external plugin execution,
  broker I/O, durable `plugin_runs`, or custom GitHub Checks/PR annotations/API
  integration;
- database-file authorization, backup/repair, managed or hardware-backed key
  custody, managed online revocation, durable/distributed session authority,
  trusted timestamps, or CI workload identity federation;
- TLS/reverse-proxy trust, hostile-local-user defense, per-client network rate
  controls, distributed rate state, or administrator-resistant logging;
- MSP430 compatibility collection, AFE/MSP430 runtime integration, or any
  hardware operation;
- production deployment or public release.

ForgeGate does not run builds or tests, control devices, or perform analog
measurements. The Studio integration consumes only its frozen public JSON
artifact; it neither imports Studio code nor converts current `BENCH_*` labels
into physical verification. Assembly only revalidates local artifacts and
joins existing evidence; persisted binding connects that local assembly to the
candidate lifecycle but does not authenticate it. Phase 12 can authenticate a
portable bundle signer against an external local trust store. Phase 13 reuses
that identity for a short-lived authenticated loopback API session and records
the successful API actor, but does not authenticate source artifacts or protect
the database from its administrator. Phase 14 adds memory-only logout,
project-scoped revocation, fixed-path trust reload, and bounded global
authentication counters. Phase 15 adds an exact received-byte cap,
pre-validation endpoint counters, and a bounded separate API security-event
journal; it still does not make the service remotely safe or create a complete
compliance record. Phase 16 adds only an offline, token-free GitHub Actions
presentation/exit bridge over the Phase 11 portable bundle; it does not add CI
workload identity, source-artifact authentication, or GitHub API authority.
Phase 17 adds only bounded import-free plugin metadata discovery; compatibility
does not authenticate a publisher, load a callable, grant permissions, isolate
a subprocess, or create durable plugin-run audit evidence.
Phase 18 now implements strict public documents for run authority, protocol
messages, legal transitions, stable failure classes, bounded validated outputs,
and terminal replay. It implements none of the runner, sandbox, broker-I/O, or
durable-store controls and still loads no plugin code. See
[`docs/architecture/PLUGIN_EXECUTION_SECURITY_CONTRACT.md`](docs/architecture/PLUGIN_EXECUTION_SECURITY_CONTRACT.md)
and the exact upstream review in
[`docs/research/OPEN_SOURCE_REFERENCE_REVIEW.md`](docs/research/OPEN_SOURCE_REFERENCE_REVIEW.md).
Phase 19 installs and pins the local Windows runtime, requires matching client
and server versions, and exercises the low-level controls with fixed hostile
fixtures. This is not the production broker, protocol, output-schema, or
durable-audit path, so external plugins remain prohibited; see
[`docs/architecture/WINDOWS_PLUGIN_SANDBOX.md`](docs/architecture/WINDOWS_PLUGIN_SANDBOX.md).
SHA-256 is not producer authentication.
The MSP430 controller may later expose a separate versioned artifact for
another optional collector.

## Roadmap

Phase 17 adds a strict Plugin API v1 manifest and import-free installed
entry-point discovery with explicit compatibility and conflict reporting.
Phase 18 freezes the security contract and implements its public content-
addressed documents plus the non-executing Windows sandbox readiness gate.
Phase 19 verifies the Windows low-level sandbox controls with fixed hostile
fixtures. The production runner, broker I/O, schema validation, and durable run
records remain separate implementation work. Custom GitHub API
writes, annotations, signed CI provenance, OIDC, and artifact upload also
remain separate. TLS, reverse-proxy identity, hostile-local-user defenses,
durable/distributed session state, security-event retention/export, and managed
key lifecycle must still be designed before any non-loopback deployment.
MSP430 compatibility remains gated on a separately frozen public result
contract. See
[docs/ROADMAP.md](docs/ROADMAP.md) for acceptance-level tasks.

## License status

No open-source license has been selected. The current local development copy is
all rights reserved and must not be published or redistributed until the owner
makes an explicit license and release decision.
