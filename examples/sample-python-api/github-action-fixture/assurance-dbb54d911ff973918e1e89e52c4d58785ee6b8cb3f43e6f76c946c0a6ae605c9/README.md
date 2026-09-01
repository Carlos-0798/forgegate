# ForgeGate portable assurance bundle

- Bundle: `sha256:dbb54d911ff973918e1e89e52c4d58785ee6b8cb3f43e6f76c946c0a6ae605c9`
- Project: `sample-api`
- Candidate: `cand-c722c4897d986a82ee18ef82`
- Version: `1.2.0`
- Commit: `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`
- Decision: **PASS**
- Assurance: `unsigned_local`

## Offline verification

```text
forgegate verify-assurance <this-directory>
```

The verifier checks exact directory contents, canonical file bytes, SHA-256
manifest entries, all document identities, and cross-document associations.

## Evidence boundary

This unsigned local bundle embeds the frozen project profile, retained evidence
binding, exact policy bytes, evaluation, lifecycle chain, and attestation. Source
artifact bytes referenced by collector receipts are not embedded, so this bundle
does not independently re-run collectors, authenticate producers, prove trusted
time, or establish hardware, bench, field, or production verification.
