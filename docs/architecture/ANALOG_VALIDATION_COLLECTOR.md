# Analog Validation Studio result collector

## Frozen upstream boundary

ForgeGate consumes Analog Validation Studio's public JSON `result-export.v1`
artifact. The upstream contract was frozen at Studio commit
`9ac23494b86212928185de9b0eef1c1a82a8c0ea` on 2026-08-30. ForgeGate owns a
consumer-side structural mirror in
`schemas/analog-validation.result-export.v1.schema.json`; Analog Validation
Studio remains the source owner.

The collector does not import `analog_validation`, rerun analysis, open a
serial port, control an AFE or MSP430, or consume the not-yet-implemented Phase
5 human-readable report. It accepts only the already-frozen machine export.

```text
result-export.v1 JSON
        |
        v
ArtifactRegistry -- root boundary + exact bytes + size + SHA-256
        |
        v
AnalogValidationResultCollector -- strict public contract + semantic lineage checks
        |
        +--> analog-validation.run
        +--> analog-validation.metric
        +--> analog-validation.criterion
```

## Contract and normalization

The parser requires the exact upstream root, TestRun metadata, criteria,
source-schema, metric, point, reference, and limitation fields. It preserves
the upstream outcome and checks the upstream invariants again, including:

- exact `result-export.v1` and `test-run.v1` versions;
- UTC timestamps and non-regressing run time;
- unique schema, metric, criterion, input, evidence, and point identities;
- contiguous point indexes and one evidence source across every point;
- exact point-to-TestRun record and raw-record lineage;
- required exclusion reasons for excluded or invalid points;
- inclusive criterion math and PASS/FAIL agreement;
- mandatory limitations and required missing requirements for
  `INCOMPLETE`/`UNSUPPORTED`.

One run record is always emitted for a valid export. Metrics and evaluated
criteria become separate records. Point detail stays in the hash-bound source
artifact rather than being duplicated into an unbounded evidence list. A
collector `COMPLETE` status means normalization completed; it does not mean the
Studio outcome or a ForgeGate release policy passed.

## Evidence-level mapping

Verification level is derived from the artifact and cannot be supplied as a
CLI override:

| Studio source | ForgeGate level |
|---|---|
| `THEORY` | `declared` |
| `SYNTHETIC`, `SPICE_IDEAL`, `SPICE_MODEL` | `simulated` |
| `CSV_REPLAY` | `replayed` |
| `HOST_TEST` | `host_tested` |
| `BENCH_DMM`, `BENCH_CONTROLLER`, `BENCH_SCOPE` | `system_observed` plus warning |

The current export does not structurally require instrument identity,
calibration state, wiring, operator, or environment references. Consequently,
`BENCH_*` is deliberately capped at `system_observed`; this collector cannot
emit `physically_verified`. A future upstream schema must add mandatory bench
provenance before that mapping can be reconsidered.

Trust remains caller-supplied because a local JSON file does not authenticate
its producer. `--commit` identifies the Studio commit claimed to have produced
the artifact; the file does not carry that commit internally. Artifact SHA-256
binds the exact bytes but does not prove the claim.

## Fail-closed and resource behavior

The collector rejects invalid UTF-8, NUL, malformed JSON, duplicate keys,
non-finite constants, unknown or missing fields, unsupported enum/version
values, semantic lineage contradictions, files above the upstream 2,000,000
byte limit, and configured JSON node/depth violations. Normalized evidence
field limits also fail the whole collection rather than dropping a record.

## Local preview

```powershell
.\.venv\Scripts\python.exe -m forgegate collect-analog-validation `
  artifacts/analog-validation-result.json `
  --root examples/sample-python-api `
  --commit 9ac23494b86212928185de9b0eef1c1a82a8c0ea `
  --collected-at 2026-08-31T13:00:00Z
```

This command is read-only. It does not evaluate a policy or persist a release
candidate.
