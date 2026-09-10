# Phase 60 frozen-package real-project acceptance

Date: 2026-09-09
Result: **LOCAL REAL-PROJECT ACCEPTANCE PASS**

## Outcome

The exact isolated ForgeGate `0.1.0a1` wheel retained by Phase 59 independently
checked two existing real-project handoffs. No source-tree import was used.

| Case | Accepted result | Negative control |
|---|---|---|
| Analog Validation Studio | Replay `VALID`, decision `FAIL`; four collections, 130 evidence records and all 12 historical rule results reproduced | A deliberately wrong expected commit exited 3 |
| MSP430 equipment-health controller | Collector `COMPLETE`; 17 `system_observed` records and both required limitation warnings retained | A deliberately wrong reported subject commit exited 3 |

The AVS `FAIL` is the correct consumer result for the frozen producer evidence;
turning it into PASS would have failed this checkpoint. `VALID` describes the
portable handoff's internal verification, not the engineering decision or
authenticated producer origin.

## Frozen delivery identity

- Source commit: `e424292c04e3e44c41ea41048e0b227aa5960699`
- Wheel SHA-256: `2262755565c0defb8be477a6f61c8f16da1a60df9c1111f97067d7efa395ff5d`
- Version: `0.1.0a1`
- Execution: isolated Phase 59 installation

## AVS retained evidence

- Producer commit declared by the retained handoff:
  `bf8c4c6f59ba9063524aea7db01df87d35170483`.
- Replay SHA-256:
  `961e6f953b7a7497d1f0a289c9d1ba884cfc54bb299553a130f47099b223ce8e`.
- The retained JUnit, coverage and SARIF bytes still match the hashes recorded
  during Phase 56.
- Verification reproduced `VALID / FAIL`, four collections, 130 normalized
  records and 12 exact rule results.
- This was a consumer regression over retained reports. AVS tests were not rerun,
  and the result does not claim current upstream state, producer authentication
  or hardware verification.

## MSP430 retained evidence

- Private checkpoint commit:
  `151fdcfa60661bce1ba04af13c1d3509706f7d4a`.
- Reported subject commit:
  `0850241c1b2aa34704228146600501346ee81745`.
- Private checkpoint archive SHA-256:
  `02491635ff4b607ec3ab98b035c5121c7341a752eda9bd6e6dfc2903fce4dda2`.
- Privacy-safe formal report SHA-256:
  `90b74521075dfc1af43a0775ccae5397c704c606072ed802379e6a4e73ae9fce`.
- All three source artifact hashes and sizes in the formal report match the
  retained private archive. The reviewed two-hour summary values also match the
  formal report.
- Collection produced 17 records, all explicitly `system_observed`, and retained
  `MSP430_HIL_SCOPE_RETAINED` plus `MSP430_REVIEW_CORRECTION_RETAINED`.

The formal MSP430 input is a privacy-safe migration fixture transcribed from the
retained Phase 6 evidence, not a newly native upstream export. This checkpoint
checks that exact historical evidence chain. It did not open a serial port, send
a board command, make a new physical measurement or establish current board
state.

## Repository regression gate

The authoritative development gate passed after the acceptance records were
integrated:

- dependency, Ruff and mypy checks: PASS;
- Python: 1,433 passed, three Windows symlink-capability skips;
- branch-aware coverage: 95.80% (minimum 95%);
- CLI/REST interaction smoke: 33/33 PASS;
- Dashboard asset inventory and committed Schema/OpenAPI checks: PASS.

## Acceptance boundaries

- Browser behavior was not rerun because the relevant Phase 56 installed-browser
  output is retained and the delivered bytes are unchanged.
- No new upstream execution, hardware access, GitHub synchronization or producer
  authentication occurred.
- Human efficiency and comparative accuracy remain unmeasured.
- This result accepts the scoped local Windows Alpha consumer workflow; it is not
  a production-readiness or general third-party compatibility claim.

Machine-readable evidence:
[PHASE_60_REAL_PROJECT_ACCEPTANCE_EVIDENCE.json](PHASE_60_REAL_PROJECT_ACCEPTANCE_EVIDENCE.json).
