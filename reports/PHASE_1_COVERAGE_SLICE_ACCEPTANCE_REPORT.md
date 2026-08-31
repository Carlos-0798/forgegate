# ForgeGate Phase 1 coverage evidence slice acceptance report

- Date: 2026-08-30
- Version: 0.1.0.dev2
- Environment: Windows, Python 3.12.10
- Scope: Cobertura/coverage.py XML and LCOV evidence normalization

## Decision

**PASS within the coverage evidence-slice scope.** Both standard coverage
formats now produce provenance-bound `coverage.line` and `coverage.branch`
facts with repository and available package/module scopes. No release threshold
or policy decision is made by either collector.

## Development verification

The pre-release full repository run completed successfully:

- dependency consistency: PASS;
- Ruff lint and formatting: PASS;
- mypy strict across 16 source files: PASS;
- pytest: 164 passed, 1 skipped;
- package branch coverage: 100% across 1,090 statements and 310 branches;
- three example project/policy configurations: VALID;
- committed JSON Schema drift: PASS.

`python tools/release_smoke.py` also passed. The `0.1.0.dev2` sdist contained
the required implementation, fixtures, golden outputs, architecture, and
acceptance report; its wheel installed into a repository-external clean
environment, where `doctor`, configuration validation, JUnit collection,
Coverage XML collection, and LCOV collection all completed successfully.

The skipped test is the existing actual Windows symlink-creation case. This
host still does not permit fixture creation; simulated outside-root resolution
rejection remains covered, while actual symlink behavior is **NOT RUN**.

## Accepted behavior

- exact source bytes, media type, size, and SHA-256 remain attached to every
  normalized record;
- XML parsing is bounded and rejects declarations, malformed structures,
  invalid numeric data, duplicate scoped lines, and inconsistent totals;
- observed XML line/branch counts take precedence over declared root summaries,
  while all mismatches remain visible as warnings;
- LCOV source records enforce ordering, termination, supported tags, duplicate
  checks, summary pairs, and count consistency;
- repository/package/module scopes are deterministic and retained without
  reading the referenced source files;
- missing branch information does not become a fabricated zero; summary-only
  LCOV branch evidence is explicitly disclosed;
- golden outputs cover both standard formats;
- the generic sample remains independent of AFE and MSP430 components.

## Evidence boundaries

- Results are local host-test evidence for ForgeGate's parsers only.
- Fixture percentages are synthetic sample data, not production quality claims.
- Artifact hashes establish byte identity, not producer authenticity.
- Claimed commit, trust, tool version, and verification metadata are not
  independently authenticated.
- No remote CI was run because no remote repository exists.
- No AFE/MSP430 runtime integration, serial access, firmware operation, or
  physical measurement occurred.

## Deferred work

- SARIF 2.1.0 and generic benchmark JSON collectors;
- deterministic policy evaluation and candidate lifecycle;
- SQLite persistence and attestations;
- signed provenance and authenticated CI identity;
- optional AFE/MSP430 compatibility collectors after their public artifact
  contracts are deliberately aligned.
