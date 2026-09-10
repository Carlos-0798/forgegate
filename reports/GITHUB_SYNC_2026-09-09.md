# Private GitHub synchronization — 2026-09-09

## Scope and authority

The owner requested a durable project stopping point and continuation plan,
followed by synchronization of the existing Private GitHub repository.
This checkpoint does not add a new product feature beyond the already accepted
Phase 64 work, or authorize Public visibility, a License, GitHub Release,
LinkedIn publication, hardware access or account spending changes.

The [resumption checkpoint](../docs/PROJECT_RESUME_CHECKPOINT_2026-09-09.md)
was written before remote writes. It records the accepted workflow, evidence,
outstanding limits and proposed adapter-conformance continuation.

## Starting state

- Remote: `Carlos-0798/forgegate`, Private, default branch `main`.
- Remote main: `8f1ea08d059fe7b97af27dd66d903d7e5d50e0ae`.
- Local starting HEAD: `9b9230ebc4db9e3c4c3bdf7a0acf34634f0d1d0d`,
  31 commits ahead of and zero commits behind the fetched main.
- Accepted Phase 64 implementation/tests/contracts/assets were uncommitted;
  these changes are preserved in their own checkpoint commit.
- Existing open PRs #9–#12 form the older activation/audit/JUnit/runtime stack.
  The synchronization branch includes their exact head commits; preserve the
  history rather than cherry-picking duplicate changes or force-pushing.

## Presentation changes

- Make the README a concise entry point: problem, delivered workflow, current
  evidence, design decisions, quickstart, limitations and focused continuation.
- Use the existing workbench and real retained AVS decision screenshots with
  explicit synthetic/retained-report labels. Optional device status is not the
  project's primary claim.
- Align the displayed local baseline to 1,568 Python tests, three host symlink
  skips, 296 frontend tests and 95.90% branch-aware Python coverage.
- Preserve original phase reports and their exact source/wheel identities.
  Recorded human efficiency remains NOT MEASURED; `VALID / FAIL` stays a valid
  handoff containing an engineering failure.

## Validation and publication receipt

Preserved runtime checkpoint:
`5f4eb15b79e5ea5f12fd964ead31e8d1b33c7c5b`
(`feat: add reusable read-only monitor presets`).

Fresh Windows checks on 2026-09-09:

- `python tools/verify.py`: exit 0, final PASS; 1,568 passed / three host
  symlink skips, 95.90% branch-aware coverage (13,847 statements / 3,598 branches),
  33 interaction checks, lint/format, strict typing, assets and contract drift PASS.
- `pnpm run check:dashboard` and `pnpm run test:dashboard`: exit 0; 296 passed.
- `pnpm run build:dashboard`, followed by the normal inventory-generation step:
  exact byte-for-byte match with the staged five-asset checkpoint; validation PASS.
  A premature inventory check before regeneration failed because Vite removes
  the generated inventory; completing the documented build sequence resolved
  that orchestration error without a product-code change.
- README/checkpoint/sync-document local links: all 37 inspected links resolved
  before the source-build instructions were added; final changed-document links
  are rechecked before pushing.
- Clean-source release smoke and retained delivery receipt: recorded after the
  documentation checkpoint below; do not infer package acceptance from an editable
  installation alone.

Detailed private command logs remain under ignored `work/github-sync-20260909/`.
The original Phase 64 browser evidence is retained, not reported as a new browser,
hardware or assistive-technology run. No actual user service/store is changed.

## Bounded privacy review

The pre-push inventory inspected 671 tracked/untracked nonignored paths, the
31 incoming commit author/committer identities and their added text, plus
representative retained screenshots including both Phase 64 images. No private
email, recognizable credential, private-key material, local database/build ZIP
or user-specific absolute path requiring removal was found in that scope.
Incoming commit identities match the configured account-specific noreply identity.
Ignored workspaces, virtual environments, build outputs and private source
artifacts are not part of the sync. This is not exhaustive historical binary
inspection or a security certification, and does not authorize public release.

## Hosted CI boundary

The latest inspected pre-sync runs reported that test jobs did not start because
of an account payment/spending-limit restriction. The last fully accepted
historical run is 33999452478, not the latest source. New workflow status must be
read back after the push; it must not be described as passing from local results.

No workflow is disabled, no required-check/protection setting is changed, and
no admin/force merge is used. If ordinary merge is blocked by repository rules,
leave the reviewed PR open for owner action. Billing changes require the owner.
