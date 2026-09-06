# Changelog

## Unreleased

- Added opt-in authenticated Dashboard job inspection, project pagination,
  reviewed cancellation and expired-lease recovery with atomic actor attribution.
  Added explicit job-store v1-to-v2 migration without rewriting historical records,
  frontend/authorization regressions and actual Edge synthetic acceptance.
  Submission/execution remain CLI-only; no automatic worker or hardware change.
- Added a separate durable local collection-job store and CLI with idempotent
  submission, bounded pending source retention, explicit run/cancel/recover,
  exact result export and fail-closed candidate rechecks. No Dashboard job UI,
  automatic worker, hardware access, evidence binding or policy decision added.
- Added job lifecycle/negative tests, three public schemas, cross-process
  expected-output acceptance and clean-wheel integration checks.
- Added bounded combined Dashboard JUnit + Cobertura/LCOV previews with independent
  metadata, duplicate/size/output limits, whole-selection warning consent and
  separate immutable binding. Source reports remain unsigned-local declarations.
- Fixed real-browser 422 binding failures caused by JSON number reserialization
  (`50.0` to `50`); preserve exact assembly JSON without changing retained identities.
- Added kind/scope labels to coverage previews, generic positive/negative fixtures,
  complete policy/attestation integration and actual Edge combined PASS evidence.
  No task queue, raw retention, hardware access or GitHub synchronization added.
- Added local `candidate backup-store` and `candidate verify-backup` commands
  for current-schema consistent SQLite snapshots, checked exclusive publication,
  offline hash/integrity validation and fixed privacy-safe failure codes.
- Added 27 regressions including committed WAL/uncommitted isolation, retained
  rows and cold candidate/evidence/attestation reads, existing-target races,
  sidecars, corruption, size/deadline checks and installed-wheel smoke. No live
  database replacement, hardware access or GitHub synchronization performed.
- Added `dashboard-check` with bounded, unauthenticated health/HTML checks,
  actionable failure states and explicit non-ownership/non-hardware labels.
- Added a Windows foreground launcher for existing database/trust files,
  advisory exclusive-port checks, literal paths and child exit-code propagation.
  No auto-start, watchdog, migration, process termination or automatic login.
- Added actual local HTTP/installed-wheel smoke and Windows PowerShell tests;
  recovery guidance preserves the existing schema and credential boundaries.
- Added bounded single-JUnit Dashboard preview with exact-byte hashing, original
  declared source time, explicit warning consent and separate immutable binding.
  No filesystem path, raw-byte retention, queue, hardware or trust promotion.
- Added 27 Python and 18 frontend host regressions and synthetic PASS/FAIL/
  warning/rejected inputs. Real Edge upload, reviewed binding, policy PASS/FAIL,
  warning-consent and forbidden-XML rejection now pass with retained screenshots.
- Fixed shared profile-authorized policy content failing on a second candidate.
  Schema v9 removes only global material-ID uniqueness, preserving candidate
  binding uniqueness and immutable guards. Explicit migration from v1-v8,
  retained-row preservation, rollback and same-database reuse are tested.
- Added an operator-only project Audit workspace with candidate filters,
  stable cursor links, full event/subject identities, recorded actors,
  text-only details, and explicit partial-preview/unknown-actor boundaries.
- Added 12 frontend and 5 BFF audit regressions; malformed BFF audit filters
  now return 422 and the committed OpenAPI retains their exact patterns.
- Fixed Dashboard activation commands to include the actual loopback origin
  and port; added manual retry, explicit code-expiry guidance, rate-window
  waiting without resubmission, and late-response isolation.
- Added 13 Node host interaction regressions over the production TypeScript,
  wired into CI separately from Python coverage and real-browser acceptance.
- Added an operator-reviewed, candidate-bound Dashboard assurance download as
  a deterministic bounded three-file ZIP with no server path or filesystem
  publication surface.
- Added exact revision/bundle identity, Origin, CSRF, project/role, response
  identity/media/size, and offline-verification gates plus retained Edge
  download screenshots and machine evidence.
- Added operator-only Dashboard commands for reviewed expected-revision
  transitions, immutable evidence binding, exact policy evaluation, and
  deterministic terminal attestation generation.
- Added bounded browser-local JSON import, per-command frozen review, CSRF,
  idempotency/stale-state recovery, and authoritative candidate-list/detail
  reload; corrected two defects found during the full Edge workflow.
- Added the strict artifact-only `forgegate.msp430-validation-report.v1`
  collector, Schema, CLI, adversarial tests, clean-wheel smoke, and a
  privacy-safe LaunchPad HIL migration fixture with retained limitations.
- Completed native Edge 100–200% zoom and a bounded Narrator keyboard/semantic
  pass; high contrast, spoken-output timing, and real Remote Desktop remain
  explicit environment gates.
- Added authenticated, project-scoped, read-only Dashboard Evidence, Decision,
  and Assurance review with candidate-preserving deep links, exact policy rule
  inputs/results, attestation/bundle identity, and explicit claim boundaries.
- Decoded versioned MSP430 UART v1 fault bits in the compatibility adapter,
  retained unknown bits without invented meaning, and recorded the
  owner-assisted unplug/replug plus a fresh live COM4 browser check.
- Added generic-data Evidence/Decision/Assurance portfolio captures with exact
  dimensions, SHA-256 records, and a Phase 26 acceptance report.
- Implemented the narrow same-origin, loopback-only local Web Dashboard with
  one-time CLI activation, an HttpOnly cookie BFF, exact Origin/Host and CSRF
  controls, and Overview, Projects, and Candidates pages.
- Added strict TypeScript/Vite build-only tooling, content-hashed packaged
  assets, a canonical SHA-256 asset inventory, CI/clean-wheel drift checks, and
  structural guards against executable HTML, persistent browser storage,
  service workers, and dynamic evaluation.
- Added a separate deterministic Dashboard BFF OpenAPI export with explicit
  operation IDs, committed-byte drift checks, and installed-wheel comparison.
- Expanded Dashboard/BFF/client/CLI/contract coverage to 46 focused tests. Edge
  and Chrome keyboard/focus, responsive, uncommon-error presentation, exact
  zoom, and installed-wheel read paths pass within their recorded boundaries.

## 0.1.0a1 — 2026-09-03

- Added bounded JSON/XML/YAML structural preflights, strict duplicate-key YAML
  loading, stable configuration reads, and adversarial resource tests before
  parser materialization.
- Replaced recursive host extraction of plugin output with a bounded trusted
  in-container exporter and independent no-extraction host archive validation;
  the clean-wheel Windows path passes both output snapshots and all 18 retained
  interaction controls.
- Updated constrained development tooling after dependency advisories and made
  the 95% branch-coverage gate enforce two-decimal precision.
- Added the Windows operator plugin workflow with exact discovery-to-plan
  authority, explicit inputs/grants, durable success/failure/replay receipts,
  and path-free single-run and cursor-page queries.
- Added revalidation of broker-accepted output into the existing audited
  collection boundary without promoting `unsigned_local` / `declared`
  evidence.
- Added `forgegate init`, which creates and strictly validates a generic four-
  collector project and pull-request policy template without overwriting
  existing files.
- Upgraded the clean-wheel Windows acceptance chain to cover installation,
  initialization, core evidence/decision paths, live CLI plugin success,
  replay, failure, collection, assembly, policy evaluation, and uninstall.
- Reworked the repository landing page around recruiter-readable value,
  architecture, verified outcomes, exact limitations, and a reproducible CLI
  transcript while moving detailed navigation into documentation/report indexes.
- Added contribution guidance plus evidence-aware Issue and pull-request
  templates, and extended the source-distribution gate to retain the new
  documentation assets while excluding local resume-handoff artifacts.
- Added a 33-check expected-versus-actual interaction smoke for the complete
  CLI decision exit contract and authenticated loopback REST boundary, and
  integrated it into development and source-distribution verification.
- This is a private Windows Alpha test candidate, not a public release,
  production-deployment approval, or hardware-verification claim.

## 0.1.0.dev28 — 2026-09-03

- Added the Windows production external-plugin broker and standard-library
  trusted runner without importing third-party entry points in the ForgeGate
  core process.
- Added strict low-trust plugin-output and immutable run-receipt contracts,
  broker-owned content-addressed input staging, double-snapshot output
  validation, atomic accepted-output registration, and cleanup enforcement.
- Added a separate append-only SQLite plugin-run store with exact idempotent
  replay and fail-closed interruption recovery.
- Upgraded the standalone sample collector to a pure-Python hostile-control
  fixture and executed it through the production broker on the verified local
  rootless Podman/WSL2 backend; all 13 broker-level checks passed.
- Added clean-wheel live-broker support to release smoke while retaining
  `unsigned_local`/`declared` output, no hardware access, Windows-only execution,
  and no publisher or general third-party trust claim.

## 0.1.0.dev27 — 2026-09-03

- Installed and verified a dedicated rootless Podman/WSL2 5.8.6 machine for
  Windows development, while retaining external execution `PROHIBITED` and the
  advertised isolation tier `NONE`.
- Added exact client/server version matching and a stable mismatch reason to
  the Windows capability gate.
- Added a development-only hostile-fixture verifier covering all 14 required
  filesystem, network, process, environment, resource, output, log, image,
  runtime, and cleanup controls, plus a path- and secret-free raw run record.
- Corrected Podman 5.8.6 tmpfs ownership options and output retrieval timing;
  output is copied while the private tmpfs is mounted, then re-counted and
  rehashed before container cleanup.
- Added focused strict-JSON, image-identity, output-bound, version-mismatch, and
  command regression tests. The production broker, runner protocol,
  output-schema/race validation, and durable `plugin_runs` remain deferred.

## 0.1.0.dev26 — 2026-09-01

- Selected a Windows-only rootless Podman/WSL2 backend direction and added a
  strict content-derived sandbox capability report.
- Added `forgegate plugins sandbox-status`, which fails closed for unsupported,
  missing, unavailable, remote, non-WSL, or rootful runtime configurations
  without importing a plugin or starting a container.
- Added a shell-free digest-pinned Podman container-create specification with
  read-only/private mounts, network/IPC/process denial, empty environment, and
  CPU/memory/output controls.
- The current host is readiness-blocked because WSL2 and Podman are absent;
  external plugin execution remains prohibited until real Windows adversarial
  verification, broker I/O, and durable run audit are complete.

## 0.1.0.dev25 — 2026-09-01

- Added strict, content-derived Plugin API v1 run-plan, protocol-message,
  transition, validated-output, and terminal-result models.
- Added fail-closed collector authority checks for declared, approved, and
  enforced permissions; `SANDBOXED`-only isolation; broker-owned logical
  subjects; deny-network/subprocess policy; and bounded resources.
- Added replay-verifiable state-chain validation, stable non-secret-bearing
  issue codes, four public JSON Schemas, configuration loading, Schema drift
  checks, and adversarial model tests.
- External plugin import, process creation, sandbox enforcement, broker I/O,
  and durable `plugin_runs` remain intentionally unimplemented.

## 0.1.0.dev24 — 2026-09-01

- Added strict content-derived `forgegate.plugin-manifest.v1` and deterministic
  `forgegate.plugin-discovery.v1` contracts for Plugin API v1.
- Added `forgegate plugins list`, which inspects installed entry-point metadata
  and bounded distribution-listed manifests without importing or executing
  plugin code.
- Added explicit compatible, incompatible, invalid, and duplicate-ID conflict
  states with stable sanitized issue codes and no installation-path disclosure.
- Added a standalone import-hostile generic plugin distribution plus clean-wheel
  install/discover/uninstall verification. Plugin execution, permission grants,
  subprocess isolation, publisher trust, and durable run audit remain deferred.

## 0.1.0.dev23 — 2026-09-01

- Added an offline `github-gate` command that strictly verifies a portable
  assurance bundle, requires exact full candidate/CI commit equality, emits a
  versioned content-derived report, and preserves 0/1/2/3 decision exits.
- Added bounded escaped GitHub Job Summary rendering and schema-constrained
  runner outputs with unsafe-target, payload, and file-size rejection.
- Added a token-free repository-local composite Action plus a canonical generic
  fixture workflow job that verifies real Action metadata and outputs without
  claiming the fixture represents the repository's current commit.
- Added the `forgegate.github-action-report.v1` Schema, adversarial/CLI tests,
  installed-wheel smoke, and explicit boundaries for unsigned-local evidence,
  absent source replay, absent GitHub API writes, and absent hardware claims.

## 0.1.0.dev22 — 2026-08-31

- Added a separate append-only SQLite v8 API security-event journal for
  rejected authentication, authentication rate limits, logout, session
  revocation, and trust-store reload without retaining tokens, signatures,
  request bodies, private keys, or arbitrary headers.
- Added bounded stable-cursor security-event queries restricted to an active
  operator whose project scope covers the complete current trust store;
  responses expose capacity, count, and saturation.
- Moved challenge/session request limiting ahead of body-model validation so
  malformed attempts consume the same fixed process-global endpoint budget.
- Enforced the 4 MiB request ceiling against actual ASGI bytes, including
  requests without `Content-Length`, while retaining the early declared-length
  rejection.
- Added v1-v7-to-v8 migration, append-only/capacity/privacy/adversarial tests,
  two standalone JSON Schemas, OpenAPI coverage, and clean-wheel persistence
  smoke. The log remains best-effort and is not claimed as a compliance audit.

## 0.1.0.dev21 — 2026-08-31

- Added authenticated self-logout and exact operator session revocation with
  fail-closed project-scope checks and non-enumerating not-found responses.
- Added explicit trust-store reload from the `serve` process's fixed startup
  path; the caller must remain a trusted operator and cover every project in
  both trust-store versions.
- Clear pending challenges and immediately remove sessions whose identity,
  role, or project authority no longer matches a successfully reloaded store.
- Added bounded fixed-window limits for validly shaped challenge requests,
  session exchanges, and invalid Bearer authentication, including `429` and
  `Retry-After` responses.
- Added lifecycle/reload/rate adversarial tests, OpenAPI operations, installed
  wheel smoke, and explicit boundaries for memory-only state, unaudited
  authentication control events, malformed-body handling, and loopback use.

## 0.1.0.dev20 — 2026-08-31

- Required an external trust store for `serve` and added domain-separated,
  single-use Ed25519 challenges plus bounded short-lived in-memory Bearer
  sessions.
- Enforced exact project scopes, producer read-only access, and operator
  write/audit authority across the protected REST surface.
- Added optional authenticated `forgegate.audit-actor.v1` attribution to
  successful API state-change events without retaining tokens or private keys.
- Added `identity sign-api-challenge`, challenge/session OpenAPI contracts,
  strict challenge loading, capacity/expiry/replay/tamper/revocation tests, and
  clean-wheel authentication smoke.
- Retained mandatory loopback bind/Host controls and explicitly deferred TLS,
  hostile-local-user defense, logout/live revocation, reverse-proxy trust, and
  non-loopback deployment.

## 0.1.0.dev19 — 2026-08-31

- Added key-derived `forgegate.signing-identity.v1` and externally supplied
  `forgegate.trust-store.v1` contracts with explicit producer/operator roles,
  project scope, active/revoked status, and content-derived IDs.
- Added domain-separated Ed25519 signatures over the exact canonical Phase 11
  bundle bytes through `forgegate.assurance-signature.v1`.
- Added strict bounded identity JSON loading, deterministic content-addressed
  signature publication, exact replay, and fail-closed key, signature, trust,
  role, project, and revocation checks.
- Added `identity derive`, `identity trust`, `sign-assurance`, and
  `verify-assurance-signature` CLI paths plus clean-install operation coverage.
- Kept the REST API loopback-only and the embedded evidence `unsigned_local`;
  trusted time, source-artifact authentication, managed key custody, and API
  authentication remain explicit limitations.

## 0.1.0.dev18 — 2026-08-31

- Added self-validating `forgegate.assurance-bundle.v1` exports that combine a
  frozen project profile, evidence binding, exact policy material, and release
  attestation without requiring the source database for later verification.
- Added deterministic content-addressed publication with canonical JSON,
  human-readable evidence limits, and a self-identifying file size/SHA-256
  manifest.
- Added `candidate export-assurance` and top-level `verify-assurance` CLI paths
  with strict directory members, byte limits, UTF-8/JSON parsing, identity,
  association, canonical-byte, and replay checks.
- Preserved `unsigned_local` assurance and explicitly declared that referenced
  source artifact bytes are not embedded or independently recollected.
- Added Schema, adversarial publication/verification tests, documentation, and
  clean-install export-to-offline-verification coverage.

## 0.1.0.dev17 — 2026-08-31

- Added self-validating `forgegate.policy-material.v1` documents that retain
  exact profile-authorized policy bytes, media type, size, SHA-256, parsed
  policy, and content-derived identity.
- Added `forgegate.policy-evaluation.v2`, binding the decision to the material
  ID, policy artifact hash, candidate profile ID/version, evidence fingerprint,
  and explicit evaluation time.
- Upgraded the SQLite store to schema v7; new profile-bound candidates require
  policy material for terminal evaluation, while v1-v6 migration preserves
  historical candidates without invented bytes or authenticity.
- Added CLI materialization/evaluation/read commands and a path-free REST
  evaluate/read contract; the API accepts validated material and never opens a
  client-selected server path.
- Added adversarial byte/identity, rollback, migration, CLI/API, Schema,
  OpenAPI, packaging, and clean-install verification for the complete slice.

## 0.1.0.dev16 — 2026-08-31

- Added append-only project-profile revision and bounded history contracts with
  full replacement configuration, previous-profile linkage, canonical identity,
  and explicit effective time.
- Upgraded the SQLite store to schema v6 with a profile ledger/head,
  expected-version compare-and-swap, exact revision idempotency, immutable
  candidate-profile bindings, and profile-revision audit events.
- Added `forgegate.release-candidate.v2`, binding every new product-surface
  candidate to the exact governing profile ID/version while retaining v1 for
  stateless and legacy compatibility.
- Added application, CLI, and loopback REST surfaces for project revision,
  current-profile read, and bounded profile history, with committed JSON Schema
  and OpenAPI updates.
- Added explicit v1-v5 migration that backfills initial registration profiles
  but never fabricates a profile binding for legacy candidates.
- Verified exact replay across later profile changes, stale-version and time
  rejection, track addition/removal isolation, corruption detection, clean
  packaging, and installed-wheel operation.

## 0.1.0.dev15 — 2026-08-31

- Required product-surface candidate creation to resolve an existing immutable
  project registration and exactly one configured release track.
- Canonicalized new candidate and policy track identities to hyphen form while
  preserving underscore-key compatibility and rejecting ambiguous profiles.
- Added strict, bounded project and project-scoped candidate page contracts
  through the shared application, CLI, REST, Schema, and OpenAPI surfaces.
- Upgraded the SQLite store to schema v5 with a project/candidate discovery
  index and an explicit v4-to-v5 migration that does not replay audit events.
- Added clean-install verification that distribution metadata and the runtime
  ForgeGate version remain identical.
- Defined future append-only project-profile revision and candidate-profile
  binding semantics without exposing a premature mutation surface.

## 0.1.0.dev14 — 2026-08-31

- Added immutable, idempotent `forgegate.registered-project.v1` persistence and
  project register/show surfaces for the CLI and loopback REST API.
- Upgraded the SQLite store to schema v4 with transactional append-only audit
  events for successful project and candidate lifecycle writes.
- Added strict `forgegate.audit-event.v1` and bounded stable-cursor
  `forgegate.audit-event-page.v1` query contracts with project/candidate filters.
- Added explicit v1/v2/v3-to-v4 migration with deterministic projection of
  existing candidate, transition, binding, evaluation, and attestation records.
- Added corruption, trigger, conflict, migration, API/CLI, OpenAPI, Schema, and
  clean-wheel coverage while retaining the loopback-only unsigned-local boundary.

## 0.1.0.dev13 — 2026-08-31

- Added local REST commands for optimistic/idempotent candidate transitions,
  audited evidence-assembly binding, bound-evidence policy evaluation, and
  durable attestation creation.
- Expanded `CandidateApplication` so CLI and HTTP share advance, bind, and
  attest paths; API evaluation computes from the persisted binding before the
  atomic terminal transition.
- Required policy evaluation names to match the candidate release track and
  retained exact revision, evidence fingerprint, decision, and timestamp gates.
- Added loopback Host validation, a declared 4 MiB request-length gate,
  adversarial state/concurrency tests, expanded OpenAPI, and clean-wheel
  operation checks.
- Made Schema and OpenAPI export bytes platform-independent by writing canonical
  UTF-8/LF output, with Windows regression coverage after the first GitHub
  Actions run exposed a CRLF-only clean-wheel mismatch.

## 0.1.0.dev12 — 2026-08-31

- Added a FastAPI-based, versioned local REST API with health, idempotent
  candidate creation, candidate/history, evidence-binding, and attestation
  read endpoints.
- Introduced a shared `CandidateApplication` service so HTTP and CLI candidate
  creation and reads use the same domain and SQLite paths.
- Added structured fail-closed error envelopes, request correlation IDs,
  loopback-only serving, strict request models, and sanitized unexpected-error
  responses.
- Committed and drift-checked the OpenAPI 3.1 contract, added API/CLI parity and
  durable evidence/attestation integration tests, and extended clean-wheel
  release smoke coverage.

## 0.1.0.dev11 — 2026-08-31

- Added self-validating `forgegate.candidate-evidence-binding.v1` documents
  covering the revision-one candidate snapshot, complete audited assembly,
  canonical fingerprints, binding time, and content-derived identity.
- Upgraded the SQLite candidate store to schema v3 with immutable binding rows,
  idempotent `bind-evidence`, validated `show-evidence`, and read-time
  candidate/assembly/audit-chain checks.
- Required new v3 candidates to bind evidence before `READY` and required the
  terminal policy evaluation to fingerprint the bound assembly's nested
  evidence bundle.
- Added explicit v1/v2-to-v3 migration without fabricating historical bindings,
  plus Schema, Golden, corruption/migration/CLI tests, architecture/threat
  documentation, and clean-wheel end-to-end binding smoke.

## 0.1.0.dev10 — 2026-08-31

- Added strict, bounded loading of collector `CollectionResult` JSON plus exact
  revalidation of every referenced source artifact.
- Added `forgegate.evidence-bundle-assembly.v1`, retaining raw result identity,
  normalized fingerprints, collector versions, artifact references, ordered
  evidence IDs, and warnings under a content-derived assembly ID.
- Added `assemble-evidence`; warnings fail closed unless explicitly retained,
  and duplicate results, conflicting artifacts, commit mismatches, and temporal
  inconsistencies are rejected.
- Allowed `evaluate-policy` to consume a validated assembly while preserving
  compatibility with direct evidence bundles.
- Added canonical Schema, deterministic Golden, adversarial tests,
  architecture/threat documentation, and clean-wheel assembly/evaluation smoke.

## 0.1.0.dev9 — 2026-08-31

- Added the optional, artifact-only Analog Validation Studio
  `result-export.v1` collector without an upstream runtime dependency or device
  access path.
- Mirrored and drift-checked the frozen public structure, revalidated TestRun,
  criteria, point, source, and raw-record lineage, and normalized run, metric,
  and criterion facts without recalculation.
- Derived verification levels from upstream evidence sources and capped current
  `BENCH_*` labels at `system_observed` with an explicit warning because the
  schema lacks mandatory instrument/calibration provenance.
- Added the `collect-analog-validation` CLI, sample artifact, deterministic
  Golden, adversarial/resource tests, compatibility/threat documentation, and
  clean-wheel smoke coverage.

## 0.1.0.dev8 — 2026-08-31

- Added a self-validating `forgegate.release-attestation.v1` document containing
  the terminal candidate, complete transition chain, policy evaluation, and
  content fingerprints.
- Added deterministic JSON and Markdown rendering plus atomic, conflict-safe
  local bundle publication with exact replay semantics.
- Upgraded the SQLite candidate store to schema v2 with durable append-only
  evaluation and attestation documents, explicit v1 migration, and legacy
  evaluation backfill.
- Completed the local persisted CLI flow with store migration, evaluation
  import, attestation generation, and attestation readback commands.
- Added committed Goldens, adversarial filesystem/database tests, schema drift
  coverage, architecture/threat-model updates, and installed-wheel smoke.

## 0.1.0.dev7 — 2026-08-31

- Added the versioned local SQLite candidate store with WAL, FULL synchronous
  durability, foreign keys, explicit transactions, and fail-closed schema
  identity checks.
- Persisted canonical candidate snapshots, content-addressed transitions, an
  optimistic current-revision pointer, and immutable idempotency responses.
- Added exact replay semantics, conflicting-key rejection, stale revision and
  compare-and-swap controls, bounded writer contention, restart recovery, and
  read-time audit-chain corruption detection.
- Added persisted candidate create/advance/show/history CLI paths, adversarial
  transaction/concurrency/corruption tests, architecture and threat-model
  updates, and clean-install database smoke coverage.

## 0.1.0.dev6 — 2026-08-30

- Added immutable, versioned release-candidate, transition-event, and
  transition-result contracts for the complete Phase 2 state graph.
- Added deterministic candidate creation, exact lifecycle revisions,
  non-regressing UTC timestamps, terminal-state immutability, and content-bound
  transition SHA-256 identities.
- Required PASS/FAIL/REVIEW terminal transitions to bind a matching policy
  evaluation ID, commit, decision, and timestamp; ERROR may fail closed without
  an evaluation result.
- Added stateless `candidate create` and `candidate transition` CLI previews,
  committed DRAFT/EVALUATING examples, Golden transitions, adversarial tests,
  canonical Schemas, documentation, and installed-wheel smoke coverage.

## 0.1.0.dev5 — 2026-08-30

- Added deterministic `forgegate.policy.v1` evaluation against immutable
  `forgegate.evidence-bundle.v1` inputs at an explicit timestamp.
- Added explicit trust and verification ranking, evidence age gates, filter and
  aggregation semantics, strict operators, conflict detection, and fail-closed
  PASS/FAIL/REVIEW/ERROR precedence.
- Added the versioned `forgegate.policy-evaluation.v1` result contract,
  SHA-256 input/evaluation identities, rule explanations, remediation hints,
  evidence references, and CI-compatible exit codes 0/1/2/3.
- Added PASS/FAIL example bundles, adversarial tests, canonical Schema,
  architecture documentation, and clean-wheel evaluation smoke coverage.

## 0.1.0.dev4 — 2026-08-30

- Added the strict ForgeGate-owned `forgegate.benchmark.v1` artifact schema and
  bounded Benchmark JSON v1 collector.
- Normalized metric name, value, unit, scope, optional baseline, and explicit
  absolute/percent tolerance into provenance-bound `benchmark.metric` evidence.
- Added duplicate-key, unknown-field, finite-number, numeric-range, duplicate
  metric, tolerance/baseline, depth, node, and metric-count rejection gates.
- Added a generic fixture, committed schema drift gate, golden projection, CLI
  path, adversarial tests, architecture/threat documentation, and release smoke.

## 0.1.0.dev3 — 2026-08-30

- Added a bounded, fail-closed SARIF 2.1.0 v1 collector.
- Normalized explicit scan summaries, individual findings, scanner/rule
  metadata, locations, fingerprints, suppression state, and baseline state
  without making policy decisions.
- Required unsuccessful invocations, ambiguous rule references, duplicate JSON
  keys, non-finite numbers, malformed structures, and resource-limit violations
  to reject collection.
- Added a generic SARIF fixture, deterministic golden projection, CLI path,
  adversarial tests, architecture/threat documentation, and clean-install smoke.

## 0.1.0.dev2 — 2026-08-30

- Added strict Cobertura/coverage.py XML and LCOV v1 collectors.
- Normalized repository, package, and module line/branch coverage into
  provenance-bound evidence without applying release thresholds.
- Added bounded parsing, declared-versus-observed audit warnings, LCOV state and
  summary validation, summary-only branch disclosure, golden outputs, and CLI
  collection commands.
- Extended clean-install release smoke coverage to exercise both installed
  coverage collectors.

## 0.1.0.dev1 — 2026-08-30

- Added a root-confined, size-bounded artifact registry with exact-byte SHA-256
  registration and change detection.
- Added the versioned JUnit v1 collector and normalized `test.summary` evidence.
- Added bounded XML parsing, forbidden declaration checks, declared-count audit
  warnings, fail-closed rejections, and deterministic golden output.
- Added the `collect-junit` preview command while keeping policy decisions out of
  the collector.

## 0.1.0.dev0 — 2026-08-30

- Established the domain-neutral Phase 0 repository scaffold.
- Added strict project, policy, and evidence-bundle contracts.
- Added trust/verification semantics and fail-closed mandatory-rule guards.
- Added configuration validation and JSON Schema export CLI commands.
- Added generic sample configuration, tests, CI, and compatibility boundaries.
- Added reproducible setup scripts, direct dependency constraints, release
  smoke verification, complete source-distribution manifest, macOS CI, and a
  95% coverage gate.
- Pinned third-party CI actions to immutable official release revisions and
  disabled checkout credential persistence.
