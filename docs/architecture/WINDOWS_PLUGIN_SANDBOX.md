# Windows external-plugin sandbox readiness

## Scope and current boundary

ForgeGate will initially support external-plugin isolation only on a Windows
host. The selected backend is a rootless Podman machine using WSL2 and Linux
OCI containers. Linux and macOS host backends are deferred and are not
advertised.

Phase 19 implemented capability probing, a fail-closed container creation
specification, and a development-only hostile-fixture verifier. A probe result of
`READY_FOR_ADVERSARIAL_VERIFICATION` still records
`external_plugin_execution=PROHIBITED` and `advertised_isolation_tier=NONE`.
The Phase 20 broker may authorize an exact production run only when that
development record and the current runtime/image capability match. Readiness
alone still grants no execution authority.

## Why Podman on WSL2

The target development host is Windows 11 Home. Client Hyper-V and Windows
Sandbox are not available as supported Home-edition product features. Podman
supports Windows editions through a WSL2-backed, rootless Podman machine and is
Apache-2.0 licensed. Rootless operation reduces the runtime's host authority;
it does not make untrusted code safe by itself.

The installed and reviewed runtime baseline is Podman `v5.8.6` at commit
`a859fc66702c23e869c282c63e92d9b6cd264229`. The probe image is pinned to the
multi-platform OCI digest
`sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db`.
Neither runtime nor image is a ForgeGate Python dependency.

## Capability probe

`forgegate plugins sandbox-status` performs bounded, read-only host inspection:

1. require a Windows host;
2. locate Podman without accepting a caller-selected executable;
3. parse bounded JSON from Podman version, connection, machine, and runtime
   information;
4. require exactly one default SSH connection to loopback;
5. require a running WSL machine provider; and
6. require a rootless Podman runtime; and
7. require the Podman client and machine server versions to match exactly.

The content-derived
`forgegate.windows-plugin-sandbox-capability.v1` report contains only sanitized
host/runtime fields and stable reasons. It never contains the Podman executable
path, SSH identity path, user profile, machine connection port, raw stderr, or
environment values.

## Fail-closed container specification

The command builder accepts only a matching
`windows-podman-wsl2`/`1.0.0` run plan, a digest-pinned OCI image, a
broker-generated container name, separate absolute non-reparse broker roots,
and bounded trusted runner arguments. It fixes these controls:

- `network=none` and isolated IPC;
- read-only root filesystem with implicit writable tmpfs disabled;
- all Linux capabilities dropped and `no-new-privileges` enabled;
- non-root UID `65532`, with container group `0` only so Podman-owned tmpfs
  directories can remain group-private and writable after all capabilities are
  dropped;
- one-PID limit for the initial subprocess-deny contract;
- hard memory and memory-plus-swap ceilings;
- CPU-rate and inherited hard CPU-time limits;
- read-only private input and control mounts;
- bounded, private, no-exec tmpfs output and temporary directories;
- digest-only images with pulling disabled; and
- `/usr/bin/env -i` as the entry point so the trusted runner starts without an
  inherited image environment. CPython deterministically adds only
  `LC_CTYPE=C.UTF-8` beside the explicit run-plan ID.

The builder returns an argument tuple and never invokes a shell. It does not
mount a writable host output directory or the repository, workspace, user
profile, database, Podman socket, device, token, or key.

Podman 5.8.6 rejects `uid=` and `gid=` options on `--tmpfs`. The verified
specification therefore uses root-owned mode `0770` tmpfs mounts with the
non-root process in group `0`; it does not make the directories world-writable
or restore Linux capabilities. The output-byte fixture also demonstrates the
filesystem's page-granularity behavior: the tmpfs rejected a 2 MiB write under
a 1 KiB requested limit after one 4 KiB page, and the host verifier rejected
the retrieved file against the exact 1 KiB plan limit.

## Development live verification

On 2026-09-03, `tools/verify_windows_sandbox_live.py` ran only hard-coded,
ForgeGate-owned fixtures against the local rootless WSL2 machine. Podman client
and server were both 5.8.6. All 14 required controls passed:

- input mutation and undeclared host-file reads fail;
- root filesystem writes fail while only bounded private output succeeds;
- network connection attempts fail;
- child-process creation fails and the complete container is cleaned up;
- the fixture observes only the explicitly constructed environment plus
  CPython's deterministic locale variable;
- CPU, memory, wall-clock, output bytes, output member count, stdout, and
  stderr limits terminate or reject hostile fixtures correctly;
- a pinned trusted runner image starts and is inspected by exact digest;
- output is copied while the private tmpfs is still mounted, then re-counted
  and rehashed by the development host verifier; and
- every container is force-cleaned and confirmed absent.

The exact run record is
[`PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json`](../../reports/PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json).
Its `backend_enforcement_verified=true` claim applies only to those fixtures
and controls. WSL automatically mounts Windows drives into the Podman machine;
the test confirms those paths are not mounted into the disposable container,
but this broader VM-level exposure remains a defense-in-depth limitation.

## Phase 20 production use of the gate

The Windows broker now validates the exact Phase 19 evidence identity and every
required control, reprobes the current rootless local runtime, and rechecks the
pinned image before starting a run. Its successful receipt may advertise
`SANDBOXED` for that exact execution. The `sandbox-status` capability report
itself deliberately remains `PROHIBITED`/`NONE` because it is only a readiness
probe.

The production path enforces the protocol, double-snapshot output validation,
atomic accepted-output registration, append-only `plugin_runs`, deterministic
replay, interruption recovery, and cleanup. See
[`PRODUCTION_PLUGIN_BROKER.md`](PRODUCTION_PLUGIN_BROKER.md) and the committed
[`PHASE_20_WINDOWS_PLUGIN_BROKER_LIVE_EVIDENCE.json`](../../reports/PHASE_20_WINDOWS_PLUGIN_BROKER_LIVE_EVIDENCE.json).

There is no subprocess-only fallback. Linux/macOS external-plugin execution,
publisher trust, native/dependency-rich plugins, and generalized third-party
compatibility remain unsupported.
