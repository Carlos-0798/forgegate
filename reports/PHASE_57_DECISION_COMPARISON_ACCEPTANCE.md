# Phase 57 — retained evaluation comparison

Date: 2026-09-08 (Windows local date). Status: **LOCAL ACCEPTANCE PASS**.

## Outcome

The Decision page now compares an explicitly chosen baseline with the selected
candidate. It shows new failed rules, rules restored to PASS, changed results,
and missing evidence. Matching project/profile/track and exact policy authority
are required before making regression or recovery statements.

Implementation reuses the authorized candidate list and assurance-review GET
endpoints. No backend model, permission, policy engine or API schema was added.
See [user guidance](../docs/DECISION_COMPARISON.md) and the
[machine-readable evidence](PHASE_57_DECISION_COMPARISON_EVIDENCE.json).

## Actual Windows Edge acceptance

The three original Phase 54 candidates were reused as retained **SYNTHETIC**
results; no upstream producer tests were rerun. A fourth control candidate was
created through the normal local application lifecycle with the same failing
evidence but a changed policy expectation. Source packs and old candidates were
not edited. Comparisons themselves use GET only.

| Comparison | Expected and observed browser result |
|---|---|
| Normal → failed security-summary rule | 1 new failure; `security-clean` actual 0 → 1, expected 0 |
| Failed → normal rule (explicit reverse comparison) | 1 rule restored to PASS; actual 1 → 0, expected 0; no defect-fix claim |
| Normal → missing benchmark evidence | 1 newly missing rule; `latency-bound` actual 42.75 → null, expected 50; PASS → REVIEW |
| Failing evidence → same evidence under changed policy | NOT COMPARABLE; actual remains 1 but expected changes 0 → 1; no recovery claim |

Retained evaluation objects were independently read back with Python and
asserted against these values. The normal/failure comparison reports six rules,
five unchanged and one newly failing. Candidate IDs, evaluation IDs and policy
fingerprints are recorded in the evidence JSON.

Screenshots (unmodified captures; hashes in evidence JSON):

- [New failure](phase57-browser/new-failure.png)
- [Rule restored](phase57-browser/restored-rule.png)
- [Missing evidence](phase57-browser/missing-evidence.png)
- [Different policy](phase57-browser/not-comparable.png)

The first browser locator attempt using an exact implicit label did not match.
The accessibility tree showed the correct combobox name; role/name selection
worked. This was an automation locator issue, not a demonstrated accessibility
defect, and no speculative product patch was made. This acceptance is not a new
screen-reader, remote-desktop or full zoom-matrix certification.

## Automated verification

- `npm run check:dashboard`: PASS.
- `npm run test:dashboard`: **248 passed**, including **38 new** comparison cases.
- Cases include policy/profile/identity mismatches, missing documents, duplicate
  rules, altered expectations, explicit pagination, permitted absence, late
  session/route/selection responses, duplicate clicks, HTTP 403/404/500 and retry.
- `npm run build:dashboard` and asset inventory: PASS.
- `python tools/verify.py`: **1,433 passed / 3 environment skips**, 95.80%
  branch-aware coverage; lint, formatting, typing, interaction smoke and
  committed schema/OpenAPI checks PASS.
- `python tools/release_smoke.py`: **PASS**, exit 0; fresh source distribution,
  clean-install wheel, packaged resources and optional dependency checks.

The release smoke includes intentional rejection outputs; its final PASS and
exit code establish the result. Package hashes and the tested JavaScript hash
are recorded in the evidence JSON. Documentation was aligned after these gates;
the smoke archive is not claimed to include the final acceptance write-up.

## Product and evidence boundaries

This removes manual pairing of rule decisions/actual values/reasons in the
supported workflow. No quantified efficiency or accuracy improvement is claimed.
No hardware was accessed, no AVS code was changed, and no GitHub operation was
performed. The existing installed Dashboard was not upgraded. The feature was
tested from the working-tree build served by the local synthetic acceptance
service; the smoke establishes separate packaging evidence.

Recommended next slice: refresh the Windows delivery package and verify the
installed workflow with the accumulated quick-assessment and comparison changes,
without adding unrelated platform modules.
