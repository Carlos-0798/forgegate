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
`CandidateTransition`, and `CandidateTransitionResult`. Persistence and
attestation remain deferred.

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
