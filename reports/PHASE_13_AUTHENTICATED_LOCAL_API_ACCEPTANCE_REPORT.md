# Phase 13 authenticated local API acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev20
- Scope: Ed25519-authenticated, role/project-authorized loopback API sessions
  with successful-write audit actors
- Evidence level: local host test
- Hardware/device evidence: none; no device access performed

## Accepted capability

`forgegate serve` now requires an external `forgegate.trust-store.v1`. An active
trusted identity can request a one-time challenge for an allowed role and exact
canonical project set, sign the domain-separated challenge with its existing
Ed25519 private key, and exchange that proof for a bounded short-lived Bearer
session. The server never receives or retains the private key and stores only a
SHA-256 token digest in process memory.

Every protected project, candidate, and audit route requires the session.
Producer sessions are read-only. Operator sessions may perform existing writes
and query audit history, but only for their exact session projects. Project
listing is authority-filtered and REST audit queries require an explicit
authorized project.

Successful API writes attach `forgegate.audit-actor.v1` to the existing
transactional state-change audit event. Identity, display name, role, session
ID, trust-store ID, and server authentication time become part of the event
identity. Tokens and private keys are not persisted. CLI and migrated events do
not gain fabricated actors.

## Fail-closed evidence

Tests cover absent and malformed Bearer credentials, invalid signatures,
single-use challenge replay, challenge/session expiry, revoked identities,
unauthorized roles and projects, producer write denial, cross-project reads,
filtered discovery, mandatory project-scoped audit queries, bounded
challenge/session capacity, unsafe TTL/capacity configuration, naive server
clocks, strict challenge file parsing, wrong private keys, authenticated actor
readback, and absence of raw session tokens from SQLite.

The OpenAPI contract declares HTTP Bearer security on protected routes and
includes the two public authentication operations. Installed-wheel smoke checks
contract drift, the mandatory trust-store serve option, CLI challenge signing,
and an in-memory challenge-to-session-to-principal exchange with an ephemeral
temporary key.

## Local acceptance

- `pip check`: PASS
- Ruff and Ruff format: PASS
- strict mypy: PASS across 56 source/tool files
- pytest: 637 passed, 1 skipped because Windows symlink creation was unavailable
- branch-aware coverage: 97.90% across 6,076 statements and 1,602 branches
- Phase 13 authentication focus: 13 passed; authentication module 97.95%
- 26 canonical document Schemas plus two artifact Schemas: generated and parsed
- OpenAPI 3.1 authentication/security contract: drift-checked
- source distribution, wheel, clean-install challenge/sign/session and existing
  end-to-end release-assurance smoke: PASS
- latest completed remote baseline before this implementation push: Phase 12
  GitHub Actions run 33455212296 PASS on Windows, Ubuntu, and macOS

## Explicit limitations

The API remains loopback-only and sends Bearer credentials without TLS. It is
not safe for proxy, tunnel, container-port, LAN, shared-host, internet, or
production exposure. It does not defend against a hostile/privileged local
process, packet observer, debugger, memory reader, compromised OS account, or
database administrator.

The trust store is a startup snapshot. Sessions are memory-only, disappear on
restart, and currently have no logout, durable revocation, live trust reload,
distributed state, rate-based throttling, or trusted timestamp. Actor
`authenticated_at` is server time, while audit operation time remains existing
caller-supplied domain time; neither is trusted time.

No long-term key was generated or retained by ForgeGate. Clean-install tests use
only ephemeral temporary keys. No AFE/MSP430 runtime was imported, no serial
port was opened, and no hardware, bench, field, or production evidence claim was
made.
