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
- README/checkpoint/sync-document local links resolved; final changed-document
  links are rechecked before pushing.
- `python tools/release_smoke.py`: exit 0, final PASS from clean documentation
  checkpoint `0af90b4da909fe6734887441fc894de1f90bdb68`; isolated package install,
  CLI/API/assurance/job/recovery chains and optional dependency import checks.
  No device was opened. Its independently built wheel SHA-256 is
  `99b10e6b47816b0966b4edeb2d54f58ee93e1a736cf5fe7182cf3a656870fe36`.

Retained private delivery from that same **CLEAN_COMMIT** source:

- Wheel: `forgegate-0.1.0a1-py3-none-any.whl`, 365,144 bytes, 120 members;
  SHA-256 `d8b33005e92e9197f3e941b301625a4f6cb8cd051225d59f9daa2a3565611035`.
- All 115 `forgegate/` runtime members match the hash-verified Phase 64
  installed-browser wheel byte for byte, including the five inventoried assets.
  The archives themselves differ; no byte-identical-whole-wheel claim is made.
- Source distribution SHA-256:
  `77cf08d6f965f6d6653175fbddc2024692d5bc1de5909f08650b2ec521ed96bd`.
- Receipt/artifacts remain under ignored `work/github-sync-20260909/delivery/`;
  no binary release or private report payload is uploaded.

The later receipt/CI wording commit changes documentation only, not the validated
runtime or package build configuration. This avoids rebuilding and rerunning
unchanged code solely to insert its own acceptance record.

See the [machine-readable local evidence](GITHUB_SYNC_LOCAL_EVIDENCE_2026-09-09.json).

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

## Remote handoff

[PR #13 — synchronize Windows Alpha and portfolio checkpoint](https://github.com/Carlos-0798/forgegate/pull/13)
is the consolidation record. The branch's initial hosted run
[34425270399](https://github.com/Carlos-0798/forgegate/actions/runs/34425270399)
reported the same account restriction for Windows, Ubuntu and macOS; jobs did
not start. This is an infrastructure blocker, not an executed test failure or
a hosted PASS. The PR's current state and final merge receipt are authoritative
for remote completion; this pre-merge evidence document does not invent a merge
hash or promise future CI success.

The older #9–#12 head commits are ancestors of the consolidation branch. If
GitHub does not mark them merged through ancestry, close them as superseded with
a link to #13, preserving their reviews and branches. No force push or history
rewrite is needed.
