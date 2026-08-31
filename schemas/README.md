# Generated schemas

The canonical contracts are the strict Pydantic models under
`src/forgegate/domain`. Regenerate committed JSON Schemas with:

```powershell
.\.venv\Scripts\forgegate.exe export-schemas schemas
```

Schema export is deterministic for a fixed ForgeGate version. Review and commit
model changes and regenerated schemas together.

`forgegate.benchmark.v1.schema.json` is the ForgeGate-owned external Benchmark
artifact contract. It is defined alongside the bounded collector and checked
for exact drift by `tools/verify.py`; it is not a project/policy configuration
schema emitted by `export-schemas`.
