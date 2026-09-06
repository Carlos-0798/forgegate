# Phase 28 Dashboard assurance export acceptance

## Outcome

Phase 28 adds an operator-reviewed, candidate-bound Dashboard download for the
existing portable assurance bundle. The implementation passed focused model,
BFF, authorization, deterministic-archive, TypeScript, and real Microsoft Edge
checks. A browser-downloaded ZIP was extracted and accepted by the existing
database-independent `verify-assurance` command.

This is a local artifact-delivery capability, not a publication, deployment, or
producer-authentication claim.

## Implemented capability

- deterministic rootless ZIP containing exactly `README.md`,
  `assurance-bundle.json`, and `manifest.json`;
- fixed member timestamps, permissions, order, compression mode, filename, and
  bounded aggregate size;
- same-origin `POST` endpoint with operator, project-scope, CSRF, expected-
  revision, and expected-bundle-ID enforcement;
- strict rejection of client-supplied output paths or unknown request fields;
- reviewed browser confirmation showing the exact candidate, revision, bundle
  identity, members, assurance, and source-byte boundary;
- response identity/media/size checks before creating the local browser file;
- visible success, stable failure recovery, focus containment, Escape closure,
  and trigger-focus restoration; and
- deterministic replay without a candidate mutation or new release-audit event.

The full contract is documented in
[`docs/architecture/DASHBOARD_ASSURANCE_EXPORT.md`](../docs/architecture/DASHBOARD_ASSURANCE_EXPORT.md).

## Automated verification

The focused pre-acceptance run completed:

```text
ruff check: PASS
ruff format --check: PASS
TypeScript no-emit check: PASS
tests/test_assurance_bundle.py + tests/test_dashboard.py: 50 passed
```

The final repository gate completed with 882 passed and 3 environment-limited
symlink tests skipped, at 95.21% branch-aware coverage across 10,429 statements
and 2,824 branches. The 48-test Dashboard focus reached 98.41%. Committed
Schema, direct API OpenAPI, 18-operation Dashboard BFF OpenAPI, asset inventory,
and 33/33 interaction-smoke checks also passed.

The new cases cover deterministic bytes, exact member names, fixed metadata,
offline extraction, size failure, unauthenticated access, missing Origin,
missing CSRF, producer denial, stale revision, wrong bundle identity, unknown
path field, security headers, content disposition, bundle response header, and
unchanged release-audit history.

The source distribution manifest, wheel build, clean-environment install,
installed 18-operation Dashboard contract, installed static assets, portable
assurance workflow, optional MSP430 dependency environment, and uninstall
checks all passed `tools/release_smoke.py`.

## Real-browser acceptance

One isolated generic completed candidate was opened in Microsoft Edge on
loopback. The operator reviewed the exact bundle ID and canonical member set,
confirmed the download once, observed the visible completion state, and found
the expected ZIP in the Windows Downloads folder.

```text
archive bytes: 15448
archive SHA-256: fa06b1d7e6fffcf2443500d6e998129fd864974f181424f2db6ed8461bc184fe
offline verifier status: VALID
decision: PASS
assurance: unsigned_local
source artifact bytes: not_embedded
```

The extracted directory contained three regular files only. The document width
was 1229 CSS pixels with an equal scroll width, the browser console contained no
warning/error entries, the modal retained keyboard focus, Escape closed it, and
focus returned to the download trigger.

Exact fixture data, negative status results, hashes, and claim boundaries are
retained in
[`DASHBOARD_PHASE28_ASSURANCE_EXPORT_EVIDENCE_2026-09-05.json`](DASHBOARD_PHASE28_ASSURANCE_EXPORT_EVIDENCE_2026-09-05.json).

## Remaining boundaries

- Producer sessions remain review-only and cannot export the complete artifact.
- No server output path, remote destination, GitHub API, release publication, or
  automatic upload exists.
- The ZIP contains retained documents and embedded policy bytes, not the source
  artifact payloads referenced by evidence receipts.
- Export success does not authenticate producers, establish trusted time,
  validate MSP430 or other hardware, approve deployment, or establish production
  readiness.
- Windows high contrast, spoken Narrator output, and real Remote Desktop remain
  separately unexecuted environment checks from the Dashboard acceptance gate.
