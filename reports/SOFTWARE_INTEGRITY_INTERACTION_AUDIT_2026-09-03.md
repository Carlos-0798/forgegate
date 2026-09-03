# Software integrity and interaction audit

- Date: 2026-09-03
- Product: ForgeGate `0.1.0a1`
- Scope: implemented private Windows Alpha surfaces
- Host evidence: Windows local host, Python 3.12.10, rootless Podman/WSL2
  client/server 5.8.6
- Highest ForgeGate-owned evidence: `LOCAL_HOST_TEST`
- Hardware access: `NOT_PERFORMED`
- Public release or production approval: not granted by this audit

## Outcome

The implemented Windows Alpha software paths pass the integrity, interaction,
packaging, dependency, and local isolation checks in this report. Two validated
resource-exhaustion weaknesses were corrected: structured documents could be
materialized before structural limits were enforced, and broker output could be
recursively copied onto the host before the tree was bounded. No unresolved
high- or medium-severity finding was identified in the audited scope.

This result is a bounded engineering checkpoint. It is not a claim that every
possible defect is absent, that arbitrary third-party plugins are trusted, or
that ForgeGate is ready for non-loopback or production deployment.

## Reference baseline

The review used current primary documentation rather than treating a tutorial
as proof:

- [OWASP ASVS 5.0.0](https://owasp.org/www-project-application-security-verification-standard/)
  for application-security control coverage;
- [OWASP API Security Top 10 (2023)](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)
  for authorization, authentication, resource-consumption, configuration, and
  unsafe-upstream-data failure classes;
- [FastAPI testing guidance](https://fastapi.tiangolo.com/tutorial/testing/)
  for request/response interaction tests through `TestClient` and pytest;
- [SQLite `integrity_check` guidance](https://www.sqlite.org/pragma.html#pragma_integrity_check)
  and ForgeGate's separate foreign-key validation for durable-store checks;
- [Python `tarfile` security guidance](https://docs.python.org/3/library/tarfile.html)
  for pre-inspection of untrusted archives and avoidance of host extraction;
- [Python Packaging User Guide](https://packaging.python.org/en/latest/flow/)
  for source-distribution, wheel, clean-install, and uninstall coverage;
- [GitHub Actions secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use)
  for immutable action references and workflow trust boundaries.

## Executed verification

| Area | Result | Evidence boundary |
|---|---|---|
| Full automated suite | PASS — 780 passed, 3 Windows symlink-capability skips | Local host |
| Branch-aware coverage gate | PASS — 95.01% across 8,959 statements and 2,520 branches | Local host |
| Static checks | PASS — Ruff lint/format and strict mypy across 75 source/tool files | Local host |
| Contract drift | PASS — committed JSON Schemas and OpenAPI match generated contracts | Local host |
| Configuration and evidence parsing | PASS — byte, UTF-8, duplicate-key, depth, node/element, and stable-read rejection | Local host |
| CLI/API/application parity | PASS — shared application commands, HTTP status/error/auth boundaries, idempotency, and durable readback | FastAPI TestClient/local host; no remote transport claim |
| SQLite lifecycle | PASS — migrations, transactions, append-only triggers, rollback injection, corruption/foreign-key rejection, replay, and concurrency | Local host |
| Plugin discovery | PASS — install/discover/uninstall without importing plugin code in the core | Clean virtual environment |
| Windows plugin interaction | PASS — 18/18 controls including denials, protocol, dual snapshots, failure persistence, replay, collection, policy handoff, and cleanup | Live local rootless Podman/WSL2; ForgeGate-owned fixture only |
| Release packaging | PASS — sdist and wheel build, manifest inspection, clean install, initialized project, end-to-end commands, live plugin run, uninstall, and import absence | Fresh temporary virtual environment |
| Dependency audit | PASS — no known vulnerabilities reported for resolved registry dependencies | `pip-audit`; editable ForgeGate itself is not a registry advisory target |
| Repository/privacy checks | PASS — Git object connectivity, diff whitespace, noreply identity, and private-email identifier scan | Local repository |

The clean-wheel live record is
[`SOFTWARE_INTEGRITY_INTERACTION_LIVE_EVIDENCE.json`](SOFTWARE_INTEGRITY_INTERACTION_LIVE_EVIDENCE.json).
It retains `hardware_access=NOT_PERFORMED`, identifies the clean-wheel
installation, and records all 18 controls individually.

## Findings and corrections

### FG-AUDIT-001 — structured-input materialization limits

- Severity: Low for XML collectors; defense-in-depth across JSON/YAML consumers
- CWE: CWE-400 (uncontrolled resource consumption)
- Status: resolved and regression-tested
- Formal scan: `4558d42a-005d-42ab-9fba-60383669fc28`, source revision
  `61400285ecb2ca6d861012541a161458f50b315c`

Collectors already limited artifact bytes, but XML trees and some JSON/YAML
object graphs could be constructed before a structural element/node/depth limit
was applied. A shared event/token preflight now rejects excessive JSON, XML,
and YAML structure before the ordinary parser constructs the object graph.
Configuration loading additionally rejects duplicate or unhashable YAML keys,
invalid UTF-8, non-regular files, and a file that changes during reading.

Affected trust boundaries now include JUnit, Cobertura XML, SARIF, Benchmark,
Analog Validation Studio export, collection assembly, portable assurance,
plugin manifests/protocol data, and general configuration loading.

### FG-AUDIT-002 — plugin output copied before validation

- Severity: Medium
- CWE: CWE-400 (uncontrolled resource consumption)
- Status: resolved and live-regression-tested
- Formal scan: `4558d42a-005d-42ab-9fba-60383669fc28`, source revision
  `61400285ecb2ca6d861012541a161458f50b315c`

The original production broker used recursive `podman cp` into a host
directory, so an untrusted output tree was materialized before ForgeGate's
entry and byte limits were applied. The broker now stages a fixed, read-only
trusted exporter next to the trusted runner. The exporter checks the exact
directory shape, regular-file type, entry count, aggregate bytes, and stable
file identity inside the isolated container, then emits a deterministic tar
stream. The host bounds that stream and independently rejects unsafe paths,
unexpected members, links, duplicates, size mismatches, excess entries, and
excess bytes without extracting the archive.

The change also avoids a Windows Podman 5.8.6 incompatibility observed when
`podman cp ... -` treated `-` as a host path. The final clean-wheel run used
`podman exec` with the trusted exporter and passed both output snapshots.

### FG-AUDIT-003 — coverage threshold rounding

- Severity: Quality-gate correctness
- Status: resolved

Coverage was displayed below 95% while its default whole-number precision
allowed the process to exit successfully. The report precision is now two
decimal places and the regression suite was expanded until the actual
branch-aware value reached 95.01%; values below 95.00 now fail the gate.

### FG-AUDIT-004 — stale and vulnerable development tooling

- Severity: Development supply-chain hygiene
- Status: resolved for the tested environment

The environment audit found advisories against the prior pip/pytest versions.
The development constraints, bootstrap scripts, CI jobs, and clean-release
environment now install constrained pip 26.2.1 and pytest 9.0.3. A fresh
`pip-audit --local --skip-editable` reports no known vulnerability in resolved
registry packages.

### FG-AUDIT-005 — diagnostics and documentation drift

- Severity: Operability/documentation correctness
- Status: resolved

The live verifier now preserves stable broker issue codes instead of reducing
all output-transfer failures to a generic startup error. CLI migration help was
updated from schema v7 to v8, and the threat model now distinguishes import-free
plugin discovery from explicitly authorized broker execution.

## Common design-problem checklist

| Common problem | Disposition |
|---|---|
| Unbounded request or artifact size | Bounded; actual HTTP stream and file sizes tested |
| Deep or high-cardinality structured input | Bounded before materialization; adversarial tests added |
| Duplicate/non-finite/invalid encoding | Rejected at strict input boundaries |
| Path traversal, symlink, special file, archive extraction | Rejected; plugin tar is inspected and read without extraction |
| Shell/command injection | Broker commands use argument arrays; no shell expansion |
| Broken authentication/authorization | Ed25519 challenge, scoped short-lived sessions, role/project checks, revocation/reload tests |
| Object/function-level API access errors | Cross-project, producer/operator, hidden-ID, and write/read boundary tests |
| Replay and concurrent writes | Caller idempotency keys, optimistic revisions, exact replay/conflict tests |
| Partial database commits | Explicit transactions, FULL synchronous WAL policy, rollback fault tests |
| Sensitive data in errors/logs | Sanitized error envelopes, bounded logs, token/body/key absence tests |
| Plugin network/host/process escape | Deny controls passed for the fixed live fixture |
| Cleanup and orphaned state | Container/staging cleanup asserted; runner grace is finite |
| Package/source drift | Wheel/sdist manifest, clean install, generated-contract drift, uninstall/import-absence checks |
| Dependency advisories | Current resolved environment reports none; must be repeated as dependencies change |
| CI claim inflation | Hosted CI and local Podman evidence remain explicitly separate |

## Remaining limits

- The live plugin is a ForgeGate-owned pure-Python fixture. Publisher
  provenance, arbitrary hostile third-party packages, native extensions, and
  dependency-rich plugins are not established.
- The API is intentionally loopback-only. TLS, reverse-proxy trust,
  non-loopback deployment, durable/distributed sessions, and hostile-local-user
  defenses are not implemented.
- Source-artifact bytes are not embedded in portable assurance bundles;
  retained hashes support integrity checks but not later source replay.
- Signed/authentication timestamps are caller/host supplied; no trusted time or
  managed online revocation service is present.
- Three symlink-specific unit cases were skipped because the current Windows
  host did not permit symlink creation. Equivalent rejection logic is covered
  by other tests, but those exact host operations were not executed.
- No MSP430, serial port, programmer, firmware, or physical device was accessed.

## Reproduction

```powershell
.\.venv\Scripts\python.exe tools\verify.py
.\.venv\Scripts\python.exe -m pip_audit --local --skip-editable
.\.venv\Scripts\python.exe tools\release_smoke.py `
  --windows-live-broker `
  --sandbox-evidence reports\PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json `
  --live-output reports\SOFTWARE_INTEGRITY_INTERACTION_LIVE_EVIDENCE.json
```

The live command requires the already verified local rootless Podman/WSL2
backend and pinned image. It does not authorize a public release or hardware
operation.
