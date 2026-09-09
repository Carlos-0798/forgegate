# Phase 58 — refreshed Windows installed-wheel acceptance

Date: 2026-09-08 (Windows local date). Status: **LOCAL ACCEPTANCE PASS**.

## Outcome

The accumulated Quick Assessment, Evidence Replay and Evaluation Comparison
work is present and operational in a new Windows Python 3.12 installation. The
wheel was built from a freshly generated source distribution, installed into an
isolated environment and run against a verified backup copy of the synthetic
Phase 54/57 candidate store. The source store remained at six candidates; only
the private installed-runtime copy gained the Phase 58 test candidate.

This working tree contains uncommitted work. The artifacts are retained local
acceptance outputs, not a clean-commit, signed, licensed, published, or public
release candidate.

## Build and startup

| Check | Actual |
|---|---|
| No-overwrite delivery build | Existing destination refused with exit 3 |
| Wheel construction | Generated sdist → fresh extracted tree → wheel |
| Wheel | 352,978 bytes; 114 members; five exact inventoried Dashboard assets |
| Isolated installation | Python 3.12.10 `site-packages`; `pip check` PASS |
| Data preparation | SQLite backup API returned `BACKUP_CREATED`; independent validation `VERIFIED` |
| Before startup | `CONNECTION_REFUSED`, correctly not ready |
| After startup | `DASHBOARD_REACHABLE`; health and exact installed HTML both HTTP 200 |
| Hardware | Disabled; NOT PERFORMED |

Exact build/download/screenshot hashes are in the
[machine-readable evidence](PHASE_58_WINDOWS_DELIVERY_EVIDENCE.json). Private
wheel, database, keys and downloaded archives remain outside tracked reports.

## Actual Microsoft Edge acceptance

The installed Dashboard was activated as an operator limited to `sample-api`.
Four small synthetic files were selected once: JUnit, Cobertura coverage, SARIF
and benchmark JSON. The UI detected each format, showed source metadata and
hashes, reused the explicitly selected frozen six-rule policy, then completed
binding, READY, evaluation and unsigned-local attestation. The result was six
rules PASS with four collections and nine normalized evidence records.

The original reports and receipts were then downloaded as an eight-file private
replay ZIP. The installed CLI independently returned `VALID / PASS`, four
collections, nine records and eight source files. The portable assurance ZIP was
also downloaded, extracted and independently returned `VALID / PASS` with
`unsigned_local` assurance and source bytes not embedded.

One initial assurance verification intentionally demonstrated fail-closed naming:
an arbitrarily named extraction directory returned
`ASSURANCE_BUNDLE_DIRECTORY_MISMATCH`. Renaming it to the content-derived bundle
directory made the unchanged files validate. This is recovery evidence, not a
product defect or modified bundle.

Evaluation Comparison then showed:

- the retained failing baseline to the new installed PASS candidate was
  `COMPARABLE`, with `security-clean` restored from FAIL to PASS (actual 1 → 0,
  expected 0);
- the changed-policy control was `NOT COMPARABLE`, preventing a false recovery
  statement across different policy bytes.

Browser console errors/warnings: **0**. Screenshots:

- [Quick-assessment preview](phase58-browser/installed-quick-preview.png)
- [Six-rule PASS](phase58-browser/installed-quick-pass.png)
- [Private replay download](phase58-browser/installed-replay-download.png)
- [Comparable restored rule](phase58-browser/installed-comparison-restored.png)
- [Changed-policy protection](phase58-browser/installed-comparison-not-comparable.png)
- [Portable assurance download](phase58-browser/installed-assurance-download.png)

## Verification and boundaries

- `python tools/verify.py`: PASS — 1,433 passed / 3 environment skips,
  95.80% branch-aware coverage, plus lint, formatting, typing, interaction,
  schema, OpenAPI and asset checks.
- `python tools/release_smoke.py`: PASS in fresh build/install environments.
- Frontend suite: 248 passed; TypeScript check PASS.

All report data is the synthetic Standard CI fixture. This does not prove
producer authenticity, real scanner/performance results, hardware behavior,
deployment approval, quantified human efficiency, or production readiness.
No GitHub, remote, AVS, or MSP430 action was performed.

Recommended next slice: consolidate the current working-tree changes into a
reviewable local commit series and repeat the delivery build from the resulting
clean commit before any GitHub synchronization or public-release discussion.
