# Phase 18 plugin execution contract-model acceptance report

- Date: 2026-09-01 (America/New_York)
- Version: 0.1.0.dev25
- Scope: public plugin run-plan, protocol-message, transition, validated-output,
  and terminal-result contracts
- External plugin execution: NOT PERFORMED
- Hardware/serial activity: NOT PERFORMED

## Outcome

**PASS for the Phase 18 public contract-model gate.** ForgeGate can now
construct, load, serialize, Schema-export, content-address, and replay-validate
the documents that a future external-plugin broker must obey. The same full
verification and release smoke passed on Windows, Ubuntu, and macOS. No plugin
entry point was imported, no subprocess was started, and no sandbox capability
is claimed.

## Implemented contracts

| Contract | Enforced model boundary |
|---|---|
| `forgegate.plugin-run-plan.v1` | exact manifest/target, collector capability and input schema, logical content-addressed inputs, canonical declared/approved/enforced permissions, `SANDBOXED` tier, deny-network/subprocess policies, resource limits, UTC time, derived ID |
| `forgegate.plugin-protocol-message.v1` | protocol v1, plan identity, sequences 0–2, direction/kind-specific `START`/`READY`/`RESULT`/`ERROR` payloads, derived ID |
| `forgegate.plugin-run-transition.v1` | legal `PLANNED`/`STARTING`/`RUNNING`/terminal edges, predecessor identity, monotonic replay fields, output-or-issue terminal shape, derived ID |
| `forgegate.plugin-run-result.v1` | complete plan-bound transition chain, terminal consistency, stable issue or validated outputs, output count/byte/kind limits, derived output-set and result IDs |

`PluginValidatedOutput` requires the explicit
`CORE_REHASHED_AND_SCHEMA_VALIDATED` marker and participates in both per-output
and output-set identities. The marker is a document invariant for a future core
validation path; this phase did not create output from external code.

## Fail-closed decisions

- Plugin API v1 execution planning supports only collector capability.
- The manifest is the maximum declared authority; approved grants cannot
  exceed it, and every approved grant must be represented in the enforced set.
- The initial contract accepts only brokered artifact reads and private bounded
  writes. Network, secrets, notifications, and subprocess grants fail closed.
- Untrusted execution plans accept only `SANDBOXED`; `NONE` and `PROCESS_ONLY`
  cannot be serialized as valid v1 plans.
- Subjects are logical relative names, never absolute paths, drive paths,
  backslash paths, empty segments, or parent traversal.
- Stable issue enums carry no raw stderr, path, token, environment value, or
  secret-bearing free text.
- A terminal result revalidates every sequence, predecessor, state, timestamp,
  plan ID, output identity, evidence kind, count, and byte bound.

## Local verification

| Check | Result |
|---|---|
| Focused execution-contract tests | PASS — 7 |
| Full pytest | PASS — 703 passed, 3 Windows-symlink skips |
| Branch-aware package coverage | PASS — 96.59% across 7,315 statements and 1,982 branches |
| Ruff lint and format | PASS |
| mypy strict | PASS — 65 source files |
| JSON Schema drift | PASS — 35 document plus 2 artifact Schemas |
| Public configuration loading | PASS — all four new document roots |
| OpenAPI drift and existing examples | PASS |
| Windows/Ubuntu/macOS CI | PASS — run [33569520396](https://github.com/Carlos-0798/forgegate/actions/runs/33569520396), commit `425038d363599d28fa33a4ae060441a6b0899c50` |

The skipped tests require Windows symlink creation and are unrelated to plugin
execution contracts. Ubuntu and macOS exercised those paths. This CI proves the
committed software verification and packaging commands ran on those hosts; it
does not prove plugin execution, sandboxing, or production readiness.

## Remaining execution gates

External plugin execution remains prohibited until ForgeGate implements and
adversarially verifies:

1. a `SANDBOXED` backend for each platform it advertises;
2. broker-owned staged input and output re-registration with race defenses;
3. bounded process/protocol transport, cleanup, and resource enforcement;
4. append-only durable `plugin_runs`, crash recovery, and exact replay; and
5. clean-wheel hostile-fixture execution/removal independence tests.

Publisher trust, remote acquisition, automatic installation, a separate plugin
repository, and hardware collectors remain outside this slice.

## Human-intervention boundary

No owner action is required for the next local implementation slice. Explicit
approval remains required before repository visibility or License changes,
Release publication, LinkedIn linkage, a new remote/plugin repository, or
hardware/serial work.
