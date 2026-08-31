# Verification matrix

| Capability | Planned evidence | Current status |
|---|---|---|
| Package imports on Python 3.12 | clean virtual environment | PASS — wheel clean-install smoke |
| Repeatable Windows setup | PowerShell bootstrap + constraints | PASS |
| Linux/macOS setup script | shell syntax + future CI | SYNTAX PASS; execution NOT RUN |
| Dependency consistency | `pip check` | PASS |
| Generic project config validates | CLI + pytest | PASS |
| Unknown fields fail closed | pytest | PASS |
| Parent/absolute paths are rejected | pytest | PASS |
| Missing evidence cannot be configured to PASS | pytest | PASS |
| Evidence commit mismatch is rejected | pytest | PASS |
| JSON Schemas export | CLI + JSON parse | PASS — three schemas |
| Committed Schema drift | model-derived byte comparison | PASS |
| Ruff | full repository | PASS |
| mypy strict | package and verification tools | PASS |
| Source distribution contents | manifest assertion | PASS |
| Clean release installation | temporary sdist/wheel/venv smoke | PASS |
| Windows/Linux/macOS CI | GitHub Actions | DEFINED; NOT RUN, no remote |
| JUnit collection | adversarial fixtures | NOT IMPLEMENTED |
| Policy evaluation | unit/property/integration tests | NOT IMPLEMENTED |
| AFE report compatibility | frozen public artifact contract | PLANNED |
| MSP430 report compatibility | frozen public artifact contract | PLANNED |
| Physical device operation | explicit owner-approved procedure | OUT OF SCOPE |

Current local result: 32 passed with 100% branch-aware package coverage on
Python 3.12.10/Windows. See `reports/PHASE_0_ENVIRONMENT_AUDIT.md`. The earlier
`reports/PHASE_0_ACCEPTANCE_REPORT.md` remains the historical initial-baseline
record.
