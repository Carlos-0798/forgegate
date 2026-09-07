# Project status

- Date: 2026-09-06
- Version: 0.1.0a1
- Stage: Phase 36 reviewed Dashboard report submission and explicit foreground
  parsing implemented, with immutable request selection, warning consent,
  identity/project-namespaced idempotency, per-instance busy rejection and
  atomic initiating-operator attribution. Real Edge single/combined/warning
  workflows and forbidden-XML preview rejection verified on synthetic data.
  No automatic worker, test-command execution, evidence binding or hardware access.
  Phase 35 opt-in operator Dashboard job list/detail/results, reviewed
  cancellation and expired-lease recovery implemented. Explicit job-store v2
  migration adds event actors without rewriting historical records; no automatic
  worker, evidence binding or automatic service restart.
  Phase 34 durable local report job engine and CLI implemented, with
  separate v1 storage, explicit execution/cancellation, expired-lease recovery,
  bounded pending input retention and independent result export. Phase 34 itself
  added no Dashboard UI; automatic workers, candidate mutation by jobs and
  coordinated job backup remain absent.
  Phase 33 combined JUnit + Cobertura/LCOV browser preview, original-JSON
  binding and generic policy workflow implemented locally. Real Edge combined
  Cobertura/LCOV PASS, low-coverage FAIL and the scoped negative-input matrix
  verified; browser error-origin and Windows asset-ordering defects corrected.
  The browser preview itself still has no durable queue/raw retention.
  Phase 32 consistent candidate-store backup and offline validation
  implemented locally; no automatic restore, encryption or browser write added.
  Phase 31 Windows startup, HTTP/HTML diagnostics and controlled recovery
  support implemented; explicit foreground lifecycle, not an uptime watchdog.
  Phase 30 bounded JUnit preview and separate binding implemented;
  real Edge PASS/FAIL, warning-consent and rejection acceptance completed.
  Shared-policy reuse corrected with explicit SQLite v8-to-v9 migration.
  Phase 29 project Audit remains available; Windows high contrast,
  spoken Narrator output, and a real Remote Desktop run remain environment gates
- Product maturity: testable Windows Alpha with generic initialization,
  local CLI/API release-assurance flow, software-peer collection, audited
  aggregation, durable lifecycle binding, offline GitHub gating, and a
  live-tested Windows-only brokered plugin path, a narrow authenticated local
  Dashboard with reviewed lifecycle/evidence/evaluation/attestation actions,
  candidate-bound portable assurance download,
  an optional read-only MSP430 status monitor, and a separate strict MSP430
  validation-report collector; not production-ready
- Highest ForgeGate-owned evidence: LOCAL_HOST_TEST
- Hardware evidence: owner-authorized input-only COM4 UART status observation;
  no command, firmware/debug action, physical measurement validation, release
  evidence, or production claim
- Remote/publication status: private `Carlos-0798/forgegate`; repository changes
  are synchronized through reviewed pull requests and required CI. The latest
  previously accepted cross-platform run was 33999452478; no public release,
  License, or LinkedIn publication is authorized

The Phase 28 post-merge run 34001577886 passed the Windows/Linux/macOS test and
package jobs, but its final generic Action job did not start because GitHub
reported an account payment/spending-limit restriction. The overall run is
not green. Billing changes require owner action; local acceptance is separate.

Per the owner's current instruction, Phases 32–36 work is local-only. No GitHub
inspection, push, PR creation or merge was performed for this checkpoint.

## Implemented

- opt-in operator-only Dashboard jobs with scope filtering, paged list/detail,
  reviewed preview/submission/execution, exact result inspection,
  reviewed cancellation/recovery and event attribution;
- durable local CLI collection jobs in a separate v2 SQLite file, with bounded
  pending input, idempotent replay, explicit execution/cancellation, manual
  expired-lease recovery and result export; no automatic worker;
- current-schema SQLite backup through a pinned read transaction and Online
  Backup API, checked before atomic create-if-absent file publication; independent
  offline verification on a disposable copy, optional expected-hash comparison,
  path-free counts/receipt and explicit private-data/recovery limitations;
- `dashboard-check` distinguishes health, HTML, refusal, timeout and protocol
  failures without authentication, database reads or device access; an existing-
  workspace Windows launcher rejects missing/empty input and busy ports;
- bounded operator-only JUnit upload preview using the existing collector and
  assembler, in-memory exact bytes, declared-only evidence, original report time,
  explicit warning retention and separate reviewed binding; no browser job queue;
- operator-only project Audit workspace with candidate filtering, stable
  25-event cursor links, full record/actor inspection, no inferred actor,
  explicit preview truncation, and candidate-to-audit navigation;
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
- SQLite candidate-store schema v9 with ForgeGate application identity, WAL,
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
- public configuration loading, six generated JSON Schemas, Schema drift
  checks, and adversarial identity/authority/state/resource tests for those
  documents without importing or starting plugin code.
- content-derived `forgegate.windows-plugin-sandbox-capability.v1` reports that
  retain execution `PROHIBITED` and isolation tier `NONE` for every probe;
- bounded `plugins sandbox-status` inspection requiring Windows, exactly one
  default local-loopback Podman connection, a running WSL provider, and a
  rootless runtime with matching client/server versions before reporting
  readiness for adversarial verification;
- shell-free, digest-pinned Podman create arguments with no network, isolated
  IPC, read-only root, dropped capabilities, no-new-privileges, PID/memory/CPU
  limits, non-root identity, read-only broker inputs, and bounded private tmpfs;
- fail-closed tests for missing/failed/malformed/version-mismatched/remote/
  rootful/non-WSL runtime states and unsafe image/name/path/plan/resource inputs;
- a development-only hostile verifier whose fixed fixtures passed all 14
  required filesystem, network, process, environment, resource, output, log,
  image, runtime, and cleanup controls on Podman/WSL2 5.8.6;
- exact raw Phase 19 evidence with no host path, username, email, token, key, or
  hardware data; the readiness report remains `PROHIBITED` and tier `NONE`.
- standard-library trusted runner plus Windows plugin broker that never
  imports external code into the ForgeGate core process;
- exact distribution/version/entry-point/manifest matching, pure-Python package
  staging, content-addressed read-only inputs, and shell-free pinned-container
  execution;
- canonical `START`/`READY`/`RESULT` enforcement, two-snapshot tmpfs validation,
  strict `forgegate.plugin-output.v1`, input lineage checks, and atomic broker-
  owned output registration;
- separate append-only SQLite plugin-run v1 storage, immutable
  `forgegate.plugin-run-receipt.v1`, exact replay without re-execution, and
  fail-closed interruption recovery;
- Phase 20 live production-path verification through the installed standalone
  generic fixture: 13/13 broker controls passed, exact run tier `SANDBOXED`,
  output retained as `unsigned_local`/`declared`, hardware not accessed.
- operator-facing `plugins run/show/runs/collect` commands with exact manifest,
  input, grant, planning-time, and idempotency authority;
- strict content-derived path-free plugin run records and stable cursor pages,
  with terminal failures printed before exit code `3` and retained for query;
- broker-output revalidation into the existing `CollectionResult` boundary,
  including accepted-member/digest/schema/identity checks and re-registration
  of original input bytes without evidence trust promotion;
- `forgegate init` with a strict generic JUnit/coverage/SARIF/benchmark project,
  pull-request policy, deterministic path-free receipt, and refusal to
  overwrite existing configuration;
- clean-wheel Windows Alpha verification covering install, init, core
  assurance chain, live plugin CLI success/replay/failure/query/collect/
  assembly/policy flow, sample-plugin independence, and uninstall.
- deterministic interaction smoke covering project validation, all four CLI
  decision/exit outcomes, API health/correlation, deliberate documentation-page
  denial, authentication/authorization, exact replay/readback, and strict
  request rejection with an ephemeral identity and database.
- `forgegate dashboard` and `dashboard-activate` for explicit loopback service
  startup and one-time CLI approval with no browser-held private key or raw
  Bearer token;
- same-origin `/app/` assets and `/app/api/` BFF with opaque HttpOnly,
  SameSite=Strict sessions, exact Origin/Host and anti-CSRF checks, bounded
  activation/session state, restrictive headers, and no persistent browser
  storage or external runtime asset;
- strict TypeScript Overview, Devices, Projects, Candidates, Evidence,
  Decision, and Assurance pages with immutable candidate review/confirmation,
  exact role/scope enforcement, audit display, explainable rule results,
  attestation/bundle identity, and explicit limitation/evidence labels;
- content-hashed deterministic frontend assets, canonical SHA-256 inventory,
  source/wheel inclusion checks, locked build dependencies, and CI drift gates;
- separate deterministic Dashboard BFF OpenAPI export with 21 explicit
  operation IDs, committed-byte drift detection, and installed-wheel comparison;
- optional `msp430` dependency and domain-neutral live-status provider boundary;
  an independently implemented MSP430 UART v1 parser validates ASCII framing,
  128-byte lines, field ranges, and CRC-16/CCITT-FALSE without importing the
  upstream runtime;
- input-only COM4 monitor with DTR/RTS inactive before opening, bounded reads,
  reconnect handling, monotonic staleness, protocol-error and sequence-gap
  counters, and no serial write surface;
- authenticated one-second Devices polling that separates connection,
  heartbeat freshness, and firmware-reported device health, retaining
  `LIVE_STATUS_ONLY_NOT_RELEASE_EVIDENCE` and `hardware_control=NOT_PERFORMED`;
- versioned MSP430 UART v1 fault-bit decoding, including explicit unknown-bit
  retention and a visible warning that device reports are not ForgeGate diagnoses;
- one project-scoped, authenticated assurance-review BFF response joining the
  retained candidate history, evidence binding, exact policy material,
  evaluation, attestation, and portable bundle identity for authoritative
  post-command review;
- Evidence, Decision, and Assurance pages with candidate-bound deep
  links, exact expected/actual rule values, referenced evidence IDs, lifecycle
  transitions, missing-stage states, and explicit assurance limitations;
- operator-only same-origin Dashboard commands for expected-revision lifecycle
  transitions, immutable evidence binding, frozen-policy evaluation, and
  deterministic terminal attestation generation, each behind reviewed
  confirmation, CSRF, project scope, and authoritative reload;
- bounded browser-local JSON selection that sends complete evidence-assembly or
  policy-material documents without exposing a client path to the server;
- operator-reviewed portable assurance download using a deterministic bounded
  three-file ZIP, exact candidate revision and bundle identity, same-origin/
  CSRF/project-role controls, no accepted path, and no server-side file write;
- 80 focused Dashboard tests plus previously retained Microsoft Edge and Chrome keyboard/focus
  operation, complete 129-record cursor pagination, browser-rendered
  409/413/422/429/500 recovery, and Chrome/in-app-browser 390 px
  responsive/clean-console runs using generic local data; uncommon statuses
  use a zero-write test-only presentation harness;
- native Edge 100/125/150/175/200% zoom with no root horizontal overflow,
  reachable reviewed actions, and a keyboard-contained 200% confirmation
  dialog; bounded Narrator keyboard/semantic testing without spoken capture;
- strict `forgegate.msp430-validation-report.v1` artifact loading and
  normalization with exact commit, hardware-context, source-hash, correction,
  and evidence-level checks, no serial/device access, and no trust promotion;
- retained generic-data Windows Dashboard workflow and exact-zoom screenshots
  with explicit Alpha, non-hardware, non-production claim boundaries and
  verified sdist inclusion.

## Designed, not implemented

- later automatic Dashboard evidence collection, plugin execution, and
  session/trust administration;
- publisher signatures/trust, remote plugin acquisition, automatic install,
  and an independent production plugin repository;
- native-extension and separately packaged plugin-dependency support;
- Linux/macOS execution backends and REST plugin-run endpoints;
- automatic promotion of validated plugin output into a candidate-bound release
  decision; the new collection projection remains an explicit separate step.

## Not implemented

full Dashboard assistive-technology acceptance (high contrast, spoken Narrator
output, and a real Remote Desktop session); automatic browser-side evidence
collection, source-artifact export, and plugin/admin commands; non-loopback/TLS
API deployment, reverse-proxy trust, hostile-local-user
defense, managed online revocation, durable/distributed sessions, per-client
network rate controls, distributed rate state, HTTP artifact collection and
file publication, complete rejected-request/warning ingestion, security/audit
export/retention, administrator-resistant logging, generalized third-party
plugin compatibility, publisher trust/provenance, native/dependency-rich
plugins, Linux/macOS plugin execution,
custom GitHub Checks/PR annotations/API writes,
managed/encrypted/hardware-backed key custody, trusted timestamps, online
revocation, CI workload identity federation, database authorization,
automatic restore/repair, retained MSP430 telemetry history,
Studio Phase 5
human-readable report ingestion, authenticated provenance/signatures, source
artifact payload/replay export, hardware control, and physical measurement
validation. Phase 33 adds manual JUnit + Cobertura/LCOV combination, not
automatic/background collection or raw report retention. Its real-browser
Cobertura/LCOV positive paths and the scoped negative manual matrix pass;
remaining OS assistive checks are separate.

## Accepted local checkpoint

- Phase 36: 23 additional Python and 14 frontend report-job regressions;
  actual Edge frozen submission, separate parsing, single-failure counts,
  combined LCOV 50% results, warning retention and forbidden-XML rejection.
  Independent store readback confirms 3 new tasks with attributed three-event
  histories and an unchanged unbound candidate. See [acceptance evidence](../reports/PHASE_36_DASHBOARD_JOB_SUBMISSION_ACCEPTANCE.md).
  Isolated port 8135 only; original 8131/MSP430 runtime untouched. GitHub paused.
- Phase 35: 16 additional Python and 17 frontend job-management regressions;
  isolated actual Edge pagination, result inspection, Escape/focus return,
  cancellation/actor retention, expired recovery and real revision-conflict checks.
  See [acceptance evidence](../reports/PHASE_35_DASHBOARD_JOBS_ACCEPTANCE.md).
  Original port 8131 and MSP430 runtime left untouched; GitHub remains paused.
- Phase 34: 32 focused job regressions and independent-process CLI acceptance;
  exact replay, exclusive claim, cancellation/late-result ordering, expired-only
  recovery, candidate rechecks, quotas, corruption rejection and separate binding.
  [Operations and limitations](COLLECTION_JOBS.md) distinguish successful
  collection from policy PASS and logical deletion from secure erasure.
  No existing Dashboard or MSP430 service was restarted or used for this work.
- Phase 33: bounded combined report preview, original-JSON reviewed binding,
  whole-selection rejection/warning behavior and existing collector reuse.
  Real Edge Cobertura preview/binding/lifecycle/policy PASS and exact rule values
  are retained; browser-discovered numeric reserialization was fixed without
  changing canonical fingerprints. No new MSP430 or GitHub operation.
  The [browser follow-up](../reports/PHASE_33_BROWSER_ACCEPTANCE_FOLLOWUP.md)
  adds 13 scoped actual-Edge cases, including LCOV PASS, low-coverage FAIL,
  warning consent, rejection/cancellation and recovery; fixes local-vs-HTTP
  error labeling and mixed-case Windows asset inventory ordering.
- Phase 32: 27 focused backup regressions; backup module 100% branch-aware
  coverage (120 statements, 32 branches), cold terminal-candidate readback,
  exact table preservation, installed CLI backup/verify/no-overwrite smoke and
  an independent manual synthetic snapshot/hash check pass. No GitHub operation.
- Phase 31: 28 focused host/Windows launcher cases; real isolated Dashboard,
  API-only and stopped-service HTTP checks; two foreground startup/shutdown
  cycles on the same synthetic database, with post-run SQLite quick-check OK.
  Phase 32 added no fresh authenticated-browser or MSP430 stability claim.
  Phase 33 adds isolated Edge test + coverage selection/binding/evaluation, not
  new hardware or assistive-technology evidence. See the Phase 33 report.
- Activation follow-up: 13 production-TypeScript host interaction regressions
  pass via `pnpm run test:dashboard` on Node 24.19.0, separately from Python
  coverage; real in-app-browser activation at port 8131 also passes
- PowerShell environment bootstrap: PASS
- direct dependency constraints and `pip check`: PASS
- Ruff and Ruff format: PASS
- mypy strict: PASS across package and verification-tool source files
- pytest: 1072 passed, 3 skipped (Windows symlink creation unavailable)
- branch-aware coverage: 95.50% across 11,343 statements and 3,042 branches
- MSP430 live-status focus: 17 passed across parser, state classification,
  staleness, invalid/recovery, counters, dependency/I/O failure, and input-only
  monitor lifecycle
- Historical Phase 30 Dashboard focus: 80 passed with 98.60% branch-aware coverage across 728
  statements and 130 branches
- Frontend host regressions: 104 passed, including 31 jobs and 30 combined-collection/import,
  18 JUnit collection, 12 Audit and 13 activation cases; separate from Python
  coverage and browser tests
- Phase 30 browser checkpoint: real Edge file selection, independent binding,
  lifecycle and policy PASS/FAIL, explicit warning retention, forbidden-XML
  rejection and unchanged canceled-preview state pass. Shared-policy reuse
  initially failed, then passed after schema v9 migration; four new migration
  tests prove retained-row preservation and transactional rollback.
- Phase 29 browser checkpoint: isolated 28-event fixture returned 25 + 3
  events, exact candidate filter returned one, nonexistent ID returned zero,
  refresh/back preserved filters, and keyboard toggled event details
- Dashboard browser checkpoint: Microsoft Edge and Chrome keyboard creation/
  read, modal Tab containment/Escape/focus return, 129-record six-page
  traversal, and 409/413/422/429/500 recovery PASS; Chrome service-restart
  recovery and 390 px responsive/clean-console checks, installed-wheel Edge
  read, in-app-browser 390 px check, and generic portfolio capture PASS;
  uncommon statuses use a zero-write test-only presentation harness; native
  Edge 100–200% zoom PASS, bounded Narrator keyboard/semantic checks PASS,
  while spoken output, high contrast, and a real Remote Desktop run remain open
- MSP430 browser checkpoint: authenticated Devices page displayed connection
  `CONNECTED`, heartbeat `NORMAL`, device health `FAULT`, and flags `0015`;
  one-second polling resumed after Overview navigation, the status sequence
  continued advancing, the inspected 1280 px viewport had no horizontal
  overflow, and the browser error/warning log was empty
- Phase 25 owner-assisted unplug/replug checkpoint: the owner observed the live
  transition; the recovered process retained `reconnects=1`, one sequence gap,
  and one protocol error, then advanced sequence 138→149 and valid frames
  3028→3039 over 10.5 seconds without increasing those counters
- Phase 26 browser checkpoint: a generic PASS fixture navigated from candidate
  detail through Evidence, Decision, and Assurance; displayed the exact
  expected/actual value `0`, `RULE_SATISFIED`, attestation/bundle IDs,
  `unsigned_local`, and explicit source-byte/authenticity/hardware boundaries
- Phase 26 live-device follow-up: COM4 remained `CONNECTED` with heartbeat
  `NORMAL`; `0015` decoded to DS18B20 missing, NTC unavailable/range, and
  INA219 communication, while 17 additional frames arrived with zero new
  protocol errors, gaps, or reconnects in the fresh process
- Phase 27 browser checkpoint: one generic Edge candidate completed reviewed
  DRAFT→COLLECTING→READY→EVALUATING→PASS→attestation writes with audit sequence
  5–12; a mismatched-commit assembly was rejected before durable binding, and
  two discovered presentation defects were corrected and retested
- Phase 28 browser checkpoint: the same generic completed candidate displayed
  its exact revision/bundle/member boundary before one Edge download; the
  15,448-byte ZIP extracted to exactly three files and `verify-assurance`
  returned `VALID`, with no server path, state mutation, publication, or
  hardware access
- MSP430 validation-report collector focus: 34 passed across strict loading,
  evidence mapping, commit/hardware/correction invariants, assembly integration,
  CLI, Schema drift, and adversarial limits; no hardware was accessed
- Plugin execution contract focus: 8 passed across plan authority, protocol
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
- portable-assurance focus: 19 passed;
  deterministic ZIP and offline extraction are included
- project-profile revision focus: 5 passed, including migration, corruption,
  REST, and CLI contracts
- Analog Validation collector focus: 59 passed; 100% across 431 statements and
  106 branches
- evidence-assembly focus: 20 passed; 100% across 218 statements and 70
  branches
- candidate evidence-binding/store focus: 71 passed; 100% across 526 statements
  and 138 branches
- committed JSON Schema, direct API OpenAPI, and Dashboard BFF OpenAPI drift
  checks: PASS
- project/policy/candidate/transition example documents: VALID
- forty-four canonical versioned document Schemas plus Benchmark, Analog
  Validation, and MSP430 validation-report artifact Schemas: drift-checked and
  parsed
- complete sdist manifest and ForgeGate/sample-plugin wheel builds: PASS
- clean-wheel MSP430 report collection, Dashboard OpenAPI export (25 paths, 27 operations),
  installed-package workflow, optional `pyserial` install, and uninstall: PASS
- Windows sandbox focus: 20 passed across probe failure isolation, client/server
  identity, rootless/local/WSL requirements, command controls, strict verifier
  JSON/output handling, public loading, and CLI behavior
- Windows hostile-runtime controls: 14/14 PASS with Podman client/server 5.8.6;
  raw report ID
  `sha256:5296f70996ff9928d54557fb97c2e667f15ccdd67ff989b85b518260cb3db38d`;
  fixed ForgeGate fixtures only, no external plugin or hardware action
- brokered Windows plugin execution: 13/13 PASS through the installed generic
  fixture, including isolation denials, complete protocol, two-snapshot output
  validation, cleanup, durable readback, and exact no-reexecution replay; raw
  Phase 20 report retained under `reports/`, no hardware action
- repository-external ForgeGate installation plus sample-plugin
  install/discover/uninstall independence smoke: PASS
- Git Bash shell-script syntax check: PASS
- latest accepted GitHub Actions baseline: merge run 33999452478
  PASS on Windows, Ubuntu, and macOS; each platform completed `verify.py` over
  783 collected tests and `release_smoke.py` for checkpoint commit
  `32e961ce72a5ce4497010fbc22a53b0aab090571`, and the dependent Ubuntu job
  passed the real composite Action against the generic fixture; the local
  Podman hostile fixtures were not run or claimed by hosted CI
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
Phase 19 live control evidence and its remaining production boundary are
recorded in `reports/PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json` and
`reports/PHASE_19_WINDOWS_SANDBOX_LIVE_VERIFICATION_REPORT.md`.
Phase 20 implementation and live production-path acceptance are recorded in
`reports/PHASE_20_PRODUCTION_PLUGIN_BROKER_ACCEPTANCE_REPORT.md` and
`reports/PHASE_20_WINDOWS_PLUGIN_BROKER_LIVE_EVIDENCE.json`.
Phase 21 operator workflow acceptance is recorded in
`reports/PHASE_21_PLUGIN_OPERATOR_WORKFLOW_ACCEPTANCE_REPORT.md`.
Phase 22 packaging and live Windows Alpha acceptance are recorded in
`reports/PHASE_22_WINDOWS_ALPHA_ACCEPTANCE_REPORT.md` and
`reports/PHASE_22_WINDOWS_ALPHA_LIVE_EVIDENCE.json`.
The post-Alpha software integrity, interaction, dependency, and clean-wheel
review is recorded in
`reports/SOFTWARE_INTEGRITY_INTERACTION_AUDIT_2026-09-03.md`, with its latest
18-control clean-wheel Podman record in
`reports/SOFTWARE_INTEGRITY_INTERACTION_LIVE_EVIDENCE.json`.
The latest expected-versus-actual CLI/API verification and browser-tool limit
are recorded in `reports/INTERACTION_ACCEPTANCE_REPORT_2026-09-04.md`.
The Phase 23 design gate remains recorded in
`reports/PHASE_23_LOCAL_WEB_DASHBOARD_DESIGN_GATE.md`. The subsequent
implementation and exact PASS/NOT_RUN boundaries are recorded in
`reports/PHASE_24_AUTHENTICATED_LOCAL_DASHBOARD_ACCEPTANCE_REPORT.md`. The
follow-up operator/producer samples, persisted-output cross-check, and corrected
expiry/restart recovery are recorded in
`reports/PHASE_24_MANUAL_INTERACTION_ACCEPTANCE_2026-09-04.md`.
The candidate-bound portable ZIP implementation, Edge download, and offline
verification are recorded in
`reports/PHASE_28_DASHBOARD_ASSURANCE_EXPORT_ACCEPTANCE_REPORT.md` and
`reports/DASHBOARD_PHASE28_ASSURANCE_EXPORT_EVIDENCE_2026-09-05.json`.
