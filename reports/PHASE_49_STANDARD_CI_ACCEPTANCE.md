# Phase 49 — standard CI Dashboard collection

Date: 2026-09-08. Local uncommitted working-tree checkpoint above 81710fb,
preserving prior Phase 46–48 work. GitHub synchronization remains paused.

## Outcome and product direction

The existing Dashboard now accepts the four software evidence families in the
original product plan: JUnit, Cobertura/LCOV, SARIF 2.1.0 and versioned benchmark
JSON. It reuses the existing collectors, exact-byte preview, separately confirmed
binding, policy evaluation and reviewed durable jobs. No new runner, plugin
framework, scheduler or hardware control was introduced.

Private owned-process management/adoption is deferred until a concrete delivery
blocker justifies it. The next product priority is one real software-project
artifact handoff through assurance export/readback, not more recovery infrastructure.

## Delivered behavior

- One report per family, up to four; 1 MiB/report and 2 MiB/selection.
- SARIF and benchmark embedded tool identities are retained. Original collection
  times and declared commit association are not upgraded into authenticated origin.
- Every report must complete; unacknowledged warnings or rejected reports prevent
  assembly. No silently accepted subset. Preview remains nonpersistent.
- Reviewed binding checks exact source hashes/sizes and preserves canonical JSON
  numeric lexemes. Binding does not itself mark READY or PASS.
- Reviewed tasks accept the same selection and replay it using the existing
  foreground lease/checkpoint lifecycle; success does not bind a candidate.
- Request/result schemas and Dashboard OpenAPI updated together. No DB migration.
  New-format jobs/backups require a Phase 49-capable reader; old readers are not
  forward compatible.

## Expected versus actual

All new sample values are SYNTHETIC_HOST_ONLY, not production/hardware measurements.

| Case | Expected | Actual evidence |
|---|---|---|
| Baseline four reports | 4 receipts, 9 records; 4 tests pass, coverage 100%, active findings 0, latency 42.75 ms; six-rule PASS | Python policy test and actual Edge selection, preview, binding, READY/EVALUATING and policy import/evaluation |
| One active SARIF finding | Parser COMPLETE but engineering FAIL | Focused Python test |
| 75 ms latency, threshold <=50 ms | Parser COMPLETE but engineering FAIL | Focused Python test |
| Missing security or benchmark family | REVIEW | Two focused Python cases |
| Malformed SARIF/benchmark, either warning choice | No assembly | Four focused Python cases; actual Edge SARIF_RUNS_INVALID, no binding/override button |
| Four-family durable job | SUCCEEDED, five lease renewals, four receipts after reopening store; no candidate write | Focused Python job lifecycle/readback and frontend reviewed-submission test; not a new real-browser task-run claim |
| Alter fingerprint-bearing benchmark value | Binding rejected with HTTP 422; original exact assembly binds | Authenticated BFF test; not a browser interception claim |
| Invalid optional time/size/duplicate/aggregate | No outgoing preview | Seven new production-TypeScript host interaction cases |

The first focused run correctly withheld assembly because the synthetic coverage
file lacked branch data. The fixture was corrected to explicitly declare 2/2
branches, without weakening warning retention. Another focused run exposed the
old two-result task model limit: four-report jobs became FAILED. That limit was
updated alongside the request contract; the full lifecycle/readback case now passes.

## Verification

- 35 focused Python tests: 12 new standard-CI plus 23 existing multi-collection.
- 10 new frontend host cases; complete frontend suite **158 passed**.
- TypeScript check and production Vite build pass.
- Full tools/verify.py: **1,392 passed / 3 skipped**, **95.89%** branch-aware
  coverage, 13,049 statements / 3,406 branches; exit 0 and
  ForgeGate development verification: PASS.
- Three skipped tests require Windows symbolic-link creation unavailable in this
  environment. They are not recorded as passing.
- Ruff, formatting, strict mypy (116 source/tool files), packaged asset inventory,
  56 document / 3 artifact schemas and both OpenAPI drift gates pass.
- Existing interaction smoke: 33/33 expected CLI/API outcomes.
- Clean sdist/wheel installation: exit 0, ForgeGate release smoke: PASS.
  This includes the existing hardware-free optional MSP dependency import check,
  not a physical MSP run.

Local detailed logs are under ignored work/phase49-verify.log,
work/phase49-frontend.log and work/phase49-release.log. These logs are not GitHub
presentation assets and should not be published without a separate privacy review.

## Actual browser evidence

Microsoft Edge, isolated loopback server and a fresh synthetic operator identity.
No user database, running service, hardware connection or GitHub content changed.
The authenticated page retained four source hashes and nine records, then displayed
all six expected rule values. No captured console warnings/errors were present at
the decision checkpoint. An invalid SARIF remained COLLECTING/unbound with its
original two history events after closing preview.

- [Four-report binding review](phase49-browser/four-report-binding.png)
- [Six-rule synthetic PASS](phase49-browser/synthetic-six-rule-pass.png)
- [Malformed SARIF, no partial binding](phase49-browser/invalid-sarif-no-binding.png)

These are real screenshots of synthetic local application data, not mockups.
One full-page screenshot attempt timed out; a successful viewport capture contains
the decision and all six rows. No browser/OS-wide certification is claimed.
The test session was explicitly ended, test tab closed and only the owned
temporary server stopped; the test port no longer had a listener.

## Remaining boundaries

No real upstream scanner/benchmark invocation, authenticated CI provenance,
physical measurement, remote deployment, live adoption or accessibility
certification was performed. Existing user services were not restarted to load
this checkout. Follow the normal controlled startup procedure when promoting it
to the user's working instance.
