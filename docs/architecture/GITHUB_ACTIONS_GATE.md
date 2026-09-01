# GitHub Actions assurance gate

## Scope

Phase 16 adds an offline bridge between one already-exported portable assurance
bundle and a GitHub Actions job. It does not collect evidence, evaluate policy,
query SQLite, call GitHub APIs, or change a repository. The bridge performs four
operations:

1. run the existing strict `verify-assurance` directory checks;
2. require the candidate's complete 40- or 64-hex commit object ID to exactly
   equal a caller-supplied CI commit;
3. append a bounded escaped Job Summary and stable action outputs;
4. return the existing ForgeGate decision exit code.

The public result is the content-derived
`forgegate.github-action-report.v1` contract. It retains the verified bundle,
manifest, project, candidate, exact commit, decision, recommended conclusion,
and evidence-boundary fields.

## CLI contract

```text
forgegate github-gate <assurance-directory> --expected-commit <complete-object-id>
```

When `GITHUB_OUTPUT` and `GITHUB_STEP_SUMMARY` exist, the command appends to
those runner files. `--github-output` and `--step-summary` provide explicit
paths for local or installed-wheel testing. If neither environment nor options
provide a path, the command still verifies, prints its versioned JSON report,
and returns the decision exit code.

| ForgeGate decision | Process exit | Recommended conclusion output |
|---|---:|---|
| PASS | 0 | `success` |
| FAIL | 1 | `failure` |
| REVIEW | 2 | `action_required` |
| ERROR or integration failure | 3 | `failure` |

`gate_status=VALID` means the portable bundle and exact commit binding were
valid. It does not mean the policy decision was PASS. On bundle, commit, or
output-file failure, the command writes only bounded ERROR metadata and exits 3.

## Composite Action

The repository-local action at `.github/actions/assurance-gate/action.yml`
requires ForgeGate to be installed first:

```yaml
- run: python -m pip install forgegate
- id: release-gate
  uses: ./.github/actions/assurance-gate
  with:
    assurance-directory: work/assurance/assurance-<bundle-sha256>
    expected-commit: ${{ github.event.pull_request.head.sha || github.sha }}
```

The caller must select the commit that the candidate actually represents. For
a pull request candidate built from the head revision, that is normally the PR
head SHA rather than GitHub's synthetic merge revision. ForgeGate never guesses
or shortens this value.

The committed CI job named `GitHub Action smoke (generic fixture)` executes the
composite Action against a canonical generic sample bundle. Its fixed
`aaaaaaaa...` commit is fixture-only evidence used to verify Action mechanics;
it is not the ForgeGate repository's current commit and is not a release claim.

## Summary and output safety

- Action inputs enter the shell through environment variables rather than
  inline script interpolation.
- Output values are schema-constrained IDs, slugs, enum values, and hexadecimal
  commits; no arbitrary evidence text is written to `GITHUB_OUTPUT`.
- Rule explanations are HTML/table escaped before entering the Job Summary.
- Each append is limited to 64 KiB and each destination to 4 MiB.
- Unsafe symlink/non-regular targets and unavailable parents fail closed.
- Rule rows are truncated with an explicit omitted-count notice before the
  summary limit.

The runner files are an operational presentation channel, not an authenticated
audit store. ForgeGate does not overwrite them, lock them across processes, or
claim administrator-resistant retention.

## Evidence and GitHub boundary

The bridge inherits the portable bundle's `unsigned_local` assurance and
`source_artifact_bytes=not_embedded` limitation. It verifies retained canonical
documents and exact commit association; it does not rerun JUnit, coverage,
SARIF, benchmarks, AFE results, or future MSP430 inputs. It does not authenticate
source producers, establish trusted time, or promote host/CI evidence to target,
HIL, bench, physical, field, or production evidence.

The composite Action requests no token and this phase does not call the GitHub
Checks, Pull Requests, Issues, Releases, or repository-administration APIs. A
GitHub workflow job naturally appears as a repository check, but custom Check
creation, PR comments, annotations, artifact upload, and workload-identity
federation remain separate future work requiring explicit authority and threat
design.
