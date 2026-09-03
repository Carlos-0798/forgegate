# Phase 21 plugin operator workflow acceptance report

- Date: 2026-09-03 (America/New_York)
- Version: 0.1.0a1
- Scope: Windows operator CLI, durable run queries, and accepted-output
  collection into the ordinary ForgeGate evidence pipeline
- Hardware/serial activity: NOT PERFORMED

## Outcome

**PASS for the Phase 21 operator-facing workflow using the ForgeGate-owned
generic plugin fixture.**

The CLI can now freeze and execute an authorized plugin run, replay an exact
idempotent request, show one path-free record, page path-free summaries, and
collect the accepted output only after the core revalidates its exact member,
digest, size, schema, run identity, evidence identity, and original inputs.
Terminal failures remain queryable and cannot be collected.

This does not authenticate a plugin publisher or elevate plugin-produced
evidence above `unsigned_local` and `declared`.

## Accepted chain

| Boundary | Accepted behavior |
|---|---|
| Selection | exactly one compatible collector and one explicit input schema |
| Inputs | operator supplies `PATH=MEDIA_TYPE`; exact bytes are registered before planning |
| Authorization | requested grants must exactly cover declared plugin permissions |
| Execution | CLI delegates only to the Phase 20 Windows broker and verified sandbox evidence |
| Replay | the same idempotency key and frozen plan return the same durable receipt |
| Query | `plugins show` and `plugins runs` expose content-addressed, path-free documents |
| Collection | only successful, core-registered output can enter the normal evidence model |
| Failure | terminal failure is persisted, returned with exit code 3, and rejected by collection |

The focused tests cover successful and failed CLI chains, exact plan
construction, discovery/schema ambiguity, stable cursor paging, tamper and
input-change rejection, strict document loading, path privacy, and evidence
assembly compatibility.

## Verification

| Check | Result |
|---|---|
| Phase 21/22 focused tests | PASS - 16 tests |
| Full pytest | PASS - 760 passed, 3 Windows-symlink skips |
| Branch-aware package coverage | PASS - 95.06% across 8,706 statements and 2,424 branches |
| Ruff lint and format | PASS |
| mypy strict | PASS - 73 source/tool files |
| Schema and OpenAPI drift | PASS - 41 document plus 2 artifact Schemas |
| Windows CLI run/replay/show/page/collect chain | PASS - local clean-wheel test |
| Evidence assembly and policy handoff | PASS - local clean-wheel test |

## Evidence boundary

No MSP430, serial port, connected device, or physical measurement was
accessed. The live path uses a controlled generic software fixture; it is not
broad third-party compatibility, bench evidence, or production deployment.
