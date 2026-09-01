# Phase 18 environment, reference, and execution-contract report

- Date: 2026-09-01 (America/New_York)
- Scope: development prerequisites, optional connector/plugin need, licensed
  upstream references, and external-plugin execution security design
- Hardware/serial activity: NOT PERFORMED
- External plugin execution: NOT PERFORMED

## Outcome

**PASS for continued ForgeGate software development.** The required local tool
chain is complete, direct development dependencies are consistent, three
high-value reference repositories were downloaded outside the ForgeGate
repository, and the Phase 18 execution security contract is documented.

No Codex/ChatGPT connector, ForgeGate runtime dependency, Node.js tool, Docker
runtime, `uv`, or `pipx` was required or installed. Adding them now would not
exercise a current product path and would create unverified maintenance and
security surface.

## Required environment

| Component | Audited result | Status |
|---|---|---|
| Windows | Windows 11 host | PASS |
| Python | 3.12.10 in repository virtual environment | PASS |
| pip dependency consistency | `pip check` reports no broken requirements | PASS |
| Git | 2.55.0.windows.3 | PASS |
| GitHub CLI | 2.98.0, authenticated to the approved account | PASS |
| PowerShell | 7.6.4 | PASS |
| Git Bash | 5.3.15; POSIX setup script syntax accepted | PASS |
| Repository visibility | Private, default branch `main` | PASS |
| Commit privacy | configured noreply identity; private email not recorded | PASS |
| Repository-local long paths | `core.longpaths=true` | PASS |

The PowerShell setup path completed from the existing environment and retained
the constrained direct dependency versions. Available major updates for mypy,
pytest, and pytest-cov are outside the declared compatibility ranges and were
not installed without a compatibility phase. The older environment pip remains
functional and is not a ForgeGate runtime dependency.

## Optional Windows settings

Windows Developer Mode and the system `LongPathsEnabled` policy are currently
disabled. They are not release blockers:

- three local tests that require creating real symlinks remain explicitly
  skipped, while the same suite runs on Linux and macOS private CI;
- repository-local Git long-path support is enabled and current build/install
  paths pass;
- enabling either Windows setting is a system-wide administrative choice, so
  no registry mutation was performed.

Owner intervention is optional only if full local Windows symlink execution is
desired. It is not needed for the next ForgeGate implementation phase.

## Plugin and connector decision

The current task was completed with built-in filesystem/shell/web capabilities
and the existing GitHub CLI session. The available project-management,
financial, media, storage, and design connectors do not provide a required
ForgeGate capability. No external Codex/ChatGPT plugin was installed.

ForgeGate's own Phase 17 sample plugin remains a build-only, import-hostile
fixture. It is installed and removed only inside the clean release smoke test;
the development environment finishes with no external ForgeGate plugin loaded.

## Open-source references

The following official GitHub projects were reviewed at exact revisions:

- in-toto Attestation Framework `2dcd055e9f72e746687c306e35f4e59720ff45be`
  (Apache-2.0), shallow-cloned externally;
- in-toto Witness `3041b832ddcc59865e645e07048851b5e78746c1`
  (Apache-2.0), shallow-cloned externally;
- pluggy `4821148db2f4c6daa62ad8bdcae2918ecf27a731` (MIT),
  shallow-cloned externally;
- Open Policy Agent `88c2ee0cdc9087ab1c3f09b95fa2b9ba5c8f69f5`
  (Apache-2.0), source-reviewed without a large local clone;
- OpenSSF Scorecard `d1fab88f54636ff366076edfc5c239f97b3c8e66`
  (Apache-2.0), source-reviewed without a large local clone.

No third-party source, binary, lock file, or license text was copied into
ForgeGate. The exact review and adopted/rejected ideas are in
`docs/research/OPEN_SOURCE_REFERENCE_REVIEW.md`.

## Resulting optimization

`docs/architecture/PLUGIN_EXECUTION_SECURITY_CONTRACT.md` now freezes the
pre-execution design boundary:

- core/broker/runner/plugin/artifact/audit trust-domain separation;
- an out-of-process bounded versioned protocol and content-derived run plan;
- broker-owned staged input and output re-registration;
- deny-by-default declared/approved/enforced permission subsets;
- explicit `NONE`, `PROCESS_ONLY`, and `SANDBOXED` tiers with no silent
  downgrade;
- startup/total timeout, CPU, memory, output, file, process, and log limits;
- stable failure-to-`ERROR` codes and append-only run transitions;
- implementation gates that prohibit external code until enforcement and
  adversarial verification exist.

Phase 18 is a design claim only. No plugin callable was imported, subprocess
started, permission granted, sandbox advertised, or `plugin_runs` record
created.

## Local verification

| Check | Result |
|---|---|
| PowerShell environment bootstrap | PASS |
| `pip check` | PASS |
| Ruff lint and format | PASS |
| mypy strict | PASS, 64 source files |
| pytest | PASS, 696 passed and 3 Windows-symlink skips |
| Branch-aware coverage | PASS, 97.55% |
| Committed JSON Schema/OpenAPI drift | PASS |
| Example contracts | PASS |
| sdist/wheel and source manifest | PASS |
| Clean external wheel installation | PASS |
| Sample plugin install/discover/uninstall | PASS, always `NOT_LOADED` |
| Clean installed core after plugin removal | PASS |
| Release smoke | PASS |
| Windows/Linux/macOS private CI | PASS — run 33566424223 for `3682361d9d3881ece12352048d2a5a19920bbae2` |

The dependent generic GitHub Action fixture job also passed in the same run.
CI proves the existing verification and release-smoke commands executed on the
three hosted operating systems; it does not prove plugin execution, sandboxing,
hardware behavior, or production readiness.

## Human-intervention boundary

No owner action is required to continue. Explicit owner authorization remains
required before changing repository visibility, selecting a License, creating
a Release, publishing/connecting LinkedIn, creating a separate production
plugin remote, or performing hardware/serial work. System-wide Windows
Developer Mode or long-path policy changes remain optional owner/admin actions.
