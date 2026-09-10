# Hosted CI and source-publication closeout — 2026-09-10

## Current decision

**ACCEPTED FOR PUBLIC-SOURCE PORTFOLIO — complete hosted CI passed.** The owner
explicitly authorized Public source visibility after hosted acceptance and
closeout. [Run 34537416870](https://github.com/Carlos-0798/forgegate/actions/runs/34537416870)
passed all four jobs at `f2ba63d055ab93a437a5de73b697b84d2afacd07`.
For the final merged revision, actual visibility transition and unauthenticated
access results, consult the post-publication completion comment on
[PR #17](https://github.com/Carlos-0798/forgegate/pull/17).
This pre-publication report does not substitute for that execution receipt.
New engineering features remain paused for job preparation.
License, packaged GitHub Release, redistribution and LinkedIn publication are
separate from this source-visibility decision.

The closeout documentation commit follows the tested revision and changes only
Markdown files. Runtime, tests, verification tools, assets, dependencies and the
manual-only workflow are identical to the tested revision; the later commit is
not claimed to have executed in that cloud run. GitHub Actions remains opt-in
through `workflow_dispatch`; publishing source does not enable automatic runs.

The owner enabled a new cloud-run budget and requested execution. Unlike the
earlier account-blocked attempts, [run 34533073332](https://github.com/Carlos-0798/forgegate/actions/runs/34533073332)
actually started Python 3.12 jobs on Windows, Ubuntu and macOS for source
`7cd841f7023272b25b3fe4f34bfb0b06e157419a`. The completed run failed: Ubuntu and
macOS each recorded 1 failed / 1,565 passed / 6 skipped; Windows recorded
3 failed / 1,569 passed / 0 skipped. The package and dependent generic Action
smokes were skipped. This is neither a budget-only failure nor a full hosted PASS.

## Encountered failures and bounded corrections

The corrections are confined to tests and release-smoke verification tools.
Product implementation, dependency constraints, workflow triggers,
negative-input rejection and gate exit semantics
are unchanged; failed checks are not disabled.

| Finding | Cause and correction | Verification boundary |
|---|---|---|
| Help-option assertion fails with hosted terminal color | ANSI sequences can split a visually correct option string. The help test now decodes ANSI before checking the exact options, and explicitly exercises plain and forced-color output. | `tests/test_monitor_preset_cli.py`; the options and successful exit codes remain asserted. Both modes pass in the complete corrected hosted run. |
| Job Summary displays an expected `GITHUB_COMMIT_MISMATCH` as an apparent release error | An intentional negative CLI test inherited the enclosing runner's summary destination. The module now isolates inherited command-file paths; the secondary-write failure test writes to its own temporary summary and asserts the original mismatch, secondary failure, exit 3 and exact error-summary content. | `tests/test_github_actions.py`; before the fix, the test passed but changed an external summary sentinel. After the fix, 12 passed / 1 Windows symlink skip and both external summary/output hashes were unchanged. Environment fallback remains tested with temporary destinations. |
| Two Windows launcher rejection tests fail in the hosted environment | The tests did not supply the running test interpreter to the PowerShell launcher. They now pass explicit `-Python` with `sys.executable`, retaining the missing-input, occupied-port and empty-database assertions. | `tests/test_dashboard_runtime.py`; isolated reproduction and the 28-case local launcher suite pass. The completed hosted trace confirms that both tests reached the missing-Python error before their intended rejection branch. |
| macOS clean-package checks reject temporary aliases | The second hosted run passed the macOS development gate, then hit the real replay-export guard because `/var` is an alias. The third run passed that export but reached the same class of error in a child Dashboard-pair smoke. The parent and all five direct smoke helpers now strictly resolve their own already-created temporary roots before store activity. | `tools/release_smoke.py`, the Dashboard runtime/pair, collection-job, workspace-backup and adoption-preflight helpers, and `tests/test_release_smoke.py`. Six real junction/symlink regressions cover the parent and helper roots; the original failure-exit test is retained. A complete Windows release-smoke chain also passes with child-only aliased TEMP/TMP/TMPDIR. Production anti-link checks are unchanged. |

The misleading summary is distinct from a real test failure: a deliberately
rejected fixture wrote to the wrong **test environment destination**. Production
`github-gate` still rejects wrong commits and writes its genuine configured
summary/output. The separate generic Action smoke evaluates a named synthetic
fixture, not the ForgeGate repository revision's release suitability.

## Accepted verification

All rows below refer to run **34537416870**, source
`f2ba63d055ab93a437a5de73b697b84d2afacd07`, Python 3.12.

| Hosted job | Python regression | Branch-aware combined coverage | Frontend regression | Development / clean-install gate |
|---|---|---|---|---|
| Windows | 1,580 passed; 0 skipped | 95.90% | 296 passed; 0 failed | PASS / PASS |
| Ubuntu | 1,574 passed; 6 Windows-only skips | 95.90% | 296 passed; 0 failed | PASS / PASS |
| macOS | 1,574 passed; 6 Windows-only skips | 95.90% | 296 passed; 0 failed | PASS / PASS |
| Generic assurance Action fixture | Stable outputs asserted: `VALID`, `PASS`, `unsigned_local` | Not applicable | Not applicable | PASS; synthetic fixture, not repository release approval |

The six Unix skips cover actual Windows PowerShell and junction behavior; those
checks execute in the Windows job. The complete development gate includes
typing, lint/format and schema/OpenAPI checks. Frontend typecheck, tests, build,
asset inventory and generated-file drift checks passed on all three platforms.
The dependency audit reported no known vulnerabilities in its inspected package
set; this is not exhaustive vulnerability clearance. Non-blocking third-party
deprecation and Node experimental-feature warnings remain visible in the logs.

The complete log archive and all check annotations were captured and screened:
**0 annotations; 0 targeted privacy-pattern findings**. Archive SHA-256:
`f4b87aee216e4130bcfd94d741e02e718746aabc280d405cacb13ed0889cc868`.
The raw local copies are retained outside tracked publication content; the
GitHub run provides the inspectable execution record. Targeted screening is
not exhaustive secret or security certification.

## Verification history and local cross-checks

- Intermediate full local verification after the first two test corrections:
  1,571 passed, 3 environment skips, 95.89% branch-aware combined coverage.
  This predates the final launcher correction and is not acceptance of that
  complete change set.
- Full local verification of the first three corrections (`728250e`): **PASS**;
  1,571 passed / 3 environment skips, 95.89% branch-aware combined coverage,
  33/33 interaction checks, lint/format, typing, schemas and both OpenAPI
  contracts passed. The configured 95% coverage floor is unchanged.
- Intermediate local development and clean-package gates after the parent smoke-path
  correction: **PASS**. Full development verification recorded 1,572 passed /
  3 environment skips, 95.89% coverage and 33/33 interaction checks. The complete
  clean-install release smoke also passed. This locally built working-tree
  package is not a published installer or GitHub Release.
- Second hosted run [34534606028](https://github.com/Carlos-0798/forgegate/actions/runs/34534606028)
  targets `728250eb8f6005c92b04c9352b9964a5225781b6`. Windows and Ubuntu completed both gates;
  macOS completed development verification but failed package replay export at
  the path guard described above. Its dependent Action job was skipped;
  this run is not overall PASS. Its complete logs and 1 annotation have zero
  targeted privacy-pattern findings; archive SHA-256:
  `8f0211be1885e11876c5bae1a4fc9f82464e87ac2b53b936e7f9b5ccd7694e4e`.
- Third hosted run [34536129723](https://github.com/Carlos-0798/forgegate/actions/runs/34536129723)
  targets `3c81b42bf0976214d471a3d0f9b0d57fafccddfc`. Windows and Ubuntu completed
  both gates. macOS passed development verification and the package replay
  export but failed the child pair-startup smoke; the dependent Action job
  was skipped and the whole run is not PASS. Its complete logs and 1 annotation
  have zero targeted privacy-pattern findings; archive SHA-256:
  `813cbb666dacc0b8866d23b11db279d02fff6010be56e3051f77e5d9e820e6e8`.
- Final full local verification after all five child-helper corrections:
  **1,577 passed / 3 environment skips, 95.89% coverage**, 33/33 interaction
  checks and the complete development gate PASS. Complete clean-package smoke
  with aliased child-process temporary roots: **PASS / exit 0**. User/system
  environment variables were not changed. This is a Windows alias reproduction,
  supplemented by the successful macOS hosted gate above.
- Failed run 34533073332: complete log archive and 3 annotations screened;
  zero targeted privacy-pattern findings. Archive SHA-256:
  `7da5ef34987d03e3f739294f814ad212eb923cd9337682246f1c79cc97dd7e58`.
- Actual Public visibility and anonymous-access readback are separate execution
  checks. Consult the final PR #17 completion receipt rather than infer those
  results from authenticated access or this hosted test result.

Original Phase 64 product, frontend, package and browser results retain their
recorded dates and scopes. No board, producer-project, independent novice,
spoken screen-reader, high-contrast, Remote Desktop or human-efficiency retest
is implied by this CI maintenance work. Counts from separate checkpoints are
not additive.

## Reused publication evidence

The pre-publication inventory at source `f2ba63d` covers 120 locally reachable
commits, 2,234 blob objects and 676 current tracked paths after fetching origin
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

The remote presentation review covered 16 preceding PR titles/bodies and
8 discussion comments, with no targeted privacy-pattern findings. Wording
corrections distinguish tool-operated browser checks from human acceptance and
separate scoped code review from external human peer approval. PR #17 records
the present corrections and their exact verification scope. Repository About
and topics were reviewed; no new AI disclosure or unverifiable ownership claim
was introduced.

This review does not establish exhaustive secret/security clearance, production
readiness or an open-source license. The
[engineering resumption checkpoint](../docs/PROJECT_RESUME_CHECKPOINT_2026-09-09.md)
remains the continuation plan after job preparation.
