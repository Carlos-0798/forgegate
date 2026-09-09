# Standard CI evidence tutorial

All files in this directory are hand-authored **synthetic acceptance inputs**.
They are not results from executing tests, a security scanner, a benchmark or hardware.
The example.invalid repository and repeated-a commit are intentional placeholders.

Use the existing Dashboard flow: select reports, preview, review immutable binding,
confirm, mark READY, begin EVALUATING, import the profile-authorized policy material,
then confirm evaluation. An already-bound candidate cannot have evidence appended;
create another candidate for a different complete evidence selection.

Prepare a new isolated workspace:

```powershell
python tools/manual_dashboard_collection.py work/my-standard-fixture --standard-reports
```

This creates a database and candidate policy-material JSON files, but does not
create an identity or start a server. Start the Dashboard with that database and
your authorized local trust store, activate an operator scoped to sample-api,
then inspect one COLLECTING candidate and choose **Collect standard CI reports**.
Use tests.xml, coverage.xml, clean.sarif and benchmark.json. Declare synthetic
tool/version for test and coverage inputs and a nonfuture UTC-offset original
time for each input (for example 2026-09-04T12:00:00Z).

| Selection/change | Expected normalized value | Policy/collection outcome |
|---|---|---|
| Four baseline files | 4 passing tests; line/branch 2/2=100%; active findings 0; latency.p95 42.75 ms | PASS under the six-rule synthetic policy |
| Replace clean.sarif with finding.sarif | Active findings 1 | Collection COMPLETE, policy FAIL |
| Replace benchmark.json with benchmark-slow.json | latency.p95 75 ms vs limit 50 ms | Collection COMPLETE, policy FAIL |
| Omit security or performance report | Required family absent | REVIEW, never invented zero/PASS |
| Replace clean.sarif with invalid.sarif | Invalid runs value | SARIF REJECTED; no assembly or partial binding |

Successful baseline collection has four receipts and nine evidence records.
The permissive unsigned_local / declared thresholds are for teaching only.
Production policies must set their own tool, trust, verification, freshness and
engineering thresholds. A clean SARIF does not establish that a scan actually ran.
The benchmark schema is ForgeGate's versioned format, not arbitrary benchmark JSON.

Keep original artifacts: synchronous preview/binding does not retain raw files.
The separate **Prepare standard CI task** flow retains raw bytes privately until
a terminal state, requires another execution confirmation, and never binds automatically.
See [contract](../../docs/DASHBOARD_COLLECTION_CONTRACT.md) and
[acceptance](../../reports/PHASE_49_STANDARD_CI_ACCEPTANCE.md).
