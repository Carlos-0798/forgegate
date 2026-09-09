# Phase 54 quick assessment acceptance

Date: 2026-09-08
Status: **IMPLEMENTED; AUTOMATED AND BROWSER ACCEPTANCE PASS**

## Outcome and product purpose

This bounded change shortens report reconciliation and release handoff without
adding a platform subsystem. Candidates now offers Quick assessment: create a
candidate, select one report batch, inspect parsed evidence, explicitly authorize
binding/readiness/evaluation/attestation, and review the existing assurance download.
Format selection is content-derived. One execution confirmation replaces the
separate command dialogs; authorization, immutable binding, rule evaluation and
audit still use existing server endpoints. This is a workflow improvement, not a
measured human time-saving or accuracy percentage.

Phase 53B human comparison is deferred by owner. Its prepared materials remain
available; no human trial has been silently marked complete.

## Verification

- `python tools/verify.py`: exit 0, 1,425 passed / 3 environment skips,
  development verification PASS; branch-aware coverage 95.80%. Existing
  uncommitted work was preserved.
- `npm run test:dashboard`: 193 passing, including 25 new quick-assessment tests.
  Production TypeScript is exercised through the DOM/HTTP harness; this is not
  a real browser or an independent backend integration test.
- TypeScript checking, Dashboard build and asset inventory verification pass.
- `python tools/release_smoke.py`: final clean-environment installation and
  release smoke PASS for the corrected packaged Dashboard asset.
- New checks cover four terminal decisions, seven interrupted chain positions,
  duplicate/oversized/unknown/changed reports, wrong profile, future time,
  conflicting inputs, hash/assembly mismatch, warnings/rejections, session change,
  double submission and folder/LCOV input handling.

## Actual browser and persisted output

Edge used an isolated loopback fixture database, declared synthetic reports and
a sample-api-only operator. No hardware or upstream producer tests ran.

| Scenario | Expected | Observed |
|---|---|---|
| DRAFT plus JUnit/Cobertura/clean SARIF/benchmark | PASS | PASS, revision 4, six passing rules, attestation and downloaded assurance |
| Same inputs except one active SARIF finding | FAIL | FAIL, revision 4, five passing rules and security-clean FAIL: actual 1, expected 0 |
| Downloaded PASS assurance | Offline VALID with decision PASS | VALID / PASS after extraction under required assurance-digest directory name |
| Folder selection / missing performance report | Complete browser preview then REVIEW | REVIEW, revision 4; latency-bound alone reports actual null / expected 50; attestation retained |
| Rejected-report quick path | Stop before binding | Invalid SARIF rejected; candidate remains COLLECTING revision 1 with no evaluation or partial binding |

Database readback independently confirmed PASS, FAIL and REVIEW terminal outcomes.
The rejected-report candidate remained COLLECTING revision 1 without evaluation.

PASS input values: four tests, zero failures/errors, 100% line coverage, zero
active findings, latency 42.75 against an upper bound of 50. The FAIL seed's
historical label is `junit-fail-fixture`, but this run intentionally fails SARIF,
not JUnit. These are fixtures, not measured production/scanner performance.

[Machine evidence](PHASE_54_QUICK_ASSESSMENT_EVIDENCE.json) retains identifiers and
download hashes. [Actual FAIL screenshot](phase54-browser/quick-fail.png) shows
the final rule results and handoff action. The
[final rejection screenshot](phase54-browser/quick-rejected-final.png) retains the
specific safe-stop message. Browser error/warning console inspection was empty.
The PASS run preceded presentation-only label/result-detail fixes; FAIL used the
preceding packaged asset and rejection used the final packaged asset.

## Findings, limits and remaining work

- Corrected normalized-record display from an absent `type` to actual `kind`;
  a regression assertion covers the displayed semantic label.
- Preserved completed-step text when showing an error instead of replacing it.
- Verified that extraction into an arbitrary folder fails the assurance naming
  check; documented the required ZIP-basename directory and reverified VALID.
- A browser-control interruption initially blocked the folder test. A fresh Edge
  tab subsequently completed the same directory chooser successfully; this is a
  Windows Edge test, not proof for other browsers or operating systems.
- Corrected rejected/warning batch presentation so the specific collector issue
  is followed by `DASHBOARD_QUICK_REPORT_REVIEW_REQUIRED`, not the misleading
  generic unexpected-browser-error panel. Real Edge and regression tests pass.
- ZIP import, automatic policy selection, background execution and automatic
  source-byte retention are not added. Keep originals for source replay.
- This is sequential, not transactional. A late failure preserves earlier writes;
  there is no automatic retry, rollback or hidden success. Policy semantic checks
  remain authoritative on the server and can fail after binding.
- Windows Local Alpha only; no hardware, human assistive-technology, independent
  operator, production, authenticated-origin or efficiency-gain claim.
- No GitHub synchronization, commit, release, visibility or license change.

See [operation guide](../docs/QUICK_ASSESSMENT.md) for inputs and recovery.
