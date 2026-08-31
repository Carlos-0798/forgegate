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
                                                         -> ReleaseAttestation

CollectionResult(s) -> EvidenceBundleAssembly -> CandidateEvidenceBinding
                                              -> ReleaseCandidate READY gate
```

Phase 0 established `ProjectConfig`, `PolicyConfig`, and `EvidenceBundle`.
Phase 2 now adds immutable evaluation results, `ReleaseCandidate`,
`CandidateTransition`, and `CandidateTransitionResult`. The SQLite candidate
store durably appends candidate snapshots, transition events, candidate-evidence
bindings, evaluations, attestations, and idempotency records while maintaining
one compare-and-swap current pointer.

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
- new SQLite-v3 candidates require one immutable assembly binding before
  `READY`; a terminal evaluation must fingerprint that assembly's nested bundle.

## Persistence invariants now enforced

- schema version and ForgeGate application identity are exact; v1/v2-to-v3
  migration is explicit and validated rather than automatic;
- WAL, FULL synchronous durability, foreign keys, and explicit transactions are
  checked on every repository operation;
- snapshots, transitions, evidence bindings, and idempotency records are
  append-only;
- current revision uses optimistic compare-and-swap and advances by exactly one;
- exact idempotency replays return the original response while conflicting key
  reuse fails closed;
- every load verifies the complete canonical snapshot/fingerprint/event chain.

## Attestation invariants now enforced

- only a terminal revision-four candidate can be attested;
- the complete four-event transition chain must link adjacent candidate
  fingerprints and end at the embedded terminal candidate;
- PASS/FAIL/REVIEW embeds the exact policy evaluation; ERROR may omit one only
  when the candidate itself has no evaluation reference;
- evaluation ID, commit, decision, timestamp, mandatory rule precedence,
  unique rule IDs, and evidence references are recomputed and checked;
- candidate, transition-chain, and evaluation fingerprints bind the embedded
  documents, while `attestation_id` binds all remaining attestation content;
- deterministic JSON and Markdown are alternate renderings of the same strict
  document;
- `unsigned_local` explicitly disclaims producer identity, authorization,
  trusted time, and cryptographic signature assurance.
