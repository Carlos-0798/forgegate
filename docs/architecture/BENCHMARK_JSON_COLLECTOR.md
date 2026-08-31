# Benchmark JSON collector

## Boundary

The collector consumes a ForgeGate-owned `forgegate.benchmark.v1` JSON artifact
beneath an explicit `ArtifactRegistry` root. It does not run a benchmark,
recalculate producer statistics, compare a value with a tolerance, or make a
release decision.

```text
benchmark.json
      |
      v
ArtifactRegistry -- exact bytes + media type + size + SHA-256
      |
      v
BenchmarkJsonCollector -- strict v1 contract + bounded JSON
      |
      v
benchmark.metric -- one record per unique (scope, metric name)
```

## Artifact contract

The root requires exactly:

- `schema_version: forgegate.benchmark.v1`;
- `tool.name` and `tool.version`;
- a non-empty `metrics` array.

Each metric requires a name, finite numeric value, and unit. `scope` defaults to
the collection request's scope. `baseline` is optional. `tolerance`, when
present, requires a non-negative value, an explicit `absolute` or `percent`
mode, and an accompanying baseline.

Metric names begin with an ASCII letter and use only letters, numbers, `.`,
`_`, `/`, and `-`. A scope/name pair must be unique. The committed
`schemas/forgegate.benchmark.v1.schema.json` is drift-checked against the
collector-owned contract during development verification.

## Normalized evidence

Every metric becomes `benchmark.metric` evidence. The evidence record's `unit`
holds the metric unit; its value is:

```json
{
  "metric": "api.request_latency.p95",
  "value": 42.75,
  "baseline": 40.0,
  "tolerance": {"value": 10.0, "mode": "percent"}
}
```

The status is `observed`. It does not mean the value passed its tolerance.
Future Phase 2 policy rules own regression direction, comparison, missing-data
handling, and final decision aggregation.

## Fail-closed behavior

The parser rejects invalid UTF-8, NUL bytes, malformed JSON, duplicate keys,
non-finite or unsupported-range numbers, unknown fields, an unsupported schema
version, empty metrics, duplicate metric identities, incomplete tolerance data,
and configured byte/node/depth/metric limit violations. Invalid entries are not
silently dropped.

Artifact SHA-256 and caller-supplied execution context, trust, and verification
metadata establish byte identity and claims. They do not authenticate the
benchmark producer or prove that the benchmark ran on the claimed environment.
