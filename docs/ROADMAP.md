# Roadmap

## Phase 0 — contract baseline

- [x] Product and independence boundary
- [x] Domain-neutral strict models
- [x] Trust and verification semantics
- [x] Generic sample project/policy
- [x] Threat model and CI definition
- [x] Optional AFE/MSP compatibility boundary
- [x] Complete local verification and freeze the checkpoint
- [x] Reproducible setup, 100% package coverage, schema drift gate, complete
  source distribution, and clean-install release smoke

## Phase 1 — first vertical slice

- [x] Add immutable artifact registry and byte-level SHA-256 verification.
- [x] Implement one adversarially tested JUnit collector.
- [x] Normalize a test summary into evidence without making a release decision.
- [x] Add golden fixtures and audit warnings/rejections.
- [x] Add Cobertura/coverage.py XML with repository/package/module scopes.
- [x] Add LCOV with strict record validation and module scopes.
- [x] Add SARIF 2.1.0 collector with explicit zero-result evidence.
- [x] Add strict generic Benchmark JSON schema and collector.

## Phase 2 — deterministic policy and CLI MVP

- [x] Implement deterministic policy evaluation at an explicit timestamp.
- [x] Enforce trust, verification, age, presence, conflict, and strict operator
  semantics without silent PASS.
- [x] Emit versioned per-rule machine results and CI exit codes 0/1/2/3.
- [x] Add release-candidate lifecycle and legal state transitions.
- [x] Add transactional SQLite persistence and concurrency controls.
- [x] Generate deterministic JSON and Markdown attestations.
- [x] Complete the local CLI MVP around persisted candidates.

## Phase 3 — software-peer compatibility

- [x] Audit the Studio public `result-export.v1` boundary at its upstream freeze
  commit without importing upstream runtime code.
- [x] Commit a consumer-side structural Schema mirror and exact drift gate.
- [x] Implement bounded run/metric/criterion normalization with retained
  limitations, source schemas, artifact identity, and record lineage checks.
- [x] Derive verification levels from upstream evidence sources and cap current
  `BENCH_*` exports at `system_observed`.
- [x] Add CLI, fixture, Golden, adversarial tests, documentation, and
  clean-install smoke.
- [x] Freeze an MSP430 validation-report contract and add an artifact-only,
  fail-closed collector without coupling ForgeGate to the upstream runtime.
- [ ] Revisit human-readable Studio report ingestion only after its Phase 5
  product report contract is implemented and frozen upstream.

## Phase 4 — audited evidence assembly

- [x] Add a strict, versioned collection-result loader with duplicate-key,
  non-finite-number, encoding, depth, node, and root-confinement gates.
- [x] Revalidate every referenced artifact against its current exact bytes.
- [x] Assemble multiple completed results for one candidate commit while
  retaining raw result identity, normalized fingerprints, artifacts, evidence
  IDs, and warnings.
- [x] Reject warnings by default and require explicit retention without
  suppressing them.
- [x] Let the existing policy CLI consume either a direct evidence bundle or a
  validated assembly.
- [x] Add canonical Schema, Golden, adversarial tests, architecture/security
  documentation, and clean-install smoke.
- [x] Bind an accepted assembly to the persisted candidate workflow; keep this
  separate from signature or producer-authentication work.

## Phase 5 — local REST API baseline

- [x] Introduce a shared candidate application service used by CLI and HTTP.
- [x] Add versioned health, idempotent candidate-create, and candidate,
  history, evidence-binding, and attestation read endpoints.
- [x] Add strict HTTP validation, structured errors, correlation IDs, and
  sanitized unexpected failures.
- [x] Restrict the server to loopback addresses and document the unauthenticated
  local-only boundary.
- [x] Commit and drift-check OpenAPI 3.1; verify API/CLI parity and clean-wheel
  export behavior.
- [x] Freeze the local command authority as equivalent to the local CLI: no
  internal identity, loopback bind plus Host checks, and no remote deployment.
- [x] Add idempotent expected-revision lifecycle writes and immutable assembly
  binding without accepting local artifact paths over HTTP.
- [x] Evaluate only the persisted binding, atomically record the terminal
  transition, and persist deterministic attestations without file publication.
- [x] Require evaluation policy names to match candidate release tracks.
- [ ] Add authenticated operator/producer identity before considering any
  non-loopback deployment.
- [x] Add projects and audit-event query APIs after their durable contracts are
  implemented.

## Phase 7 — project registry and audit queries

- [x] Add an immutable versioned project-registration document with canonical
  profile identity and exact idempotent replay.
- [x] Upgrade SQLite to v4 with append-only project and audit-event records.
- [x] Append successful state-change audit events inside the authoritative
  project/candidate write transaction without duplicating exact replays.
- [x] Explicitly migrate validated v1/v2/v3 stores and project only existing
  durable documents without fabricating project profiles or identities.
- [x] Add bounded stable-cursor audit queries and project/candidate filters.
- [x] Expose project register/read and audit queries through the shared CLI/API
  boundary; commit Schemas/OpenAPI and verify the installed wheel.

## Phase 8 — project authority and discovery

- [x] Require new product-surface candidate creation to reference a registered
  project and configured release track while preserving legacy database reads.
- [x] Add bounded project and project-scoped candidate listing contracts.
- [x] Define explicit project-profile revision/update semantics before allowing
  mutable configuration.

## Phase 9 — profile-bound candidates and append-only revisions

- [x] Add a candidate contract that binds the exact registered project profile
  identity and version used at creation.
- [x] Add an append-only project-profile revision document with previous-profile
  linkage and content-derived identity.
- [x] Persist revisions under expected-version compare-and-swap and exact
  idempotency without rewriting historical profiles.
- [x] Apply track additions/removals only to later candidates while preserving
  historical candidate/profile resolution.
- [x] Expose revision history and current-profile reads through bounded CLI/API
  contracts before considering any mutation convenience surface.

## Phase 10 — profile-authorized policy materialization

- [x] Resolve the selected release-track policy from an explicit project root
  and retain its exact bytes, media type, size, and SHA-256 identity.
- [x] Bind evaluation to policy material authorized by the candidate's frozen
  profile rather than accepting name equality as sufficient authority.
- [x] Preserve path-free REST operation by accepting or referencing a validated
  policy document, never dereferencing client-controlled server paths.
- [x] Define migration and legacy semantics without fabricating historical
  policy bytes or producer authenticity.

## Phase 11 — portable assurance bundle

- [x] Define a domain-neutral `forgegate.assurance-bundle.v1` that combines the
  frozen project profile, evidence binding, exact policy material, and release
  attestation with cross-document validation.
- [x] Publish a deterministic content-addressed directory with canonical JSON,
  human-readable limitations, and a SHA-256/size manifest.
- [x] Add path-independent offline verification with strict member, size,
  encoding, duplicate-key, canonical-byte, identity, and association checks.
- [x] Verify exact replay and fail closed on altered, missing, extra, unsafe, or
  renamed bundle content.
- [x] Exercise export and database-independent verification from an installed
  wheel while preserving the unsigned-local and source-artifact boundaries.

## Phase 12 — authenticated assurance identity foundation

- [x] Define key-derived Ed25519 public identities and an external trust-store
  contract with explicit role, project, active/revoked, and content identity.
- [x] Sign canonical portable-assurance bytes with a domain-separated statement
  that binds bundle ID/hash, signer, role, and caller-supplied time.
- [x] Verify the signature before requiring an exact active trust record whose
  role and project authority cover the bundled candidate.
- [x] Add strict bounded identity JSON loading, content-addressed signature
  publication, exact replay, conflict handling, and installed-wheel CLI smoke.
- [x] Preserve `unsigned_local` evidence semantics and explicitly defer trusted
  time, source-producer chains, online revocation, and managed key custody.
- [x] Design authenticated API sessions, authorization, transport security, and
  audit actor semantics before considering non-loopback deployment.

## Phase 13 — authenticated local API foundation

- [x] Require an external Phase 12 trust store when serving the local API.
- [x] Add domain-separated, one-time Ed25519 challenges and bounded short-lived
  in-memory Bearer sessions without sending a private key to the server.
- [x] Enforce exact project scopes with producer read-only and operator
  write/audit permissions across every protected route.
- [x] Add authenticated actor identity to successful API-origin audit events in
  the existing state-change transaction without persisting tokens.
- [x] Add challenge/session capacity limits, expiry/replay/tamper/revocation
  tests, strict challenge-file signing CLI, OpenAPI, and clean-wheel smoke.
- [x] Freeze TLS termination, reverse-proxy trust, hostile-local-user defense,
  and durable/distributed session policy as separate prerequisites before any
  non-loopback deployment.

## Phase 14 — local session lifecycle and abuse controls

- [x] Add authenticated self-logout that removes only the presented in-memory
  session and rejects later token reuse.
- [x] Add operator session revocation with exact target session IDs, complete
  project-scope coverage, producer denial, and non-enumerating not-found errors.
- [x] Reload the external trust store only from the server's fixed startup path;
  require the caller to remain a trusted operator covering every old/new
  project, clear pending challenges, and revoke incompatible sessions.
- [x] Add bounded fixed-window limits for valid challenge requests, session
  exchanges, and invalid Bearer authentication with explicit retry guidance.
- [x] Commit OpenAPI, adversarial lifecycle/reload/rate tests, architecture and
  security documentation, and clean-installed-wheel smoke.
- [ ] Design TLS, proxy identity, hostile-local-user defense, complete durable
  security audit, and durable/distributed sessions before considering any
  non-loopback deployment. Phase 15 addresses only the local malformed-request
  budget and bounded best-effort journal portions.

## Phase 15 — local API security boundaries

- [x] Enforce the 4 MiB limit against actual ASGI request bytes, including
  bodies without `Content-Length`, before application parsing.
- [x] Count challenge/session requests before strict body-model validation so
  malformed authentication JSON cannot bypass the existing fixed windows.
- [x] Define a minimal content-addressed API security-event contract separate
  from the release/project audit chain and free of tokens, signatures, request
  bodies, private keys, and arbitrary headers.
- [x] Add a bounded append-only SQLite v8 security-event journal with explicit
  v7 migration, visible saturation, and stable cursor pages.
- [x] Record authentication rejections/rate limits and successful logout,
  scoped revocation, and fixed-path trust reload on a best-effort basis; require
  global operator authority for REST queries.
- [x] Commit JSON Schemas/OpenAPI, migration/privacy/abuse tests, architecture
  and security documentation, and installed-wheel persistence smoke.
- [ ] Define retention/export operations, durable/distributed sessions and rate
  state, TLS/proxy identity, hostile-local-user controls, and
  administrator-resistant logging before any non-loopback deployment.

## Phase 16 — offline GitHub Actions assurance gate

- [x] Verify an existing portable assurance bundle before using any retained
  candidate or decision field in CI presentation.
- [x] Require exact complete candidate/CI commit equality and preserve decision
  exit codes 0/1/2/3.
- [x] Define a content-derived `forgegate.github-action-report.v1` with explicit
  `unsigned_local` and source-artifact-not-embedded boundaries.
- [x] Append bounded escaped Job Summary content and schema-constrained outputs
  through runner-provided or explicit regular files.
- [x] Add a token-free repository-local composite Action and a clearly labeled
  generic fixture job that exercises its real metadata and outputs.
- [x] Add model, adversarial, CLI, Schema, clean-wheel, and cross-platform CI
  verification plus architecture/security documentation.
- [ ] Design custom Checks/PR annotations, signed CI provenance, artifact
  upload, permissions, OIDC workload identity, and any GitHub API mutation as
  separate explicitly authorized work.

## Phase 17 — Plugin SDK discovery foundation

- [x] Define a content-derived plugin manifest with plugin/API versions,
  capabilities, input schemas, requested permissions, and output evidence kinds.
- [x] Discover only the `forgegate.plugins.v1` entry-point group without
  importing or executing plugin modules.
- [x] Report compatible, incompatible, invalid, and duplicate-ID conflict
  states through a deterministic versioned document and `plugins list` CLI.
- [x] Bound manifest path, bytes, encoding, JSON shape, node/depth, identity,
  entry-point, and installation-path disclosure risks.
- [x] Prove clean core operation before installation, import-free discovery of
  one standalone generic fixture, and clean operation after uninstall.
- [ ] Move a production-quality example to an independent plugin repository
  only after separate remote creation/push authorization.

## Phase 18 — External plugin execution security contract

- [x] Review exact licensed upstream revisions for attestation envelopes,
  attestor schemas, policy/enforcement separation, plugin contracts, and
  evidence-aware security checks without copying or vendoring source.
- [x] Define an out-of-process versioned callable protocol with immutable input
  subjects, content-derived run plans, broker-owned I/O, and validated output.
- [x] Define deny-by-default declared/approved/enforced permission subsets,
  explicit isolation tiers, mandatory resource limits, and fail-closed platform
  behavior.
- [x] Define stable failure-to-`ERROR` mapping and append-only durable run-audit
  semantics before loading external plugin code.
- [x] Preserve Phase 17 `execution=NOT_LOADED` behavior and explicitly reject
  same-process third-party plugin execution.
- [x] Implement strict run-plan, protocol-message, transition, and result
  models with JSON Schemas and content-derived identities.
- [x] Select a Windows-only rootless Podman/WSL2 backend, implement a strict
  capability report, and build a fail-closed digest-pinned container-create
  specification without executing plugin code.
- [x] Enable WSL2/Podman and adversarially verify the low-level backend controls
  on the actual Windows host without advertising `SANDBOXED` or executing an
  external plugin.
- [x] Keep Linux/macOS external-plugin backends explicitly unsupported unless
  the owner later expands the intended deployment platforms.

## Phase 19 — Windows sandbox live control verification

- [x] Install official Podman 5.8.6 and create a dedicated local rootless WSL2
  machine without device passthrough.
- [x] Require matching Podman client/server versions and fail closed on a
  mismatch.
- [x] Adapt the private tmpfs specification to Podman 5.8.6 without a
  world-writable output or restored Linux capabilities.
- [x] Add a development-only verifier with fixed filesystem, host-path,
  network, subprocess, environment, memory, CPU, wall-time, output, log, and
  cleanup attacks.
- [x] Copy tmpfs output before container shutdown, then re-count and rehash it;
  retain exact raw run evidence without host paths or secrets.
- [x] Pass all 14 required low-level controls while retaining external
  execution `PROHIBITED` and advertised isolation tier `NONE`.

## Phase 20 — brokered Windows external-plugin execution

- [x] Implement the trusted runner and broker over the frozen protocol without
  importing external code into the ForgeGate core process.
- [x] Stage broker-owned immutable inputs and re-register accepted output after
  exact member, byte, digest, schema, and race validation.
- [x] Persist append-only `plugin_runs`, terminal errors, cleanup results,
  idempotent replay, and crash recovery.
- [x] Add clean-wheel end-to-end hostile fixture tests through the production
  broker before advertising `SANDBOXED` for any installed-plugin run.

## Phase 21 — operator-facing plugin evidence workflow

- [x] Add a bounded Windows CLI that creates an exact run plan from one
  compatible installed collector plus explicit input subjects and grants.
- [x] Add path-free run/receipt query commands over the separate plugin-run
  store without exposing raw plugin output or host/container paths.
- [x] Convert broker-validated output into the existing audited collection
  boundary so it can enter evidence assembly without trust promotion.
- [x] Prove failed, replayed, and successful CLI runs through clean-wheel tests
  while retaining explicit Windows-only and no-hardware behavior.

## Phase 22 — private Windows Alpha delivery candidate

- [x] Add `forgegate init` with a strict generic four-collector project and
  policy template plus a no-overwrite publication contract.
- [x] Validate initialization from a clean wheel and retain a path-free,
  content-addressed initialization receipt.
- [x] Exercise the established core collection, assembly, decision,
  attestation, portable verification, and GitHub gate chain in a clean
  environment.
- [x] Exercise live Windows CLI plugin success, exact replay, persisted
  failure, path-free queries, low-trust collection, evidence assembly, and a
  sample-policy PASS through the pinned Podman/WSL2 fixture.
- [x] Verify sample-plugin independence and ForgeGate uninstall, then complete
  the security, privacy, claim, and delivery-document audit.

## Phase 23 — local Web Dashboard design gate

- [x] Freeze a same-origin, loopback-only Dashboard architecture over the
  existing authentication and application services.
- [x] Define the browser/CLI activation boundary without exposing a private key
  or raw API Bearer token to browser JavaScript.
- [x] Define interaction states, evidence/status presentation, error recovery,
  keyboard/zoom expectations, and explicit non-goals.
- [x] Record the Dashboard threat model and automated plus manual Windows
  acceptance matrix while preserving all current product limitations.

Phase 23 is design evidence only. It implements no page, static asset bundle,
browser session, Dashboard route, or browser test.

## Phase 24 — authenticated local Dashboard vertical slice

- [x] Add `forgegate dashboard` with loopback-only startup, explicit service
  lifecycle, safe port validation, and clean-wheel packaged static assets.
- [x] Implement one-time companion CLI activation and a same-origin
  cookie-authenticated BFF with exact Host/Origin and CSRF controls.
- [x] Implement Overview, Projects, and Candidates pages using the existing
  application/domain services and bounded cursor contracts.
- [x] Commit a deterministic Dashboard BFF OpenAPI contract with explicit
  operation IDs, local drift verification, and installed-wheel comparison.
- [x] Prove candidate creation review, exact idempotent replay, changed-payload
  conflict, and safe refresh/back/forward behavior.
- [ ] Complete adversarial-content, credential-exposure, role/scope, cache,
  API-drift, Edge/Chrome, keyboard, focus, zoom, and clean-wheel acceptance.

The automated boundary, Microsoft Edge keyboard and complete modal-focus path,
129-record six-page cursor traversal, browser-rendered 409/413/422/429/500
recovery, in-app-browser 390 px layout check, clean-wheel asset/install smoke,
an installed-wheel Edge read path, and Chrome core/focus/large-data/restart/
responsive runs pass. Uncommon statuses use an isolated zero-write
presentation harness and are not authentic operational-failure evidence.
Exact Microsoft Edge 100/125/150/175/200% zoom now passes. Narrator has a
bounded keyboard/semantic result without spoken-output capture. High contrast
and a real Remote Desktop run remain separate open environment checks; Phase
24 therefore remains open rather than overstating complete UI accessibility.

Evidence upload/collection, policy execution, assurance export, plugin
execution, session administration, and trust-store administration remain
outside this slice. Read-only Evidence/Decision/Assurance review is completed
separately in Phase 26.

## Phase 25 — optional MSP430 live-status monitor

- [x] Freeze the consumer implementation against the public MSP430 UART v1
  contract at upstream commit `151fdcfa60661bce1ba04af13c1d3509706f7d4a`
  without importing upstream code.
- [x] Add an optional `pyserial` extra while keeping the generic package,
  sample, tests, and Dashboard usable without it.
- [x] Validate bounded ASCII TEL framing, CRC-16/CCITT-FALSE, numeric ranges,
  state/fault fields, sequence gaps, and monotonic heartbeat staleness.
- [x] Open only the explicitly selected application UART in input-only mode;
  expose no serial write, firmware, debug, FRAM, GPIO, or load-control action.
- [x] Add an authenticated Devices page that refreshes every second and keeps
  connection, heartbeat freshness, and device-reported health independent.
- [x] Observe the connected COM4 board in the production Dashboard path:
  `CONNECTED`, heartbeat `NORMAL`, device `FAULT`, flags `0015`, with sequence
  58007→58017 and 10 accepted frames over 10 seconds without a sequence gap.
- [x] Prove disconnected, stale, invalid-frame, device-warning/fault, recovery,
  and read-only lifecycle behavior with deterministic automated tests.
- [x] Perform one owner-assisted physical unplug/replug transition while the
  Dashboard remains open. The owner observed the live transition; post-recovery
  counters retained one reconnect, one sequence gap, and one protocol error,
  then remained stable while sequence and valid-frame counts advanced.

Phase 25 is live status only. It creates no candidate evidence, authenticates no
producer, validates no sensor measurement, and controls no hardware. The later
Phase 27 report collector consumes a separate upstream artifact and does not
promote this live process state.

## Phase 26 — read-only Dashboard assurance review

- [x] Add one authenticated, project-scoped BFF read model joining candidate
  history, evidence binding, exact policy material, policy evaluation,
  attestation, and portable bundle identity.
- [x] Implement candidate-bound Evidence, Decision, and Assurance pages without
  introducing evidence upload, policy execution, lifecycle mutation, or export
  from the browser.
- [x] Show trust/verification labels, artifact references, expected/actual rule
  values, evidence IDs, reason codes, lifecycle transitions, and explicit
  assurance limitations.
- [x] Preserve candidate context across review tabs and refresh using a
  non-secret hash query, with explicit no-selection and incomplete-stage states.
- [x] Bound Evidence and Decision rendering to 25 rows per page with visible,
  keyboard-operable range and navigation controls.
- [x] Decode MSP430 UART v1 fault bits in the compatibility adapter, retain
  unknown bits without invented meaning, and label all decoded values as device
  reports rather than ForgeGate diagnoses.
- [x] Validate the slice with strict TypeScript, deterministic assets, BFF and
  adapter tests, a generic PASS browser fixture, a live input-only COM4 follow-up,
  and retained screenshot hashes.

Phase 26 is a review surface only. It validates and presents retained ForgeGate
documents; it does not re-run collectors, authenticate artifact producers,
embed source artifact bytes, approve deployment, or validate hardware.

## Phase 27 — reviewed Dashboard workflow and MSP430 evidence contract

- [x] Add same-origin operator-only BFF commands for expected-revision lifecycle
  transitions, immutable evidence binding, exact policy evaluation, and
  terminal attestation generation.
- [x] Require one explicit reviewed confirmation per command, enforce CSRF,
  role/project scope, idempotency, stale-state handling, and authoritative
  list/detail reload.
- [x] Add bounded local JSON selection for an exact evidence assembly and exact
  frozen policy material without retaining or interpreting a client path.
- [x] Exercise the full Edge DRAFT→COLLECTING→READY→EVALUATING→PASS→attestation
  flow plus a mismatched-commit rejection and retain portfolio-safe captures.
- [x] Freeze `forgegate.msp430-validation-report.v1` and implement a fail-closed,
  artifact-only collector with host/target/HIL/bench verification mapping.
- [x] Retain one privacy-safe Phase 6 LaunchPad HIL migration fixture with exact
  source hashes, correction history, and limitations; do not claim a new run.
- [x] Execute exact Edge 100/125/150/175/200% zoom and bounded Narrator
  keyboard/semantic checks.
- [x] Pass 878 full-suite tests, 95.23% branch-aware coverage, the committed
  contract gates, and clean-wheel release smoke including the new collector.
- [ ] Execute Windows high contrast and a real Remote Desktop session; spoken
  Narrator output timing also remains uncaptured.

Phase 27 adds engineering workflow capability but does not add automatic
collection, server filesystem browsing, assurance export, remote publication,
producer authentication, MSP430 control, or physical measurement validation.

## Phase 28 — candidate-bound Dashboard assurance export

- [x] Freeze an operator-only, project-scoped, same-origin and CSRF-protected
  export request bound to the current candidate revision and bundle identity.
- [x] Render the existing portable assurance contract as a deterministic,
  bounded, uncompressed ZIP with exactly three root regular-file members.
- [x] Accept no server path, client path, filename, URL, archive option, or
  remote destination; create no server-side export file or release-state event.
- [x] Add reviewed confirmation, response identity/media/size checks, browser
  download, visible recovery, modal containment, and focus return.
- [x] Reject producer, missing-origin, missing-CSRF, stale-revision,
  wrong-bundle, and unknown-field requests while preserving authoritative state.
- [x] Download the ZIP through real Microsoft Edge, extract it, and pass the
  existing database-independent offline verifier with retained hashes and
  portfolio-safe screenshots.
- [x] Pass 882 full-suite tests at 95.21% branch-aware coverage, 48 focused
  Dashboard tests at 98.41%, all contract gates, and clean-wheel release smoke.

Phase 28 delivers local artifact download only. It does not add automatic
collection, source-artifact payload export, producer authentication, trusted
time, remote publication, deployment approval, or hardware validation.

### Phase 28 follow-up — activation reliability

- [x] Preserve the exact current loopback origin/port in the CLI command.
- [x] Provide manual recovery for creation/poll failures and code expiry;
  respect Retry-After without sending another request automatically.
- [x] Ignore delayed creation/poll responses after the activation screen changes.
- [x] Run 13 production-TypeScript host regressions and real local-browser
  activation on port 8131, with screenshot evidence kept separately.
- [ ] Restore a complete post-merge GitHub CI run after the owner resolves the
  reported billing/spending restriction; never bypass required checks.

## Phase 29 — project Audit workspace

- [x] Add a dedicated operator-only, project-scoped workspace over the existing
  audit service, without introducing a new data store or write operation.
- [x] Retain project/candidate/cursor in local deep links; present 25-event
  pages, first/next navigation and manual refresh without fabricated totals.
- [x] Display exact subject/event identities and recorded actor metadata;
  never infer an actor for historical CLI or migration records.
- [x] Link candidate audit previews to full history and disclose truncation.
- [x] Reject malformed filter parameters with 422 before model construction;
  preserve project/role/Origin/session authorization and no-store responses.
- [x] Verify 12 frontend and 5 BFF cases, 887 full Python tests, real-browser
  28-event traversal/filter/recovery, and retain portfolio-safe screenshots.

This is release-operation history, not a complete security-event workspace,
tamper-proof logging, telemetry history, or physical measurement evidence.
Automatic collection, plugin/admin workflows and remaining assistive checks
remain later gates.

## Phase 30 — bounded raw JUnit Dashboard collection

- [x] Freeze the file, authorization, declared source/time, warning consent,
  in-memory processing, cancellation and recovery boundaries before execution.
- [x] Reuse the JUnit collector and assembler through an exact-byte source
  interface; add no new report parser, policy engine, database or dependency.
- [x] Add one candidate-scoped preview endpoint with a 1 MiB decoded cap,
  explicit revision/commit, original report time, and fixed low-trust labels.
- [x] Add a browser form, counts/issues preview, explicit warning retention and
  separate reviewed binding; reject stale responses after leaving the preview.
- [x] Add generic positive/negative examples and test the API chain through
  binding, policy PASS/FAIL/REVIEW, attestation and archive generation.
- [x] Check the actual Edge form, missing-file validation, Escape and focus
  restoration; retain an unedited screenshot with no uploaded-result claim.
- [x] Complete real Edge file selection, warning review, binding and policy
  PASS/FAIL workflows with synthetic inputs and retained actual screenshots.
- [x] Correct shared policy-content reuse across candidates; preserve immutable
  candidate bindings through an explicit, rollback-tested v8-to-v9 migration.

Do not call this a durable task center, multi-report upload, raw-artifact store,
source authentication, test execution or hardware validation. Do not start the
next collector until this slice's real-browser acceptance is complete.

## Phase 31 — Windows startup and diagnostic recovery

- [x] Add loopback-only, unauthenticated CLI diagnostics with bounded response
  bodies, explicit HTTP/HTML outcomes, exit codes and non-ownership labels.
- [x] Provide an existing-workspace PowerShell launcher with literal paths,
  missing/empty-file and advisory port checks; retain foreground shutdown and
  process exit behavior without automatic migration or credential changes.
- [x] Exercise actual local Dashboard/API-only/stopped cases and the installed
  command in clean-wheel smoke; preserve a path-free JSON receipt.
- [x] Test native Windows PowerShell error/argument behavior, spaced paths,
  startup, Ctrl+C shutdown and restarting the same isolated database.
- [x] Document recovery, consistent-backup boundaries, fresh session activation,
  private logs and the distinction between reachability and successful use.

This is not background supervision, reboot persistence, service installation,
automatic crash recovery, database repair, browser acceptance or device testing.
Those operating modes require a separate lifecycle/ownership design. Durable
collection jobs and artifact retention remain later engineering slices, not
implied by the current synchronous preview or runtime diagnostic.

## Phase 32 — candidate-store data protection

- [x] Snapshot a current-schema store using SQLite's backup API and a pinned
  read transaction, including committed WAL content without uncommitted data.
- [x] Reject existing targets and sidecars; validate before exclusive hard-link
  publication, without overwrite fallback, initialization or migration.
- [x] Verify an offline copy's hash, SQLite integrity, foreign keys, schema and
  17 table counts without opening or changing the input through SQLite.
- [x] Test exact retained-row equality and cold candidate/evidence/attestation
  readback on a terminal synthetic candidate, plus races, corruption and limits.
- [x] Add installed-wheel backup/verify/no-overwrite checks and local operations
  documentation; retain only synthetic results, never a database in the gallery.

No automatic restore, encryption, retention service, browser backup button,
producer authentication or blanket domain-history validation is implied.
GitHub synchronization is paused by owner instruction; development remains local.

## Phase 33 — combined browser test and coverage collection

- [x] Accept bounded JUnit + Cobertura/LCOV with separate source metadata and
  original collection times; reject duplicates, excessive output and unsafe counts.
- [x] Require all reports to succeed and explicit warning retention before one
  immutable combined binding; no silent partial success or trust promotion.
- [x] Add frontend count/hash/identity/recovery/cancellation tests and API chains
  through shared-policy PASS/FAIL, attestation and portable archive creation.
- [x] Correct browser JSON number reserialization without changing historical
  fingerprints or weakening validation; retain original assembly JSON on writes.
- [x] Verify actual Edge Cobertura selection, preview, independent binding,
  READY/EVALUATING transitions, policy PASS and exact rule values; save screenshots.
- [x] Keep CLI-only larger collections, generic examples and source evidence labels.

Phase 34 adds the local job engine separately; Phase 33 is not a durable
task center. The scoped real-browser LCOV/negative matrix now passes in
the Phase 33 follow-up (13 cases). Browser error provenance and Windows
mixed-case asset ordering were corrected. Remaining OS assistive checks stay
separate gates; host regressions do not replace actual OS acceptance.

## Phase 34 — durable local report jobs

- [x] Versioned request/record/result contracts and a separate explicit v1 store;
  no candidate-store migration, automatic binding or producer authentication.
- [x] Idempotent submission, exclusive claim, revision checks and bounded
  pending report bytes; exact-result retention with assembly consistency checks.
- [x] Explicit cancellation that prevents late publication; expired-only manual
  recovery to INTERRUPTED; queued work survives process restart, no silent retry.
- [x] CLI create/submit/show/list/run/cancel/recover/result commands, strict
  bounded JSON loading and path-free operational errors.
- [x] Host race/fault/recovery tests, independent-process expected-value checks
  and clean installed-wheel execution. No real-device or new browser claims.
- [x] Document quotas, local-file authority, logical deletion, source replay
  limitations and the absence of coordinated job backup/retention management.

## Phase 35 — authenticated Dashboard job management

- [x] Opt-in existing-store configuration, operator/project authorization and
  scoped list/detail/result views; no automatic initialization or migration.
- [x] Same-origin/CSRF and reviewed-revision cancellation and expired recovery;
  atomically retain the authenticated actor without inferring historical actors.
- [x] Explicit transactional v1-to-v2 job-store upgrade and rollback tests.
- [x] Pagination/filter/error/late-response frontend regressions and isolated
  real Edge expected-value, confirmation, recovery and 409 conflict checks.
- [x] Package assets, schemas, operation guidance and synthetic screenshot evidence.

## Phase 36 — reviewed browser submission and foreground parsing

- [x] Freeze exact selected bytes, declared metadata, candidate revision and
  warning consent before separately confirmed durable submission.
- [x] Scope idempotency by identity/project; preserve CLI creation authority and
  atomically attribute new browser submit/claim/completion events.
- [x] Separately confirm foreground parsing with revision checks, nonblocking
  per-app busy rejection, cancellation-safe publication and no automatic retry.
- [x] Verify host authorization/concurrency/error cases and real Edge single,
  combined, warning-consent and forbidden-XML workflows; retain screenshots.
- [x] Keep parsing completion separate from test success, policy PASS and binding.

## Phase 37 — reviewed job-result evidence handoff

- [x] Add operator-only canonical assembly export with frozen job revision,
  result fingerprint and assembly identity checks; return exact no-store bytes.
- [x] Verify response media, identities, size and SHA-256 in the browser before
  offering the local download; original report bytes remain excluded.
- [x] Re-read the authoritative candidate and require exact project, commit,
  revision, fingerprint, `COLLECTING` state and absent binding before confirmation.
- [x] Reuse the immutable candidate-evidence binding service with namespaced
  idempotency and actor attribution; leave job, candidate revision and policy unchanged.
- [x] Cover authorization, stale/conflict/non-bindable/unknown-outcome behavior
  in host tests and complete an isolated actual-Edge download/binding/readback run.
- [x] Retain screenshot and machine-readable acceptance evidence with explicit
  synthetic/no-hardware/no-production boundaries.

## Phase 38 — durable foreground execution lifecycle

- [x] Freeze `forgegate.collection-job.v2` with a visible, random execution owner
  that is explicitly not a credential, host identity or authentication proof.
- [x] Upgrade the separate store to v3 only through an explicit, transactional
  v1/v2 migration that preserves historical record bytes and infers no actor/owner.
- [x] Renew the private five-minute lease before each report and before assembly,
  retaining bounded append-only renewal events and current revision.
- [x] Make durable cancellation cooperatively stop later stages at those same
  checkpoints while retaining late-publication rejection and no mid-parser claim.
- [x] Give one Dashboard process a stable lifetime owner ID; after restart, a new
  owner cannot adopt, renew or finish the old lease, which remains manual recovery.
- [x] Display owner/renewal fields in job detail and expand reviewed command
  revisions without exposing the private token or adding automatic retry.
- [x] Verify new/legacy records, renewal/token guards, cancellation ordering,
  migration rollback, CLI cross-process smoke, frontend behavior and schemas.

Phase 38 is still explicit foreground parsing. It adds no scheduler, daemon,
automatic worker, arbitrary parser termination, candidate transition, policy
decision, GitHub operation or hardware access.

## Phase 39 — coordinated workspace recovery

- [x] Reserve both database writers and snapshot candidate v9/job v3 as one
  validated archive; reject running jobs and preserve queued input/history.
- [x] Freeze a bounded manifest with member hashes and explicit data boundaries;
  verify offline copies and exact historical job/candidate associations.
- [x] Restore to a new directory with required expected hash, exact copied bytes
  and a final readiness marker; preserve existing workspaces and launch settings.
- [x] Generate cutoff-based retention plans that protect active, bound and recent
  jobs, retain audit/replay records and perform no deletion or quota reclamation.
- [x] Test locking, committed WAL, corruption, incomplete recovery, cold domain
  reads and independent CLI execution from a restored synthetic workspace.

## Phase 40 — reviewed job archival and logical capacity

- [x] Explicitly migrate job v3 to v4 without changing historical records/events.
- [x] Generate a bounded one-job plan tied to a verified backup, exact job/event
  bytes, revision, result identity, cutoff and current candidate fingerprint.
- [x] Recheck live candidate/binding state while reserving both writers; atomically
  archive result bytes and insert an immutable receipt with exact replay behavior.
- [x] Preserve task identity, audit and request-key protection; release one logical
  slot and result quota within bounded 100-live/1,000-archived storage limits.
- [x] Read original results through an explicit backup/hash, and support v4
  backups/restores with clear external dependency disclosure; keep v1 frozen.
- [x] Display archive metadata/history in Dashboard detail, reject stale result
  actions, and retain actual isolated Edge acceptance with synthetic screenshots.
- [x] Test corruption/staleness, binding protection, lock contention, transaction
  rollback, quota reuse, replay, exact readback and clean-wheel CLI recovery.

## Phase 41 — capacity, dependency and archive visibility

- [x] Add an owner-only, store-wide logical capacity document and CLI command.
- [x] Distinguish v3 archive capability from the quota available after v4 migration.
- [x] Report external backup hashes with availability explicitly not checked and
  physical database size explicitly not reported.
- [x] Add project-scoped Dashboard usage without leaking store-wide remaining
  capacity or other-project counts.
- [x] Filter All / Current / Archived tasks while scanning the complete bounded
  identity set, including archive records beyond the first 100 IDs.
- [x] Preserve filters through browser pagination/detail navigation and label
  current versus archived records.
- [x] Generate strict schemas/OpenAPI/assets and cover privacy, quotas, malformed
  filters, model coherence, CLI and frontend behavior.

## Phase 42 — offline dependency verification and recovery readiness

- [x] Require an exact root backup hash and explicit original backup mappings.
- [x] Verify ZIP structure, manifest identity and original task/event/result bytes.
- [x] Distinguish verified, absent mappings and failed dependencies in a strict,
  path-free report; reject duplicate/unused mappings and enforce a shared deadline.
- [x] Verify shared and multi-generation dependencies, no-result tasks, corruption
  and mismatch refusal, source preservation and independent CLI/restore chains.
- [x] Retain local acceptance artifacts and installed-wheel execution evidence.

Next engineering slice: operator recovery rehearsal and artifact handoff UX,
using the explicit snapshot identities without presenting old offline reports
as live availability. Native assistive technology remains a separate acceptance
gate. GitHub synchronization is paused.

## Phase 43 — reviewed recovery handoff

- [x] Add new-only CLI report output for both READY and INCOMPLETE results.
- [x] Add an operator-only same-origin Dashboard import with browser and server
  byte/hash/schema bounds; no server path or backup-payload input.
- [x] Derive a strict content-addressed handoff with dependency totals and
  explicit `NOT_CHECKED`, `NOT_INCLUDED` and `NOT_PERFORMED` boundaries.
- [x] Cover READY/BLOCKED, authorization, malformed input, response consistency,
  409/413/429/500 presentation and stale responses in Python/TypeScript tests.
- [x] Regenerate the document Schema, Dashboard OpenAPI and packaged assets.
- [x] Complete native Edge READY/BLOCKED file selection, sequential reselection,
  download hashing and strict downloaded-document validation. Interactive
  screenshots were captured but cannot be repository-retained through the
  browser's blocked `file://` transfer path.

Next engineering slice after manual acceptance: execute a new-directory-only
recovery rehearsal from the same explicitly rechecked identity set and retain
post-restore verification evidence. GitHub synchronization remains paused.
