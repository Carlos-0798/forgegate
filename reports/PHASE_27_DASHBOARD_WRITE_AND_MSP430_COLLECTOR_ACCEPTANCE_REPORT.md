# Phase 27 reviewed Dashboard writes and MSP430 collector acceptance

## Outcome

Phase 27 implements the first complete, reviewed Dashboard release-assurance
workflow and a separate artifact-only MSP430 validation collector. The
Dashboard path was exercised in Microsoft Edge against an isolated local
service from DRAFT through PASS and attestation. The MSP430 collector accepts a
strict v1 report and emits bounded normalized evidence without opening a serial
port or controlling hardware.

This is Windows local Alpha evidence. It is not production approval, remote
deployment evidence, evidence-producer authentication, or new MSP430 physical
measurement.

## Dashboard write workflow

The same-origin BFF now exposes four operator-only command families:

1. expected-revision candidate transitions;
2. immutable evidence-assembly binding;
3. exact frozen-policy evaluation;
4. immutable terminal attestation generation.

Every command requires an authenticated Dashboard session, exact Origin,
anti-CSRF token, role/project authority, and domain validation. Transition,
binding, and evaluation requests use command-owned idempotency keys.
Attestation generation uses the existing deterministic exact-replay contract.
The browser does not retry ambiguous 409, 413, or 500 outcomes automatically;
429 retains the exact frozen request through its bounded cooldown.

The Edge workflow produced candidate `cand-270169223181fdd6a6d287a0`, reached
PASS at revision 4, and retained audit sequence 5–12. The evaluated test-summary
rule expected zero failures and observed zero. The final attestation remained
`unsigned_local` and visibly excluded deployment and hardware claims.

## Actual-browser negative and defect-driven checks

A structurally valid evidence assembly with another commit was rejected with
HTTP 422 before a durable binding. The positive assembly then passed complete
server-side identity, receipt, evidence, artifact, and warning validation.

Browser interaction checks found two presentation defects and verified their corrections:

- a detail-only reload could show PASS below a stale DRAFT table row; completion
  now reloads the whole candidate workspace before reopening its detail;
- reviewed-command focus could initially stay on Cancel; the dialog is now
  opened before its reviewed contents are rendered, so confirmation receives
  initial focus.

Tab and Shift+Tab wrap inside the dialog. Escape closes it and returns focus to
the invoking command. No mutation was issued during navigation or focus tests.

## Exact zoom and assistive results

Microsoft Edge ran native 100%, 125%, 150%, 175%, and 200% zoom on a host using
150% Windows display scaling. At all five levels:

- root horizontal overflow remained zero;
- the primary write action stayed horizontally reachable;
- the side navigation and workspace did not overlap;
- no checked action, link, heading, header, term, or definition was
  horizontally clipped.

At 200%, the reviewed-command dialog also had zero horizontal overflow, kept
both actions reachable, trapped forward/backward focus, and returned focus on
Escape. Windows Narrator ran for a bounded system-keyboard and semantic pass;
spoken wording and announcement timing were not captured. High contrast and a
real Remote Desktop session retain `NOT_RUN` in the machine-readable record.

## MSP430 formal artifact collector

`forgegate.msp430-validation-report.v1` freezes the compatibility contract for
host tests, target builds, LaunchPad HIL, and instrumented bench results. The
collector rejects malformed encoding/JSON, duplicate keys, non-finite values,
unknown schema fields, size/node/depth excess, path escape, commit mismatch,
duplicate identities, outcome/check contradictions, and impossible hardware
claims.

Evidence levels map to `host_tested`, `target_built`, `system_observed`, or
`physically_verified`. LaunchPad HIL is always `system_observed`. Bench evidence
can become `physically_verified` only when physical context and complete
instrument calibration provenance are structurally present; otherwise it is
capped with a retained warning.

The migration fixture for upstream commit
`0850241c1b2aa34704228146600501346ee81745` produces 17 evidence records and two
retained warnings. Its 7,206-row/7,200-second Phase 6 result remains
LaunchPad-only and explicitly excludes external sensors, INA219, MOSFET, fan,
load, calibration, and electrical measurement. ForgeGate did not re-run or
promote that historical result.

## Evidence

- `reports/DASHBOARD_PHASE27_INTERACTION_EVIDENCE_2026-09-05.json`
- `docs/architecture/MSP430_VALIDATION_COLLECTOR.md`
- `schemas/forgegate.msp430-validation-report.v1.schema.json`
- `examples/msp430-validation/artifacts/phase6-soak-report.json`
- `tests/test_dashboard.py`
- `tests/test_msp430_validation_collector.py`

## Verification result

- `python tools/verify.py`: PASS;
- full Python suite: 878 passed, 3 skipped because Windows symlink creation is
  unavailable;
- branch-aware coverage: 95.23% across 10,389 statements and 2,810 branches;
- Dashboard focus: 46 passed, 98.37% branch-aware coverage across 626
  statements and 110 branches;
- MSP430 collector focus: 34 passed;
- Ruff, Ruff format, and strict mypy: PASS across 91 source/tool files;
- TypeScript no-emit check and deterministic Vite assets: PASS;
- 41 document Schemas, 3 artifact Schemas, direct API OpenAPI, and the
  17-operation Dashboard BFF OpenAPI: PASS drift checks;
- `python tools/release_smoke.py`: PASS, including source manifest, wheel/sdist,
  clean install, MSP430 report collection, Dashboard contract export, optional
  `pyserial` environment, and uninstall.

The three requested engineering deliverables are accepted at the Windows local
Alpha boundary. High contrast, spoken Narrator output, and a real Remote
Desktop session are not inferred from these results.
