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

`create_candidate` normalizes identity fields and the explicit creation time,
then derives a stable `cand-` identifier from canonical JSON. The resulting
candidate is frozen by the strict Pydantic model. Transition services construct
a new candidate instead of mutating the previous instance.

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

## Current CLI boundary

`candidate create` and `candidate transition` emit deterministic JSON previews.
They do not write files or databases, acquire locks, or establish the current
authoritative revision. SQLite transactions, optimistic concurrency, replay
protection, and durable audit ordering belong to the next Phase 2 checkpoint.
