# Quick assessment

Phase 54 adds a shorter Dashboard path for a report set from one run. Select
**Candidates → Quick assessment**, review creation of the DRAFT, then choose
**Select reports and assess**. An existing unbound DRAFT/COLLECTING candidate
also exposes Quick assessment in its workflow panel.

1. Select 1–4 report files, or a folder containing only those reports. Content
   identifies JUnit XML, Cobertura XML/LCOV, SARIF 2.1.0 and ForgeGate benchmark
   JSON. One report per family is allowed; limits remain 1 MiB/file, 2 MiB total.
2. Select exact profile-authorized policy-material JSON, or explicitly **Load
   saved policies** and choose a compatible retained material. Supply the original
   run time plus default JUnit/coverage tool metadata. For differing metadata,
   expand **Per-report metadata overrides**: supply coverage tool and version
   together, and separate coverage/SARIF/benchmark times when needed. Blank
   overrides inherit the defaults; SARIF/benchmark tools remain report-embedded.
3. Start collection and preview. A DRAFT becomes COLLECTING; existing collectors
   validate the complete bytes. Inspect detected formats, hashes, policy rules,
   normalized values and issues. Unsupported, duplicate or rejected reports
   cannot proceed. Complete reports with at most 25 warnings each require
   viewing the warnings, checking consent, and explicitly selecting **Retain
   reviewed warnings and preview**. The second read-only preview must return
   identical collection results and receipt bytes; otherwise the flow stops.
4. Confirm assessment and attestation. This explicitly authorizes immutable
   binding, READY, EVALUATING, policy evaluation and unsigned-local attestation.
   Each step uses the existing API authorization, validation and audit records.
   FAIL/REVIEW/ERROR are retained as actual engineering outcomes.
5. Review the displayed rule results and select **Review assurance download**.
   The existing exporter produces the deterministic three-member ZIP. Verify
   the extracted directory with `forgegate verify-assurance` before relying on it.
   Keep the directory name equal to the ZIP basename (`assurance-<digest>`).
6. Before closing Quick assessment, select **Save originals for offline replay**.
   Review the prepared report/receipt hashes, confirm private-data review, and
   download the replay ZIP. No second file selection is needed. Independently run
   `forgegate evidence-replay verify <replay.zip> --expected-commit <commit>`.

## Repeated use and original-file handoff (Phase 55)

Saved choices come from previously evaluated candidates with the exact same
project, frozen profile ID/version and release track. The operator-only lookup
is read-only and returns at most ten distinct materials, with an explicit
truncation notice. It neither selects a policy automatically nor approves its
engineering quality. With no compatible history, keep using a policy JSON file.
Evaluation still checks the selected material against the candidate's authority.

Quick assessment keeps the originally selected bytes and exact canonical
collection receipts in browser memory. Receipt spelling, including numeric
precision, is preserved for source-hash verification. The replay handoff is
offered only when every required file matches its hash and size and fits the
existing 1 MiB/file and 2 MiB aggregate limits, including receipts. If it cannot
prepare that bounded set, assessment remains available and the UI explains the
separate replay workflow. This is not server-side original-file retention:
**download before closing or navigating away**. Keep that private ZIP with your
delivery materials; it is the durable copy. The ordinary assurance ZIP remains
available separately and does not embed original reports.

## Failure and recovery

Execution is sequential, not one transaction. A failed request stops all later
steps. Earlier writes remain visible in the candidate and audit; inspect retained
state and use its next authorized command to continue. A lost response can mean
a write succeeded. No automatic retry, rollback, hidden PASS, or replacement
candidate is performed. Closing/navigating/ending a session stops later requests;
an in-flight request may still complete. Double confirmation is suppressed.

Policy shape/profile checks run locally before collection starts; authoritative
policy byte/fingerprint checks still happen in the existing evaluation endpoint.
A semantically invalid policy may therefore stop after evidence has been bound.
Warnings are never silently discarded. Their review does not bind evidence or
change policy thresholds; the subsequent assessment needs its own confirmation.
More than 25 warnings in one report require the individual workflow or CLI.

## Scope and benefit

This path replaces per-report format selection and separate confirmation dialogs
for binding, readiness, evaluation and attestation with a batch review and one
execution confirmation. That is a demonstrated reduction in required workflow
actions, not a measured percentage of time saved or human accuracy improvement.

ZIP import, unrelated-file filtering and background execution are not included.
Imported evidence remains declared and unsigned local. Phase 55 adds a bounded
read-only policy-choice endpoint and exact receipt strings to collection preview;
it does not add a collector or storage schema.

See [Phase 54 acceptance](../reports/PHASE_54_QUICK_ASSESSMENT_ACCEPTANCE.md)
for the original workflow, and [Phase 55 acceptance](../reports/PHASE_55_QUICK_HANDOFF_ACCEPTANCE.md)
for saved-policy reuse and integrated original-file delivery.
The [Phase 56 real AVS acceptance](../reports/PHASE_56_AVS_QUICK_ACCEPTANCE.md)
checks different tool/time metadata, retained warnings and the unchanged FAIL
decision against the original handoff. This is reuse of archived host reports,
not a new producer test run.
