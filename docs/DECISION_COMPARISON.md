# Comparing retained evaluations

The Decision page compares two explicitly selected evaluated candidates. It
reduces manual side-by-side report checking without adding a new evaluation
engine, permission scope, or release action. Human time savings remain unmeasured.

## Use

1. Open **Candidates**, inspect the candidate of interest, then **Review decision**.
2. In **Compare evaluations**, load baseline choices and select one explicitly.
   Choices are project-scoped, exclude the current/unevaluated candidates, and
   load in pages of 100. **Load more baseline choices** continues the list.
3. Select **Compare with current**. Both retained reviews are fetched again.
4. Check candidate IDs, commits and evaluation timestamps before reading changes.
   “Current” means the candidate on the page, not necessarily the latest run.
   Direction is chosen by the operator; reverse comparisons are allowed.

No baseline is chosen automatically. Changing selection clears the previous
comparison. Requests do not change candidates, bind evidence, evaluate policy,
attest, export, publish, or access hardware. Producer sessions can use the same
read-only comparison within their existing project scopes.

## Meaning of the results

| Result | Exact meaning |
|---|---|
| New failure | A rule changed from a non-FAIL decision to FAIL |
| Rule restored to PASS | A rule changed from FAIL to PASS; not proof that an individual defect was fixed |
| Now REVIEW / ERROR / PASS | Another decision transition, without claiming a resolved failure |
| Changed result | Decision is unchanged but the actual value or reason code changed |
| Unchanged | Decision, actual value and reason code match; evidence IDs, report contents and other metadata may still differ |
| Missing evidence | Current rule has `EVIDENCE_MISSING`; newly missing excludes rules already missing in the baseline |
| NOT COMPARABLE | Project, release track, profile/version, policy fingerprint/source bytes or retained references differ or are unavailable |

`ABSENCE_PERMITTED`, `STALE_OR_FUTURE_EVIDENCE` and `INSUFFICIENT_ASSURANCE`
are not counted as missing evidence. Original reasons and evidence IDs remain
visible in the comparison table. Numeric changes alone are not interpreted as
performance gains. A policy byte change blocks like-for-like conclusions even
if it only changes formatting; this is a deliberately conservative boundary.

## Limits and recovery

- This is a view of retained rule results, not policy re-execution, source-byte
  verification, producer authentication, a security finding tracker, or approval.
- Legacy/unbound reviews without matching retained policy authority are not
  compared. No migration or upgrade of historical records is implied.
- The comparison does not establish causal improvements or individual test/finding
  identity across runs. It does not compare hardware and software evidence as equals.
- Session, route and selection changes discard late results. Duplicate clicks
  do not start another pair. Failed requests clear old comparison results and
  permit an explicit retry; expired sessions use existing activation handling.
- Long evidence text uses the existing scrollable, paginated review table.
- This feature is in the current working-tree build. Older installed Windows
  packages need a separately verified update before they contain it.

Acceptance: [Phase 57](../reports/PHASE_57_DECISION_COMPARISON_ACCEPTANCE.md).
