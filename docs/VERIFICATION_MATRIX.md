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
| JSON Schemas export | CLI + JSON parse | PASS — fifteen document plus two artifact schemas |
| Benchmark artifact Schema | committed contract + drift check | PASS — local host |
| Analog Validation result Schema mirror | committed upstream-consumer contract + drift check | PASS — local host |
| Committed Schema drift | model-derived byte comparison | PASS |
| Ruff | full repository | PASS |
| mypy strict | package and verification tools | PASS |
| Source distribution contents | manifest assertion | PASS |
| Clean release installation | temporary sdist/wheel/venv smoke | PASS |
| Windows/Linux/macOS CI | GitHub Actions | PASS — `verify.py` + `release_smoke.py`, Phase 7 run 33406259713 |
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
| Candidate lifecycle | state-transition/adversarial tests | PASS — local host, 100% branch coverage |
| Terminal evaluation binding | commit/decision/time mismatch tests | PASS — local host |
| Candidate CLI preview | Golden create/transition output | PASS — stateless local host |
| SQLite schema bootstrap | application ID/version/WAL/FULL/FK tests | PASS — local host |
| SQLite persistence | transaction/restart/recovery tests | PASS — local host |
| Optimistic concurrency | stale revision, CAS, and writer-lock tests | PASS — local host |
| Idempotent writes | exact replay/conflicting-key tests | PASS — local host |
| Append-only audit history | trigger and corruption tests | PASS — local host |
| Persisted candidate CLI | clean-process create/advance/show/history smoke | PASS — local host |
| SQLite v1/v2 migration | explicit migration/backfill/rollback tests | PASS — local host; no historical binding fabricated |
| Durable evaluation binding | restart/corruption/append-only tests | PASS — local host |
| JSON/Markdown attestations | deterministic Golden byte comparison | PASS — local host |
| Attestation self-consistency | adversarial model/chain/evaluation tests | PASS — local host |
| Attestation output publication | atomic publish/replay/conflict/fault tests | PASS — local host |
| Installed attestation CLI | clean-wheel terminal flow and exact replay | PASS — local host |
| AFE `result-export.v1` compatibility | frozen public artifact, adversarial tests, Golden output | PASS — local host; no Studio import/device access |
| AFE source-to-verification mapping | all nine v1 sources + bench cap tests | PASS — `BENCH_*` maxes at `system_observed` |
| Installed AFE collector CLI | clean wheel + sample result | PASS — local host |
| Collection-result strict loading | malformed/duplicate/non-finite/resource adversarial tests | PASS — local host |
| Referenced-artifact revalidation | missing/replaced/path/hash tests | PASS — local host |
| Multi-collector evidence assembly | model/service/CLI + committed Golden | PASS — local host |
| Warning retention boundary | default rejection + explicit retention tests | PASS — local host |
| Assembly-fed policy evaluation | direct and clean-wheel CLI integration | PASS — local host |
| Candidate-to-assembly binding | model/Golden/store/CLI tests | PASS — local host, immutable SQLite v3 record |
| `COLLECTING -> READY` evidence gate | missing/time/legacy migration tests | PASS — local host |
| Bound terminal evaluation | nested-bundle fingerprint mismatch tests | PASS — local host |
| Installed binding workflow | clean-wheel assembly/bind/READY/terminal/attest smoke | PASS — local host |
| Shared CLI/API application service | parity and integration tests | PASS — candidate create/read paths |
| Local REST health and candidate API | FastAPI TestClient + durable SQLite flow | PASS — local host |
| HTTP idempotency and error mapping | replay/conflict/404/422/500/503 tests | PASS — local host |
| Request correlation and error sanitization | generated/supplied/invalid IDs + injected exception | PASS — local host |
| Loopback-only API bind | IPv4/IPv6/localhost allowlist + external-address rejection | PASS — local host |
| OpenAPI 3.1 contract | committed byte comparison + installed-wheel export | PASS — drift-checked |
| Authenticated/non-loopback API | identity, authorization, transport controls | NOT IMPLEMENTED |
| REST lifecycle transitions | expected revision + idempotent replay/conflict | PASS — local host |
| REST evidence binding | strict nested assembly + immutable SQLite binding | PASS — local host |
| REST bound-evidence evaluation | policy engine + atomic terminal transition | PASS — local host |
| Release-track policy identity | mismatch rejection before terminal commit | PASS — local host |
| REST attestation persistence | deterministic create/replay/conflict | PASS — database only |
| HTTP Host and declared body length | loopback allowlist + 4 MiB Content-Length gate | PASS — local host |
| Immutable project registration | model/store/idempotency/conflict tests | PASS — introduced in SQLite v4, retained in v5 |
| Project CLI and REST readback | shared application + installed-wheel smoke | PASS — local host |
| Transactional state-change audit | create/bind/transition/evaluate/attest tests | PASS — local host |
| Audit cursor pagination and filters | bounded/empty/multi-page/adversarial tests | PASS — local host |
| SQLite v1/v2/v3/v4-to-v5 migration | complete-chain audit projection and v4 index-only tests | PASS — no project/identity fabrication or duplicate audit |
| Project/audit contract drift | five JSON Schemas + OpenAPI | PASS — byte checked |
| Registered-project candidate authority | application/CLI/API/store tests | PASS — unregistered project and missing track fail closed |
| Release-track normalization | underscore compatibility plus ambiguity tests | PASS — new candidate/policy identity is canonical hyphen form |
| Project/candidate discovery | bounded page model, stable cursor, CLI/API, installed-wheel smoke | PASS — candidates are project-scoped |
| Project-profile revision mutation | architecture contract only | NOT IMPLEMENTED — append-only/CAS semantics defined for Phase 9 |
| HTTP artifact loading/file publication | no loader/output path; nested metadata is not dereferenced | OUT OF SCOPE |
| MSP430 report compatibility | frozen public artifact contract | PLANNED |
| Physical device operation | explicit owner-approved procedure | OUT OF SCOPE |

See `reports/PHASE_8_PROJECT_AUTHORITY_DISCOVERY_ACCEPTANCE_REPORT.md` for the
current exact test and coverage result. Earlier acceptance reports remain
historical records.
