# Security policy

ForgeGate is pre-release software. Do not use it as a security or compliance
control for a production release.

Phase 0 accepts local YAML/JSON configuration only. The loader uses safe YAML
parsing, rejects unknown fields, limits each configuration file to 1 MiB, and
does not load plugins or evaluate executable expressions.

Artifact hashes, commit metadata, and unsigned local attestations establish
integrity or claimed association only. They do not prove that a test actually
ran or that metadata is authentic. See `docs/security/THREAT_MODEL.md`.
