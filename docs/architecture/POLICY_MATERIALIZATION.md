# Profile-authorized policy materialization

## Scope

Phase 10 closes the gap between a candidate's frozen project profile and the
exact policy bytes used for its terminal decision. A configured path is
authority to select a file inside an explicit project root; a matching policy
name alone is no longer sufficient for new persisted candidates.

This slice remains local, unsigned, and domain-neutral. It does not authenticate
the project profile, policy author, HTTP caller, filesystem owner, CI producer,
clock, or commit.

## Material contract

`forgegate.policy-material.v1` retains:

- project ID and the candidate's immutable project-profile ID/version;
- canonical release-track identity;
- normalized root-relative policy path, allowed YAML/JSON media type, exact
  byte size, and SHA-256;
- canonical base64 of the exact bytes;
- the strict `forgegate.policy.v1` object parsed from those bytes and its
  canonical fingerprint; and
- a material ID derived from every field above.

Validation decodes the bytes again, recomputes size and SHA-256, rejects
noncanonical base64, unsafe paths, unsupported media types, non-UTF-8 content,
duplicate YAML keys, unknown fields, and any difference between the parsed
bytes and embedded policy. The policy name must equal the canonical release
track. Policy input is capped at 1 MiB; the enclosing configuration-document
limit is 4 MiB to accommodate base64 plus the strict parsed representation.

## Resolution and transport boundaries

Only the CLI-side application operation resolves a policy path. It loads the
candidate and exact frozen profile, resolves exactly one normalized release
track, and registers the configured policy through the existing stable-read,
regular-file, root-confined artifact registry. The caller must supply the
project root explicitly.

The loopback REST API has no materialization or filesystem-path parameter.
`POST /v1/candidates/{id}/evaluate` accepts a complete validated policy-material
document, and `GET /v1/candidates/{id}/policy` returns the material retained for
that terminal evaluation. A client can materialize locally and send the
document; the server never dereferences `artifact.path_or_uri`.

## Evaluation and persistence

`forgegate.policy-evaluation.v1` remains the stateless and legacy contract.
`forgegate.policy-evaluation.v2` adds the policy-material ID, policy artifact
SHA-256, and governing project-profile ID/version. Its evaluation ID binds the
material ID, evidence fingerprint, and normalized evaluation time.

SQLite schema v7 adds an immutable `policy_material_required` candidate marker
and one append-only `candidate_policy_materials` row. New product-surface
profile-bound candidates set the marker to one. At a terminal evaluation the
repository checks, in the same transaction, that:

1. the material project, profile, version, and track equal the candidate;
2. the frozen profile authorizes the material's exact root-relative path;
3. the v2 evaluation references the exact material and profile fields;
4. the evaluation evidence fingerprint equals the candidate's durable evidence
   binding; and
5. material, evaluation, snapshot, transition, audit events, current pointer,
   and idempotency response commit or roll back together.

PASS, FAIL, and REVIEW remain lifecycle decisions derived from evaluation.
Generic ERROR transition semantics remain available for fail-closed system
failure without claiming a policy result.

## Migration and limitations

Validated v1-v6 stores migrate explicitly to v7. The new requirement marker
defaults to zero for every historical candidate, and no material row is
created. This preserves old reads and exact v1 evaluation backfill semantics
without asserting which bytes were historically used. Candidates created after
migration set the requirement marker to one.

SHA-256 proves local byte identity and association only. The current
`forgegate.release-attestation.v1` embeds the v2 evaluation and material ID but
not the full policy-material bytes; the v7 database and policy read endpoint
retain those bytes. Phase 11 keeps attestation v1 stable and instead includes
the complete material in the separate `forgegate.assurance-bundle.v1` portable
envelope. Authentication, signatures, trusted timestamps, policy approval,
database authorization, and non-loopback operation remain deferred.
