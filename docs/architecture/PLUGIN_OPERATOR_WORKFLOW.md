# Plugin operator workflow

## Scope

Phase 21 exposes the existing Windows production broker through four bounded
commands: `plugins run`, `plugins show`, `plugins runs`, and `plugins collect`.
The commands do not weaken the Phase 18–20 security contract. Linux and macOS
remain unsupported execution hosts, and discovery still imports no plugin code.

## Authority and execution

`plugins run` requires one exact compatible collector ID, one or more explicit
`PATH=MEDIA_TYPE` input subjects, explicit permission grants, an explicit UTC
planning time, an operator idempotency key, and the retained Phase 19 sandbox
evidence. ForgeGate registers the current input bytes, selects exactly one
installed distribution, freezes the manifest and entry point in a content-
addressed run plan, and delegates only that plan to the Windows broker.

The required collector permissions are `artifact-read` and
`filesystem-write`. Requested network, secrets, notification, or subprocess
authority remains unenforceable and fails before execution. A failed terminal
receipt is printed before exit code `3`, so the durable failure remains
queryable.

## Path-free audit reads

`plugins show` returns `forgegate.plugin-run-record.v1`; `plugins runs` returns
a bounded `forgegate.plugin-run-page.v1` ordered by run-plan ID. These documents
contain logical input names, immutable identities, state transitions, sanitized
issue codes, and terminal receipts. They contain no database, work-directory,
accepted-output, container, installation, or host path.

## Evidence projection

`plugins collect` accepts only a successful terminal receipt. It re-reads the
broker-owned output directory, requires the exact recorded member set, sizes,
SHA-256 digests, canonical JSON, run ID, evidence IDs, and evidence kinds, then
re-registers every original input artifact. The emitted ordinary
`CollectionResult` can be saved beneath the artifact root and passed to
`assemble-evidence`.

This projection does not promote trust. External-plugin evidence must remain
`unsigned_local` and `declared`; successful collection is not a policy decision,
producer authentication, physical verification, or deployment approval.

## Remaining boundary

Publisher trust, remote acquisition, automatic installation, native extensions,
separately packaged dependencies, REST execution, and non-Windows backends are
not part of this phase. The only live acceptance fixture is the ForgeGate-owned
generic pure-Python collector.
