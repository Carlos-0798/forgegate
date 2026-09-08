# Phase 45 — Dashboard recovery rehearsal receipt review

Date: 2026-09-07 America/New_York.
Evidence: LOCAL_HOST_TEST_SYNTHETIC. GitHub synchronization remains paused.

## Delivered

The operator-only Recovery page now accepts the exact, path-free completion
receipt created by the Phase 44 CLI rehearsal. Browser and server independently
enforce UTF-8, size, schema and SHA-256 constraints; the service additionally
rejects duplicate keys, non-finite values and incoherent or forged derived
identities. A strict `forgegate.recovery-rehearsal-review.v1` response exposes
the restored-copy identities and explicit non-actions.

The endpoint performs no retained candidate/job/audit write and provides no
server path, restore, rehydration or live-database-switch control. The Dashboard
also avoids an eager import cycle by loading its public route exports lazily; a
fresh-process regression covers the original failing import order.

## Automated verification

- 93 focused recovery/Dashboard Python tests pass.
- All 148 production-TypeScript interaction tests pass, including successful
  receipt rendering, reselection, browser-side invalid/oversize rejection,
  409/413/429/500 no-retry behavior, inconsistent responses and late results.
- Full `tools/verify.py`: PASS, 1,295 passed and 3 skipped; 95.77% branch-aware
  coverage across 12,536 statements and 3,246 branches. The skips require
  unavailable Windows symlink creation. Ruff, formatting, strict mypy across
  110 source/tool files, 55 document plus 3 artifact schemas, 29-path/31-operation
  Dashboard OpenAPI, packaged assets and 33 interaction-smoke controls pass.
- Clean-install `tools/release_smoke.py`: PASS with installed Schema/OpenAPI/
  assets, the new Dashboard operation, recovery/readback smoke, uninstall and
  optional MSP430-extra import. Tested wheel SHA-256:
  `71d74a9a225e97a27a09d8df6ea6c3015c7265539bd5f515267af2ede1781a9a`;
  tested sdist SHA-256:
  `791f2985c7f939bd5fcea650c01cb9b5a05175b1e547a7ae1e2c196aad22e78e`.
  These identify the packages tested before this final prose/evidence update.

## Actual browser acceptance

An isolated Microsoft Edge session activated against a copied local candidate
and job store on `127.0.0.1:8145`. The actual Phase 44 `REHEARSAL.json` produced
`VERIFIED_RESTORED_COPY` twice with HTTP 200. The page showed 27 tasks, 43 events,
one archived task, one verified external result, exact database sizes/hashes and
the restored-copy inspection fingerprint. Selecting the same bytes under a
different filename cleared the previous result and enabled a fresh explicit
submission. The final page had no browser-console warning or error.

The repository-retained screenshot is
[phase45-recovery-rehearsal-review.png](../docs/assets/phase45-recovery-rehearsal-review.png),
SHA-256 `e2337d5b9a77522e77de04db72da968fe02ded0c74e4ed7a623b802970701c7f`.
Exact machine values are in the [Phase 45 evidence](PHASE_45_RECOVERY_REHEARSAL_REVIEW_EVIDENCE.json).

## Boundaries

This is a review of a historical, completed local synthetic rehearsal receipt.
It does not execute or repeat recovery, open a server-side path, upload a backup
or database, rehydrate archived results, switch the live workspace, prove future
availability, run tasks, authenticate producers, control hardware, publish a
release or establish production readiness.
