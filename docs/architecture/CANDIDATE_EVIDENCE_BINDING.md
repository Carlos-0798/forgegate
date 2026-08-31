# Candidate evidence binding

## Purpose

Phase 4 persists the exact audited evidence assembly accepted for a release
candidate. A new schema-v3 candidate cannot move from `COLLECTING` to `READY`
until one `forgegate.candidate-evidence-binding.v1` document has been stored.
This closes the gap between standalone assembly validation and the durable
candidate lifecycle.

## Binding contract

`candidate bind-evidence` accepts only a validated
`forgegate.evidence-bundle-assembly.v1` document and a revision-one
`COLLECTING` candidate. The binding records:

- the complete candidate snapshot and its canonical SHA-256 fingerprint;
- the complete assembly and its canonical SHA-256 fingerprint;
- a caller-supplied, timezone-aware binding time;
- a content-derived binding ID covering all fields above.

The candidate commit must equal the nested evidence-bundle commit. Binding time
cannot precede either the candidate snapshot or assembly generation. Every
model load recomputes the candidate fingerprint, assembly fingerprint, and
binding ID; changing embedded content without changing its identities fails
closed.

## Lifecycle gates

The SQLite repository applies three linked controls:

1. exactly one immutable binding may be stored while the candidate is at
   revision one in `COLLECTING`;
2. `COLLECTING -> READY` requires that binding and cannot be timestamped before
   it;
3. a terminal policy evaluation must contain the canonical fingerprint of the
   binding's nested `EvidenceBundle`.

The last check is intentionally against the policy engine's existing evidence
fingerprint, not the assembly fingerprint. The assembly receipts remain audit
provenance; policy rules continue to evaluate only normalized evidence facts.

An exact retry with the same idempotency key returns the stored response. An
exact binding requested under a new key records that key before returning.
Reusing either key for different normalized input, or attempting a different
binding for the candidate, fails closed.

## SQLite v3 and migration

Schema v3 adds an immutable `evidence_binding_required` candidate flag and the
append-only `candidate_evidence_bindings` table. New candidates set the flag to
one. Read-time validation compares table metadata with the embedded binding,
the revision-one snapshot, the candidate audit chain, and any later transition
time.

`candidate migrate-store` explicitly migrates validated v1 or v2 stores to v3.
All pre-existing candidates retain `evidence_binding_required = 0`; ForgeGate
does not invent a historical assembly or claim that one was bound. Their prior
lifecycle semantics remain readable and attestable after any required legacy
evaluation backfill. New candidates created after migration use the v3 gate.

## CLI flow

After creating and advancing a persisted candidate to `COLLECTING`:

```powershell
.\.venv\Scripts\python.exe -m forgegate candidate bind-evidence `
  work/forgegate.db cand-dab25eb0be1a0107b3996080 `
  work/evidence-assembly.json `
  --bound-at 2026-08-30T20:31:00Z `
  --idempotency-key bind-evidence:sample-api-1.2.0

.\.venv\Scripts\python.exe -m forgegate candidate show-evidence `
  work/forgegate.db cand-dab25eb0be1a0107b3996080
```

The later `READY` transition must occur at or after `bound_at`. Evaluate the
same assembly and pass that evaluation to the terminal transition.

## Attestation and assurance boundary

The current release-attestation v1 document embeds the terminal evaluation and
therefore its evidence fingerprint, but it does not embed the complete
candidate-evidence binding or assembly receipts. The authoritative companion
record is available through `candidate show-evidence`, and every attestation
load first validates the same SQLite candidate history. A future attestation
schema can make the companion relationship portable without silently changing
v1.

SHA-256 provides deterministic local content identity, not authentication.
This feature does not verify a producer, CI run, commit authority, operator,
clock, signature, or physical measurement. It performs no network, Studio,
serial, or MSP430 action.
