# ForgeGate Phase 1 JUnit evidence slice acceptance report

- Date: 2026-08-30
- Version: 0.1.0.dev1
- Environment: Windows, Python 3.12.10
- Scope: local artifact registration and JUnit-to-evidence normalization

## Decision

**PASS within the JUnit evidence-slice scope.** The artifact registry, bounded
JUnit collector, normalized `test.summary` evidence, audit results, CLI preview,
and golden output are implemented and locally verified. This checkpoint is
pre-MVP and does not contain a policy engine or release decision.

## Development verification

`python tools/verify.py` completed successfully:

- dependency consistency: PASS;
- Ruff lint and formatting: PASS;
- mypy strict across 15 source files: PASS;
- pytest: 88 passed, 1 skipped;
- package branch coverage: 100% across 592 statements and 118 branches;
- three example project/policy configurations: VALID;
- committed JSON Schema drift: PASS.

`python tools/release_smoke.py` also passed: the sdist manifest was complete,
the `0.1.0.dev1` wheel installed into a repository-external clean environment,
and the installed CLI completed `doctor`, configuration validation, and the
sample JUnit collection path.

The skipped case attempts to create an actual outside-root Windows symlink. The
host did not grant symlink creation. Outside-root resolved-path rejection is
still covered with a simulated resolver, but actual symlink behavior on this
host is recorded as **NOT RUN**, not PASS.

## Accepted behavior

- a registry accepts only relative, root-confined, regular files within an 8
  MiB default limit;
- exact artifact bytes are hashed with SHA-256 and checked for stable size and
  modification metadata during the read;
- changed bytes under an already registered path fail closed;
- the collector rejects NUL/unsupported encoding, DOCTYPE/ENTITY declarations,
  malformed XML, unsupported roots, excess depth/elements, invalid or
  inconsistent counts/durations, and conflicting testcase outcomes;
- testcase-derived observations take precedence over declared aggregate counts,
  with mismatches retained as audit warnings;
- incomplete durations remain unknown rather than becoming a partial total;
- normalized evidence remains bound to the supplied commit, source tool,
  collection time, trust claim, verification level, and artifact identity;
- collection completion and test outcome are distinct from a future release
  decision.

## Evidence boundaries

- Results are `LOCAL_HOST_TEST` evidence only.
- A SHA-256 hash establishes byte identity, not producer authenticity.
- Caller-supplied commit, trust, and verification metadata remain claims.
- No remote CI was run because no remote repository has been created.
- No AFE/MSP430 integration was implemented and no connected hardware, serial
  port, firmware, or FRAM was accessed.

## Deferred work

- policy evaluation and candidate lifecycle;
- SQLite persistence and attestations;
- coverage, SARIF, and benchmark collectors;
- signed provenance and authenticated CI identity;
- optional AFE and MSP430 compatibility collectors after public artifact
  contracts are aligned.
