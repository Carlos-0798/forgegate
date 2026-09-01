# Security policy

ForgeGate is pre-release software. Do not use it as a security or compliance
control for a production release.

Configuration and evidence loaders use strict schemas, bounded parsing, and
safe YAML handling. Identity and signature inputs use bounded strict JSON with
duplicate-key and non-finite-number rejection. The product does not load
external plugins or evaluate executable policy expressions. The REST API uses
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
operator duties. See `docs/security/THREAT_MODEL.md`.
