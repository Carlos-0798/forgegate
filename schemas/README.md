# Generated schemas

The canonical contracts are the strict Pydantic models under
`src/forgegate/domain`. Regenerate committed JSON Schemas with:

```powershell
.\.venv\Scripts\forgegate.exe export-schemas schemas
```

Schema export is deterministic for a fixed ForgeGate version. Review and commit
model changes and regenerated schemas together.
