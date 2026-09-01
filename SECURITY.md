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

SQLite v7 requires product-surface candidate creation to resolve an immutable
project profile and one configured release track. Successful authenticated API
writes add a public identity, role, session ID, trust-store ID, and server
authentication time to the same durable audit event transaction. Legacy and
CLI events retain no fabricated actor. Audit events do not retain Bearer tokens,
private keys, rejected requests, collector warnings, or OS logs, and an
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
sessions whose authority no longer matches. These controls are memory-only,
are not a durable security-event audit, do not rate-limit malformed bodies that
fail before endpoint execution, and do not establish online managed revocation,
reverse-proxy trust, hostile-local-user defense, or persistent/distributed
session authority. ForgeGate does not manage or generate long-term private
keys; private-key and trust-store custody remain operator duties. See
`docs/security/THREAT_MODEL.md`.
