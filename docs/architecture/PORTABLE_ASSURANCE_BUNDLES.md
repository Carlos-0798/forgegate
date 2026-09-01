# Portable assurance bundles

## Scope

Phase 11 adds a deterministic, content-addressed export that can be verified
without the originating SQLite database, project tree, network service, or
source repository. The export combines only records already retained and
validated by ForgeGate:

- the exact immutable project profile bound to the candidate;
- the candidate's audited evidence-assembly binding;
- the exact profile-authorized policy bytes and parsed policy;
- the material-bound evaluation, lifecycle chain, and release attestation.

The `forgegate.assurance-bundle.v1` model validates every nested document and
then checks the associations between them. Its content-derived `bundle_id`
changes if any included field changes.

## Directory contract

`candidate export-assurance` publishes one directory named
`assurance-<bundle-sha256>` with exactly three regular, non-symlink files:

```text
assurance-<bundle-sha256>/
  assurance-bundle.json
  manifest.json
  README.md
```

`assurance-bundle.json` is the complete machine-readable document. `README.md`
is a deterministic human summary and limitation notice. `manifest.json` is a
self-identifying `forgegate.assurance-bundle-manifest.v1` document containing
the exact size and SHA-256 of the other two files. Files are staged, flushed,
and atomically renamed into a content-addressed target. An exact rerun verifies
and reuses existing bytes; a conflict fails closed.

## Offline verification

```powershell
forgegate verify-assurance <assurance-directory>
```

The verifier:

1. accepts only a non-symlink directory with the exact member set;
2. enforces 16 MiB for the bundle document and 64 KiB for each auxiliary file;
3. requires strict UTF-8 JSON, unique keys, finite numbers, and strict models;
4. revalidates every nested content identity and cross-document association;
5. regenerates canonical JSON, Markdown, and manifest bytes;
6. checks the content-addressed directory name and returns a bounded summary.

It never opens paths named by evidence or policy metadata. Verification is
therefore independent of the source project and safe to run without its
database, but it is not a collector replay.

## Evidence and trust boundary

The bundle explicitly declares
`verification_scope=retained_documents_and_embedded_policy_bytes` and
`source_artifact_bytes=not_embedded`. Collector receipts retain source
references, sizes, and hashes, but source JUnit, coverage, SARIF, benchmark, AFE,
or future MSP430 artifact bytes are not copied into this Phase 11 format.

Consequently, successful offline verification proves internal consistency and
exact retained policy bytes. It does not prove that source artifacts remain
available, independently recompute collector outputs, authenticate a producer
or operator, establish trusted time, provide a digital signature, or promote
software evidence into bench, hardware, field, or production evidence.

The `unsigned_local` assurance label remains unchanged. Authenticated identity
is still required before any non-loopback service deployment.
