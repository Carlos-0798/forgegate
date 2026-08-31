# ForgeGate Phase 1 SARIF evidence slice acceptance report

- Date: 2026-08-30
- Version: 0.1.0.dev3
- Environment: Windows, Python 3.12.10
- Scope: SARIF 2.1.0 summary and finding evidence normalization

## Decision

**PASS within the SARIF evidence-slice scope.** A valid SARIF 2.1.0 artifact now
produces one explicit `static_analysis.summary` record and one
`static_analysis.finding` record per result. A successful zero-result report
still produces summary evidence. No severity threshold, release policy, or
final release decision is applied by the collector.

## Development verification

The pre-release full repository run completed successfully:

- dependency consistency: PASS;
- Ruff lint and formatting: PASS;
- mypy strict across 17 source files: PASS;
- pytest: 226 passed, 1 skipped;
- package branch coverage: 100% across 1,523 statements and 448 branches;
- three example project/policy configurations: VALID;
- committed JSON Schema drift: PASS.

`python tools/release_smoke.py` also passed. The `0.1.0.dev3` source
distribution contained the SARIF implementation, sample, golden projection,
architecture note, and this acceptance report. Its wheel installed into a
repository-external clean environment, where the installed `collect-sarif`
command completed successfully alongside the earlier collection paths.

The skipped test is the existing actual Windows symlink-creation case. This
host does not permit the fixture creation; simulated outside-root resolution
rejection remains covered, while actual symlink behavior is **NOT RUN**.

## Accepted behavior

- exact source bytes, media type, size, and SHA-256 are attached to all records;
- duplicate JSON keys, non-finite numbers, invalid UTF-8, NUL bytes, malformed
  structures, unsupported versions, and resource-limit violations fail closed;
- each supplied invocation must explicitly report successful execution;
- tool/rule metadata, message, level, kind, physical/logical locations,
  fingerprints, suppression state, and baseline state are normalized;
- rule references must be present and unambiguous;
- declared full/partial fingerprints are preferred, while a deterministic
  fallback is visibly labeled as ForgeGate-derived;
- non-normalized complex detail remains in the hash-bound artifact and produces
  an explicit warning;
- the generic sample has no AFE or MSP430 dependency.

## Evidence boundaries

- Results are local host-test evidence for ForgeGate's parser only.
- Fixture findings are synthetic and are not production vulnerability claims.
- Artifact hashes establish byte identity, not producer authenticity.
- Claimed commit, trust, and verification metadata are not authenticated.
- No remote CI ran because no remote repository exists.
- No AFE/MSP430 runtime integration, serial access, firmware operation, or
  physical measurement occurred.

## Deferred work

- generic benchmark JSON collector;
- deterministic policy evaluation and candidate lifecycle;
- SQLite persistence and attestations;
- signed provenance and authenticated CI identity;
- optional AFE/MSP430 compatibility collectors after their public artifact
  contracts are deliberately aligned.
