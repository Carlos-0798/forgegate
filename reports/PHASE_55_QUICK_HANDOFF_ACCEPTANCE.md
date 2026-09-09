# Phase 55 repeated-use quick handoff acceptance

Date: 2026-09-08  
Scope: local Windows working tree; synthetic report fixtures

Status: **IMPLEMENTED; AUTOMATED AND BROWSER ACCEPTANCE PASS**

## Delivered outcome

Quick assessment now supports explicitly selecting a compatible policy already
retained in the workspace, followed by saving the original reports and exact
collection receipts as a private replay ZIP from the completed assessment.
The report batch is selected once. The existing assurance-only export remains
available in the same dialog. This removes repeated file selection and manual
receipt gathering; no human time-saving percentage is claimed.

The read-only policy lookup matches project, frozen profile ID/version and
release track, validates retained histories, deduplicates by material ID and
returns ten choices plus a truncation indicator. An operator must choose;
first-use and unavailable-history cases retain the policy-file path. Previously
stored policy material is not an endorsement of the policy's engineering quality.
The existing authoritative evaluation checks remain in force.

Raw reports are held in browser memory, and preview now supplies exact canonical
receipt strings. Before offering replay, the client checks their complete
hash/size mapping against assembly references. Reviewed export then independently
validates them on the server. Numeric spelling is preserved rather than rebuilt
through JavaScript number serialization. No database migration or generic policy
registry was introduced.

## Verification record

- Final `python tools/verify.py`: exit 0 / development verification PASS;
  1,430 tests passed, three Windows symlink-permission skips, 95.80% branch-aware
  coverage. Lint, formatting, type checks, asset inventory and exported contracts
  passed. `npm run test:dashboard`: 200 passed; TypeScript check/build passed.
- `python tools/release_smoke.py`: exit 0 / release smoke PASS, including a fresh
  sdist-derived wheel and isolated install. Runtime/assets match this acceptance;
  final documentation was updated after the build. This is not a clean-commit
  release artifact.
- Five new Python integration cases cover independently replayed PASS, FAIL and
  REVIEW decisions, exact receipt bytes, unchanged history on lookup, anonymous/
  producer/cross-project/foreign-origin denial, and frozen-profile isolation.
- Seven new frontend cases cover saved-policy selection, exact policy numeric
  bytes, invalid/mismatched selections, stale sessions, prepared source files,
  required privacy review, changed receipts and suppressed late export.
- Actual Windows Edge acceptance used an isolated sample-api fixture workspace,
  not the owner's active MSP430 or AVS database.
- Full verification results and artifact hashes are recorded in the
  [machine evidence](PHASE_55_QUICK_HANDOFF_EVIDENCE.json).

The first full regression run found one outdated exact OpenAPI path-set assertion
after adding the policy-choice route (1 failure, 1,429 passes, 3 skips). The
exported schema and contract assertion were aligned; this was not hidden or
converted to a skip. The targeted contract test passed before the full rerun.

## Actual browser input and output

1. Opened an unbound fixture candidate and loaded one compatible saved policy.
   Selected it from the dropdown; no policy file was uploaded.
2. Selected `tests.xml`, `coverage.xml`, `clean.sarif` and `benchmark.json` from
   `examples/dashboard-standard-ci` once. Preview showed four completed
   collections and nine records: four tests, zero failures/errors, 100% line
   coverage, zero active findings and latency 42.75.
3. Confirmed assessment. All six rules passed; the retained candidate reached
   revision 4 and an unsigned-local attestation was available.
4. Selected **Save originals for offline replay**, reviewed the eight already
   prepared files, checked privacy confirmation and downloaded the ZIP without
   reopening a file chooser. Download size: 50,096 bytes.
5. Ran the independent replay CLI on that actual browser download with the
   expected fixture commit. It returned **VALID / PASS**, four replayed
   collections, nine evidence records and eight source files.
6. Returned to Quick assessment, opened the ordinary assurance export and
   completed its browser download too. Browser error/warning log inspection
   returned no entries during this acceptance run.

The six rule expectations remain tests-failed = 0, test-errors = 0, test-count > 0,
line-coverage >= 80, active-findings = 0, and latency <= 50. These numbers are
synthetic test inputs, not measured production performance.

Screenshots: [assessment result](phase55-browser/assessment-pass.png) and
[reviewed replay download](phase55-browser/replay-downloaded.png). Exact hashes,
candidate identity and replay identifiers are retained in the machine evidence.

## Operational limits and next useful acceptance

Save the replay ZIP before closing Quick assessment or navigating away. Browser
memory is not durable server storage. Existing limits include receipts: 1 MiB
per file and 2 MiB total. If preparation is incomplete or exceeds those limits,
assessment can still proceed with an explanatory separate-export fallback.
Privacy confirmation remains mandatory because originals may contain sensitive
data. Source replay reparses reports; it does not rerun the producer's tests or
authenticate their origin.

The current runtime and regression suite are Windows local acceptance, not a
clean-commit release or hardware/production verification. Human efficiency
measurement remains deferred. GitHub synchronization remains paused.

Next: run this shorter handoff against the retained real AVS host-report set,
preserving its producer failure and commit metadata. Extend formats only if a
real input requires it; do not add an unrelated platform subsystem.

See the [operation guide](../docs/QUICK_ASSESSMENT.md).
