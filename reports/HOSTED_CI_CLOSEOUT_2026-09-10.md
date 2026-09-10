# Hosted CI and source-publication closeout — 2026-09-10

## Current decision

**PENDING — the repository remains Private.** The owner explicitly authorized
Public source visibility after complete hosted CI acceptance and closeout.
This record does not yet establish a passing corrected cloud run or anonymous
Public access. New engineering features remain paused for job preparation.
License, packaged GitHub Release, redistribution and LinkedIn publication are
separate from this source-visibility decision.

The owner enabled a new cloud-run budget and requested execution. Unlike the
earlier account-blocked attempts, [run 34533073332](https://github.com/Carlos-0798/forgegate/actions/runs/34533073332)
actually started Python 3.12 jobs on Windows, Ubuntu and macOS for source
`7cd841f7023272b25b3fe4f34bfb0b06e157419a`. The completed run failed: Ubuntu and
macOS each recorded 1 failed / 1,565 passed / 6 skipped; Windows recorded
3 failed / 1,569 passed / 0 skipped. The package and dependent generic Action
smokes were skipped. This is neither a budget-only failure nor a full hosted PASS.

## Encountered failures and bounded corrections

All three corrections are confined to tests. Product implementation, dependency
constraints, workflow triggers, negative-input rejection and gate exit semantics
are unchanged; failed checks are not disabled.

| Finding | Cause and correction | Verification boundary |
|---|---|---|
| Help-option assertion fails with hosted terminal color | ANSI sequences can split a visually correct option string. The help test now decodes ANSI before checking the exact options, and explicitly exercises plain and forced-color output. | `tests/test_monitor_preset_cli.py`; the options and successful exit codes remain asserted. Complete corrected hosted acceptance is pending. |
| Job Summary displays an expected `GITHUB_COMMIT_MISMATCH` as an apparent release error | An intentional negative CLI test inherited the enclosing runner's summary destination. The module now isolates inherited command-file paths; the secondary-write failure test writes to its own temporary summary and asserts the original mismatch, secondary failure, exit 3 and exact error-summary content. | `tests/test_github_actions.py`; before the fix, the test passed but changed an external summary sentinel. After the fix, 12 passed / 1 Windows symlink skip and both external summary/output hashes were unchanged. Environment fallback remains tested with temporary destinations. |
| Two Windows launcher rejection tests fail in the hosted environment | The tests did not supply the running test interpreter to the PowerShell launcher. They now pass explicit `-Python` with `sys.executable`, retaining the missing-input, occupied-port and empty-database assertions. | `tests/test_dashboard_runtime.py`; isolated reproduction and the 28-case local launcher suite pass. The completed hosted trace confirms that both tests reached the missing-Python error before their intended rejection branch. |

The misleading summary is distinct from a real test failure: a deliberately
rejected fixture wrote to the wrong **test environment destination**. Production
`github-gate` still rejects wrong commits and writes its genuine configured
summary/output. The separate generic Action smoke evaluates a named synthetic
fixture, not the ForgeGate repository revision's release suitability.

## Verification status

- Intermediate full local verification after the first two test corrections:
  1,571 passed, 3 environment skips, 95.89% branch-aware combined coverage.
  This predates the final launcher correction and is not acceptance of that
  complete change set.
- Fresh full local verification of all three corrections: **PASS**;
  1,571 passed / 3 environment skips, 95.89% branch-aware combined coverage,
  33/33 interaction checks, lint/format, typing, schemas and both OpenAPI
  contracts passed. The configured 95% coverage floor is unchanged.
- Corrected source commit, full hosted matrix, clean-package smoke and dependent
  generic Action job: **PENDING**.
- Failed run 34533073332: complete log archive and 3 annotations screened;
  zero targeted privacy-pattern findings. Archive SHA-256:
  `7da5ef34987d03e3f739294f814ad212eb923cd9337682246f1c79cc97dd7e58`.
  Corrected-run log review and final public-page readback: **PENDING**.
- Public visibility change and anonymous-access verification: **NOT PERFORMED**.

Original Phase 64 product, frontend, package and browser results retain their
recorded dates and scopes. No board, producer-project, independent novice,
spoken screen-reader, high-contrast, Remote Desktop or human-efficiency retest
is implied by this CI maintenance work. Counts from separate checkpoints are
not additive.

## Reused publication evidence

The pre-publication inventory at source `7cd841f` covers 117 locally reachable
commits, 2,213 blob objects and 675 current tracked paths after fetching origin
refs. It reports no targeted privacy-pattern finding or identity mismatch;
all 92 reachable image blobs belong to the current image inventory and all 91
detected binary blobs are those current raster images. This is a bounded review
of the inspected refs, not unreachable server objects or third-party copies.

The earlier [portfolio closeout](GITHUB_PORTFOLIO_CLOSEOUT_2026-09-10.md) and its
[image receipt](GITHUB_PORTFOLIO_CLOSEOUT_EVIDENCE_2026-09-10.json) retain individual
original-resolution review of 91 rasters plus separate SVG source review. Image
identities are unchanged; no screenshot is regenerated or claimed as a new
application run. Hidden metadata, steganography, cropped or blurred content are
not certified by visual review.

The retained historical hosted review attempted 75 run logs: 60 available logs
had no targeted finding, while 15 logs were unavailable. Their 60 job records
and 43 annotations were reviewed separately. Missing logs remain unavailable,
not PASS or proof that no steps executed. New run logs require their own review.
Earlier Private/no-cloud-run notes describe their original authorization and
evidence checkpoints, not the owner's current conditional Public approval.

This review does not establish exhaustive secret/security clearance, production
readiness or an open-source license. The
[engineering resumption checkpoint](../docs/PROJECT_RESUME_CHECKPOINT_2026-09-09.md)
remains the continuation plan after job preparation.
