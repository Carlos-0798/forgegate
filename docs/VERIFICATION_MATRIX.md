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
| JSON Schemas export | CLI + JSON parse | PASS — thirty-six document plus two artifact schemas |
| Benchmark artifact Schema | committed contract + drift check | PASS — local host |
| Analog Validation result Schema mirror | committed upstream-consumer contract + drift check | PASS — local host |
| Committed Schema drift | model-derived byte comparison | PASS |
| Ruff | full repository | PASS |
| mypy strict | package and verification tools | PASS |
| Source distribution contents | manifest assertion | PASS |
| Clean release installation | temporary sdist/wheel/venv smoke | PASS |
| Windows/Linux/macOS CI | GitHub Actions | PASS — `verify.py` + `release_smoke.py`, Phase 18 contract-model run 33569520396 (`425038d`) |
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
| Authenticated local API | Ed25519 challenge, Bearer session, trust recheck | PASS — local host, loopback only |
| API role/project authorization | producer/operator and cross-project adversarial tests | PASS — exact session scopes; producer read-only |
| Authenticated audit actor | API write/readback, event identity, token absence | PASS — successful writes only |
| Session replay/expiry/capacity | one-time challenge, bounded memory, restart semantics | PASS — local host |
| Session logout/operator revocation | token reuse, role, target scope, hidden-ID adversarial tests | PASS — memory-only local host |
| Fixed-path trust-store reload | old/new scope, invalid input, challenge/session invalidation | PASS — explicit operator action; no managed online distribution |
| Authentication request limits | challenge/session/failure fixed windows + retry header | PASS — process-global; challenge/session counters precede body validation |
| API security-event journal | rejected auth, rate limits, logout, revocation, reload | PASS — bounded separate SQLite v8 log; best-effort, not compliance audit |
| Security-event privacy and access | token/body/key absence + global operator query | PASS — local host, saturation disclosed |
| Non-loopback/TLS API | transport, proxy, hostile-local-user controls | NOT IMPLEMENTED |
| REST lifecycle transitions | expected revision + idempotent replay/conflict | PASS — local host |
| REST evidence binding | strict nested assembly + immutable SQLite binding | PASS — local host |
| REST bound-evidence evaluation | policy engine + atomic terminal transition | PASS — local host |
| Release-track policy identity | mismatch rejection before terminal commit | PASS — local host |
| REST attestation persistence | deterministic create/replay/conflict | PASS — database only |
| HTTP Host and actual request body | loopback allowlist + 4 MiB declared/streamed byte gate | PASS — unknown-length/chunked test included |
| Immutable project registration | model/store/idempotency/conflict tests | PASS — introduced in SQLite v4, retained in v6 |
| Project CLI and REST readback | shared application + installed-wheel smoke | PASS — local host |
| Transactional state-change audit | create/bind/transition/evaluate/attest tests | PASS — local host |
| Audit cursor pagination and filters | bounded/empty/multi-page/adversarial tests | PASS — local host |
| SQLite v1/v2/v3/v4/v5-to-v6 migration | audit/profile backfill and legacy-candidate tests | PASS — registration profiles only; no candidate-profile fabrication or duplicate audit |
| Project/audit contract drift | five JSON Schemas + OpenAPI | PASS — byte checked |
| API security-event contract drift | two JSON Schemas + OpenAPI query | PASS — byte checked and clean-wheel persisted |
| GitHub Action report contract | model/identity/Schema/loader tests | PASS — content-derived v1 report; local host |
| Portable bundle to CI commit binding | strict verifier + complete exact object ID | PASS — partial/invalid/mismatch rejected; local host |
| GitHub Job Summary and outputs | escaping, truncation, size/path/adversarial tests | PASS — bounded append-only runner files; local host |
| GitHub composite Action | committed generic fixture + real workflow job | PASS — private CI run 33566424223 (`3682361`) |
| Installed GitHub gate | clean-wheel portable-bundle/summary/output/report smoke | PASS — local host |
| Custom GitHub Checks/PR/API writes | token/permissions/OIDC design | NOT IMPLEMENTED — no token requested and no GitHub API called |
| Plugin manifest contract | model/identity/Schema/loader/adversarial tests | PASS — bounded content-derived v1 metadata; local + private CI |
| Import-free plugin discovery | entry-point metadata + import-hostile package | PASS — code remains `NOT_LOADED`; local + private CI |
| Plugin compatibility/failure isolation | compatible/incompatible/invalid/conflict cases | PASS — discovery metadata only; no runtime execution |
| Plugin install/uninstall independence | standalone fixture wheel + clean ForgeGate wheel | PASS — local + three-platform clean-package smoke; no optional dependency retained |
| Plugin execution security contract | exact upstream/license traceability + architecture/threat review | DESIGN PASS — protocol, permissions, isolation tiers, limits, errors, and audit semantics defined; no code loaded |
| Plugin run-plan/protocol/transition/result contracts | model/identity/authority/chain/resource/Schema/loader tests | PASS — local + three-platform CI; 7 focused tests, four content-derived document Schemas, no process started |
| Windows sandbox capability gate | host/runtime probe, client/server identity, command-construction adversarial tests | PASS — 20 focused tests; local rootless WSL2 Podman client/server 5.8.6 match; execution `PROHIBITED`, tier `NONE` |
| Windows Podman/WSL2 low-level enforcement | fixed hostile container tests for filesystem/network/process/environment/resources/cleanup | PASS — all 14 controls in development report `sha256:5296f70996ff9928d54557fb97c2e667f15ccdd67ff989b85b518260cb3db38d`; external code not tested |
| External plugin execution and audit | production broker/runner/protocol/output validation/plugin_runs implementation | NOT IMPLEMENTED — no installed plugin callable is loaded; execution remains `PROHIBITED`, tier `NONE` |
| Registered-project candidate authority | application/CLI/API/store tests | PASS — unregistered project and missing track fail closed |
| Release-track normalization | underscore compatibility plus ambiguity tests | PASS — new candidate/policy identity is canonical hyphen form |
| Project/candidate discovery | bounded page model, stable cursor, CLI/API, installed-wheel smoke | PASS — candidates are project-scoped |
| Project-profile revision contract | model/Schema/identity/chain tests | PASS — complete append-only replacement with previous-profile linkage |
| Project-profile CAS/idempotency | store concurrency/replay/conflict/time tests | PASS — local host, SQLite v6 |
| Profile current/history surfaces | application/CLI/REST/OpenAPI/clean-wheel smoke | PASS — bounded version cursor |
| Profile-bound candidate v2 | store/application/CLI/REST/lifecycle tests | PASS — exact profile ID/version retained across transitions |
| Track revision isolation | addition/removal and historical-read tests | PASS — only later candidates use the revised profile |
| Legacy candidate profile semantics | v5 migration and corruption tests | PASS — v1 remains readable with no fabricated binding |
| Exact policy material | byte/hash/model/adversarial tests | PASS — local host, exact profile-authorized bytes retained |
| Material-bound evaluation v2 | application/store/CLI/REST integration | PASS — material/profile/evidence/time bound atomically |
| SQLite v1-v7-to-v8 migration | migration and legacy semantics | PASS — no historical policy/security event fabricated |
| Path-free REST policy workflow | strict material request + retained readback | PASS — no client-selected server policy path |
| Portable assurance document | strict model/Schema/cross-document identity tests | PASS — profile, evidence, material, evaluation, lifecycle, and attestation bound |
| Content-addressed publication | exact replay/conflict/member/tamper tests | PASS — canonical JSON/Markdown/manifest bytes |
| Database-independent verification | exported directory verified without store or project reads | PASS — local host |
| Portable evidence boundary | model field, generated README, and adversarial tests | PASS — source artifact bytes explicitly not embedded |
| Key-derived Ed25519 identity | model, Schema, derive CLI, private-key mismatch tests | PASS — local host; no long-term key generated or retained |
| External trust-store authorization | role/project/status/content-ID adversarial tests | PASS — exact active trust record required |
| Assurance signature | domain-separated Ed25519 sign/verify and tamper tests | PASS — exact canonical Phase 11 bundle bytes |
| Strict identity document loading | size/encoding/duplicate/non-finite/schema/change tests | PASS — bounded JSON-only trust boundary |
| Signature publication | staging, content address, replay/conflict/concurrency tests | PASS — local host |
| Installed identity workflow | ephemeral key derive/trust/sign/replay/verify smoke | PASS — clean-wheel local host |
| Trusted timestamp/managed online revocation | managed external infrastructure | NOT IMPLEMENTED — signed/auth times are not trusted; API reload is explicit from one fixed local file |
| Source-artifact producer chain | producer-signed artifact receipts | NOT IMPLEMENTED — signature covers retained bundle only |
| HTTP artifact loading/file publication | no loader/output path; nested metadata is not dereferenced | OUT OF SCOPE |
| MSP430 report compatibility | frozen public artifact contract | PLANNED |
| Physical device operation | explicit owner-approved procedure | OUT OF SCOPE |

See `reports/PHASE_16_GITHUB_ACTIONS_GATE_ACCEPTANCE_REPORT.md`
for the current exact local test and coverage result. Earlier acceptance
reports remain historical records.
