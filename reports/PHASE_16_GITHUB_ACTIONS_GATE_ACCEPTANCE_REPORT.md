# Phase 16 GitHub Actions assurance gate acceptance report

- Date: 2026-09-01
- Version: `0.1.0.dev23`
- Stage: implemented and locally verified; private cross-platform CI
  confirmation pending
- Evidence class: local-host software tests over a generic fixture

## Accepted scope

Phase 16 adds a bounded offline GitHub Actions presentation and exit-code bridge
without granting ForgeGate repository or GitHub API authority:

1. verify an existing Phase 11 portable assurance directory using its exact
   canonical bytes, manifest, content identities, and document associations;
2. require the candidate's complete 40- or 64-hex commit to exactly equal the
   caller-supplied CI commit;
3. emit `forgegate.github-action-report.v1`, stable schema-constrained outputs,
   and a bounded escaped Job Summary;
4. preserve PASS/FAIL/REVIEW/ERROR process exits 0/1/2/3;
5. expose the command through a token-free repository-local composite Action.

The committed workflow's Action job uses the generic sample bundle with fixed
`aaaaaaaa...` commit metadata. It verifies the integration mechanics only and
is explicitly not a claim about the current ForgeGate repository revision.

## Local verification evidence

- pytest: 666 passed, 2 skipped
- branch coverage: 97.46%
- measured source: 6,623 statements and 1,750 branches
- Phase 16 focus: 10 passed, 1 skipped; report model 100% and integration
  service 98%
- Ruff, format check, strict mypy, dependency check, committed Schema drift:
  PASS
- regenerated OpenAPI metadata drift check: PASS
- `python tools/release_smoke.py`: PASS, including complete sdist manifest,
  clean wheel installation, portable-bundle verification, exact commit gate,
  Job Summary/output writes, report validation, and unchanged identity workflow

Both skipped tests require Windows symlink creation, which this host does not
permit. The new skipped case directly exercises the runner-output symlink
rejection; equivalent non-regular, missing-parent, oversize, and I/O failure
paths passed, while CI will exercise the same suite on other hosts.

## Explicit limitations

- The bridge retains `unsigned_local`; source artifact bytes are not embedded or
  rerun, and their producers are not authenticated.
- Exact commit equality is caller-supplied association, not GitHub workload
  identity, trusted time, repository identity, or signed provenance.
- Job Summary and output files are presentation channels, not durable or
  administrator-resistant audit storage.
- No GitHub token is requested and no Checks, Pull Requests, Issues, Releases,
  artifact-upload, or repository-administration API is called.
- Custom annotations, PR comments, signed CI provenance, OIDC, artifact upload,
  and token permission design remain future explicitly authorized work.
- No MSP430 access, AFE runtime import, physical device operation, target/HIL/
  bench validation, production deployment, public release, or License change
  occurred.

## Cross-platform evidence

Private GitHub synchronization and Windows/Ubuntu/macOS CI confirmation are
pending. This section must be updated with the exact implementation commit and
run before the Phase is reported as cross-platform verified.
