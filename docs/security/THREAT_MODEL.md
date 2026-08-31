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

## Addressed in the Phase 1 coverage slice

| Threat | Current control |
|---|---|
| Malformed or entity-bearing coverage XML | Strict parse plus DOCTYPE/ENTITY rejection |
| Pathological coverage XML | 250,000-element and depth-64 default limits |
| Misleading declared coverage rates | Derive from countable lines/branches and audit mismatches |
| Ambiguous line/package/module ownership | Reject mixed scoped/unscoped line data |
| Duplicate or inconsistent LCOV records | Strict source-record state and duplicate/count checks |
| Oversized LCOV record set | 500,000-line default limit plus artifact byte limit |
| Missing branch detail hidden as observation | Explicit summary-only warning or unavailable warning |

## Addressed in the Phase 1 SARIF slice

| Threat | Current control |
|---|---|
| Missing scan represented as no evidence | Every successfully parsed run set emits an explicit summary, including zero results |
| Failed scanner invocation represented as valid evidence | Any declared unsuccessful invocation rejects the artifact |
| Ambiguous or absent rule identity | Require `ruleId` or a resolvable `ruleIndex`; conflicting references reject |
| Duplicate JSON keys or non-finite numbers | Strict object-pair and numeric-constant rejection |
| Pathological JSON shape or result volume | Node, depth, run, result, rule, location, suppression, and fingerprint limits |
| Unsupported nested detail silently normalized | Retain exact artifact bytes and emit `SARIF_DETAIL_NOT_NORMALIZED` warnings |
| Fabricated fingerprint stability | Prefer declared full/partial fingerprints; label fallback explicitly as ForgeGate-derived SHA-256 |
| Suppressed result treated as active | Preserve suppression records and mark accepted suppressions explicitly |

## Addressed in the Phase 1 Benchmark slice

| Threat | Current control |
|---|---|
| Ambiguous producer-specific benchmark shape | Exact `forgegate.benchmark.v1` schema version and strict field allowlists |
| Empty benchmark represented as successful evidence | Reject empty metric arrays; complete collections always contain metrics |
| Duplicate metric overwrites or double counting | Reject duplicate `(scope, name)` identities |
| NaN, Infinity, overflow, or underflow distortion | Decimal JSON parsing plus finite/range and conversion checks |
| Tolerance interpreted without comparison point | Any tolerance requires an explicit baseline |
| Percent versus absolute tolerance ambiguity | Required `mode` enum with `absolute` and `percent` only |
| Pathological JSON shape or volume | Artifact byte, JSON node/depth, and metric-count limits |
| Unknown fields silently ignored | Unknown root, tool, metric, and tolerance fields reject collection |

## Deferred risks

- archive and compressed-input bombs in future collectors;
- stronger filesystem race resistance than the current open-handle metadata
  stability check;
- malicious plugins and subprocess isolation;
- CI identity verification, secret redaction, signing, revocation, and key
  management;
- database authorization, API authentication, audit retention, and concurrency.
