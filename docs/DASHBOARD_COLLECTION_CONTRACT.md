# Dashboard bounded collection contract (Phase 30)

The first slice accepts one JUnit report through an operator-only,
candidate-scoped, same-origin and CSRF-protected preview POST. It is a bounded
synchronous operation, not a durable job queue or a general upload endpoint.

- Maximum decoded report: 1 MiB; canonical base64 preserves exact bytes.
  Existing 4 MiB actual HTTP body limit remains enforced.
- No client filename, server path, URL, archive, executable, or device input.
  An in-memory source uses a server-generated content-addressed logical name.
- Use the existing JUnit collector and evidence assembler; at most 10,000 XML
  elements and depth 32. No filesystem writes or network fetches occur.
- Require expected candidate revision and an explicit matching reported commit;
  candidate must be COLLECTING and have no retained evidence binding.
- Require caller-reported collection time with offset and no future timestamp,
  source tool and version. Do not replace old test time with upload time.
  Source metadata and commit association remain unverified declarations.
- Force unsigned_local / declared. Test-summary success is not policy PASS.
- Preview returns collection warnings/rejections and no assembly for a rejected
  report or unacknowledged warnings. A separate request can explicitly retain
  warnings. A complete assembly remains unbound until separate reviewed binding.
- No preview is durable. Closing/navigating away discards browser preview state;
  it does not promise server cancellation. Restart/session expiry requires a new
  preview. No automatic retry, resume, or fabricated percentage progress.
- The retained binding contains normalized evidence, receipt and exact hashes,
  not source report bytes. Users must retain originals themselves. The source
  receipt identifies canonical in-memory CollectionResult JSON, not a disk file.

Existing policies may reject declared-only JUnit evidence or require other
collectors. Users needing multiple reports should continue using the CLI assembly
workflow; binding this one-report assembly is immutable.

Acceptance requires positive/negative report cases, exact hash/count comparison,
warning consent, authorization/CSRF/scope/state checks, no preview writes,
separate binding, frontend recovery/stale-response tests, and browser evidence.
Queues, bulk formats, automatic execution and raw-artifact retention are deferred.
