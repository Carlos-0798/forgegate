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
- [ ] Add an MSP430 compatibility collector only after new hardware progress is
  aligned in this project context and its public report contract is frozen.
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
