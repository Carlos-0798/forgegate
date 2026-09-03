# Windows production external-plugin broker

## Scope and status

Phase 20 implements ForgeGate's first external-plugin execution path. It is
explicitly limited to Windows hosts using the verified rootless Podman/WSL2
backend. The production broker has executed one installed, ForgeGate-owned,
pure-Python generic collector fixture through the real container boundary.

`SANDBOXED` is a per-run claim recorded only after authorization against the
committed Phase 19 control evidence and successful cleanup. It is not a claim
that ForgeGate is production-ready, that arbitrary third-party plugins are
trusted, or that Linux and macOS execution are supported.

## Trusted path

The core never imports or calls an external entry point. The execution flow is:

1. validate a content-derived `forgegate.plugin-run-plan.v1` and reserve its
   idempotency key in the separate append-only plugin-run store;
2. require the current Podman capability, pinned image identity, and every
   Phase 19 low-level control to match the committed live evidence;
3. resolve exactly one installed distribution matching the plan's name,
   version, entry point, and manifest;
4. copy its pure-Python top package, the trusted runner, and exact
   content-addressed inputs into a broker-owned private staging directory;
5. start one digest-pinned, shell-free, networkless container using the frozen
   Windows sandbox specification;
6. validate canonical `START`, `READY`, and `RESULT` protocol messages and
   append the corresponding core-authored transitions;
7. copy private tmpfs output twice while the container is alive, require exact
   equality, and reject unexpected members, limits, schema violations,
   unauthorized kinds, or input-reference mismatches;
8. rehash accepted files, atomically register them under a broker-owned output
   root, remove the container and staging directory, and commit one immutable
   `forgegate.plugin-run-receipt.v1`.

The trusted runner is standard-library-only and loaded from the installed
ForgeGate package. External code is imported only inside the disposable
container with isolated Python flags and a constructed environment.

## Output evidence boundary

The only accepted runtime member type is canonical
`forgegate.plugin-output.v1`. Its embedded `EvidenceRecord` must remain
`trust=unsigned_local` and `verification_level=declared`. The broker also
requires the artifact reference to identify an exact run-plan input.

Successful validation creates `PluginValidatedOutput` identities stating only
`CORE_REHASHED_AND_SCHEMA_VALIDATED`. This proves that ForgeGate checked the
bytes and contract. It does not authenticate the plugin publisher, prove the
underlying measurement, or authorize a release transition. Normal evidence
assembly and policy evaluation remain separate operations.

## Durable execution audit

Plugin execution uses a separate SQLite v1 database with ForgeGate application
identity, exact schema version, foreign keys, `FULL` synchronization, WAL, and
no-update/no-delete triggers. It stores canonical run plans, idempotency
bindings, transitions, and terminal receipts.

An exact repeated request returns the existing receipt without executing the
plugin again. If a reserved run has no terminal receipt after interruption, a
later request attempts container/staging cleanup and closes it as `ERROR`; it
never infers success from leftover output. Terminal transition and receipt are
committed in one transaction.

Durable fields contain stable issue codes and bounded execution counts, not raw
stderr, environment values, host paths, credentials, or container identifiers.

## Fail-closed limits

Contract v1 supports one collector, pure-Python distribution files, exact
`artifact-read` plus `filesystem-write` grants, deny-network, deny-subprocess,
sanitized environment, one process, and mandatory CPU/memory/time/output/log
limits. Native extensions and dependency-package staging are rejected.

Any authorization, staging, protocol, output, resource, or cleanup failure that
can be durably recorded produces a terminal error receipt, and no output is
marked accepted. The receipt, not leftover files, is authoritative. Failed
container or staging cleanup is reported as `PLUGIN_CLEANUP_FAILED`.

## Verification and remaining limits

The committed Phase 20 live evidence records 13/13 passing checks through the
production broker, including sandbox denials, canonical protocol completion,
double-snapshot validation, atomic output registration, cleanup, durable
readback, and exact idempotent replay. The clean-wheel release smoke installs
ForgeGate and the standalone sample plugin into an isolated environment before
running the same path.

Still outside this checkpoint:

- publisher signatures, plugin provenance, remote acquisition, automatic
  installation, and an independent plugin repository;
- native-extension or separately packaged dependency support;
- general third-party/adversarial plugin compatibility beyond the fixed
  ForgeGate-owned fixture;
- Linux/macOS execution backends, hardware/device passthrough, or MSP430 use;
- direct CLI/REST run endpoints and automatic promotion of plugin output into a
  candidate's release evidence.
