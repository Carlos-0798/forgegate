# Windows Alpha feature freeze and completion plan

Effective: 2026-09-09. Owner-approved direction: feature freeze, code closeout,
real-project acceptance, then a final reproducible demonstration.

Historical plan: after these gates completed, the owner reopened scope for an
independent product reassessment. The current work is described at the top of
[Roadmap](ROADMAP.md). The freeze below documents the Phase 59-61 decision; it
does not override that newer authorization.

## Product objective and frozen scope

ForgeGate helps a Windows engineering user turn existing test, coverage, static
analysis and benchmark reports into an explainable, reviewable release decision.
Its demonstration must show exact input association, useful failure reasons,
retained comparison and an independently verifiable handoff.

The frozen baseline is the integrated Phase 46-58 implementation: generic
CLI/API/Dashboard assurance, Quick Assessment, saved-policy selection, Evidence
Replay, Evaluation Comparison, foreground jobs, offline backup/recovery,
existing-pair startup and optional AVS/MSP430 compatibility. Existing plugin
isolation and read-only UART status remain supported within their recorded scope.

During this freeze, accept fixes only for a reproduced acceptance blocker,
incorrect decision/data, installation failure, contract regression or misleading
documentation. Each fix needs its triggering input, expected/actual result and
relevant regression evidence. A new collector, managed background service,
cloud/team deployment or general plugin marketplace requires a future product
decision and does not extend this completion checklist automatically.

Completion uses the gates below. Percentage estimates have no defined denominator
and are not project acceptance evidence.

## Three finite completion checkpoints

| Checkpoint | Exit criteria | Starting evidence |
|---|---|---|
| Phase 59: code closeout | Preserve accumulated work; commit a coherent integrated baseline and freeze plan; run full development and frontend gates from a clean checkout; build a fresh-sdist wheel tied to that commit; clean-install smoke; record hashes and explicit limitations | Phase 58 already passed installed Edge acceptance; this checkpoint establishes the commit/build relationship |
| Phase 60: real-project acceptance | Use the frozen ForgeGate package to independently check one retained real AVS handoff and one real MSP430 artifact against known expected outcomes; record producer commits, hashes, warnings and evidence levels; exercise relevant Dashboard outputs only where fresh acceptance is needed | AVS Phases 50/51/56 already passed with a correctly retained producer FAIL; MSP430 collector and input-only status have earlier bounded acceptance |
| Phase 61: final demonstration | Provide one documented Windows launch path, generic positive/negative examples, real-project evidence references, expected results and screenshot gallery; execute the documented demo from the frozen package; retain reproducible handoff and limitations | Phase 58 screenshots and prior walkthroughs are reusable; capture again only if the delivered behavior or data changes |

Status: Phase 59 **PASS**; Phase 60 **PASS**; Phase 61 **PASS**. This finite
Windows Alpha milestone is complete. See the [Phase 60 real-project report](../reports/PHASE_60_REAL_PROJECT_ACCEPTANCE.md)
and [Phase 61 final demo](../reports/PHASE_61_FINAL_DEMO_ACCEPTANCE.md).

Each checkpoint records PASS, FAIL, BLOCKED or DEFERRED against its actual scope.
After Phase 61, close this Alpha milestone. Add work only for observed defects or
a separately chosen next product milestone.

## Real-project acceptance rules

- Reuse already accepted original reports when the task is consumer regression.
  A new upstream test run is needed only to claim current producer behavior or
  when the required original artifact is missing/incompatible.
- AVS's frozen commit `bf8c4c6f59ba9063524aea7db01df87d35170483` has an accepted
  130-record, 12-rule handoff with decision FAIL. Preserving that FAIL is success
  for ForgeGate integration; this does not describe today's upstream state.
- MSP430 artifact collection and live UART observation are separate cases.
  A historical HIL artifact remains `system_observed`; an input-only heartbeat
  observation establishes only connection/protocol status during its window.
  If a new physical reconnect observation is needed, record the owner's action
  and exact observation window. Do not manufacture physical measurements.
- Check the available originals and peer handoff first. Missing producer
  artifacts must be recorded as blockers to that case, not replaced with
  synthetic data under a real-project label.
- Report hashes/declared commit binding do not authenticate the producer.
  VALID means the handoff verifies; its engineering decision may be FAIL.

## Open quality and deployment boundaries

| Item | Disposition for this Alpha |
|---|---|
| Spoken screen-reader output, native high contrast, real Remote Desktop | Open quality commitments; not prerequisites for the scoped default Windows/Edge demonstration, and no broad accessibility/RDP claim is permitted |
| Three Windows symlink test skips | Explicit environment coverage gap; retain skips and their reasons |
| Independent first-use operator acceptance | Not established by agent-driven browser testing; disclose this in the final handoff |
| Human time/accuracy comparison | Phase 53B remains owner-deferred; no quantified speedup or accuracy improvement claim |
| Managed workspace switching, producer authentication, network/team deployment | Outside this frozen local Alpha milestone |
| GitHub synchronization, public Release, License, LinkedIn | Separate publication decisions; current local-only direction remains in effect |

An environment limitation is not a passed test. Future deployment outside the
documented local Windows scope requires a new acceptance plan.
