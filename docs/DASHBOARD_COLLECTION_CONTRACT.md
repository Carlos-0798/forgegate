# Dashboard bounded collection contract (Phases 30, 33 and 49)

The first slice accepts one JUnit report through an operator-only,
candidate-scoped, same-origin and CSRF-protected preview POST. It is a bounded
synchronous operation, not a durable job queue or a general upload endpoint.

- Maximum decoded report: 1 MiB; canonical base64 preserves exact bytes.
  Existing 4 MiB actual HTTP body limit remains enforced.
- No client filename, server path, URL, archive, executable, or device input.
  An in-memory source uses a server-generated content-addressed logical name.
- Use the existing JUnit collector and evidence assembler; at most 10,000 XML
  elements and depth 32. No filesystem writes or network fetches occur.
- Require expected candidate revision and an explicit matching reported commit;
  candidate must be COLLECTING and have no retained evidence binding.
- Require caller-reported collection time with offset and no future timestamp,
  source tool and version. Do not replace old test time with upload time.
  Source metadata and commit association remain unverified declarations.
- Force unsigned_local / declared. Test-summary success is not policy PASS.
- Preview returns collection warnings/rejections and no assembly for a rejected
  report or unacknowledged warnings. A separate request can explicitly retain
  warnings. A complete assembly remains unbound until separate reviewed binding.
- No preview is durable. Closing/navigating away discards browser preview state;
  it does not promise server cancellation. Restart/session expiry requires a new
  preview. No automatic retry, resume, or fabricated percentage progress.
- The retained binding contains normalized evidence, receipt and exact hashes,
  not source report bytes. Users must retain originals themselves. The source
  receipt identifies canonical in-memory CollectionResult JSON, not a disk file.

Existing policies may reject declared-only evidence or require other collectors.
Single-report binding remains immutable. The Phase 33 combined form below is
available before binding; larger combinations still require CLI assembly.

Acceptance requires positive/negative report cases, exact hash/count comparison,
warning consent, authorization/CSRF/scope/state checks, no preview writes,
separate binding, frontend recovery/stale-response tests, and browser evidence.
This preview does not queue work. Separately reviewed durable submission is
available through the [existing collection jobs](COLLECTION_JOBS.md) workflow.

## Standard CI report preview

`POST /app/api/candidates/{candidate_id}/collection-preview` applies the same
operator, project, Origin/CSRF, candidate revision/commit and unbound-COLLECTING
checks. Its `reports` array accepts one to four reports: at most one `junit`,
one `coverage_xml` or `lcov`, one `sarif` and one `benchmark_json`.
Each has separate original collection time and
canonical base64 bytes. Duplicate bytes, duplicate format families and unknown
fields/formats fail strict validation. The browser form selects both test and
coverage reports, with optional security and performance reports before immutable
binding; the BFF also supports smaller selections without fabricating missing
families. SARIF tools are retained in the summary's embedded tool list and finding
metadata; benchmark tools come from the report. Envelope tool/version fields
remain required for compatibility but do not override these self-describing
formats (the UI sends `report-embedded` placeholders).

- Per-file 1 MiB, aggregate 2 MiB decoded; existing HTTP body cap is 4 MiB.
- Coverage XML allows at most 25,000 elements and depth 32 (Phase 56); the
  14,134-element retained AVS report fits. Exact 25,000/25,001-element tests
  cover acceptance/refusal. JUnit's 10,000-element limit is unchanged.
- Coverage XML: 25,000 elements/depth 32; LCOV: 10,000 lines. No new parser.
- SARIF/benchmark: 25,000 JSON nodes and depth 32; up to 32 SARIF runs and
  512 results, or 512 benchmark metrics. The final 512-record limit still applies.
- At most 512 normalized records per report; integer counts outside JavaScript's
  exact safe-integer range are rejected rather than displayed rounded. Use the
  CLI for larger reports. A rejection discards all normalized evidence from that
  report and blocks the entire assembly, never silently binding a subset.
- All reports must complete. Any warning requires explicit whole-selection
  retention. The page shows at most 25 records/issues per report with a visible
  count; more than 25 issues disables browser warning consent and directs to CLI.
- Each visible value is labeled with evidence kind and scope. Exact source
  hashes/sizes are checked against the selected files before offering binding.
- Preview returns `assembly_json` alongside the parsed assembly. The browser
  checks semantic agreement and submits this original JSON text inside the
  separately reviewed binding body. It must not reserialize fingerprint-bearing
  numbers (`50.0` becomes `50` in JavaScript). Existing backend fingerprint
  validation and historical canonicalization are unchanged.
- Phase 55 also returns `collection_json`: exact canonical strings for each
  collection receipt, whose hashes/sizes match `assembly.collections[].source`.
  Quick assessment preserves these strings with the selected raw report bytes
  for reviewed replay export. Neither preview nor binding stores originals.

This remains synchronous, nonpersistent collection of caller-provided reports.
It does not execute tests, verify report provenance, promote CI/hardware trust,
retain raw bytes, provide a durable task center, or run a third-party plugin.

### Reproduce the synthetic acceptance

Create a **new** disposable workspace with:

```powershell
python tools/manual_dashboard_collection.py work/my-combined-fixture --multi-report
```

Start a separate Dashboard using that database and an existing authorized local
trust store; activate an operator for `sample-api`. Do not reuse a real project
database. Inspect an unbound COLLECTING candidate and select **Collect standard
CI reports**. Use `examples/dashboard-multi-report/tests.xml` plus
`coverage.xml` (or choose LCOV and `coverage.info`). Enter caller-declared tool,
version and original UTC-offset time; confirm commit association.

Expected: 4 passing tests, repository line/branch coverage 1/2 = 50%, two
receipts; Cobertura yields seven evidence records including package/module
scopes. Preview changes no state. Review binding, confirm separately, advance
READY then EVALUATING, and import the generated candidate policy material.
The deliberately permissive **synthetic** policy expects at least 50% line
coverage and returns PASS. `coverage-low.xml` returns 0% and FAIL. Neither
result demonstrates production coverage, upstream AFE testing or hardware.

### Four-family synthetic tutorial

Use `python tools/manual_dashboard_collection.py work/my-standard-fixture --standard-reports`
to initialize a new isolated fixture. The files and expected outputs are in
[examples/dashboard-standard-ci](../examples/dashboard-standard-ci/README.md).
Select its test, coverage, SARIF and benchmark files in the same dialog, entering
the declared original time for each. Review binding separately, then READY,
EVALUATING and the generated policy-material JSON as in the existing workflow.

The complete selection yields four receipts and nine evidence records. The
six-rule synthetic policy expects nonempty passing tests, >=80% line coverage,
zero active SARIF findings and latency.p95 <=50 ms. Clean artifacts return PASS;
one active finding or 75 ms returns FAIL; missing required families return REVIEW.
Malformed reports block assembly, not merely produce a failing release decision.
See [actual browser acceptance](../reports/PHASE_49_STANDARD_CI_ACCEPTANCE.md).
