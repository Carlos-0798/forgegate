# GitHub reviewer-path audit — 2026-09-09

## Outcome and scope

This is an agent-led hiring-reviewer perspective, not feedback from an actual
employer or a certification. ForgeGate has a demonstrable Windows-local
engineering workflow suitable for discussion in a software, validation or
developer-tools interview. It is not a production service, an adopted commercial
product or evidence of measured human productivity gains.

The starting GitHub main was `0c56c6644d873a4c8564d4b7eb40bd0df8c31d6a`.
The existing in-app tab still displayed the previous merge, so a fresh, signed-in
Microsoft Edge tab was opened before judging current content. Live inspection
covered the repository page, rendered README, About/topics, loaded workbench and
real AVS images, the Mermaid diagram, and the linked real-project report.

## Findings and changes

| Reviewer question / observed issue | Applied presentation change |
|---|---|
| What problem does this solve? | Explain reconciling reports for one version and handing off a checkable decision before listing implementation detail; retain the unmeasured-human-gain boundary |
| Whose project and which work? | Identify the independent project maintainer, component scope and upstream ownership; distinguish project responsibility from tool assistance |
| Where should a reviewer start? | Direct links to a curated screenshot map, a plain-language real case, design decisions and independent Windows setup |
| Can I read the architecture without zooming? | Replace the visibly cramped seven-node graph with a four-stage summary; detailed collector, policy, database and authentication information remains in prose/docs |
| Are the numbers and pictures consistent? | Show the 1,569-test regression record from PR #14; preserve Phase 64's earlier 1,568 count as history; distinguish synthetic workflows, retained real AVS reports and historical physical UART observation |
| Does the demo require the owner's private files? | Promote independent workspace setup; retain the legacy frozen demo under historical material, not the first-use path |
| Is cloud CI broken or mandatory? | Keep manual-only policy visible, move account/run details to the CI section, retain historical failures and do not claim current hosted PASS |

## Evidence reviewers can inspect

- [Current workspace UI and evidence map](../docs/PORTFOLIO_EVIDENCE.md#recommended-review-path).
- [Real software case](PHASE_56_AVS_QUICK_ACCEPTANCE.md): four reports,
  130 normalized records and 12 rules, with 10 PASS / 2 FAIL; independent replay
  retained VALID / FAIL. This is successful integration, not producer-test PASS.
- [Independent first-use instructions](../docs/LOCAL_WORKSPACE_QUICKSTART.md):
  isolated local initialization, browser activation and known positive/negative
  examples; no board required.
- [Regression record](https://github.com/Carlos-0798/forgegate/pull/14):
  1,569 passed, three Windows symlink-capability skips, 95.90% branch-aware
  combined coverage. The previous Phase 64 record is not overwritten.
- [Engineering design](../docs/README.md#product-and-trust-model) and
  [verification boundaries](../docs/VERIFICATION_MATRIX.md).

The presentation-only change does not alter runtime, dependencies, schemas,
workflow triggers or original evidence files. Its full local verification and
post-merge browser readback are recorded in the accompanying pull request.
No new software-browser workflow, hardware, package, hosted CI, novice-user or
human-efficiency acceptance is implied by checking GitHub's presentation.

## Remaining owner decisions

The repository remains **Private**. An ordinary recruiter without granted
access cannot inspect it from a resume link. A later decision is needed between
controlled access, a reviewed public showcase, or public repository visibility;
this audit does not authorize any of those changes or select a License.

Interview claims should focus on the implemented report-to-decision workflow,
failure preservation, evidence boundaries and reproducible delivery. Be prepared
to explain and modify the relevant code; a repository alone does not establish
individual fluency, production operations experience or customer demand.

No arbitrary numerical HR score, hiring probability, customer adoption, human
speedup, security certification or broad hardware compatibility is asserted.
