# Phase 19 Windows sandbox live verification report

- Date: 2026-09-03 (America/New_York)
- Version: 0.1.0.dev27
- Scope: Windows-only low-level Podman/WSL2 sandbox control verification
- External plugin execution: NOT PERFORMED and PROHIBITED
- Hardware/serial activity: NOT PERFORMED

## Outcome

**PASS for all 14 low-level controls exercised by fixed ForgeGate-owned hostile
fixtures; NOT ACCEPTED for production external-plugin execution.**

The workstation now has a dedicated rootless WSL2 Podman machine. The client
and server are both Podman 5.8.6. The development verifier created disposable
containers from an exact digest-pinned image and confirmed the required
filesystem, network, process, environment, resource, output, log, image,
runtime, and cleanup behavior.

The public capability report intentionally remains
`READY_FOR_ADVERSARIAL_VERIFICATION`, with external execution `PROHIBITED` and
advertised isolation tier `NONE`. The production broker, runner protocol,
output-schema/race validation, artifact re-registration, append-only
`plugin_runs`, and crash recovery are not implemented.

## Runtime identity

| Item | Observed value |
|---|---|
| Host | Windows 11 Home, AMD64 |
| WSL | 2.7.12.0; WSL2 machine provider |
| Machine | `forgegate-sandbox`; rootless; 2 CPU; 4 GiB memory; 512 MiB swap; 20 GiB disk |
| Podman client | 5.8.6; commit `a859fc66702c23e869c282c63e92d9b6cd264229` |
| Podman server | 5.8.6; commit `a859fc66702c23e869c282c63e92d9b6cd264229` |
| Probe image | `docker.io/library/python@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db` |
| Local image ID | `sha256:acf8897bf01a3a0ea273a50a58fc10b6317a3e360bd29aa7c9246a54d7c63e88` |
| Live report ID | `sha256:5296f70996ff9928d54557fb97c2e667f15ccdd67ff989b85b518260cb3db38d` |

Podman is an external development runtime, not a ForgeGate Python dependency.
No Podman source or binary is committed to this repository, and ForgeGate's
License status is unchanged.

## Verified controls

| Control | Result | Fixture evidence |
|---|---|---|
| Local WSL2 machine | PASS | running local-loopback WSL provider |
| Rootless runtime | PASS | Podman security metadata reports rootless |
| Pinned image | PASS | requested digest and inspected content identity checked |
| Read-only root | PASS | root write rejected |
| Private input mount | PASS | declared input readable; mutation and undeclared `/mnt/c` read rejected |
| Network deny | PASS | outbound connection rejected under `network=none` |
| Subprocess deny | PASS | child creation rejected under the one-PID policy |
| Empty environment | PASS | only run-plan ID and CPython-added `LC_CTYPE=C.UTF-8` observed |
| Memory limit | PASS | 64 MiB fixture OOM-killed with non-zero exit |
| CPU limit | PASS | CPU loop terminated before the wall limit |
| Total timeout | PASS | sleeping fixture killed by the host deadline |
| Bounded private output | PASS | tmpfs write stopped; host byte/member revalidation rejected excess |
| Bounded log capture | PASS | stdout and stderr floods retained exactly 1,024 bytes each before kill |
| Cleanup | PASS | every disposable container was removed and confirmed absent |

The exact case timings, exit states, bounded log previews, output members, and
hashes are retained in
[`PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json`](PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json).
That file contains no username, local absolute path, email address, token, key,
Podman SSH identity path, or hardware data.

## Failures found and corrected during live verification

1. Podman 5.8.6 rejected `uid=`/`gid=` in the `--tmpfs` option. The command now
   runs non-root UID 65532 with group 0 and root-owned mode 0770 tmpfs mounts;
   all Linux capabilities remain dropped and the directories are not
   world-writable.
2. Copying a stopped container's tmpfs returned no files because the mount had
   already been destroyed. The verifier now detects a bounded completion
   marker, copies and rehashes output while the container is alive, then kills
   and removes it.
3. Buffered pipe reads delayed the completion marker until process exit. The
   verifier now uses bounded immediate OS-level reads and still kills the
   container as soon as either log limit is exceeded.
4. A fresh Podman machine initially exposed a 5.8.3 client/5.8.6 server mismatch.
   The capability model now records both versions and rejects any mismatch.

These failures are retained because the initial code-only specification did
not prove actual Podman behavior.

## Local verification

| Check | Result |
|---|---|
| Windows sandbox focused tests | PASS — 20 |
| Fixed hostile controls | PASS — 14/14 |
| Full pytest | PASS — 723 passed, 3 Windows-symlink skips |
| Branch-aware package coverage | PASS — 96.23% across 7,601 statements and 2,082 branches |
| Ruff lint and format | PASS |
| mypy strict | PASS — 67 source/tool files |
| Schema and OpenAPI drift | PASS |
| dev27 sdist/wheel clean-install smoke | PASS |

## Residual risks and next gate

WSL automatically mounts Windows drives inside the Podman machine. The
disposable test container could not read `/mnt/c`, because ForgeGate mounts only
its separate input/control roots, but machine-level drive exposure remains a
defense-in-depth limitation. The live verifier also tests only fixed project
fixtures, not an installed third-party plugin.

Phase 20 must implement and test the production broker/runner boundary before
any external callable is loaded. No administrator, publication, License,
Release, LinkedIn, or hardware action is required for this checkpoint.
