# Product brief

ForgeGate answers one question: given a release candidate, its versioned policy,
and engineering artifacts produced elsewhere, is there sufficient attributable
evidence to mark the candidate PASS, FAIL, REVIEW, or ERROR?

The first user is an individual developer or small team that already runs tests
and scans but lacks a consistent, explainable release decision. ForgeGate does
not execute those tools. It validates and normalizes their outputs, binds them to
a candidate and execution context, applies a deterministic policy, and exports
an auditable result.

## Phase 0 outcome

Phase 0 freezes the vocabulary and safe configuration boundary. It does not
claim to collect evidence or make release decisions. The canonical example is a
generic Python API and remains usable if every embedded compatibility document
is removed.

## Non-goals

- device control, telemetry, analog acquisition, or test execution;
- a generic project-management system;
- production-grade identity, signing, SaaS, SSO, or compliance certification;
- treating file presence, a hash, or user-supplied CI metadata as proof that a
  test truly ran.
