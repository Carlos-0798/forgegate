# Artifact registry and JUnit evidence slice

## Boundary

This slice consumes one existing JUnit XML file beneath an explicitly selected
local root. It does not execute tests, call a CI provider, evaluate policy, or
make a release decision. The core remains domain-neutral and imports no AFE or
MSP430 code.

```text
relative JUnit path
        |
        v
ArtifactRegistry -- exact bytes + SHA-256 --> ArtifactReference
        |
        v
JUnitCollector -- bounded parse + audit --> test.summary EvidenceRecord
        |
        +--> COMPLETE + evidence + warnings
        +--> REJECTED + stable rejection code
```

`CollectionResult.status=COMPLETE` means the input was collected successfully.
`EvidenceRecord.status=passed|failed` reports the observed test outcome. A later
policy engine, not this collector, will decide whether a candidate may release.

## Artifact invariants

- paths are relative to one resolved registry root;
- absolute paths and parent traversal are rejected;
- resolved paths must remain under the root;
- only regular files within the configured byte limit are accepted;
- bytes are read once, hashed with SHA-256, and retained for parsing;
- file size and modification metadata must remain stable across the read;
- registering changed bytes under an already registered path is rejected.

## JUnit v1 behavior

- accepts UTF-8-compatible `testsuite` and `testsuites` roots;
- rejects NUL bytes, DOCTYPE, ENTITY, malformed XML, excess depth/elements,
  invalid counts/durations, and conflicting testcase outcomes;
- derives counts from testcase elements when available;
- records declared-versus-observed count mismatches as warnings;
- keeps aggregate duration unknown when any testcase duration is missing;
- distinguishes failures, errors, and skipped tests;
- binds evidence to the supplied commit, trust claim, verification level, and
  exact artifact hash.

Hashes and caller-supplied metadata establish identity and claims, not producer
authenticity. Signed provenance and CI identity verification remain deferred.
