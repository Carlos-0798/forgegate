# AVS host acceptance handoff to the upstream agent

Date: 2026-09-08. Scope: independent archived commit
`bf8c4c6f59ba9063524aea7db01df87d35170483`, **not the current dirty worktree**.
ForgeGate did not change the AVS project, approve fixes, push, or access hardware.

## Findings needing owner review

1. `tests/golden/test_phase5_public_api_golden.py::test_phase5_public_contract_matches_frozen_manifest[golden_sha256]`
   failed. The full isolated host run was 2,469 passed / one failed.
   `test-data/golden/phase5_public_api.json` expects stale Phase 2/3 golden hashes:

   | File | Phase 5 expected SHA-256 | Actual archived SHA-256 |
   |---|---|---|
   | phase2_public_api.json | c06e0b7c1bdde709797015f8e3cf64d395111bd2797ea2cfb58c88f0ed64af97 | ae322cc61781c73c1904303dc892c4811ac2883fa4914968ea479178bdf2949b |
   | phase3_public_api.json | 94aa7c8f98d9012a91855d9c33c494f55b2aefb8da1072f06e282f05a2bb015e | cbb3bbb5707a722ae17f23c425ec9a649ce397fb72886ea419baffc2d54c8413 |

   `git ls-tree` at the commit equals `git hash-object --no-filters` on archived
   bytes for Phase 2, 3 and 5: blob IDs respectively
   `4df3f28e96e9c90fb730da6cb3441994f165cc7a`,
   `9c28029e7e344e33648098befe3c6c51840ff1bc`,
   `db3bcde47c65027724a3a164fa47e3e5c9af2a56`.
   First determine whether newer work already resolves this; otherwise review
   intentional public-contract changes before updating a manifest. Do not
   blindly regenerate snapshots or overwrite uncommitted work.

2. `ruff check src --select S --output-format sarif` generated 15 active
   review candidates: S101 ×12, S311 ×2, S105 ×1. These have **not** been validated
   as vulnerabilities. Review the `assert`, simulator pseudo-random use and
   possible-password string contexts; document justified dispositions or fix
   confirmed problems. Do not globally suppress the family just to obtain PASS.

## Already observed, with boundaries

- Statement coverage 100% (13,834 lines), branches not measured.
- All 15 versioned product-quality host checks passed.
- Quality demo/live workloads are SYNTHETIC; hardware access NOT_PERFORMED.
- ForgeGate preserved the original results, produced two failing consumer rules
  and exported an internally VALID bundle whose engineering decision is FAIL.
- The consumer's zero-active-static-result policy is a review gate, not an
  assertion that every reported candidate is an exploitable vulnerability.

## Return handoff

Provide the owner-approved exact new commit and fresh JUnit, coverage XML, SARIF,
`phase5-product-quality-acceptance.v1` JSON, tool versions and individual command
exit codes. Explain any policy or scanner-disposition change. ForgeGate should
create a **new candidate**, preserving the previous FAIL and its immutable audit
history. No immediate action against the active worktree is requested here.

See [acceptance](PHASE_50_AVS_HOST_ACCEPTANCE.md),
[path-free evidence](PHASE_50_AVS_HOST_EVIDENCE.json), and
[reproduction steps](../examples/analog-validation-studio-host/README.md).
