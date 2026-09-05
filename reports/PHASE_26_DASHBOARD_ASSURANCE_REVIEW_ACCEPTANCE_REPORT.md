# Phase 26 Dashboard assurance review acceptance

- Date: 2026-09-05
- Platform: Windows
- Decision: **IMPLEMENTATION AND LOCAL BROWSER PASS**
- Evidence class: local-host automation and generic local-browser fixture

## Outcome

ForgeGate now exposes a read-only Dashboard review path for the product's core
release-assurance chain. From a candidate detail view, an authorized session can
inspect its retained Evidence, explainable Decision, and Assurance artifacts
without uploading evidence, running a collector, changing candidate state, or
exporting a file from the browser.

The same increment decodes MSP430 UART v1 fault flags into versioned adapter
labels. The live page continues to separate connection, heartbeat freshness,
and firmware-reported health, and explicitly states that decoded flags are
device reports rather than ForgeGate diagnoses.

## Implemented slice

- one project-scoped BFF read operation joins candidate history, evidence
  binding, policy material, policy evaluation, attestation, and portable bundle
  identity;
- Evidence page shows binding/assembly identities, record values, trust,
  verification level, and referenced artifact hash;
- Decision page shows exact policy authority, expected/actual rule values,
  evidence IDs, reason code, and explanation;
- Assurance page shows attestation and bundle identities, assurance level,
  verification scope, source-byte boundary, and the four-step transition chain;
- candidate detail provides deep links, and the candidate ID remains in the
  hash query across Evidence/Decision/Assurance navigation and refresh;
- missing selection, missing evidence, unevaluated, and unattested states are
  explicit rather than inferred;
- Evidence and Decision tables render 25 rows per page with a live range label
  and keyboard-operable Previous/Next controls;
- route changes reset the document scroll position so a review page does not
  inherit a misleading mid-page position from the prior route;
- the browser receives no new mutation operation or private credential.

## Verification

| Check | Result | Boundary |
|---|---:|---|
| BFF joined review, unauthenticated denial, DRAFT null-state, PASS chain | PASS | local FastAPI tests |
| MSP430 known and unknown fault-bit decoding | PASS | deterministic adapter tests |
| TypeScript strict check and deterministic Vite build | PASS | local build |
| Evidence page browser navigation and values | PASS | generic local fixture |
| Decision expected `0`, actual `0`, reason `RULE_SATISFIED`, result `PASS` | PASS | generic committed evidence fixture |
| Assurance attestation/bundle IDs and `unsigned_local` label | PASS | generic local fixture |
| Review route without a candidate selection | PASS | local browser showed a clear empty state and a safe Candidates link |
| COM4 `0015` decoded to DS18B20, NTC, and INA219 reports | PASS | authorized read-only live observation |
| GitHub-ready screenshots and SHA-256 capture record | PASS | four retained JPEGs |

The machine-readable evidence is in
[`DASHBOARD_ASSURANCE_REVIEW_EVIDENCE_2026-09-05.json`](DASHBOARD_ASSURANCE_REVIEW_EVIDENCE_2026-09-05.json).
The owner-assisted unplug/replug follow-up and decoded COM4 observation are in
[`MSP430_MANUAL_UNPLUG_REPLUG_EVIDENCE_2026-09-05.json`](MSP430_MANUAL_UNPLUG_REPLUG_EVIDENCE_2026-09-05.json).

## Evidence boundary

The screenshots use generic ephemeral test data and prove only the tested local
review interaction. They do not prove producer authenticity, remote deployment,
production approval, hardware measurement validity, or that source artifact
bytes were embedded. Hashes and cross-document validation establish retained
content consistency, not independent truth of the producing system.

The COM4 follow-up sent no bytes, changed no firmware/configuration, and created
no release evidence. `FAULT`/`0015` is the upstream firmware's intentional
availability sentinel with external sensors absent.
