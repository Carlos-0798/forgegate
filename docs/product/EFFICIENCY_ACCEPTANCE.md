# Phase 53 — operator efficiency and decision accuracy

Date: 2026-09-08. Status: **PHASE 53B DEFERRED BY OWNER; HUMAN COMPARISON NOT RUN**.
The owner prioritized engineering workflow automation over formal human trials.
Phase 53A materials are retained for optional future use. Independent answer-key
review is required only if the human trial is resumed; it is not a gate for
Phase 54 engineering work. No measured efficiency/accuracy gains are claimed.
This is an engineering usability pilot, not a market study or a production claim.
The last accepted installed-wheel/browser checkpoint is
[Phase 52](../../reports/PHASE_52_WINDOWS_DELIVERY_ACCEPTANCE.md).

## Decision and scope

Determine whether ForgeGate reduces the work needed to assess and hand off a
version compared with a competent manual workflow. Optimize the largest observed
obstacle, then repeat the comparison. Do not add unrelated infrastructure to
complete this gate. No upstream test execution, crawling, hardware access or
GitHub publication is required.

The owner may be the initial participant. Record prior exposure to the code,
fixtures and answer key. Owner-only results describe a familiar-user pilot;
independent first-use acceptance requires a participant unfamiliar with the flow.
AI/browser automation and host tests are separate engineering checks and must
never be entered as human observations.

## Tasks and equal output requirements

| Task | Start | Finish and required output |
|---|---|---|
| T1 assess a version | Participant receives reports, expected commit, policy and instructions; tools are ready | Save decision or input-rejection status, blocking/missing rules, actual/expected values and source file/record references |
| T2 explain a blocker | Receive an already prepared assessment and its source reports | Identify the relevant report and value, explain the threshold or missing evidence, and state the next required action |
| T3 hand off and verify | Sender receives a completed assessment and originals; recipient has the same requirements | Recipient checks version, report identities and rule outcomes and saves a reproducible review record |

Record T3 sender and recipient time separately and combined. Owner acting as both
is a self-rehearsal, not independent handoff acceptance. T2 is a separate task;
do not add its duration to a T1 duration that already includes explanation.

Manual users may use familiar editors, search, report viewers, spreadsheets,
calculators and PowerShell hash commands. Supply the same plain-language policy
and source metadata to both arms. Record tools, versions, reusable templates and
pre-existing scripts. Time newly created scripts/templates as setup; do not make
the manual user implement ForgeGate's JSON schema or signature format. A folder
of originals, hash listing and a clear assessment table can satisfy the same
logical T3 deliverable as a ForgeGate export. Both must allow independent checking.
Evaluate a reader's reasoning, not matching UI labels or proprietary serialization.

Freeze the ForgeGate arm as Dashboard or CLI before a run; do not silently switch
to a faster interface after seeing results. Any help or interface switch is recorded.

## Case preparation and independent answer key

Reuse [standard CI examples](../../examples/dashboard-standard-ci/README.md)
and their [policy](../../examples/dashboard-standard-ci/policies/pull-request.yaml).
These are synthetic acceptance inputs, not executed scanner/benchmark results.
The assessor reads the raw files and policy to freeze the answer key before
running ForgeGate. Existing tests corroborate the key, but product output alone
must not define the expected answer. Keep answers away from the timed task sheet.

| Case | Change from four-report baseline | Expected disposition and reason |
|---|---|---|
| C1 | tests.xml, coverage.xml, clean.sarif, benchmark.json | PASS: four tests, no failures/errors; 100% line coverage >=80%; active findings 0; p95 42.75 ms <=50 |
| C2 | finding.sarif replaces clean.sarif | FAIL: active finding count 1 exceeds 0; not a confirmed vulnerability claim |
| C3 | benchmark-slow.json replaces benchmark.json | FAIL: p95 75 ms exceeds 50 ms |
| C4 | Omit security report | REVIEW: required security evidence missing; never invent zero findings |
| C5 | Omit performance report | REVIEW: required performance evidence missing |
| C6 | invalid.sarif replaces clean.sarif | INPUT REJECTED: malformed report; no partial binding or release PASS |

Use the same required commit in both arms. Add a separate T3 negative control:
verify a completed package against a different expected commit, then a modified
original byte. Both must refuse a valid/acceptable handoff; record exact product
error separately from the logical rejection. These controls do not prove that
declared source metadata or an original producer was authentic.

For timed trials, prepare two matched packs A/B with the same report families,
similar file sizes and equivalent rule difficulty but distinct values/names.
Hash every input and the independently reviewed answer key; record them in the
run sheet. `tools/prepare_efficiency_acceptance.py NEW_DIRECTORY` prepares a
no-overwrite participant/assessor split, neutral filenames, frozen run order,
input hashes and ForgeGate cross-check receipt. The answer key uses an explicit
rule oracle and is cross-checked against ForgeGate; independent human review is
still **NOT PERFORMED**. Do not edit real AVS reports
to manufacture variants. Previously seen examples may be used for training only.

Before a scored run, an assessor who will not participate in the blind trial
must review the raw reports and policy without using ForgeGate output, then compare
their recorded conclusions with `assessor/answer-key.json`. Record reviewer ID,
date, answer-key hash, agreement/discrepancies and disposition in a separate
private review note. Any discrepancy freezes trials until corrected and a new
no-overwrite pack is generated. Do not move the answer key into `participant`.

Use the frozen AVS report set as an additional realistic-scale rehearsal after
the synthetic pilot: four collections, 130 records, 12 rules, 10 PASS / 2 FAIL.
This is the historical Phase 50 baseline, not current AVS development state.
Do not combine its timing with small synthetic cases or rerun upstream tests.

## Measurement procedure

1. Record exact input/key hashes, expected commit, policy, ForgeGate source or
   wheel hash, machine/browser/tool versions, participant ID and prior exposure.
   Install/init/activation/training are setup. Use separate disposable workspaces
   and fresh candidates; preserve the user's running database and other projects.
2. Provide one untimed practice task per arm using non-scored materials. Record
   practice/setup time and freeze the task time limit before scored runs.
3. Start with six paired T1 trials spanning C1-C6. Alternate manual-first and
   ForgeGate-first; alternate A/B assignment. Freeze order before running. This
   small convenience sample supports descriptive pilot results only.
4. Start the elapsed timer at the defined task start. Stop when the participant
   submits an answer or reaches the limit. Retain the initial answer. Score it
   before showing feedback; record correction/rework time separately. Do not
   replace a wrong fast attempt with an unlabelled corrected successful attempt.
5. Record active human time (reading, typing, clicking, deciding), system wait,
   field entries, page/dialog transitions and assistance. Elapsed time includes
   normal app waits and recovery. Mark unrelated interruptions and retain their
   raw durations; any exclusion must be justified before aggregation.
6. Retain timeout, abandonment, errors and incomplete deliverables with reasons.
   Successful-only timing is supplementary; it cannot hide a worse completion
   rate. Report T2/T3 separately, using unseen matched materials and the same
   observation rules. A recorder may record actions but not solve timed cases.
7. Review the results, select at most two material bottlenecks and explain each
   proposed change. Preserve policy/integrity checks. Remeasure the revised arm
   on reserved matched inputs; do not overwrite the original measurements.

## Metrics and acceptance

| Primary metric | Calculation / source | Interpretation |
|---|---|---|
| End-to-end effort | Paired wall-clock seconds from run sheets; show each pair, median and range by task and completion status | Includes navigation and ordinary failures; backend latency alone is insufficient |
| Human workload | Active seconds per task; field entries and page/dialog transitions diagnose the difference | Screen recording with permission or observer notes; estimates must be labelled, never silently treated as exact |
| Correctness | Correct final dispositions / all scored attempts, with counts for wrong PASS, false blocking, and reason/source-reference errors | A disposition with the wrong explanation is not a fully correct task; blanks/timeouts are incomplete, not correct |

For a valid completed pair, savings = manual seconds - ForgeGate seconds;
relative savings = savings / manual seconds * 100 (manual time must be >0).
Report the median of paired percentages as such, not as the ratio of medians.
Include failures/completion counts alongside timing. No missing observation is 0.

Record setup and practice separately for each arm. If repeat use saves time,
report the number of uses needed to recover any extra ForgeGate setup time:
ceil(max(0, ForgeGate setup - manual setup) / positive repeat-task saving).
Use comparable per-task savings, disclose the small-sample estimate, and report
"no observed break-even" if there is no positive saving. Also show first-use total.

The improvement gate requires lower paired median elapsed and active time for
the declared primary task T1, without worse completion or correctness; all input
controls must reject unsafe acceptance. Report every pair and variability. Tiny
differences comparable to observation uncertainty are INCONCLUSIVE. No numeric
percentage target is invented before baseline measurement. Secondary-task gains
cannot silently replace a failed T1 goal. If both methods are fully correct,
claim correctness preserved, not increased accuracy.

Outcomes: **OBSERVED PILOT IMPROVEMENT**, **NO OBSERVED IMPROVEMENT**, or
**INCONCLUSIVE**, with participant/task/sample limits. None establishes population
significance, commercial superiority or real-world defect prevention rates.
Before data exists, outcome stays **NOT RUN**.

## Deliverables and exit gates

- Protocol and [blank observation record](EFFICIENCY_RUN_TEMPLATE.md): prepared.
- Matched A/B inputs, hashes and implementation-independent rule oracle:
  generated and machine-validated in the retained private Phase 53 pack;
  independent human key review pending.
- Human baseline/current-tool observations and scored outputs: pending.
- Bottleneck selection and bounded implementation, if needed: pending.
- Revised measurements, recorded limitations and a reproducible demo: pending.

Evidence must distinguish human observations, actual browser automation, host
tests and machine microbenchmarks. Keep raw reports, recordings and private paths
outside Git; review and redact exported presentation artifacts without rewriting
original measurements. A portfolio claim cites the exact scope and retained
evidence. Phase 53 remains open until operator observations and the resulting
improvement decision are reviewed; a passing development suite does not close it.
