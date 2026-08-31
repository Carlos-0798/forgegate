# Phase 0 domain model

```text
Project -> ReleaseTrack -> Policy -> PolicyRule
   |
   +-> ReleaseCandidate -> EvidenceBundle -> EvidenceRecord -> ArtifactReference
                                      |              |
                                      |              +-> ExecutionContext
                                      +-> producer identity claim

PolicyRule + matching valid evidence -> RuleEvaluation -> PolicyEvaluation
                                                        -> ReleaseCandidate terminal
                                                        -> future Attestation
```

Phase 0 established `ProjectConfig`, `PolicyConfig`, and `EvidenceBundle`.
Phase 2 now adds immutable evaluation results, `ReleaseCandidate`,
`CandidateTransition`, and `CandidateTransitionResult`. The SQLite candidate
store durably appends candidate snapshots, transition events, and idempotency
records while maintaining one compare-and-swap current pointer. Attestation
remains deferred.

## Invariants already enforced

- unknown fields are rejected;
- paths in project configuration are relative and cannot traverse parents;
- schema versions must be recognized exactly;
- mandatory rules require evidence presence and missing evidence cannot PASS;
- artifact hashes are lower-case SHA-256 values;
- evidence timestamps include a UTC offset;
- every evidence record is bound to the bundle's candidate commit;
- evidence and policy rule IDs are unique within their owning document.

## Evaluation invariants now enforced

- evaluation time is explicit and timezone-aware;
- trust and verification ordering use explicit compatibility tables;
- future, stale, insufficient-assurance, missing, and conflicting evidence do
  not silently pass mandatory rules;
- optional rule outcomes are reported but do not block the overall decision;
- overall mandatory precedence is ERROR, then FAIL, then REVIEW, then PASS;
- canonical policy/evidence fingerprints and evaluation identity are emitted.

## Candidate invariants now enforced

- the only legal path is DRAFT → COLLECTING → READY → EVALUATING, followed by
  exactly one terminal PASS, FAIL, REVIEW, or ERROR transition;
- revisions are exact for each state and every transition increments by one;
- timestamps are timezone-aware, normalized by lifecycle services to UTC, and
  never regress;
- terminal candidates cannot transition again;
- transition IDs bind all event content plus before/after candidate fingerprints;
- PASS/FAIL/REVIEW require a policy evaluation with matching commit, decision,
  and timestamp; ERROR may represent a fail-closed system outcome without one.

## Persistence invariants now enforced

- schema version and ForgeGate application identity are exact and never
  auto-migrated;
- WAL, FULL synchronous durability, foreign keys, and explicit transactions are
  checked on every repository operation;
- snapshots, transitions, and idempotency records are append-only;
- current revision uses optimistic compare-and-swap and advances by exactly one;
- exact idempotency replays return the original response while conflicting key
  reuse fails closed;
- every load verifies the complete canonical snapshot/fingerprint/event chain.
