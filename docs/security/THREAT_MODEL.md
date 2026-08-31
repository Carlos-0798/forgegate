# Phase 0 threat model

## Assets

- versioned project and policy definitions;
- evidence/artifact integrity metadata;
- future release decisions and attestations;
- developer workstation paths and CI metadata.

## Trust boundaries

Configuration and evidence files are untrusted input. Local users, CI metadata,
future plugins, and remote artifact locations are separate trust domains.
Phase 0 has no authenticated producer and runs no plugin code.

## Addressed in Phase 0

| Threat | Current control |
|---|---|
| Unknown or ambiguous schema | Exact version dispatch and extra-field rejection |
| Unsafe YAML tags | `yaml.safe_load` |
| Oversized configuration | 1 MiB pre-parse limit |
| Parent or absolute output paths | Relative-path validation |
| Missing scan represented as zero findings | Mandatory `require_presence` invariant |
| Evidence reused for another commit | Per-record candidate commit equality |
| Artifact replacement | Strict SHA-256 field; byte verification is future work |
| Naive timestamps | UTC-offset requirement |

## Deferred risks

- XML entity expansion, archives, and pathological parser inputs when collectors
  are implemented;
- symlink escape and time-of-check/time-of-use behavior for artifact paths;
- malicious plugins and subprocess isolation;
- CI identity verification, secret redaction, signing, revocation, and key
  management;
- database authorization, API authentication, audit retention, and concurrency.
