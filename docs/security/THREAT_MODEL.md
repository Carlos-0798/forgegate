# ForgeGate threat model

## Assets

- versioned project and policy definitions;
- evidence/artifact integrity metadata;
- future release decisions and attestations;
- developer workstation paths and CI metadata.

## Trust boundaries

Configuration and evidence files are untrusted input. Local users, CI metadata,
future plugins, and remote artifact locations are separate trust domains.
The current slice has no authenticated producer and runs no plugin code.

## Addressed in Phase 0

| Threat | Current control |
|---|---|
| Unknown or ambiguous schema | Exact version dispatch and extra-field rejection |
| Unsafe YAML tags | `yaml.safe_load` |
| Oversized configuration | 1 MiB pre-parse limit |
| Parent or absolute output paths | Relative-path validation |
| Missing scan represented as zero findings | Mandatory `require_presence` invariant |
| Evidence reused for another commit | Per-record candidate commit equality |
| Artifact replacement | Strict SHA-256 field plus Phase 1 exact-byte registration |
| Naive timestamps | UTC-offset requirement |

## Addressed in the Phase 1 JUnit slice

| Threat | Current control |
|---|---|
| Absolute or parent-traversal artifact path | Explicit registry-root confinement |
| Symlink resolution outside root | Resolved-path containment check |
| Special file or oversized input | Regular-file check and 8 MiB default limit |
| Artifact mutation during collection | File metadata/size stability check and exact-byte hash |
| XML entity/DOCTYPE processing | Pre-parse rejection of declarations |
| Pathological XML shape | Element-count and tree-depth limits |
| Ambiguous JUnit outcomes/counts | Fail-closed rejection or explicit mismatch warning |

## Deferred risks

- archive and compressed-input bombs in future collectors;
- stronger filesystem race resistance than the current open-handle metadata
  stability check;
- malicious plugins and subprocess isolation;
- CI identity verification, secret redaction, signing, revocation, and key
  management;
- database authorization, API authentication, audit retention, and concurrency.
