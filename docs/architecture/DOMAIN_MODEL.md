# Phase 0 domain model

```text
Project -> ReleaseTrack -> Policy -> PolicyRule
   |
   +-> ReleaseCandidate -> EvidenceBundle -> EvidenceRecord -> ArtifactReference
                                      |              |
                                      |              +-> ExecutionContext
                                      +-> producer identity claim

PolicyRule + matching valid evidence -> RuleEvaluation -> PolicyEvaluation
                                                        -> future Attestation
```

Phase 0 established `ProjectConfig`, `PolicyConfig`, and `EvidenceBundle`.
Phase 2 now adds immutable `RuleEvaluation` and `PolicyEvaluation` results.
Candidate lifecycle, persistence, and attestation remain deferred.

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
