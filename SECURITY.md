# Security policy

ForgeGate is pre-release software. Do not use it as a security or compliance
control for a production release.

Configuration and evidence loaders use strict schemas, bounded parsing, and
safe YAML handling. Identity and signature inputs use bounded strict JSON with
duplicate-key and non-finite-number rejection. The product does not load
external plugins or evaluate executable policy expressions. The REST API is
unauthenticated and must remain on a loopback address; it is not approved for
LAN, shared-host, or internet use.

SQLite v7 requires product-surface candidate creation to resolve an immutable
project profile and one configured release track; this is configuration
authority, not operator authentication. Audit events record successful local
project and candidate state changes. They do not automatically retain rejected
requests, collector warnings, OS logs, or authenticated actor identity, and an
administrator able to replace the database is outside the append-only trigger
boundary.

Artifact hashes, commit metadata, and unsigned local attestations establish
integrity or claimed association only. A Phase 12 Ed25519 sidecar authenticates
the signer of exact canonical assurance-bundle bytes only when the verifier
supplies a matching external trust store. It does not prove that a test ran,
authenticate the source artifacts, establish trusted time, or make the local
REST API safe for remote use. ForgeGate does not manage or generate long-term
private keys; private-key and trust-store custody remain operator duties. See
`docs/security/THREAT_MODEL.md`.
