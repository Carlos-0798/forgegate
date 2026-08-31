# ForgeGate Phase 0 acceptance report

> Historical note: this report records the initial Phase 0 baseline. The current
> prerequisite/environment result is in `PHASE_0_ENVIRONMENT_AUDIT.md`; later
> hardening increased test coverage and changed future build artifacts without
> rewriting this initial evidence record.

- Date: 2026-08-30 (America/New_York)
- Version: 0.1.0.dev0
- Environment: Windows 11, Python 3.12.10
- Evidence level: LOCAL_HOST_TEST
- Hardware/serial activity: NOT PERFORMED

## Result

**PASS within the Phase 0 contract-baseline scope.** This is not an MVP
acceptance and does not establish collector, evaluator, persistence,
attestation, API, plugin, CI-service, AFE, MSP430, or hardware capability.

## Accepted checks

| Check | Result |
|---|---|
| Editable install in project virtual environment | PASS |
| Ruff lint | PASS |
| Ruff format check | PASS |
| mypy strict | PASS, 9 source files |
| pytest | PASS, 24 tests |
| Branch-aware package coverage | PASS, 92.38% |
| Generic project configuration | VALID |
| Pull-request and production policy configurations | VALID |
| Canonical JSON Schema export | PASS, three schemas |
| sdist/wheel build | PASS |
| Repository-external wheel install | PASS |
| Clean-installed `forgegate doctor` | PASS |
| Clean-installed generic config validation | PASS |
| Windows/Linux GitHub Actions | NOT RUN; no remote repository |

## Artifact hashes

```text
forgegate-0.1.0.dev0-py3-none-any.whl
5aee5b03292dd27a095f53aa4eeecec148084167b374d7aca4fbbfe35b09a75b

forgegate-0.1.0.dev0.tar.gz
65dad58102dcb5892c68834eb5ceab88bf63ef085894e2137c1a49c1a7ed63b2

forgegate.project.v1.schema.json
25533d2f5abf951df51ca09de772a86736f3808b86acf5a38ff8b0235c99f70f

forgegate.policy.v1.schema.json
cfe59fc9972c33d62a9cf95d7ab0b30038ff5f07824ed4762fe4e0406a7e3893

forgegate.evidence-bundle.v1.schema.json
914a230a08fa928a6e2d80e327500bca40ce94d214597fa81505900d35ff07bc
```

## Corrected verification attempt

The first clean-install orchestration request did not start because it selected
a working directory before that directory existed. No ForgeGate process ran and
this is not a product test failure. The directory was then created from the
existing workspace root; wheel installation, `doctor`, and generic config
validation passed in that repository-external environment.

## Evidence boundary

The connected MSP430 LaunchPad was not queried, opened, flashed, commanded, or
otherwise changed. Analog Validation Studio and MSP430 information in the
compatibility document is a dated planning snapshot, not ForgeGate-owned
acceptance evidence.
