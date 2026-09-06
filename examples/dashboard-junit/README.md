# Synthetic JUnit browser acceptance fixture

These hand-authored reports are test inputs, not results from real software or
hardware. The fixture policy deliberately accepts `unsigned_local` / `declared`
records to exercise workflow decisions. It does not replace or weaken the
canonical sample project's CI policy.

| Report | Expected collection | Expected fixture-policy result |
|---|---|---|
| pass.xml | 4 total, 4 passed, no warnings | PASS |
| fail.xml | 4 total, 2 passed, 1 failed, 1 skipped | FAIL |
| warning.xml | 1 observed case, count mismatch and missing duration | No assembly until warnings explicitly retained |
| rejected.xml | Forbidden DOCTYPE; referenced URI never fetched | REJECTED; no assembly or binding |

Run `python tools/manual_dashboard_collection.py work/my-new-junit-fixture` to
create an isolated database with four COLLECTING candidates and exact policy
material. The destination must not exist. No keys are generated and no server
or hardware is started. Use your authorized `sample-api` operator trust store
to start a separate loopback Dashboard against that database.

In Candidates, inspect a fixture, choose **Collect JUnit report**, select its
XML file, enter `synthetic-junit-fixture` / `1.0`, and supply an explicit fixture
time with UTC offset that is not in the future. The commit is forty `a` characters,
an explicit synthetic association. Preview alone must not bind evidence.

Review counts and SHA-256, then separately review and confirm binding. Continue
READY and EVALUATING confirmations, import the generated matching
`*-policy-material.json`, and confirm evaluation. Review Decision and Assurance.
Retain the original XML yourself: the service stores normalized binding metadata,
not uploaded source bytes. A restart discards unbound previews.
