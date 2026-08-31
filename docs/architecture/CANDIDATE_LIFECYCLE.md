# Release-candidate lifecycle

The lifecycle layer is a pure, immutable boundary over validated candidate and
policy-evaluation documents. It uses caller-supplied timestamps, performs no
I/O, and does not persist or authenticate state.

## State graph and revisions

```text
DRAFT(0) -> COLLECTING(1) -> READY(2) -> EVALUATING(3)
                                               |
                         +---------------------+---------------------+
                         |           |             |                |
                      PASS(4)     FAIL(4)       REVIEW(4)        ERROR(4)
```

No state can be skipped, repeated, reversed, or left after a terminal result.
Every transition increments the exact lifecycle revision by one. Equal event
timestamps are permitted because revision supplies ordering; a timestamp older
than the candidate's current `updated_at` is rejected.

`create_candidate` normalizes identity fields, canonicalizes release-track
underscores to hyphens, and normalizes the explicit creation time,
then derives a stable `cand-` identifier from canonical JSON. The resulting
candidate is frozen by the strict Pydantic model. Transition services construct
a new candidate instead of mutating the previous instance.

`create_profile_bound_candidate` produces
`forgegate.release-candidate.v2`. Its identity additionally includes the exact
governing `project_profile_id` and `project_profile_version`. The same transition
service accepts v1/v2 documents and preserves the v2 binding across every
lifecycle revision.

## Evaluation binding

PASS, FAIL, and REVIEW are release conclusions, so entering them requires a
validated `forgegate.policy-evaluation.v1` document whose:

- candidate commit equals the release candidate commit;
- decision equals the requested terminal state;
- evaluation timestamp equals the transition timestamp.

The resulting candidate and transition both retain the evaluation ID. ERROR may
be entered without an evaluation when the system must fail closed before a
policy result can be produced; it may also bind a matching ERROR evaluation.

This boundary prevents the lifecycle service or CLI from manufacturing PASS by
state assignment alone. It does not cryptographically authenticate the
evaluation producer.

## Audit identity

Every `forgegate.candidate-transition.v1` event contains the prior and result
candidate SHA-256 fingerprints, exact revisions, states, timestamp, optional
reason, and optional evaluation ID. Its `transition_id` is recomputed from all
event content when the model is validated. A
`forgegate.candidate-transition-result.v1` envelope verifies that the result
candidate and transition agree.

## CLI and persistence boundary

`candidate create` and `candidate transition` emit deterministic JSON previews.
Without `--database`, they do not write files or establish an authoritative
revision. The accepted SQLite checkpoint adds `candidate init-store`, persisted
`candidate create --database`, atomic `candidate advance`, `candidate show`,
`candidate history`, and project-scoped `candidate list`. Persisted
product-surface creation is authorized by the current registered project
profile and one normalized configured track, then persisted as candidate v2;
direct reads of legacy v1 candidates remain available. See
`PROJECT_PROFILE_REVISIONS.md` and `SQLITE_CANDIDATE_STORE.md` for profile,
transaction, idempotency, recovery, and corruption-detection guarantees.
