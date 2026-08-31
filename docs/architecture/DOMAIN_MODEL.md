# Phase 0 domain model

```text
Project -> ReleaseTrack -> Policy -> PolicyRule
   |
   +-> ReleaseCandidate -> EvidenceBundle -> EvidenceRecord -> ArtifactReference
                                      |              |
                                      |              +-> ExecutionContext
                                      +-> producer identity claim

PolicyRule + matching valid evidence -> future ClaimResult -> future Attestation
```

Phase 0 implements configuration contracts through `ProjectConfig`,
`PolicyConfig`, and `EvidenceBundle`. Candidate lifecycle, evaluation,
persistence, and attestation are intentionally deferred.

## Invariants already enforced

- unknown fields are rejected;
- paths in project configuration are relative and cannot traverse parents;
- schema versions must be recognized exactly;
- mandatory rules require evidence presence and missing evidence cannot PASS;
- artifact hashes are lower-case SHA-256 values;
- evidence timestamps include a UTC offset;
- every evidence record is bound to the bundle's candidate commit;
- evidence and policy rule IDs are unique within their owning document.
