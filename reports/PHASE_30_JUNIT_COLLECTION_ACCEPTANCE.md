# Phase 30 — bounded Dashboard JUnit collection

Date: 2026-09-06. Base: `714b0b1dddcbdafe3b9a9163aca3dd48aaaee90c`.
Status: bounded real-Edge acceptance PASS after the shared-policy correction
below. Broader accessibility, durable jobs and hosted CI remain separate gates.

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
| Real Edge file selection and full workflow | Upload, preview, bind, evaluate | Initially blocked; follow-up PASS/FAIL chains now pass after schema v9 correction |

## Initial host verification (before browser-discovered correction)

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
No permission was changed or bypassed by the agent. A later connection allowed
normal file selection; the follow-up below supersedes the upload blocker.

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
- At the initial form-only checkpoint no remote push/merge occurred. PR 9 and PR 10
  were already pending; this branch stacks on their code. Hosted CI remains
  a separate gate, including the previously reported owner billing restriction.

## Real Edge follow-up and shared-policy correction

The same isolated fixture on port 8132 completed actual file chooser uploads,
production preview, separate binding confirmations, READY/EVALUATING transitions
and exact-policy evaluation. All source metadata was explicitly synthetic:
`synthetic-junit-fixture`, version `1.0`, commit `a` repeated 40 times and original
report time `2026-09-06T06:00:00Z`. No serial monitor was enabled on this service.

| Browser input | Observed result |
|---|---|
| `fail.xml` | COMPLETE collection: total 4, passed 2, failures 1, errors 0, skipped 1, duration 0.5; separately evaluated FAIL, no-failures expected 0 / actual 1 |
| `pass.xml` | COMPLETE collection: total 4, passed 4, failures/errors/skipped 0, duration 0.5; separately evaluated PASS, all three rules satisfied |
| `warning.xml` | Actual total 1 overrides declared 2; duration null; both mismatch and missing-duration warnings visible; no binding offered before explicit retention |
| Warning retention then cancel | Binding review reports `retained`; Cancel leaves candidate COLLECTING revision 1, no binding or new release audit event |
| `rejected.xml` | REJECTED / JUNIT_FORBIDDEN_DECLARATION; no evidence-binding control, candidate remains COLLECTING revision 1 |

The second candidate initially returned HTTP 400 / STORE_DATABASE_ERROR because
`candidate_policy_materials.material_id` had a global UNIQUE constraint. Policy
material identity belongs to exact profile-authorized content, so reuse by a
second candidate is legitimate. The earlier parametrized tests used independent
databases and missed this case. Both tests were expanded to evaluate two
candidates in the same database and failed before the fix, then passed.

Schema v9 removes only the global material-ID uniqueness. Candidate primary-key
uniqueness, foreign key, immutable triggers, exact content validation and atomic
evaluation remain. Four new migration tests cover explicit migration, unchanged
retained rows, repeated migration, integrity, guards and three rollback points.
No policy bytes, fingerprints, historical evaluation or evidence label were
changed to make the browser fixture pass.

The isolated service was stopped, its database backed up using SQLite backup
(`integrity_check=ok`), then explicitly migrated and restarted. After fresh CLI
activation the previously failed candidate was reviewed again with the identical
policy material and evaluated PASS. Final read-only DB cross-check: two evidence
bindings, two policy bindings sharing the same material ID, 19 release-audit
events; each canceled/rejected preview candidate still has its original two
events. Both terminal candidates are revision 4. Database integrity is `ok`.
An intermediate file-chooser timeout was recovered by reconnecting the browser
and reloading; no security setting or upload restriction was bypassed.

Post-fix `tools/verify.py`: **918 passed, 3 skipped**, **95.25%** branch-aware
coverage over 10,520 statements and 2,840 branches; static checks, 33/33
interaction smoke, committed Schemas and both OpenAPI contracts pass.
The 43 frontend host cases and strict TypeScript check were rerun and passed,
separately from browser evidence. Clean-wheel `tools/release_smoke.py` passed,
including the five new screenshots and migration regression in the sdist.
Raw logs: `work/phase30-reuse-verify.log`, `work/phase30-reuse-release.log` and
`work/phase30-reuse-frontend.log` (not portfolio material).

The normal port-8131 database was also backed up through SQLite, explicitly
migrated and restarted with its existing input-only monitor configuration.
All retained domain/release-audit tables matched the backup exactly. The existing
security-event prefix matched; one authentication-rejection event was appended
when the browser presented its expired pre-restart session. Integrity remained
`ok`; fresh companion activation restored Overview to Healthy / schema v9.
This is service-maintenance evidence, not a new hardware-verification result.

For private synchronization this follow-up remains stacked on the pending Audit
branch. Required CI must pass before merge. The inspected PR 10 check annotation
reports an account payment/spending-limit restriction before the job started;
no billing setting, check requirement, visibility or license is changed here.

### Retained unedited screenshots

All captures are actual Edge viewport JPEGs, 2537 x 1300, containing synthetic
fixture data. The modal backdrop blur is produced by the interface, not editing.

| File under `docs/assets/` | SHA-256 |
|---|---|
| forgegate-dashboard-junit-fail-decision.jpg | 4cc750209174efba36a698f4b7b38ce59bd7ab9f34085740de72a44e1d48291e |
| forgegate-dashboard-junit-pass-decision.jpg | f10ecf116d9c758bf8e40efd9211ccbc40d99afbf0abd25e882ab53799e89c33 |
| forgegate-dashboard-junit-warning-consent.jpg | 364dae1a4ccd17fd1cf37a4d2660dcd0293e15821f25fe23ce29e100a545ffe4 |
| forgegate-dashboard-junit-rejected.jpg | 8513e8d0d7a788996fe4484093b741c08bb1a9b65b1acd1816061a58166a994a |
| forgegate-dashboard-shared-policy-error.jpg | a5979ae84ff1a47c56a593f0f7341fbb15472ec2a19b9d7a7d21042670e1c34f |

This follow-up proves the bounded single-report browser slice, not durable jobs,
multi-report assembly UI, test execution, source authenticity, hardware validation
or production readiness. New browser attestation/ZIP downloads were not repeated
in this follow-up; those paths retain their separate host and Phase 28 evidence.
The next engineering work is multi-report planning and Windows service reliability.
