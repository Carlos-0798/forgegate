# Coverage XML and LCOV collectors

## Boundary

The coverage collectors consume existing Cobertura/coverage.py XML or LCOV
artifacts beneath an explicit registry root. They do not execute coverage tools,
read referenced source files, evaluate thresholds, or make release decisions.

```text
coverage.xml / coverage.info
            |
            v
ArtifactRegistry -- exact bytes + SHA-256
            |
            +--> CoverageXmlCollector -- bounded XML + observed count audit
            |
            +--> LcovCollector -------- strict source-record state + summaries
                                      |
                                      v
                         coverage.line / coverage.branch
                    repository + package/module scoped evidence
```

## Normalized value

Each evidence record uses:

```json
{"covered": 2, "total": 3, "percent": 66.666667}
```

The unit is `percent`. A nonzero opportunity count has status `observed`; a
known zero-opportunity count has status `not_applicable`. If branch information
is absent, no branch evidence is manufactured and an audit warning is returned.

Percentages are rounded deterministically to six decimal places. They remain
facts for explicit policy evaluation; neither collector applies a minimum.

## Coverage XML v1

- accepts namespace-neutral `coverage` roots;
- rejects NUL bytes, DOCTYPE/ENTITY declarations, malformed XML, excess
  elements/depth, invalid rates/counts, duplicate class line numbers, ambiguous
  scopes, and covered counts above totals;
- derives repository/package/module counts from class line elements when they
  exist;
- treats observed line and condition counts as authoritative and records root
  summary/rate differences as warnings;
- accepts root count summaries when detailed lines are unavailable and returns
  an explicit summary-only warning;
- requires explicit `(covered/total)` counts for branch-line condition data.

## LCOV v1

- accepts UTF-8 `TN`, `SF`, `DA`, `BRDA`, line/branch/function summaries, and
  validated function records;
- requires each source record to contain `DA` data and terminate explicitly;
- rejects unknown tags, invalid state transitions, duplicate line/branch keys,
  malformed values, partial summary pairs, and inconsistent totals;
- derives repository and module counts from `DA`/`BRDA` records;
- may use paired `BRF`/`BRH` when branch details are absent, but emits
  `LCOV_BRANCH_SUMMARY_ONLY` so the evidence limitation remains visible;
- validates function records but does not normalize them in v1, returning an
  explicit warning instead of silently discarding their presence.

Artifact hashes and caller-supplied commit/producer metadata still establish
identity and claims, not authenticated provenance.
