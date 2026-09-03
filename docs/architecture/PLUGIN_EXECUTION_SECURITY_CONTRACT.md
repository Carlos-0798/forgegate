# External plugin execution security contract

## Status and boundary

Phase 18 defined the contract that had to exist before ForgeGate could execute
an external plugin. Phase 20 now implements that contract for one Windows-only
rootless Podman/WSL2 path. Phase 17 discovery remains import-free and every
discovery result remains `execution=NOT_LOADED`; execution requires a separate
approved run plan and broker call.

The core rule is fail-closed: a valid manifest proves only that metadata is
well-formed. It does not authenticate the publisher, approve a capability,
grant a permission, or make plugin code safe to execute.

## Reference-informed decisions

The design adopts four ideas from reviewed upstream projects without copying
their source code:

1. in-toto's fixed statement plus typed predicate separation informs a stable
   run envelope that binds output to immutable input subjects;
2. Witness's attestor enumeration and per-attestor schema surface informs
   schema inspection before execution and separation of collection from policy;
3. OPA's policy-decision/enforcement separation informs a broker that enforces
   grants independently of both plugin declarations and policy output;
4. pluggy's explicit hook specification/implementation contract informs a
   versioned callable protocol, while its same-process execution model is
   explicitly rejected for untrusted ForgeGate plugins.

Exact upstream revisions, licenses, local-reference handling, and adoption
limits are recorded in
[`docs/research/OPEN_SOURCE_REFERENCE_REVIEW.md`](../research/OPEN_SOURCE_REFERENCE_REVIEW.md).

## Trust domains

The following components are separate trust domains:

- **core** validates public ForgeGate contracts and makes release decisions;
- **broker** converts an approved run plan into enforceable operating-system
  controls and owns all plugin I/O;
- **runner** hosts one plugin process and is disposable;
- **plugin** is untrusted code, including its dependencies;
- **artifact store** exposes only content-addressed inputs selected for one run;
- **audit store** retains core-authored run state and validated result identity.

No plugin process receives the candidate database, trust store, signing key,
GitHub token, inherited user environment, or unrestricted workspace path.

## Versioned callable protocol

The first runtime protocol will be an out-of-process, bounded JSON message
exchange. It will not use `EntryPoint.load` in the core process.

Before spawning anything, the core must construct a content-derived run plan
that contains at least:

- protocol and Plugin API versions;
- plugin ID, distribution/version, entry-point name, and exact `manifest_id`;
- one requested capability and its versioned input schema;
- immutable input subject names, media types, sizes, and SHA-256 values;
- declared permissions, separately approved grants, and the enforcing backend;
- wall-clock, CPU, memory, output-byte, file-count, and process-count limits;
- a sanitized working-directory policy and network/subprocess policy;
- a content-derived `run_plan_id`.

The broker must pass inputs by broker-created handles or private staged copies,
not caller-selected absolute paths. Every request and response must have a
fixed schema version, bounded byte size, duplicate-key and non-finite-number
rejection, strict UTF-8, a monotonically increasing sequence number, and the
same run-plan identity. Unknown messages fail the run.

Plugin output is a proposal, never trusted evidence by itself. The core must
re-read broker-owned output files, enforce the declared member set and limits,
recompute content digests, validate every evidence schema, and only then create
a separate ForgeGate collection record. A plugin cannot directly transition a
candidate, evaluate policy, sign an assurance bundle, or write audit rows.

The public execution-document surface consists of:

- `forgegate.plugin-run-plan.v1`, which binds the exact manifest, target,
  inputs, authority, isolation tier, policies, resource limits, and UTC time;
- `forgegate.plugin-protocol-message.v1`, which permits only ordered
  `START`, `READY`, `RESULT`, and `ERROR` envelopes;
- `forgegate.plugin-run-transition.v1`, which binds each legal state change to
  its predecessor and optional protocol message; and
- `forgegate.plugin-run-result.v1`, which revalidates the complete terminal
  chain and binds only core-rehashed, schema-validated output identities;
- `forgegate.plugin-output.v1`, the low-trust proposal written by the isolated
  plugin; and
- `forgegate.plugin-run-receipt.v1`, the immutable broker result binding
  protocol messages, execution counters, cleanup, output registration, and the
  complete terminal result.

These documents can be constructed, serialized, Schema-checked, and replay-
validated without loading a plugin. A receipt claims backend enforcement only
for its exact authorized run; the committed Windows live report supplies the
corresponding local-host evidence.

## Permissions and enforcement

Permissions are deny-by-default and have three distinct values:

1. **declared**: the manifest's maximum requested authority;
2. **approved**: the project/run policy's narrower authorization;
3. **enforced**: controls the selected backend can actually guarantee.

The enforced set must be a subset of the approved set, which must be a subset
of the declared set. Any mismatch produces `PLUGIN_PERMISSION_UNENFORCEABLE`
before process start.

Initial external plugins may receive only content-addressed artifact reads and
bounded private temporary writes. Network, secrets, notifications, child
processes, device access, arbitrary filesystem reads/writes, database access,
and host environment inheritance remain denied. Adding any permission requires
a versioned contract, threat-model update, adversarial tests, and a backend
that can enforce it on every supported platform.

## Isolation and resource limits

A subprocess boundary alone is not a sandbox. ForgeGate must declare the
selected backend and assurance tier in every run record:

| Tier | Meaning | External plugin policy |
|---|---|---|
| `NONE` | in-process or no enforceable boundary | forbidden |
| `PROCESS_ONLY` | separate process, sanitized protocol, timeout only | forbidden for untrusted plugins |
| `SANDBOXED` | filesystem/network/process grants and resource limits are enforced | eligible after verification |

The implementation must fail with `PLUGIN_ISOLATION_UNAVAILABLE` when the host
cannot supply the required tier. ForgeGate will not silently weaken isolation
on Windows, Linux, or macOS. Backend-specific mechanisms and their limitations
must be tested and reported separately; Docker or another container runtime is
not a current prerequisite merely because it may be one future backend.

The broker must independently enforce startup and total timeouts, bounded
stdout/stderr capture, output size/file count, process count, and cleanup. CPU
and memory limits are mandatory for `SANDBOXED`; if a platform cannot enforce
them, execution does not start. Timeout or limit failures terminate the process
tree and discard unvalidated output.

## Durable run audit

The append-only run record distinguishes:

`PLANNED -> STARTING -> RUNNING -> SUCCEEDED | ERROR | CANCELLED`

Only the core writes transitions. Each transition binds the run-plan ID,
plugin/manifest identity, enforcement backend/tier, granted permissions,
timestamps, bounded exit metadata, sanitized stable issue codes, validated
output evidence IDs, and the previous transition identity. Raw plugin stderr,
absolute paths, environment variables, secrets, and tokens are not durable
audit fields.

An exact completed replay may return the existing immutable result. A changed
plan or changed input digest is a new run. Crash recovery may only close an
abandoned run as `ERROR`; it may not infer success from files left on disk.

## Stable failure mapping

At minimum, the implementation must preserve these categories:

| Code | Boundary |
|---|---|
| `PLUGIN_PLAN_INVALID` | plan identity, capability, input, or schema invalid |
| `PLUGIN_PERMISSION_DENIED` | requested grant is not approved |
| `PLUGIN_PERMISSION_UNENFORCEABLE` | backend cannot enforce the approved set |
| `PLUGIN_ISOLATION_UNAVAILABLE` | required isolation tier is unavailable |
| `PLUGIN_START_FAILED` | runner could not start safely |
| `PLUGIN_PROTOCOL_INVALID` | malformed, oversized, out-of-order, or mismatched message |
| `PLUGIN_TIMEOUT` | startup or total deadline exceeded |
| `PLUGIN_RESOURCE_LIMIT` | CPU, memory, output, file, or process limit exceeded |
| `PLUGIN_EXIT_ERROR` | bounded nonzero/abnormal process termination |
| `PLUGIN_OUTPUT_INVALID` | result members, digests, or evidence schemas invalid |
| `PLUGIN_AUDIT_FAILED` | required durable transition could not be committed |
| `PLUGIN_CANCELLED` | an authorized cancellation closed the run |

All failure codes map to the plugin run's `ERROR` state; `PLUGIN_CANCELLED`
maps only to `CANCELLED`. Neither outcome automatically changes a release
candidate. A later policy may explicitly consume validated run evidence and
decide how absence, error, or cancellation affects the release.

## Implementation gates

The initial Windows execution path is enabled because all of the following are
implemented and verified for the fixed generic fixture:

1. **implemented:** strict run-plan, protocol-message, transition, and result
   models plus JSON Schemas and content-derived identities;
2. **implemented:** one explicitly Windows-scoped `SANDBOXED` backend with
   denial tests for filesystem, network, child-process, environment, and
   resource escape;
3. **implemented:** append-only durable run audit with crash recovery and
   deterministic replay;
4. **implemented:** broker-side staged inputs and output re-registration with
   double-snapshot race defenses;
5. **implemented:** clean-wheel install/discover/run/remove independence tests using a generic
   hostile fixture;
6. **implemented:** documentation and reports that continue to separate discovery,
   compatibility, execution, validated software evidence, CI, and hardware.

Publisher signatures and trust, remote plugin acquisition, automatic install,
plugin repositories, and production-quality example publication are later
decisions. None is implied by this contract.

The implementation and its remaining pure-Python, Windows, and evidence-trust
limits are detailed in
[`PRODUCTION_PLUGIN_BROKER.md`](PRODUCTION_PLUGIN_BROKER.md).
