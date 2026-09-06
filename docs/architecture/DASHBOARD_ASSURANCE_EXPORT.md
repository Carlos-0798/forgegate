# Dashboard assurance export

## Status

Phase 28 implements a narrow, operator-reviewed browser download of an existing
portable assurance bundle. It reuses the Phase 11 bundle model and verifier; it
does not create a second assurance format.

## Contract

The same-origin BFF exposes one operation:

```text
POST /app/api/candidates/{candidate_id}/assurance-export
```

The strict JSON request contains only `expected_revision` and
`expected_bundle_id`. The request accepts no input path, output path, filename,
URL, artifact selector, or archive option. The server requires:

1. an active Dashboard operator session;
2. exact project scope for the persisted candidate;
3. exact local Origin and a valid session CSRF value;
4. the authoritative candidate revision to equal `expected_revision`; and
5. the regenerated bundle identity to equal `expected_bundle_id`.

A stale revision or bundle identity returns `409` before an archive is sent.
Producer sessions may inspect the existing assurance review but cannot export
the complete artifact.

## Archive shape

The response is `application/zip` with a fixed attachment filename:

```text
assurance-<64 lowercase hexadecimal bundle digest>.zip
```

The ZIP is deterministic and uncompressed. It has fixed member timestamps,
fixed regular-file permissions, no directory entries, and exactly these three
root members in canonical order:

```text
README.md
assurance-bundle.json
manifest.json
```

The archive filename stem is the directory name required by the existing
offline verifier. Extracting the ZIP into its default Windows folder therefore
produces a directory accepted by:

```text
forgegate verify-assurance assurance-<digest>
```

The canonical JSON member remains bounded at 16 MiB. Each auxiliary member is
bounded at 64 KiB, and the complete stored archive has a fixed aggregate limit.
The browser independently rejects an empty, oversized, wrong-media-type, or
wrong-bundle response.

## Interaction and recovery

The Assurance page first displays the candidate revision, bundle ID, exact
member set, assurance level, and source-artifact boundary. Only a separate
confirmation initiates the download. The submit control is disabled while the
single request is in flight.

The operation is a deterministic read/export and creates no candidate mutation
or release-audit event. A repeated request for unchanged authoritative state
returns identical ZIP bytes. A `401` returns to activation; `403` retains the
session but denies export; `409` requires reload and re-review; other failures
show the stable code, request ID, and a manual recovery action. No failure is
automatically retried.

## Evidence boundary

The download copies retained assurance documents into a local browser file. It
does not publish to GitHub, deploy software, authenticate evidence producers,
establish trusted time, embed the referenced source-artifact bytes, re-run a
collector, access MSP430 hardware, validate a physical measurement, or approve
production use.
