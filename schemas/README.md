# Generated schemas

The canonical contracts are strict Pydantic models under `src/forgegate`,
including domain, policy, candidate, and attestation packages. Regenerate
committed JSON Schemas with:

```powershell
.\.venv\Scripts\forgegate.exe export-schemas schemas
```

Schema export is deterministic for a fixed ForgeGate version. Review and commit
model changes and regenerated schemas together.

`forgegate.evidence-bundle-assembly.v1.schema.json` describes the audited
envelope around a candidate-bound evidence bundle and its collection receipts.
It is accepted by configuration validation and policy evaluation without
changing the nested evidence contract.

`forgegate.candidate-evidence-binding.v1.schema.json` describes the immutable
companion document that binds one revision-one `COLLECTING` candidate snapshot
to one complete audited assembly before a new SQLite-v3 candidate may become
`READY`.

`forgegate.benchmark.v1.schema.json` is the ForgeGate-owned Benchmark artifact
contract. `analog-validation.result-export.v1.schema.json` is ForgeGate's
consumer-side structural mirror of the upstream Studio contract; it does not
transfer schema ownership to ForgeGate. Both are emitted by `export-schemas`
and drift-checked by `tools/verify.py`. Neither is a project/policy
configuration schema.
