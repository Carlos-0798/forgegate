# Deterministic release attestations

## Scope and assurance

`forgegate.release-attestation.v1` is the terminal local record for one
persisted release candidate. It is self-contained: a reader receives the
terminal candidate, its complete four-event transition chain, and the policy
evaluation when the decision requires one. The current assurance value is
always `unsigned_local`.

This proves deterministic content association within ForgeGate. It does not
prove who produced the inputs, who authorized release, whether the clock was
trusted, whether CI was authentic, or whether any hardware was exercised.

## Content binding

The model validates the following identities on every construction and load:

1. `candidate_fingerprint` covers the embedded terminal candidate;
2. each transition links adjacent candidate fingerprints and the fourth event
   must equal the embedded terminal state, time, evaluation reference, and
   fingerprint;
3. `transition_chain_fingerprint` covers the four ordered transition IDs;
4. `evaluation_fingerprint` covers the embedded policy evaluation;
5. the evaluation ID is recomputed from policy fingerprint, evidence
   fingerprint, and explicit evaluation time;
6. evaluation commit, decision, time, rule identity, evidence references, and
   mandatory-rule precedence are checked independently;
7. `attestation_id` covers all attestation content except its schema version and
   its own ID field.

PASS, FAIL, and REVIEW require the complete evaluation. ERROR may omit it only
when the terminal candidate also has no evaluation reference. No incomplete or
nonterminal candidate can produce an attestation.

## Deterministic renderings

The JSON rendering is sorted, indented UTF-8 with a final newline. The Markdown
rendering is derived only from the validated model and escapes table-sensitive
untrusted text. It includes:

- the decision, candidate identity, commit, times, and fingerprints;
- all four ordered transitions;
- policy/rule outcomes and evaluated evidence IDs when available;
- the generator version and explicit unsigned-local warning.

Committed JSON and Markdown Goldens prevent accidental rendering drift. The
JSON Schema is model-derived and covered by the repository-wide schema drift
gate.

## Persistence and publication

SQLite schema v3 stores exactly one immutable attestation per candidate,
including canonical JSON and deterministic Markdown. Reads reconstruct and
validate the model, rerender Markdown, and compare the embedded inputs with the
authoritative candidate, transition, evaluation, and, for new v3 candidates,
evidence-binding rows.

`candidate attest DATABASE CANDIDATE_ID --issued-at TIME --output-root DIR`
first creates or exactly replays the durable row. It then stages
`attestation.json` and `attestation.md` in a private directory and atomically
renames that directory to `attestation-<sha256>`.

An existing target is accepted only if it is a non-symlink directory containing
exactly those two regular files with byte-identical content. Any mismatch is an
output conflict; ForgeGate never overwrites it. A concurrent publisher that
wins the rename race is treated as an exact replay only after the same byte
verification.

The SQLite commit and filesystem rename are intentionally not described as one
atomic transaction. A filesystem failure can leave a durable database record
without a bundle. Rerunning the same command recovers safely because the
attestation and output location are content-addressed.

## Compatibility boundary

The attestation contains only ForgeGate public contracts. It imports no Analog
Validation Studio or MSP430 code and makes no device or electrical claim.
Future compatibility collectors may normalize versioned public reports into
generic ForgeGate evidence before policy evaluation; the attestation format
does not need upstream repository internals.

Attestation v1 carries the terminal evaluation's evidence fingerprint but does
not embed the complete assembly binding or its receipts. The durable companion
record is `forgegate.candidate-evidence-binding.v1`, available through
`candidate show-evidence`. This limitation is explicit rather than silently
changing the frozen attestation v1 contract.
