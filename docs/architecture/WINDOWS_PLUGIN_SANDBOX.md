# Windows external-plugin sandbox readiness

## Scope and current boundary

ForgeGate will initially support external-plugin isolation only on a Windows
host. The selected backend is a rootless Podman machine using WSL2 and Linux
OCI containers. Linux and macOS host backends are deferred and are not
advertised.

This checkpoint implements capability probing and a fail-closed container
creation specification. It does not execute a plugin. A probe result of
`READY_FOR_ADVERSARIAL_VERIFICATION` still records
`external_plugin_execution=PROHIBITED` and `advertised_isolation_tier=NONE`.
Only a later adversarial verification record may authorize the backend for a
run plan.

## Why Podman on WSL2

The target development host is Windows 11 Home. Client Hyper-V and Windows
Sandbox are not available as supported Home-edition product features. Podman
supports Windows editions through a WSL2-backed, rootless Podman machine and is
Apache-2.0 licensed. Rootless operation reduces the runtime's host authority;
it does not make untrusted code safe by itself.

The reviewed runtime baseline is Podman `v5.8.3` at commit
`3a2e1c7e9c15a218768206af59ab2974271ebf4f`. The probe image is pinned to the
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
6. require a rootless Podman runtime.

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
- non-root UID/GID `65532`;
- one-PID limit for the initial subprocess-deny contract;
- hard memory and memory-plus-swap ceilings;
- CPU-rate and inherited hard CPU-time limits;
- read-only private input and control mounts;
- bounded, private, no-exec tmpfs output and temporary directories;
- digest-only images with pulling disabled; and
- `/usr/bin/env -i` as the entry point so the trusted runner starts without an
  inherited image environment.

The builder returns an argument tuple and never invokes a shell. It does not
mount a writable host output directory or the repository, workspace, user
profile, database, Podman socket, device, token, or key.

## Remaining proof gate

The following must pass on the actual Windows/WSL2/Podman host before the
backend may advertise `SANDBOXED` or execute external code:

- input mutation and undeclared host-file reads fail;
- root filesystem writes fail while only bounded private output succeeds;
- network connection attempts fail;
- child-process creation fails and the complete container is cleaned up;
- the runner observes only the explicitly constructed environment;
- CPU, memory, wall-clock, output bytes, output member count, stdout, and
  stderr limits terminate or reject hostile fixtures correctly;
- a pinned trusted runner image starts and is inspected by exact digest; and
- broker-side output copy, rehash, schema validation, race defense, and durable
  run audit are implemented.

Until those checks pass, `PLUGIN_ISOLATION_UNAVAILABLE` is the only valid
execution result. There is no subprocess-only fallback.
