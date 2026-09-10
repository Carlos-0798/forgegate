# Analog Validation Studio: file-only host acceptance

This consumer pack connects real AVS software reports to the existing ForgeGate
candidate workflow. It imports no AVS package, opens no device, and never edits
the producer repository. It is a consumer-owned review policy, not AVS release
authorization. A valid report or portable bundle may carry an engineering FAIL.

## Producer handoff

Use an owner-selected immutable commit in a separate checkout/archive and Python
environment. Do not run cleanup or overwrite reports in an active dirty worktree.
Retain the commit, tool versions, commands, exit codes and original report bytes.
From that isolated producer source, with its installed development dependencies:

```powershell
python -m pytest -q --junitxml=../reports/junit.xml `
  --cov=analog_validation --cov=analog_validation_app --cov=analog_validation_pyserial `
  --cov-report=xml:../reports/coverage.xml --cov-report=term --cov-fail-under=100
python -m ruff check src --select S --output-format sarif --output-file ../reports/security.sarif
python tools/product_quality_acceptance.py --output ../reports/product-quality.json
```

Record each command's exit immediately; a later successful command must not mask
an earlier test/scanner failure. This coverage command measures statements, not
branches. Ruff S-rule results are untriaged review candidates, not confirmed
vulnerabilities. Timings measure this host executing synthetic workloads; they
are neither real-time guarantees nor hardware performance measurements.

The quality mapper accepts `phase5-product-quality-acceptance.v1`, requires the
known 15 boolean checks, host-only boundary and 10,000-item workloads, then copies
six finite nonnegative timing/memory values plus the failed-check count. False
checks remain visible. Unknown versions/check sets need explicit compatibility
review. The original quality JSON and its hash are retained alongside the derived
benchmark; the original quality bytes are not embedded in the assurance bundle.

## Prepare a new ForgeGate handoff

From the ForgeGate source distribution, using its environment (replace all
placeholder paths, commit and version values with the retained producer facts):

```powershell
python tools/avs_host_acceptance.py `
  --reports C:/review/producer-reports --output C:/review/new-forgegate-handoff `
  --commit YOUR_40_CHARACTER_COMMIT_SHA `
  --pytest-version YOUR_PYTEST_VERSION --coverage-version YOUR_COVERAGE_VERSION
```

The output must not exist. If an understood collector warning is present, retain
the failed attempt as a diagnostic and retry into a **new** directory with
`--retain-warnings`. This never converts a rejected report into a complete one.
The tool reads bounded originals, copies exact bytes, collects all four reports,
validates receipts, registers this pack and leaves one candidate **COLLECTING and
unbound**. It writes `assembly.json`, `policy-material.json`, `handoff.json`, the
private reports/receipts and a new `forgegate.db`. It does not start a server.
Observed original file modification times are declared, unauthenticated collection
times; neither those times nor a supplied commit prove producer origin.

Run the existing authenticated Dashboard against that isolated database, using
an operator identity scoped to `analog-validation-studio`. Do not replace a live
user database. In Candidates:

1. Inspect the candidate and import `assembly.json`; review hashes, commit,
   receipt/record counts and warning disposition, then confirm binding.
2. Separately confirm READY and EVALUATING.
3. Import `policy-material.json` and confirm evaluation; compare all 12 rule
   outputs with the original reports, including non-PASS outcomes.
4. Generate the unsigned-local attestation and review/download the assurance ZIP.
5. Extract to a directory named exactly like the ZIP without `.zip`, such as
   `assurance-<64-hex-bundle-hash>`, then run:

```powershell
forgegate verify-assurance C:/review/assurance-BUNDLE_HASH
```

Exit 0 / `VALID` means internal bundle integrity, **not** an engineering PASS.
The three-file portable contract does not embed original report bytes. Retain
those privately for independent source verification. Original XML/SARIF, logs,
databases, identities and key files may contain machine paths or sensitive data;
do not copy them into a public repository.

## Accepted baseline

[Phase 56](../../reports/PHASE_56_AVS_QUICK_ACCEPTANCE.md) also accepts these
retained reports through [Quick assessment](../../docs/QUICK_ASSESSMENT.md).
Use pytest as the default tool, override coverage.py and its version, enter the
original per-report times, and explicitly retain the coverage warning after
review. Save the prepared private replay ZIP before closing the dialog. The
historical FAIL is preserved; newer AVS changes are not characterized by this run.

[Phase 50](../../reports/PHASE_50_AVS_HOST_ACCEPTANCE.md) used a real frozen AVS
commit. It deliberately retained one test failure and 15 static review candidates:
10 policy rules passed, two failed, and the browser-downloaded FAIL bundle verified
as VALID. No claim is made about AVS's newer uncommitted work.
