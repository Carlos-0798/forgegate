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
| JSON Schemas export | CLI + JSON parse | PASS — four versioned document schemas |
| Benchmark artifact Schema | committed contract + drift check | PASS — local host |
| Committed Schema drift | model-derived byte comparison | PASS |
| Ruff | full repository | PASS |
| mypy strict | package and verification tools | PASS |
| Source distribution contents | manifest assertion | PASS |
| Clean release installation | temporary sdist/wheel/venv smoke | PASS |
| Windows/Linux/macOS CI | GitHub Actions | DEFINED; NOT RUN, no remote |
| Artifact root and byte identity | unit/adversarial tests | PASS — local host |
| Stable artifact read/change rejection | simulated metadata cases | PASS — local host |
| Actual Windows symlink escape | privileged symlink fixture | NOT RUN — host disallowed symlink creation |
| JUnit collection | adversarial fixtures + golden output | PASS — local host |
| Bounded/forbidden JUnit XML | unit/adversarial tests | PASS — local host |
| Collection audit warnings/rejections | unit + CLI tests | PASS — local host |
| Coverage XML collection | adversarial fixtures + golden output | PASS — local host |
| LCOV collection | adversarial fixtures + golden output | PASS — local host |
| Coverage repository/package/module scopes | unit + golden tests | PASS — local host |
| Declared/observed coverage mismatch audit | unit tests | PASS — local host |
| Installed coverage CLI paths | clean wheel environment | PASS — local host |
| SARIF 2.1.0 collection | adversarial fixtures + golden output | PASS — local host |
| Successful zero-result SARIF scan | explicit summary evidence | PASS — local host |
| Failed/ambiguous SARIF scan | invocation/rule-reference rejection | PASS — local host |
| Installed SARIF CLI path | clean wheel environment | PASS — local host |
| Benchmark JSON collection | adversarial fixtures + golden output | PASS — local host |
| Benchmark numeric/schema bounds | finite/range/unknown-field tests | PASS — local host |
| Duplicate metric identity | scope/name collision tests | PASS — local host |
| Installed Benchmark CLI path | clean wheel environment | PASS — local host |
| Policy evaluation | unit/adversarial/integration tests | PASS — local host, 100% branch coverage |
| Policy decision exit codes | installed CLI PASS/FAIL smoke | PASS — 0/1; unit-tested 2/3 |
| Explicit time and evidence age | boundary/adversarial tests | PASS — local host |
| Trust and verification thresholds | explicit-rank tests | PASS — local host |
| 1,000-record policy evaluation | local performance guard | PASS — under 2 seconds |
| Candidate lifecycle | state-transition tests | NOT IMPLEMENTED |
| SQLite persistence | transaction/concurrency tests | NOT IMPLEMENTED |
| JSON/Markdown attestations | deterministic golden output | NOT IMPLEMENTED |
| AFE report compatibility | frozen public artifact contract | PLANNED |
| MSP430 report compatibility | frozen public artifact contract | PLANNED |
| Physical device operation | explicit owner-approved procedure | OUT OF SCOPE |

See `reports/PHASE_2_POLICY_ENGINE_ACCEPTANCE_REPORT.md` for the current exact
test and coverage result. Earlier acceptance reports remain historical records.
