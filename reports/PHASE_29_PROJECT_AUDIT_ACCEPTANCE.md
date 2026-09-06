# Phase 29 — project Audit workspace

Date: 2026-09-06. Base: `ca09ad6dd2f78a0c396f6d2b2980282a55ae9021`.
Status: implemented and locally verified; hosted CI remains a separate gate.

## Delivered

The operator can inspect project-wide release history rather than only the
first 100 candidate events embedded in candidate detail. The new Audit page
supports exact project and optional candidate selection, 25-event cursor pages,
full event/subject identities, recorded actor metadata, native expandable
details, manual refresh, and URL-based first/next/back navigation.

The scope selector uses all project IDs in the authenticated principal, not a
silently truncated project-list cache. Missing actors are explicitly not
recorded; the UI does not assign the currently signed-in operator to old events.
Candidate detail discloses a truncated preview and links to the full workspace.

The existing BFF/app/store query remains authoritative. Project and candidate
patterns are now included in HTTP validation and the generated OpenAPI, so
malformed values return 422 instead of reaching model construction. No endpoint,
database migration, dependency, write permission, or evidence-level change was
introduced.

## Expected versus actual

| Input or action | Expected | Actual |
|---|---|---|
| Isolated fixture: one registration plus 27 created candidates | 28 retained events | 28 |
| First page, limit 25 | Sequences 1–25; more available | Match |
| Next cursor 25 | Sequences 26–28; no next page | Match |
| Candidate `cand-24954f5750e3fa883a5c0b86` | One event, sequence 26 | Match |
| Nonexistent `cand-ffffffffffffffffffffffff` | Explicit empty result, no success claim | Match |
| Refresh filtered URL | Same project/candidate and result | Match |
| Browser Back after empty-result query | Previous candidate query restored | Match |
| Enter on focused event summary | Expand/collapse details | Match |
| Historical fixture actor missing | Unknown, not current operator | Match |
| Producer role / out-of-scope project / hostile Origin | Denied | Host tests pass |
| Invalid project/candidate, negative cursor, limit 201 | 422 | Host tests pass |
| Delayed audit response after logout | No protected data restored | Host test passes |
| HTML-shaped actor text | Text, not executable markup | Host test passes |

The real browser is the Codex in-app browser on Windows, using a separate
loopback service and isolated fixture database at port 8132. The fixture was
created through `CandidateApplication`, not by changing stored audit rows.
Its source times are fixed fixture values, not the current time. No serial
monitor or device access was enabled in this fixture service.

The independently loaded sequence-26 record has event ID
`sha256:b4feaaa523b47e7b5717c691ae3c2eed62cf304bd06a9d453cd9c5b48acd5676`
and subject fingerprint
`sha256:2eab81a54acf707b863ed1fcb2e9eb7bef718040bf4bc7bdd77d710718bc3866`.
The page showed the full values, original subject schema, exact candidate ID,
and absent-actor boundary.

## Verification commands

- `pnpm run check:dashboard`: strict TypeScript PASS.
- `pnpm run test:dashboard`: 25 PASS (12 Audit + 13 activation), controlled
  DOM/HTTP/clock host tests, not browser certification or Python coverage.
- `python -m pytest tests/test_dashboard_audit.py -q`: 5 PASS, including
  real BFF pagination/filtering/authorization and repeated read equality.
- `pnpm run build:dashboard` and asset inventory: PASS.
- `python tools/verify.py`: 887 PASS, 3 Windows symlink skips; 95.21%
  branch-aware coverage across 10,431 statements and 2,824 branches.
- Dashboard Python coverage in that full run: 98.42%, 644 statements and
  114 branches. Dashboard/client/audit tests total 53.
- `python tools/release_smoke.py`: PASS, including clean-wheel
  build/install/workflow/uninstall and the updated packaged assets.

After loading the final build on the normal port 8131, the existing database
correctly showed four audit events (not the separate 28-event fixture).
The input-only Devices page at 05:56:36 UTC remained CONNECTED / heartbeat
NORMAL / firmware FAULT 0015, with 37 accepted frames and zero protocol
errors/gaps/reconnects in that fresh process. This brief status check does not
extend hardware assurance or long-duration stability claims. The isolated
8132 fixture service was then stopped; its local database was retained.

## Portfolio evidence

Two unedited viewport screenshots are retained. They show generic test data,
not production use or peer-project measurements. The overview and scrolled
detail are complementary views, not a stitched image.

| Path under docs/assets | SHA-256 |
|---|---|
| `forgegate-dashboard-project-audit.png` | `ff43afab36e2cadc920b82a7ab5cf9480756ea9ce3f52119d7c6fca8eb639c35` |
| `forgegate-dashboard-audit-detail.png` | `0ae9327acdc8a954831a29c0691f6f4341bbd4e9961fe224c272b6edf55e6777` |

No private key, bearer token, cookie, personal email, or machine path is shown.
Authenticated session IDs are not displayed by the new event-detail view.

## Boundaries and remaining work

Audit reads do not append release-operation events. This page is not the
separate security-event journal, tamper-proof logging, forensic completeness,
trusted time, producer authentication, or device/measurement evidence.
Pagination follows an append-only sequence; it does not claim a snapshot total.
First/next links plus browser Back are implemented; arbitrary page-number jumps,
server-side event-type/time filtering, and audit export are not.

No fresh Edge/Chrome, high-contrast, spoken Narrator, or real Remote Desktop
acceptance is claimed. Automatic collection and plugin/security administration
remain separate later vertical slices. The existing GitHub account billing
restriction must not be bypassed to claim hosted CI success or merge.
