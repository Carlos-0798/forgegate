# Verification matrix

| Capability | Planned evidence | Current status |
|---|---|---|
| Package imports on Python 3.12 | clean virtual environment | PASS — wheel clean-install smoke |
| Generic project config validates | CLI + pytest | PASS |
| Unknown fields fail closed | pytest | PASS |
| Parent/absolute paths are rejected | pytest | PASS |
| Missing evidence cannot be configured to PASS | pytest | PASS |
| Evidence commit mismatch is rejected | pytest | PASS |
| JSON Schemas export | CLI + JSON parse | PASS — three schemas |
| Ruff | full repository | PASS |
| mypy strict | `forgegate` package | PASS — 9 source files |
| Windows/Linux CI | GitHub Actions | NOT RUN; no remote |
| JUnit collection | adversarial fixtures | NOT IMPLEMENTED |
| Policy evaluation | unit/property/integration tests | NOT IMPLEMENTED |
| AFE report compatibility | frozen public artifact contract | PLANNED |
| MSP430 report compatibility | frozen public artifact contract | PLANNED |
| Physical device operation | explicit owner-approved procedure | OUT OF SCOPE |

Local test result: 24 passed with 92.38% branch-aware coverage on Python
3.12.10/Windows. See `reports/PHASE_0_ACCEPTANCE_REPORT.md` for exact scope and
artifact hashes.
