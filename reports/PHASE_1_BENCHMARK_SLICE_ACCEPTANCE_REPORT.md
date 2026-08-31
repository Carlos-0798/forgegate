# ForgeGate Phase 1 Benchmark evidence slice acceptance report

- Date: 2026-08-30
- Version: 0.1.0.dev4
- Environment: Windows, Python 3.12.10
- Scope: `forgegate.benchmark.v1` metric evidence normalization

## Decision

**PASS within the Benchmark evidence-slice scope.** The final Phase 1 standard
collector now converts each valid, unique scope/name metric into one
provenance-bound `benchmark.metric` record. Values, units, baselines, and
tolerances remain facts; the collector does not decide whether performance
passed or regressed.

## Development verification

The pre-release full repository run completed successfully:

- dependency consistency: PASS;
- Ruff lint and formatting: PASS;
- mypy strict across 18 source files: PASS;
- pytest: 278 passed, 1 skipped;
- package branch coverage: 100% across 1,756 statements and 510 branches;
- three example project/policy configurations: VALID;
- three configuration Schemas and one Benchmark artifact Schema drift checks:
  PASS.

`python tools/release_smoke.py` also passed. The `0.1.0.dev4` source
distribution contained the Benchmark implementation, machine-readable Schema,
sample, golden projection, architecture note, and this acceptance report. Its
wheel installed into a repository-external clean environment, where the
installed `collect-benchmark` command completed successfully alongside the four
earlier standard collection paths.

The skipped test is the existing actual Windows symlink-creation case. This
host does not permit fixture creation; simulated outside-root resolution
rejection remains covered, while actual symlink behavior is **NOT RUN**.

## Accepted behavior

- exact source bytes, media type, size, and SHA-256 remain attached to evidence;
- the versioned ForgeGate-owned schema has exact root/tool/metric/tolerance
  fields and is committed as a machine-readable JSON Schema;
- empty metric arrays and duplicate scope/name identities fail closed;
- invalid UTF-8, NUL bytes, malformed JSON, duplicate keys, unknown fields,
  non-finite/extreme values, and resource-limit violations fail closed;
- optional baselines and explicit absolute/percent tolerances are retained;
- tolerance without baseline is rejected instead of being guessed;
- golden output and CLI tests cover the generic sample;
- the generic sample remains independent of AFE and MSP430 components.

## Evidence boundaries

- Results are local host-test evidence for ForgeGate's parser only.
- Fixture metrics are synthetic and are not production performance claims.
- ForgeGate did not execute the sample benchmark or verify its statistics.
- Artifact hashes establish byte identity, not producer authenticity.
- Claimed commit, environment, trust, and verification metadata are not
  independently authenticated.
- No remote CI ran because no remote repository exists.
- No AFE/MSP430 runtime integration, serial access, firmware operation, or
  physical measurement occurred.

## Deferred work

- deterministic Phase 2 policy evaluation and candidate lifecycle;
- explicit performance regression rules and explanations;
- SQLite persistence and JSON/Markdown attestations;
- signed provenance and authenticated CI identity;
- optional AFE/MSP430 compatibility collectors after their public artifact
  contracts are deliberately aligned.
