# ADR-0001: Domain-neutral core and artifact-only integrations

- Status: Accepted for Phase 0
- Date: 2026-08-30

## Decision

ForgeGate Core owns release candidates, evidence provenance, policies, claims,
decisions, attestations, and audit events. Domain integrations consume
versioned artifacts through collectors or optional packs. Core must not import
Analog Validation Studio or MSP430 repository code.

The canonical sample and all core tests must run without an embedded pack.
Domain-specific labels may be retained as tags in imported evidence, but they
must not become required fields in project, policy, or evidence-bundle schemas.

## Consequences

- Upstream repositories retain their algorithms, protocols, tests, and claims.
- Compatibility can advance quickly through stable report contracts without
  synchronizing runtime dependencies.
- ForgeGate cannot claim an upstream result until it ingests and validates an
  explicit artifact produced by that upstream repository.
