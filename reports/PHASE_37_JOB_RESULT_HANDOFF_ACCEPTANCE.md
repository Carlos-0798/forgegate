# Phase 37 — reviewed job-result evidence handoff

Date: 2026-09-06 America/New_York (browser writes occurred 2026-09-07 UTC).
Scope: Windows local Alpha, synthetic report/job/candidate data and a temporary
test identity. GitHub and MSP430 hardware were not accessed. Existing services
on 8131 and 8135 were not changed. An isolated service on 8136 exercised the
production Dashboard BFF and built frontend in Microsoft Edge.

## Delivered

A `SUCCEEDED` retained collection task can now expose two separate operator-only
workflows:

1. review and download the exact canonical evidence assembly; or
2. re-read the authoritative candidate, review frozen identities and explicitly
   bind that retained assembly through the existing immutable evidence workflow.

Export freezes and rechecks job revision, result fingerprint and assembly ID.
The browser independently checks media type, result/assembly/fingerprint headers,
the 32 MiB bound and SHA-256 of the received bytes before offering a file.
Binding additionally freezes and rechecks candidate revision/fingerprint, project,
commit, `COLLECTING` state and absence of an existing binding. It uses a scoped
idempotency key and retains the authenticated operator on the existing candidate
audit event.

Neither path executes project tests, reruns parsing, embeds original report bytes,
authenticates the producer, accesses a device, advances the candidate or evaluates
policy. A successful handoff response explicitly says candidate transition and
policy decision were `NOT_PERFORMED`.

## Host gates

- `tools/verify.py`: 1093 passed, 3 skipped; 95.51% branch-aware coverage across
  11,401 statements and 3,052 branches. The skips require unavailable Windows
  symlink creation.
- Ruff/format and strict mypy pass; mypy checked 102 source/tool files.
- The focused job chain is 92 Python cases: 32 engine, 16 management, 23
  submission/execution and 21 result-handoff cases.
- All 127 frontend interaction tests pass, including 23 result-handoff cases;
  type checking, Vite build and the five-file asset inventory pass.
- The new backend cases cover exact repeated export, authorization/CSRF/origin,
  stale job/result/assembly identities, non-bindable states, exact immutable
  binding/replay, candidate conflicts, idempotency conflict, unknown input,
  actor attribution and disabled-store failure.
- The new frontend cases cover cancel/no-write, exact byte validation, six export
  mismatch modes, frozen one-shot binding, busy-dialog protection, three response
  mismatch modes, stale/already-bound candidates, 409/500/503 unknown outcomes,
  late logout and producer/non-success hiding.
- Contracts remain 44 document and 3 artifact schemas. Dashboard BFF OpenAPI is
  now 27 paths and 29 operations with committed-byte drift checks.

Host tests and a synthetic browser fixture are not producer-authentication,
physical-device, native assistive-technology or production evidence.

## Actual Edge acceptance

The isolated fixture retained a `SUCCEEDED` revision-2 task containing one JUnit
summary: total 4, passed 3, failures 1, errors 0, skipped 0 and duration 0.5.
The report stays `unsigned_local / declared` and its failed status is intentionally
preserved.

| Browser case | Observed result |
|---|---|
| Download review cancel | Dialog closed with no export and no state change |
| Canonical export | Edge received `evidence-assembly-47775ee...e25a.json`; page reported exact-byte verification |
| Independent disk check | 2,010 bytes; SHA-256 `30d2a452...8a6aea`; strict assembly model loaded 1 record, 1 collection, warnings `none` |
| Binding review back | Only the candidate read occurred; no binding write |
| Explicit binding | Binding `sha256:a798a6ff...87254f` retained the same assembly fingerprint and synthetic operator audit actor |
| Candidate boundary | Candidate remained `COLLECTING`, revision 1, evaluation ID null; no READY/PASS transition |
| Job boundary | Job remained `SUCCEEDED`, revision 2; result says `candidate_write = NOT_PERFORMED` |
| Duplicate review | Existing immutable binding was shown with a review link; no replacement confirmation or write |
| Independent CLI/store readback | Candidate, binding, job result and audit event matched browser identities and failed test count |
| Browser presentation | Warn/error log query returned empty; inspected document width was 1255/1255 with no horizontal overflow |

The durable correlation is content identity, not a new field added to a frozen
contract: the job result, export and binding share assembly ID
`sha256:47775ee9749ff535e68434707d6d4ae023344f8f85a4c0dad02c03a95295e25a`
and canonical assembly fingerprint
`sha256:30d2a4520483c12222773a97e7acb90b02dc32cca7f9e6665637d90fb48a6aea`.
The separate job and candidate SQLite files are not a distributed transaction.

## Screenshots and receipt

Actual 1255 × 1244 Edge viewport captures, not mockups or full-page/browser-OS
certification:

- [Result actions](../docs/assets/phase37-job-result-actions.jpg)
- [Exact download review](../docs/assets/phase37-assembly-download-review.jpg)
- [Binding result](../docs/assets/phase37-evidence-binding-result.jpg)
- [Independent bound-evidence view](../docs/assets/phase37-bound-evidence.jpg)

The [companion machine receipt](PHASE_37_JOB_RESULT_HANDOFF_EVIDENCE.json) retains
the exact synthetic identities, file and screenshot hashes, dimensions, expected
outputs and evidence boundaries. Fixture databases, private key, session cookie,
downloaded local file and raw service logs are not committed.

## Browser-found correction

The first successful binding dialog showed a thin horizontal scrollbar because a
long fingerprint could enlarge a nested grid item. The production CSS now permits
the review panel/status block to shrink and wrap anywhere. The rebuilt 8136 service
was freshly activated and re-exercised; the success dialog measured client/scroll
width 671/671 and the document 1255/1255. This is a scoped Edge result, not an
exhaustive zoom, browser or remote-desktop certification.

## Remaining boundaries

- No automatic worker, scheduler, retry, cooperative parser stop or lease renewal.
- No coordinated job/candidate backup, purge, archival or retention UI.
- No raw report replay/export, producer signature or hostile-local-user proof.
- No automatic candidate transition, policy evaluation, release publication or
  GitHub operation.
- No MSP430 connection, command, telemetry conversion, physical measurement or
  hardware evidence in this phase.
- Existing high-contrast, spoken screen-reader and real Remote Desktop gates remain
  separate from this feature acceptance.

## Final package checkpoint

`tools/release_smoke.py` completed with exit 0. The source distribution contains
the Phase 37 implementation tests, report, receipt and four screenshots; clean
installation, installed contracts/assets, CLI assurance workflow, 12-check job
lifecycle/migration smoke, optional serial dependency import and uninstall
isolation all pass. The optional serial import opens no device. No live broker,
browser or hardware action occurs in this packaging test.

Transient package identities captured before the final documentation-only receipt
and gallery edits (not a release, signature or hash of a later rebuild):

- Wheel SHA-256: `d60ea6689da60c2e349b00054efe9bebbc545b3a701f270ee6cc6742f804cbda`
- Sdist SHA-256: `7dd1c688f9a9d8a3f352ef7b5f2fd2acd4eb31a6085f44bb0203ac43fe21731a`
