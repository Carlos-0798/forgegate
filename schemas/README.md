# Generated schemas

The canonical contracts are strict Pydantic models under `src/forgegate`,
including domain, policy, candidate, and attestation packages. Regenerate
committed JSON Schemas with:

```powershell
.\.venv\Scripts\forgegate.exe export-schemas schemas
```

Schema export is deterministic for a fixed ForgeGate version. Review and commit
model changes and regenerated schemas together.

`forgegate.openapi.v1.json` is the deterministic OpenAPI 3.1 description of
the local REST surface. Regenerate it with `forgegate export-openapi
schemas/forgegate.openapi.v1.json`. `tools/verify.py` compares the committed
bytes with the current FastAPI application, and clean-wheel smoke verifies that
an installed package exports the same contract. It is an interface description,
not an authentication or deployment guarantee.

Phase 14 adds OpenAPI-only response components and operations for self-logout,
operator session revocation, and fixed-startup-path trust-store reload. These
ephemeral process-control documents are not standalone configuration or durable
audit Schemas and are therefore committed only inside the OpenAPI contract.

`forgegate.evidence-bundle-assembly.v1.schema.json` describes the audited
envelope around a candidate-bound evidence bundle and its collection receipts.
It is accepted by configuration validation and policy evaluation without
changing the nested evidence contract.

`forgegate.candidate-evidence-binding.v1.schema.json` describes the immutable
companion document that binds one revision-one `COLLECTING` candidate snapshot
to one complete audited assembly before a new persisted candidate may become
`READY`.

`forgegate.registered-project.v1.schema.json` describes one immutable local
project-profile registration. `forgegate.audit-actor.v1.schema.json` describes
the authenticated public identity, role, session, and trust snapshot attached
to a successful API-origin write. `forgegate.audit-event.v1.schema.json`
describes content-bound metadata for one successful durable state change and
optionally includes that actor, while `forgegate.audit-event-page.v1.schema.json`
describes bounded stable-cursor query output. Legacy and CLI events retain a
null actor; no Bearer token or private key is part of these contracts.
`forgegate.registered-project-page.v1.schema.json` and
`forgegate.release-candidate-page.v1.schema.json` describe bounded project and
project-scoped candidate discovery.

`forgegate.project-profile-revision.v1.schema.json` and
`forgegate.project-profile-page.v1.schema.json` describe append-only complete
profile replacements and bounded version history. The
`forgegate.release-candidate.v2.schema.json` contract adds the exact governing
profile ID/version to candidate identity; v1 remains committed for stateless
and legacy compatibility.

`forgegate.assurance-bundle.v1.schema.json` describes the portable combination
of the exact project profile, evidence binding, policy material, and release
attestation. `forgegate.assurance-bundle-manifest.v1.schema.json` describes the
canonical README and machine-document byte sizes and SHA-256 entries. Both are
unsigned local integrity contracts, not signatures or producer identity.

`forgegate.signing-identity.v1.schema.json` describes one key-derived Ed25519
public identity. `forgegate.trust-store.v1.schema.json` authorizes exact public
identities for bounded roles and projects, while
`forgegate.assurance-signature.v1.schema.json` binds one signer and role to the
exact canonical assurance-bundle bytes. A trust-store ID is an integrity value,
not a trust root by itself; trust-store distribution and custody are external.

`forgegate.benchmark.v1.schema.json` is the ForgeGate-owned Benchmark artifact
contract. `analog-validation.result-export.v1.schema.json` is ForgeGate's
consumer-side structural mirror of the upstream Studio contract; it does not
transfer schema ownership to ForgeGate. Both are emitted by `export-schemas`
and drift-checked by `tools/verify.py`. Neither is a project/policy
configuration schema.
