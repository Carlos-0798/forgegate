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

`forgegate.evidence-bundle-assembly.v1.schema.json` describes the audited
envelope around a candidate-bound evidence bundle and its collection receipts.
It is accepted by configuration validation and policy evaluation without
changing the nested evidence contract.

`forgegate.candidate-evidence-binding.v1.schema.json` describes the immutable
companion document that binds one revision-one `COLLECTING` candidate snapshot
to one complete audited assembly before a new SQLite-v3 candidate may become
`READY`.

`forgegate.registered-project.v1.schema.json` describes one immutable local
project-profile registration. `forgegate.audit-event.v1.schema.json` describes
content-bound metadata for one successful durable state change, while
`forgegate.audit-event-page.v1.schema.json` describes bounded stable-cursor
query output. `forgegate.registered-project-page.v1.schema.json` and
`forgegate.release-candidate-page.v1.schema.json` describe bounded project and
project-scoped candidate discovery. These contracts do not authenticate an
operator or producer.

`forgegate.benchmark.v1.schema.json` is the ForgeGate-owned Benchmark artifact
contract. `analog-validation.result-export.v1.schema.json` is ForgeGate's
consumer-side structural mirror of the upstream Studio contract; it does not
transfer schema ownership to ForgeGate. Both are emitted by `export-schemas`
and drift-checked by `tools/verify.py`. Neither is a project/policy
configuration schema.
