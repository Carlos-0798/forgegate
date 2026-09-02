# Project status

- Date: 2026-09-01
- Version: 0.1.0.dev26
- Stage: Phase 18 Windows sandbox readiness/code gate implemented; WSL2/Podman
  hostile-runtime verification, plugin runner, broker, and durable run storage
  remain absent
- Product maturity: local CLI/API MVP with software-peer collection, audited aggregation, durable lifecycle binding, versioned project authority, offline GitHub gating, bounded import-free plugin metadata discovery, non-executing plugin contracts, and a fail-closed Windows sandbox prerequisite probe; not production-ready
- Highest ForgeGate-owned evidence: LOCAL_HOST_TEST
- Hardware evidence: not applicable; no device access performed
- Remote/publication status: private `Carlos-0798/forgegate` synchronized
  through the Phase 18 contract-model baseline; no public release, License, or
  LinkedIn publication authorized

## Implemented

- repository/package scaffold;
- strict project, policy, and evidence-bundle contracts;
- safe configuration loader;
- `doctor`, `validate-config`, and `export-schemas` CLI surface;
- generic sample project and policies;
- architecture, evidence, security, compatibility, roadmap, and verification
  documentation;
- Windows/Linux/macOS CI definition;
- immutable-in-session artifact registration with explicit root, size, regular
  file, stable-read, and SHA-256 checks;
- bounded JUnit XML collection into one normalized `test.summary` record;
- explicit collection warnings and rejections with stable codes;
- `collect-junit` CLI preview and committed golden output;
- Cobertura/coverage.py XML collection with observed-count precedence and
  repository/package/module scopes;
- LCOV collection with strict record state, count validation, module scopes,
  and explicit disclosure when only branch summaries are present;
- `collect-coverage-xml` and `collect-lcov` CLI previews and golden outputs;
- bounded SARIF 2.1.0 collection with strict JSON parsing, verified-success
  invocation state, rule/location/fingerprint normalization, and explicit
  zero-result summary evidence;
- `collect-sarif` CLI preview, generic fixture, and golden output;
- strict `forgegate.benchmark.v1` artifact contract with deterministic committed
  JSON Schema drift verification;
- bounded Benchmark JSON collection into one `benchmark.metric` evidence record
  per unique scope/name, retaining value, unit, baseline, and tolerance;
- `collect-benchmark` CLI preview, generic fixture, and golden output.
- deterministic policy evaluation over immutable policy/evidence models at an
  explicit timezone-aware timestamp;
- explicit trust, verification, age, presence, filter, aggregation, strict
  operator, conflict, and mandatory decision-precedence semantics;
- versioned `forgegate.policy-evaluation.v1` outputs with canonical
  fingerprints, evidence references, explanations, and remediation hints;
- `evaluate-policy` PASS/FAIL/REVIEW/ERROR exit codes 0/1/2/3 with committed
  generic PASS and FAIL examples.
- strict, versioned release-candidate, candidate-transition, and transition-result
  contracts;
- deterministic DRAFT creation plus the complete legal state graph with exact
  revision, timestamp, terminal-state, and transition-fingerprint invariants;
- PASS/FAIL/REVIEW terminal transitions bound to matching policy evaluation ID,
  commit, decision, and timestamp;
- stateless `candidate create` and `candidate transition` CLI previews with
  generic DRAFT/EVALUATING fixtures and structural/evaluation-bound Goldens;
- SQLite candidate-store schema v8 with ForgeGate application identity, WAL,
  FULL synchronous durability, foreign keys, exact-version validation, and
  explicit read/write transactions;
- append-only canonical candidate snapshots, content-addressed transitions,
  compare-and-swap current revision, and immutable idempotency responses;
- exact replay, conflicting-key rejection, stale revision protection, bounded
  writer contention, restart recovery, rollback fault injection, and corruption
  detection;
- persisted candidate create/advance/show/history CLI flow while retaining the
  stateless preview commands;
- explicit, validated SQLite v1/v2/v3/v4/v5/v6/v7-to-v8 migration plus exact legacy
  terminal evaluation and audit backfill where applicable;
- durable append-only policy-evaluation and release-attestation documents bound
  to the authoritative candidate audit chain;
- self-validating `forgegate.release-attestation.v1` with candidate,
  transitions, policy evaluation, content fingerprints, and unsigned-local
  assurance disclosure;
- deterministic JSON and Markdown rendering with committed Goldens;
- atomic directory publication, exact output replay, conflict rejection,
  symlink/unsafe-target defenses, and stable filesystem errors;
- persisted `candidate migrate-store`, `import-evaluation`, `attest`, and
  `show-attestation` CLI paths.
- frozen consumer-side structural mirror of Analog Validation Studio's public
  `result-export.v1` contract at upstream commit
  `9ac23494b86212928185de9b0eef1c1a82a8c0ea`;
- bounded, strict `collect-analog-validation` artifact path with no upstream
  package import, serial access, analysis rerun, or device operation;
- retained TestRun outcome, limitations, source schemas, metrics, criteria,
  point/evidence/raw-record lineage, exact bytes, and SHA-256 identity;
- automatic evidence-source mapping with current `BENCH_*` capped at
  `system_observed` and warned rather than promoted to physical verification;
- committed sample, Golden normalization, compatibility Schema, adversarial
  tests, architecture/security documentation, and clean-install smoke path.
- strict, bounded loading of collection-result JSON with UTF-8, duplicate-key,
  finite-number, depth, node, and exact-model gates;
- exact re-registration of every referenced artifact so missing, replaced, or
  metadata-conflicting bytes fail before assembly;
- versioned `forgegate.evidence-bundle-assembly.v1` containing a normal
  candidate-bound bundle plus one audited receipt per collector output;
- raw result file SHA-256, normalized result fingerprint, collector identity,
  original artifact references, ordered evidence IDs, and warnings retained;
- duplicate result/source, artifact conflict, evidence ownership, commit, time,
  and content-derived assembly identity invariants;
- `assemble-evidence` plus policy-CLI compatibility with direct bundles and
  validated assemblies;
- committed assembly Schema, Golden, adversarial tests, architecture/threat
  documentation, and clean-install assembly-to-policy smoke path.
- strict `forgegate.candidate-evidence-binding.v1` contract embedding the
  revision-one `COLLECTING` snapshot and complete audited assembly;
- canonical candidate, assembly, and binding fingerprints plus commit and
  monotonic-time invariants on every construction and load;
- immutable/idempotent SQLite binding persistence with candidate-chain metadata
  validation and append-only triggers;
- `candidate bind-evidence` and `show-evidence` CLI paths;
- mandatory binding before new v3 candidates reach `READY`, and terminal policy
  evaluation enforcement against the bound nested evidence bundle;
- explicit legacy semantics that preserve v1/v2 candidates without inventing a
  historical binding;
- committed binding Schema, Golden, migration/corruption/adversarial tests,
  architecture/threat documentation, and clean-wheel end-to-end binding smoke.
- shared `CandidateApplication` service for CLI and REST candidate creation and
  candidate/history/evidence/attestation reads;
- local FastAPI v1 health, idempotent candidate-create, and persisted read
  endpoints with strict request models;
- structured request/domain/store/internal error envelopes, stable status-code
  mapping, safe request correlation IDs, and exception-detail sanitization;
- loopback-only `serve` command supporting localhost, IPv4 loopback, and IPv6
  loopback while rejecting external and wildcard binds;
- deterministic `export-openapi`, committed OpenAPI 3.1 bytes, verification
  drift gate, and clean-wheel comparison;
- API/CLI creation parity plus full durable evidence-binding, terminal
  attestation, and history readback integration coverage.
- shared application commands for candidate advancement, evidence binding,
  policy evaluation, and durable attestation creation;
- REST transition commands with caller-owned idempotency keys and optimistic
  `expected_revision` control;
- REST evidence binding that accepts a strict assembly document but no path
  from which the API loads an assembly or artifact;
- REST evaluation that uses only the candidate's persisted binding and commits
  the resulting terminal transition atomically;
- legacy/stateless release-track/policy-name matching in the candidate
  lifecycle boundary, strengthened by exact material authority for new
  persisted candidates;
- REST attestation persistence with deterministic replay and no filesystem
  output parameter;
- loopback HTTP Host enforcement, declared 4 MiB request-length rejection, and
  state/concurrency/error adversarial tests.
- immutable `forgegate.registered-project.v1` profiles with canonical config
  fingerprints, content-derived registration IDs, and exact idempotent replay;
- SQLite candidate-store schema v4 with append-only project, project-idempotency,
  and audit-event tables plus indexed project/candidate cursors;
- transactional audit events for successful project registration, candidate
  creation, evidence binding, transitions, evaluation persistence, and
  attestation persistence, with no duplicate event on exact replay;
- explicit v1/v2/v3-to-v4 migration with deterministic audit projection and no
  fabricated project profile, evidence, or actor identity;
- bounded `forgegate.audit-event-page.v1` queries by stable local sequence,
  project, and candidate through shared application, CLI, and REST paths;
- committed project/audit Schemas, expanded OpenAPI, corruption/trigger/
  pagination/adversarial tests, and clean-wheel smoke coverage.
- application/CLI/REST candidate creation authorized by an existing immutable
  project profile and exactly one normalized configured release track;
- canonical hyphen candidate/policy track identity with documented compatibility
  for existing underscore project keys and fail-closed ambiguity rejection;
- bounded `forgegate.registered-project-page.v1` and
  `forgegate.release-candidate-page.v1` discovery contracts through CLI/API;
- SQLite v5 composite project/candidate index and explicit v4 migration without
  duplicate audit projection;
- the previously frozen append-only, compare-and-swap project-profile revision
  semantics implemented without rewriting the initial registration;
- strict `forgegate.project-profile-revision.v1` and bounded
  `forgegate.project-profile-page.v1` contracts with content-derived identity,
  previous-profile linkage, full replacement configuration, and effective time;
- SQLite v6 append-only profile ledger, compare-and-swap profile head,
  immutable revision-idempotency records, profile-revision audit events, and
  validated v1-v5 migration that backfills registrations only;
- `project revise/current/history` and matching loopback REST/application
  surfaces with exact replay, stale-version, time-regression, and project-ID
  rejection;
- `forgegate.release-candidate.v2` with the exact governing profile ID/version,
  immutable durable binding rows, profile-preserving lifecycle transitions, and
  fail-closed corruption checks;
- release-track additions/removals applied only to later candidates, historical
  candidate/profile resolution preserved, and legacy v1 candidates retained
  without fabricated binding rows.
- self-validating `forgegate.policy-material.v1` with exact base64 bytes,
  root-relative path, media type, byte size, SHA-256, parsed policy,
  profile/track authority, and content-derived material identity;
- `forgegate.policy-evaluation.v2` binding the decision to the exact material,
  evidence fingerprint, frozen profile ID/version, and explicit timestamp;
- CLI-only materialization through an explicit root-confined project directory,
  plus `candidate evaluate` and `show-policy` durable paths;
- path-free REST evaluation accepting a complete validated material document
  and policy-material readback without server-side client-path dereference;
- atomic SQLite material/evaluation/transition/audit/idempotency persistence,
  immutable material rows, rollback fault injection, and corruption checks;
- explicit v1-v6 migration that assigns no historical material requirement and
  fabricates no policy bytes, approval, producer identity, or authenticity.
- self-validating `forgegate.assurance-bundle.v1` joining the exact candidate
  profile, evidence binding, policy material, evaluation, lifecycle, and
  attestation under one content-derived identity;
- deterministic three-file publication with canonical machine JSON,
  human-readable limitations, and a self-identifying size/SHA-256 manifest;
- database/project-independent `verify-assurance` with exact member, regular
  file, byte-limit, UTF-8, duplicate-key, finite-number, identity, association,
  canonical-byte, and directory-name gates;
- exact export replay and conflict/tamper rejection without dereferencing any
  path embedded in policy or evidence metadata;
- explicit `unsigned_local`, retained-document verification scope and
  `source_artifact_bytes=not_embedded` evidence boundary.
- key-derived `forgegate.signing-identity.v1` documents with canonical Ed25519
  public-key base64 and stable identity IDs;
- external `forgegate.trust-store.v1` authorization for explicit active/revoked
  identities, producer/operator roles, and project scopes;
- domain-separated `forgegate.assurance-signature.v1` statements binding exact
  canonical bundle bytes, signer, role, and caller-supplied time;
- cryptographic verification followed by exact external trust-record, status,
  role, and project authorization checks;
- bounded strict-JSON identity loading and deterministic content-addressed
  signature publication with exact replay and conflict rejection;
- installed `identity derive`, `identity trust`, `sign-assurance`, and
  `verify-assurance-signature` CLI workflow without private-key generation or
  retention.
- external trust-store requirement for `serve`, with no unauthenticated runtime
  application construction path;
- domain-separated one-time Ed25519 challenges binding server instance,
  trust-store ID, identity, role, exact projects, nonce, and expiry;
- short-lived memory-only Bearer sessions retaining token digests rather than
  raw tokens, with bounded challenge/session caches and restart expiry;
- exact project authorization, producer read-only policy, operator write/audit
  authority, filtered project discovery, and mandatory REST audit project scope;
- `forgegate.audit-actor.v1` attribution inside successful API state-change
  transactions, with content-derived event binding and no token/key retention;
- strict `identity sign-api-challenge`, authentication routes, OpenAPI security
  scheme, adversarial authentication/authorization tests, and installed-wheel
  challenge/session smoke.
- authenticated self-logout and operator-only exact-session revocation with
  complete target-project coverage and non-enumerating not-found responses;
- explicit reload from the fixed `serve --trust-store` startup path, requiring
  the caller to remain an exact trusted operator and cover all projects in both
  store versions;
- pending-challenge invalidation and immediate incompatible-session removal on
  successful changed trust-store reload, with validated no-op semantics;
- three bounded process-local fixed-window counters for valid challenge
  requests, session exchanges, and invalid Bearer attempts, returning `429`
  with `Retry-After`;
- lifecycle/reload/rate OpenAPI, adversarial tests, security documentation, and
  installed-wheel smoke while retaining the loopback-only boundary.
- exact ASGI request-byte accounting with a 4 MiB cap for declared and
  unknown-length/chunked bodies;
- challenge and session endpoint counters applied before strict request-model
  parsing, so malformed authentication JSON consumes the same bounded window;
- separate content-addressed `forgegate.api-security-event.v1` and bounded page
  contracts for authentication rejections, rate limiting, logout, scoped
  revocation, and trust reload;
- SQLite v8 append-only API security-event table with explicit v7 migration,
  10,000-event default capacity, visible saturation, stable cursor queries, and
  global-operator REST authorization;
- best-effort journal writes that retain no token, signature, request body,
  private key, or arbitrary header and do not alter the transactional release
  audit, session outcome, or loopback-only product boundary.
- strict content-derived `forgegate.github-action-report.v1` retaining verified
  bundle/manifest IDs, exact full candidate/CI commit binding, decision,
  recommended conclusion, and unchanged evidence-boundary fields;
- `github-gate` over a Phase 11 portable directory with existing 0/1/2/3
  decision exits, bounded escaped rule summary, schema-constrained runner
  outputs, unsafe-target rejection, and sanitized integration failures;
- token-free repository-local composite Action using environment-bound inputs,
  plus a canonical generic PASS fixture and real Ubuntu workflow smoke job that
  is explicitly not the ForgeGate repository's current revision;
- installed-wheel GitHub gate/report validation and local Action mechanics
  coverage without GitHub API, artifact upload, source replay, CI identity, or
  hardware claims.
- strict content-derived plugin manifest and deterministic discovery-report
  contracts for Plugin API v1;
- installed `forgegate.plugins.v1` entry-point enumeration through bounded,
  distribution-listed manifests without `EntryPoint.load` or module import;
- explicit compatible, incompatible, invalid, and duplicate-ID conflict states
  with stable sanitized issues and no installation-path disclosure;
- standalone import-hostile generic plugin package plus clean-wheel
  install/discover/uninstall independence smoke.
- strict `forgegate.plugin-run-plan.v1` authority envelope binding an exact
  target manifest, content-addressed logical inputs, declared/approved/enforced
  permission sets, `SANDBOXED` tier, deny policies, limits, and UTC plan time;
- strict `forgegate.plugin-protocol-message.v1` sequencing for bounded `START`,
  `READY`, `RESULT`, and stable-code `ERROR` envelopes;
- append-only-shaped `forgegate.plugin-run-transition.v1` legal state links and
  replay-validating `forgegate.plugin-run-result.v1` terminal documents with
  core-rehashed/schema-validated output identities;
- public configuration loading, four generated JSON Schemas, Schema drift
  checks, and adversarial identity/authority/state/resource tests for those
  documents without importing or starting plugin code.
- content-derived `forgegate.windows-plugin-sandbox-capability.v1` reports that
  retain execution `PROHIBITED` and isolation tier `NONE` for every probe;
- bounded `plugins sandbox-status` inspection requiring Windows, exactly one
  default local-loopback Podman connection, a running WSL provider, and a
  rootless runtime before reporting readiness for adversarial verification;
- shell-free, digest-pinned Podman create arguments with no network, isolated
  IPC, read-only root, dropped capabilities, no-new-privileges, PID/memory/CPU
  limits, non-root identity, read-only broker inputs, and bounded private tmpfs;
- fail-closed tests for missing/failed/malformed/remote/rootful/non-WSL runtime
  states and unsafe image/name/path/plan/resource inputs; no container started.

## Designed, not implemented

- external-plugin trust domains separating core, broker, disposable runner,
  untrusted plugin, content-addressed inputs, and core-authored audit;
- out-of-process runner and broker implementation for the modeled bounded
  protocol and broker-owned input/output handling;
- actual Windows WSL2/Podman hostile-fixture enforcement for the modeled
  deny-by-default permissions, `SANDBOXED` isolation tier, and mandatory
  resource limits;
- durable append-only run storage, crash recovery, and idempotent replay over
  the implemented transition/result contracts;
- exact upstream reference review with three shallow external clones and two
  source-only fixed revisions; no third-party source copied or dependency added.

## Not implemented

Non-loopback/TLS API deployment, reverse-proxy trust, hostile-local-user
defense, managed online revocation, durable/distributed sessions, per-client
network rate controls, distributed rate state, HTTP artifact collection and
file publication, complete rejected-request/warning ingestion, security/audit
export/retention, administrator-resistant logging,
external plugin execution, verified sandbox backend, permission/resource enforcement,
and durable run-audit implementation,
custom GitHub Checks/PR annotations/API writes,
managed/encrypted/hardware-backed key custody, trusted timestamps, online
revocation, CI workload identity federation, database authorization,
backup/repair, MSP430
collector, Studio Phase 5
human-readable report ingestion, authenticated provenance/signatures, source
artifact payload/replay export, and hardware access.

## Accepted local checkpoint

- PowerShell environment bootstrap: PASS
- direct dependency constraints and `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict: PASS across package and verification-tool source files
- pytest: 715 passed, 3 skipped (Windows symlink creation unavailable)
- branch-aware coverage: 96.26% across 7,588 statements and 2,074 branches
- Plugin execution contract focus: 7 passed across plan authority, protocol
  sequencing, legal transitions, terminal replay, resource limits, JSON
  loading, and content-derived identity; no process started
- Plugin SDK discovery focus: 30 passed, 1 skipped; plugin package 99.27%
  branch-aware coverage, with the skipped path requiring unavailable Windows
  symlink creation
- GitHub Actions gate focus: 10 passed, 1 skipped (Windows symlink creation
  unavailable); models 100%, integration service 98%
- API security-event focus: 5 passed, covering contracts, persistence,
  migration, access, saturation, privacy, and control behavior
- authenticated-identity focus: 22 passed; identity package 96.48%
- portable-assurance focus: 17 passed; assurance models 100% and portable
  publication/verifier 95%
- project-profile revision focus: 5 passed, including migration, corruption,
  REST, and CLI contracts
- Analog Validation collector focus: 59 passed; 100% across 431 statements and
  106 branches
- evidence-assembly focus: 20 passed; 100% across 218 statements and 70
  branches
- candidate evidence-binding/store focus: 71 passed; 100% across 526 statements
  and 138 branches
- committed JSON Schema and OpenAPI drift checks: PASS
- project/policy/candidate/transition example documents: VALID
- thirty-six canonical versioned document Schemas plus Benchmark and Analog
  Validation artifact Schemas: drift-checked and parsed
- complete sdist manifest and ForgeGate/sample-plugin wheel builds: PASS
- Windows sandbox readiness focus: 12 passed across probe failure isolation,
  content identity, rootless/local/WSL requirements, command controls, public
  loading, and CLI behavior; current host remains `RUNTIME_MISSING`
- repository-external ForgeGate installation plus sample-plugin
  install/discover/uninstall independence smoke: PASS
- Git Bash shell-script syntax check: PASS
- latest implementation GitHub Actions baseline: Phase 18 run 33569520396 PASS
  on Windows, Ubuntu, and macOS; each platform completed `verify.py` over 706
  collected tests and `release_smoke.py` for contract-model commit
  `425038d363599d28fa33a4ae060441a6b0899c50`, and the dependent Ubuntu job
  passed the real composite Action against the generic fixture
- private GitHub synchronization: `main` pushed with noreply commit identity;
  repository visibility, default branch, About, and ten Topics read back

See `reports/PHASE_0_ENVIRONMENT_AUDIT.md` for the prerequisite audit and exact
human-intervention boundary. See
`reports/PHASE_6_LOCAL_REST_COMMAND_WORKFLOW_ACCEPTANCE_REPORT.md` for the
previous REST command slice and
`reports/PHASE_7_PROJECT_REGISTRY_AUDIT_QUERY_ACCEPTANCE_REPORT.md` for the
project-registry baseline and
`reports/PHASE_8_PROJECT_AUTHORITY_DISCOVERY_ACCEPTANCE_REPORT.md` for the
previous authority/discovery slice. See
`reports/PHASE_9_PROJECT_PROFILE_REVISIONS_ACCEPTANCE_REPORT.md` for the
previous slice and
`reports/PHASE_10_POLICY_MATERIALIZATION_ACCEPTANCE_REPORT.md` for the previous
slice. Phase 11 acceptance is recorded in
`reports/PHASE_11_PORTABLE_ASSURANCE_BUNDLE_ACCEPTANCE_REPORT.md`.
Phase 12 acceptance is recorded in
`reports/PHASE_12_AUTHENTICATED_IDENTITY_FOUNDATION_ACCEPTANCE_REPORT.md`.
Phase 13 acceptance is recorded in
`reports/PHASE_13_AUTHENTICATED_LOCAL_API_ACCEPTANCE_REPORT.md`.
Phase 14 acceptance is recorded in
`reports/PHASE_14_LOCAL_SESSION_LIFECYCLE_ACCEPTANCE_REPORT.md`.
Phase 15 acceptance is recorded in
`reports/PHASE_15_LOCAL_API_SECURITY_BOUNDARIES_ACCEPTANCE_REPORT.md`.
Phase 16 acceptance is recorded in
`reports/PHASE_16_GITHUB_ACTIONS_GATE_ACCEPTANCE_REPORT.md`.
Phase 17 acceptance is recorded in
`reports/PHASE_17_PLUGIN_SDK_DISCOVERY_ACCEPTANCE_REPORT.md`.
Phase 18 environment/reference review and the non-executing security-contract
acceptance are recorded in
`reports/PHASE_18_ENVIRONMENT_REFERENCE_AND_EXECUTION_CONTRACT_REPORT.md`.
The implemented public model slice is recorded separately in
`reports/PHASE_18_PLUGIN_EXECUTION_CONTRACT_MODELS_ACCEPTANCE_REPORT.md`.
The Windows-only readiness gate and administrator boundary are recorded in
`reports/PHASE_18_WINDOWS_SANDBOX_READINESS_REPORT.md`.
