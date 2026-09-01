# Open-source reference review

## Scope

This review records upstream projects consulted for ForgeGate Phase 18. The
repositories are references only: no third-party source was copied, vendored,
installed as a ForgeGate dependency, or added to the ForgeGate Git history.
ForgeGate's License status is unchanged.

Three small or medium repositories were shallow-cloned into the workspace's
separate `references/forgegate-open-source` area. Two large repositories were
reviewed through their official GitHub source and fixed revisions without a
local clone. The reference area is not part of this repository.

## Reviewed revisions

| Project | Revision reviewed | License | Local copy | Relevance |
|---|---|---|---|---|
| [in-toto Attestation Framework](https://github.com/in-toto/attestation) | `2dcd055e9f72e746687c306e35f4e59720ff45be` | Apache-2.0 | shallow clone | subject/digest binding, fixed statement layer, typed predicate, verification order |
| [in-toto Witness](https://github.com/in-toto/witness) | `3041b832ddcc59865e645e07048851b5e78746c1` | Apache-2.0 | shallow clone | attestor discovery/schema, collection-policy separation, provenance verification |
| [pluggy](https://github.com/pytest-dev/pluggy) | `4821148db2f4c6daa62ad8bdcae2918ecf27a731` | MIT | shallow clone | explicit hook specification/implementation validation and API evolution |
| [Open Policy Agent](https://github.com/open-policy-agent/opa) | `88c2ee0cdc9087ab1c3f09b95fa2b9ba5c8f69f5` | Apache-2.0 | not cloned | policy decision separated from enforcement and application I/O |
| [OpenSSF Scorecard](https://github.com/ossf/scorecard) | `d1fab88f54636ff366076edfc5c239f97b3c8e66` | Apache-2.0 | not cloned | check-specific results, evidence-aware claims, least-privilege CI review |

The revisions above identify the exact snapshots inspected on 2026-09-01.
They are not dependency pins and ForgeGate does not automatically update them.

## Adopted ideas

- Keep an immutable subject/digest envelope separate from type-specific plugin
  result data.
- Expose plugin capability and input/output schemas before any code execution.
- Separate policy decisions from the mechanism that enforces permissions.
- Define a strict host protocol and validate implementations against it.
- Treat every check/result as evidence with a precise boundary rather than a
  general security or release claim.
- Retain exact upstream revision and license metadata for reproducible design
  review.

These ideas are implemented only as the design decisions in
[`PLUGIN_EXECUTION_SECURITY_CONTRACT.md`](../architecture/PLUGIN_EXECUTION_SECURITY_CONTRACT.md).
No upstream-compatible attestation, Rego execution, Scorecard score, or pluggy
runtime integration is claimed.

## Explicitly rejected or deferred

- **In-process third-party hooks:** pluggy intentionally runs plugin code in the
  host process. ForgeGate may borrow hookspec-style contract discipline but
  rejects that trust model for untrusted external plugins.
- **OPA as a mandatory dependency:** ForgeGate already has a bounded versioned
  policy engine. OPA remains a possible optional future adapter, not a core
  runtime requirement.
- **Witness or in-toto format claims:** ForgeGate will not label its existing
  attestations in-toto-compatible without a separate schema mapping,
  interoperability tests, and terminology review.
- **Automatic upstream scoring:** Scorecard heuristics are useful review input,
  but a score does not replace ForgeGate's artifact-bound verification.
- **Immediate sandbox dependency:** Docker, a VM, or an OS-specific sandbox was
  not installed. The execution contract requires an enforcing backend to prove
  its capabilities before external code can run.
- **Source reuse or vendoring:** no third-party implementation code is imported;
  any future reuse requires an explicit dependency/license review.

## Maintenance rule

Future reference updates must record a new exact revision, re-check the
upstream license and security status, state which design decision changed, and
keep third-party clones outside the ForgeGate repository. A reference update
alone is not evidence that ForgeGate implemented or verified the upstream
feature.
