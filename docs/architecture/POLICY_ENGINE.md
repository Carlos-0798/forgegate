# Deterministic policy engine

The evaluator is a pure decision boundary over a validated
`forgegate.policy.v1`, a validated `forgegate.evidence-bundle.v1`, and a
caller-supplied timezone-aware evaluation timestamp. It does not read artifact
bytes, collect evidence, execute tools, use the wall clock, or change external
state. Evaluation time cannot precede bundle generation, and non-finite values
cannot enter canonical fingerprints.

## Rule pipeline

Each rule is evaluated in this order:

1. select records with the exact `evidence_kind`;
2. retain records meeting explicit minimum trust and verification ranks;
3. reject future records and apply optional `maximum_age_seconds`;
4. apply exact `where` filters;
5. extract `where.field` when required and perform `value`, `count`, `all`, or
   `any` aggregation;
6. apply the type-strict operator and emit one immutable rule result.

`where.field` is a dot path into normalized `value`. The reserved filters
`scope`, `status`, `unit`, `source_tool`, and `source_version` select record
fields. `tags.*` selects evidence tags, `context.*` selects execution-context
fields, and remaining keys select dot paths inside normalized `value`.

`count` requires at least one fresh, sufficiently trusted record of the
evidence kind before a filtered zero may be evaluated. It cannot use
`where.field`. `value` accepts duplicate identical normalized values but emits
REVIEW for conflicts. `all` and `any` require at least one matched record, so
empty sets never pass vacuously.

## Decisions

- PASS: the expression is satisfied, or an optional rule explicitly permits
  absence;
- FAIL: eligible evidence explicitly does not satisfy the expression;
- REVIEW: required evidence is missing, stale/future, insufficiently assured,
  or conflicting according to configured missing semantics;
- ERROR: the expression or normalized value cannot be evaluated safely.

Only mandatory rules affect the overall decision. Their precedence is ERROR,
FAIL, REVIEW, then PASS. Optional outcomes remain visible in the result.

## Determinism and audit identity

Canonical JSON SHA-256 fingerprints identify the validated policy and evidence
bundle. The evaluation ID also binds the explicit evaluation timestamp. Every
result includes actual and expected values, evidence IDs, a stable reason code,
an explanation, and an optional remediation hint.

The CLI prints `forgegate.policy-evaluation.v1` JSON and returns `0` for PASS,
`1` for FAIL, `2` for REVIEW, and `3` for ERROR. Invalid configuration and
system input also return `3`, before evaluation output is created.
