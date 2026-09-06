# Phase 30 — bounded Dashboard JUnit collection

Date: 2026-09-06. Base: `714b0b1dddcbdafe3b9a9163aca3dd48aaaee90c`.
Status: implemented and host-verified; real-browser upload acceptance OPEN.

## Delivered

An operator can open **Collect JUnit report** for an unbound COLLECTING
candidate. One report up to 1 MiB is represented as exact base64 bytes, parsed
by the existing JUnit collector through an in-memory artifact source, and
assembled by the existing evidence service. The preview does not write files,
bind evidence, advance a candidate or append a release-operation audit event.

Original report time, declared tool/version and explicit matching commit are
required. Trust/verification are fixed to `unsigned_local` / `declared`; no
host OS, CI identity, hardware context or producer authenticity is invented.
Warnings require explicit retention before an assembly is offered. A separate
reviewed command uses the existing immutable evidence-binding endpoint.

The source receipt hashes canonical in-memory collection-result JSON. The
binding retains metadata and hashes, not source XML or result JSON bytes.
This is not a durable task queue, multiple-report assembly UI, test runner,
arbitrary upload store, source-path reader, plugin runner or device collector.

## Expected versus actual

| Case | Expected | Actual and evidence class |
|---|---|---|
| 4 tests, 1 failure, 1 skip | 2 passed, 1 failed, 1 skipped; 0.5 seconds | Exact match; Python BFF integration |
| Original report bytes | Exact SHA-256 and byte size | Match; independently hashed in tests |
| Preview only | No binding or release audit mutation | Match; before/after authoritative readback |
| Separate binding | One retained binding; still COLLECTING | Match; real BFF/application/store path |
| Synthetic pass.xml / fail.xml | Fixture policy PASS / FAIL | Match through preview, binding, lifecycle, evaluation, attestation and ZIP generation |
| Original CI policy with declared-only input | REVIEW, not trust promotion | Match; policy engine test |
| Count mismatch / omitted duration | Visible warnings; no assembly until consent | Match; Python + frontend host tests |
| Malformed XML, NUL, DOCTYPE, bad counts | REJECTED; no assembly | Match; production collector tests |
| XML depth / element bounds | REJECTED at depth 32 / 10,000 elements | Match; host tests |
| Bad base64, oversized bytes, no-offset/future time | Validation rejection | Match; strict request model tests |
| Client path or elevated evidence label | Reject unknown fields | Match; strict request model tests |
| Missing session / producer / wrong project / CSRF / Origin | Denied | Match; BFF integration |
| Wrong revision / state / commit / already bound | Conflict | Match; BFF integration |
| Actual request body over 4 MiB | 413 | Match; ASGI integration |
| Close, logout or navigate during preview | Ignore late response | Match; production TypeScript host tests |
| 401/409/413/422/429/500 responses | No automatic retry or binding | Match; frontend host fixtures, not injected operational incidents |
| Real Edge empty-file submit | Native missing-file validation | Observed: required file field focused, no preview submitted |
| Real Edge Escape | Close dialog, return focus to Collect JUnit report | Observed |
| Real Edge file selection and full workflow | Upload, preview, bind, evaluate | BLOCKED by extension file-access setting; NOT PASSED |

## Verification

- `python tools/verify.py`: 914 passed, 3 skipped; 95.25% branch-aware coverage
  across 10,517 statements and 2,840 branches. Symlink privileges caused the
  three retained Windows skips. Ruff/format/mypy (93 files), schema/OpenAPI,
  asset inventory and 33/33 CLI/API interaction cases pass.
- `python -m pytest tests/test_dashboard_collection.py -q`: 27 pass.
- Dashboard Python package: 98.60% branch-aware coverage across 728 statements
  and 130 branches. New collection module: 100% of 72 statements/10 branches.
- `pnpm run test:dashboard`: 43 pass (18 collection, 12 Audit, 13 activation).
  Controlled DOM/HTTP/clock host tests are not real browser certification.
- `pnpm run check:dashboard` and `pnpm run build:dashboard`: pass.
- `python tools/release_smoke.py`: clean-wheel build/install/workflow/uninstall
  passed, including installed JUnit preview, unchanged declared-only labels,
  matching BFF OpenAPI and the new fixture/document inventory.

Local raw logs: `work/phase30-verify-final.log` and
`work/phase30-release-final.log`. They are not committed because environment
paths and transient test identities are not portfolio material.

## Browser and presentation evidence

Real Microsoft Edge, separate loopback service on port 8132, synthetic fixture
database prepared through `tools/manual_dashboard_collection.py`. No serial
monitor is enabled in the isolated fixture. The failed selection returned
`fileChooser.setFiles failed` / `Not allowed`; browser guidance requires the
owner to enable **Allow access to file URLs** for the ChatGPT extension.
No permission was changed or bypassed by the agent. Resume at file selection.

The unedited 2537 x 1300 form screenshot is
`docs/assets/forgegate-dashboard-junit-import-form.jpg` (original JPEG bytes):
`sha256:ea6cca48c5b257414488948810c01015467382c0afbb831e12a08395770cda50`.
It shows no uploaded results, secret, local path or personal email. The original
interface blurs the backdrop; this was not a post-capture edit. It supports a
form-implementation claim only, not full browser-workflow success.

## Corrections and boundaries

- A TypeScript optional tuple flag was made explicit after strict compilation
  caught it. Error messages now use the structured visible problem contract.
- Oversized parametrized XML initially exceeded Windows' environment-variable
  length limit in pytest's generated test names; short stable IDs fixed the
  harness without reducing the XML limits or test data.
- Test fixture command/state names were corrected to the actual application
  contract; the subsequent complete PASS/FAIL chains passed.
- The existing port-8131 service was restarted with the same database and
  existing read-only monitor configuration, then its browser session reactivated.
  No new hardware-verification result is claimed by this service maintenance.
- No remote push/merge or publication occurs at this checkpoint. PR 9 and PR 10
  were already pending; this local branch stacks on their code. Hosted CI remains
  a separate gate, including the previously reported owner billing restriction.

Do not add another collector until real-browser acceptance is completed. The
next engineering work is multi-report planning and Windows service reliability,
not a claim that the durable task-center roadmap is complete.
