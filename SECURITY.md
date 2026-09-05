# Security policy

ForgeGate is pre-release software. Do not use it as a security or compliance
control for a production release.

Configuration and evidence loaders use strict schemas, bounded parsing, and
safe YAML handling. Identity, signature, and plugin-manifest inputs use bounded
strict JSON with duplicate-key and non-finite-number rejection. Plugin
discovery reads installed metadata without importing or executing plugin code.
The separate Windows broker may execute an exactly planned pure-Python
collector only inside the verified rootless Podman/WSL2 boundary; external
code is never imported into the core process. The product does not evaluate
executable policy expressions. The REST API uses
one-time Ed25519 challenges, short-lived in-memory Bearer sessions, and exact
role/project authorization, but must remain on a loopback address. It has no
TLS or hostile-local-user defense and is not approved for LAN, shared-host, or
internet use.

SQLite v8 requires product-surface candidate creation to resolve an immutable
project profile and one configured release track. Successful authenticated API
writes add a public identity, role, session ID, trust-store ID, and server
authentication time to the same durable audit event transaction. Legacy and
CLI events retain no fabricated actor. Audit events do not retain Bearer tokens,
private keys, rejected requests, collector warnings, or OS logs. A separate,
bounded API security-event journal records minimal metadata for rejected
authentication, authentication rate limits, logout, session revocation, and
trust-store reload. It deliberately excludes tokens, signatures, request
bodies, private keys, and arbitrary headers. Logging is best-effort so a full
journal does not prevent the security control itself from completing, and an
administrator able to replace the database is outside the append-only trigger
boundary.

Artifact hashes, commit metadata, and unsigned local attestations establish
integrity or claimed association only. A Phase 12 Ed25519 sidecar authenticates
the signer of exact canonical assurance-bundle bytes only when the verifier
supplies a matching external trust store. It does not prove that a test ran,
authenticate the source artifacts, establish trusted time, or make the local
REST API safe for remote use. API sessions disappear on restart. Phase 14 adds
self-logout, project-scoped operator revocation, bounded in-process
authentication rate limits, and an explicit reload of the same fixed startup
trust-store path. A reload succeeds only for an operator session covering every
project in the old and new stores; it clears pending challenges and removes
sessions whose authority no longer matches. Phase 15 counts challenge/session
requests before body-model validation, enforces the 4 MiB ceiling against bytes
actually received, and adds the separate v8 security-event journal plus a
global-operator query. The session and rate-window controls remain memory-only;
the journal is not a complete compliance log and has no retention/export policy,
administrator-resistant storage, trusted time, or guarantee that a saturated
or unavailable store records every control event. These controls do not
establish online managed revocation, reverse-proxy trust, hostile-local-user
defense, or persistent/distributed session authority. ForgeGate does not manage
or generate long-term private keys; private-key and trust-store custody remain
operator duties.

Phase 16 adds an offline GitHub Actions bridge over an already-verified portable
bundle. It requires exact full commit equality, escapes and bounds Job Summary
content, and writes only schema-constrained values to runner output files. It
requests no GitHub token and calls no GitHub API. A successful bridge retains
the bundle's `unsigned_local` and source-artifact-not-embedded limitations; it
does not authenticate the workflow, repository, evidence producers, or time,
and it does not turn CI execution into target, HIL, bench, physical, field, or
production verification. Runner summary/output files are not durable audit or
administrator-resistant storage. See `docs/security/THREAT_MODEL.md`.

Phase 17 adds manifest-only Python entry-point discovery. A compatible result
means only that a content-derived manifest targets Plugin API v1; it does not
authenticate a publisher or approve code execution. Missing, malformed,
incompatible, and conflicting metadata is reported but never loaded. Discovery
still grants no permissions and never loads a callable.

The Windows sandbox slices add a fail-closed Podman/WSL2 capability probe,
container-create specification, and development-only hostile-fixture verifier.
All 14 low-level controls passed fixed ForgeGate-owned fixtures on a matching
rootless Podman 5.8.6 client/server pair. The Phase 20 production broker now
requires that exact evidence plus a matching current runtime and image before
starting an installed plugin. It stages only exact content-addressed inputs and
pure-Python distribution files, enforces canonical protocol messages, validates
tmpfs output twice, atomically re-registers accepted low-trust evidence, cleans
the container/staging area, and retains an append-only terminal receipt with
idempotent replay and fail-closed interruption recovery.

The Phase 20 live test passed all 13 broker-level controls using only the
ForgeGate-owned generic fixture. `SANDBOXED` applies to that exact authorized
run; the readiness probe itself remains `PROHIBITED`/`NONE`. Accepted plugin
evidence remains `unsigned_local` and `declared` and cannot directly change a
candidate or release decision. Publisher authentication, native/dependency-rich
plugins, generalized third-party compatibility, and Linux/macOS execution are
not established. There is no subprocess-only fallback. WSL's automatic
machine-level Windows-drive mounts remain a documented defense-in-depth
limitation even though the disposable container test could not read `/mnt/c`.

Phase 25 adds an optional MSP430 live-status monitor behind the authenticated
Dashboard. The operator must select one application UART at process startup.
The adapter is input-only, sets DTR/RTS inactive before opening, performs
bounded reads, validates the frozen public UART v1 TEL framing and CRC, and
returns sanitized connection/heartbeat/device-state snapshots. It exposes no
serial write command and does not access the debug interface, firmware, FRAM,
GPIO, or external loads. Live status is explicitly not candidate evidence,
measurement validation, producer authentication, hardware control, or a release
decision. The optional `pyserial` dependency is loaded only when this monitor is
enabled; the generic core and default Dashboard remain device-independent.

Phase 27 adds reviewed Dashboard writes without extending the loopback trust
boundary. Candidate transitions, evidence binding, policy evaluation, and
attestation generation require an authenticated operator session, exact
project scope, exact Origin, anti-CSRF token, and the existing application and
domain validation. State-changing requests carry an explicit expected revision
or deterministic replay identity; the browser never retries an ambiguous write
automatically. Evidence assemblies and policy materials are selected locally
as bounded JSON, then sent as complete documents. The server receives no client
file path and does not browse or dereference the client filesystem. Browser
hashing and review are usability controls only; server-side contract and
content-identity validation remain authoritative.

The separate MSP430 validation-report collector accepts only bounded strict
`forgegate.msp430-validation-report.v1` artifacts. It opens no serial port,
imports no upstream runtime, sends no command, and does not convert live-status
state into evidence. Exact commit association, evidence level, hardware scope,
source digests, corrections, limitations, and outcome consistency are checked
before normalization. LaunchPad HIL is capped at `system_observed`; only a
structurally complete external-bench report with physical context and full
instrument calibration provenance can map to `physically_verified`. SHA-256
integrity does not authenticate the producer or prove that a reported run
occurred.
