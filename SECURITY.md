# Security policy

ForgeGate is pre-release software. Do not use it as a security or compliance
control for a production release.

Configuration and evidence loaders use strict schemas, bounded parsing, and
safe YAML handling. Identity, signature, and plugin-manifest inputs use bounded
strict JSON with duplicate-key and non-finite-number rejection. Plugin
discovery reads installed metadata without importing or executing plugin code;
requested permissions are not granted. The product does not load external
plugin callables or evaluate executable policy expressions. The REST API uses
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
incompatible, and conflicting metadata is reported but never loaded. External
plugin execution, sandboxing, permission enforcement, secrets, subprocesses,
network access, and durable plugin-run audit remain unimplemented.
