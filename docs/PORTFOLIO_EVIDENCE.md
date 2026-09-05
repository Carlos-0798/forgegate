# Portfolio evidence gallery

This page collects the small set of real, reproducible artifacts intended for
the repository landing page and portfolio review. Every image uses generic
local fixture data. None of the captures contains a private key, API token,
personal email address, physical measurement, or production environment.

## Evidence boundary

- Environment: Google Chrome on Windows, loopback-only ForgeGate Dashboard
- Evidence level: `LOCAL_BROWSER_TEST`
- Product status: private Windows Alpha `0.1.0a1`
- Hardware access: `NOT_PERFORMED`
- Remote deployment and release approval: not demonstrated
- Source checkpoint used for the captures: `ed205c7`

The exact fixture values, output cross-checks, image dimensions, and SHA-256
digests are retained in the
[machine-readable capture record](../reports/DASHBOARD_PORTFOLIO_CAPTURE_EVIDENCE_2026-09-04.json).

## 1. Authority and limitations

![ForgeGate Dashboard Overview showing service health, authenticated scope, and explicit evidence limitations](assets/forgegate-dashboard-overview.jpg)

This view demonstrates the authenticated local shell, service/schema status,
project scope, and the visible distinction between request success and a
release decision. The identity and trust-store fingerprints belong to a
deterministic generic test identity; no secret key material is shown.

## 2. Candidate workspace

![ForgeGate Dashboard candidate list containing one generic DRAFT candidate](assets/forgegate-dashboard-candidates.jpg)

The retained fixture contains one `sample-api` candidate:

- version `portfolio-alpha-1.0.0`;
- commit `7777777777777777777777777777777777777777`;
- branch `portfolio/readme-evidence`;
- track `pull-request`; and
- state `DRAFT`, revision `0`.

The page explicitly says that collection and evaluation are later actions.

## 3. Candidate state and append-only audit

![ForgeGate Dashboard candidate detail separating DRAFT state, NOT_EVALUATED decision, and NOT_PERFORMED hardware claim](assets/forgegate-dashboard-candidate-detail.jpg)

The detail view exposes the authoritative candidate ID, exact commit, frozen
project profile version, engineering-decision state, hardware boundary, and
the matching `candidate.created` audit event. A `DRAFT` is not presented as a
passing release decision.

## 4. Strict validation and recovery

![ForgeGate Dashboard validation error showing stable code, safe next step, and request ID](assets/forgegate-dashboard-validation-error.jpg)

The browser submitted a deliberately invalid track, `INVALID!`, with generic
version, commit, and branch values. The server returned HTTP 422 with
`API_REQUEST_VALIDATION_FAILED`, a safe recovery instruction, and a request ID.
An independent CLI read immediately afterward found the same one candidate and
the same two audit events (`project.registered` and `candidate.created`), so the
rejected request did not create a durable candidate or audit event.

## 5. Pagination acceptance

![ForgeGate Dashboard large generic candidate fixture used for pagination acceptance](assets/forgegate-dashboard-alpha.jpg)

This earlier Chrome capture comes from the separate generic 129-record
acceptance fixture. All six pages were traversed as
`25/25/25/25/25/4`, producing 129 unique versions with no duplicates. The
complete input/output record and remaining manual boundary are in the
[Phase 24 manual interaction report](../reports/PHASE_24_MANUAL_INTERACTION_ACCEPTANCE_2026-09-04.md).

## What these artifacts support

They support the narrow claim that the authenticated, loopback-only Dashboard
implements activation, Overview, Projects, and candidate list/create/detail/
audit interactions, including visible evidence boundaries and actionable
validation errors, on the tested Windows/Chrome setup.

They do not support claims of hardware validation, evidence authenticity,
production readiness, public release, non-loopback security, full
accessibility conformance, or completion of the planned Evidence, Decision,
Assurance, Plugins, and Security pages.
