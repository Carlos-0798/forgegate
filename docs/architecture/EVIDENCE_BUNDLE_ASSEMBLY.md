# Evidence-bundle assembly

## Purpose

Phase 4 joins one or more completed collector outputs into a candidate-bound
`forgegate.evidence-bundle-assembly.v1` document. Assembly is deliberately
separate from collection and policy evaluation: it does not run a producer,
change evidence, or decide whether a release is acceptable.

## Input boundary

`assemble-evidence` accepts collection-result JSON files beneath one explicit
`--root`. The loader applies the same byte-stable, regular-file, size, and root
confinement rules as every collector, then requires UTF-8 JSON with:

- no NUL bytes, duplicate object keys, or non-finite numbers;
- bounded node count and nesting depth;
- an exact strict `CollectionResult` contract;
- `COMPLETE` status and at least one evidence record;
- every referenced source artifact still present under the same root with the
  exact declared path, media type, size, and SHA-256.

Collection warnings reject assembly by default. `--retain-warnings` is an
explicit acknowledgement that keeps the complete warnings in the assembly; it
does not suppress, downgrade, or reinterpret them.

## Output contract

The assembly contains:

- a normal `forgegate.evidence-bundle.v1` for the candidate commit;
- one receipt per input with the raw collection-result file identity;
- a canonical fingerprint of each parsed collection result;
- collector name/version, original artifact references, evidence IDs, and
  retained warnings;
- a content-derived `assembly_id` covering the bundle and every receipt.

Input order is preserved. Receipt evidence IDs must exactly equal bundle
evidence order. Duplicate sources, duplicate normalized results, duplicate
evidence IDs, conflicting artifact identities, candidate-commit mismatches,
and generation times earlier than collection all fail closed.

## Policy compatibility

`evaluate-policy` accepts either a direct evidence bundle or an assembly. For
an assembly it evaluates only the validated nested bundle; the assembly
receipts remain audit provenance and do not become policy facts.

## Persisted candidate binding

An accepted assembly can be stored against a revision-one `COLLECTING`
candidate with `candidate bind-evidence`. New SQLite-v3 candidates must have
this immutable companion record before `READY`; their terminal evaluation must
then reference the canonical fingerprint of the assembly's nested evidence
bundle. See `CANDIDATE_EVIDENCE_BINDING.md` for the lifecycle and migration
contract.

## Explicit non-claims

SHA-256 establishes local byte identity, not producer authenticity. A claimed
commit, CI identity, trust level, or verification level is preserved rather
than authenticated. This slice performs no network access, build/test run,
Studio import, serial access, or MSP430 operation.
