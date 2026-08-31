# SARIF 2.1.0 collector

## Boundary

The collector consumes an existing UTF-8 SARIF 2.1.0 artifact beneath an
explicit `ArtifactRegistry` root. It does not run a scanner, follow referenced
source paths or URIs, evaluate security severity, or make a release decision.

```text
security.sarif
      |
      v
ArtifactRegistry -- exact bytes + media type + size + SHA-256
      |
      v
SarifCollector -- strict JSON + bounded SARIF 2.1.0 subset
      |
      +--> static_analysis.summary  (always one for a valid artifact)
      |
      +--> static_analysis.finding  (one per SARIF result)
```

## Accepted subset and normalized values

Each run requires `tool.driver.name`. Tool version, semantic version,
information URI, rules, and invocations are optional, but every supplied field
is type and length checked. A supplied invocation must declare
`executionSuccessful: true`; otherwise the whole artifact is rejected.

Every result requires an unambiguous `ruleId` or resolvable `ruleIndex` and a
message containing `text` or `markdown`. The collector retains:

- SARIF level and kind, using SARIF defaults where absent;
- scanner and matching rule metadata;
- physical artifact URI/base ID and line/column bounds;
- logical location name, fully qualified name, and kind;
- full and partial fingerprint maps plus one deterministic selected fingerprint;
- suppression kind/status/justification and baseline state.

If the producer supplies no fingerprint, ForgeGate derives a SHA-256 from the
tool, rule ID, message, and normalized locations and labels its source
`forgegate-derived-sha256`. This is a deterministic local correlation aid, not
an authenticated producer fingerprint.

The summary records total, active, suppressed, counts by level/kind, and tool
metadata. A valid scan with no results still produces a summary with `total: 0`;
absence of the artifact therefore remains distinct from a successful clean scan.

## Fail-closed and audit behavior

The v1 parser rejects malformed or non-UTF-8 JSON, NUL bytes, duplicate keys,
NaN/Infinity, unsupported SARIF versions, empty/malformed run sets, failed
invocations, ambiguous rule references, inconsistent regions, invalid enum
values, and configured resource-limit violations.

Selected complex fields such as code flows, fixes, stacks, and related
locations remain in the hash-bound source artifact but are not normalized in
v1. Their presence produces `SARIF_DETAIL_NOT_NORMALIZED`; it is not silently
discarded. A nonstandard `$schema` URI also produces a warning.

Artifact SHA-256 and caller-supplied commit/trust/verification metadata establish
byte identity and claims. They do not authenticate the scanner or CI producer.
