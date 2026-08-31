# ForgeGate threat model

## Assets

- versioned project and policy definitions;
- evidence/artifact integrity metadata;
- release decisions and local unsigned attestations;
- developer workstation paths and CI metadata.

## Trust boundaries

Configuration and evidence files are untrusted input. Local users, CI metadata,
future plugins, and remote artifact locations are separate trust domains.
The current slice has no authenticated producer and runs no plugin code.

## Addressed in Phase 0

| Threat | Current control |
|---|---|
| Unknown or ambiguous schema | Exact version dispatch and extra-field rejection |
| Unsafe YAML tags | `yaml.safe_load` |
| Oversized configuration | 4 MiB pre-parse document limit; policy content remains capped at 1 MiB |
| Parent or absolute output paths | Relative-path validation |
| Missing scan represented as zero findings | Mandatory `require_presence` invariant |
| Evidence reused for another commit | Per-record candidate commit equality |
| Artifact replacement | Strict SHA-256 field plus Phase 1 exact-byte registration |
| Naive timestamps | UTC-offset requirement |

## Addressed in the Phase 1 JUnit slice

| Threat | Current control |
|---|---|
| Absolute or parent-traversal artifact path | Explicit registry-root confinement |
| Symlink resolution outside root | Resolved-path containment check |
| Special file or oversized input | Regular-file check and 8 MiB default limit |
| Artifact mutation during collection | File metadata/size stability check and exact-byte hash |
| XML entity/DOCTYPE processing | Pre-parse rejection of declarations |
| Pathological XML shape | Element-count and tree-depth limits |
| Ambiguous JUnit outcomes/counts | Fail-closed rejection or explicit mismatch warning |

## Addressed in the Phase 1 coverage slice

| Threat | Current control |
|---|---|
| Malformed or entity-bearing coverage XML | Strict parse plus DOCTYPE/ENTITY rejection |
| Pathological coverage XML | 250,000-element and depth-64 default limits |
| Misleading declared coverage rates | Derive from countable lines/branches and audit mismatches |
| Ambiguous line/package/module ownership | Reject mixed scoped/unscoped line data |
| Duplicate or inconsistent LCOV records | Strict source-record state and duplicate/count checks |
| Oversized LCOV record set | 500,000-line default limit plus artifact byte limit |
| Missing branch detail hidden as observation | Explicit summary-only warning or unavailable warning |

## Addressed in the Phase 1 SARIF slice

| Threat | Current control |
|---|---|
| Missing scan represented as no evidence | Every successfully parsed run set emits an explicit summary, including zero results |
| Failed scanner invocation represented as valid evidence | Any declared unsuccessful invocation rejects the artifact |
| Ambiguous or absent rule identity | Require `ruleId` or a resolvable `ruleIndex`; conflicting references reject |
| Duplicate JSON keys or non-finite numbers | Strict object-pair and numeric-constant rejection |
| Pathological JSON shape or result volume | Node, depth, run, result, rule, location, suppression, and fingerprint limits |
| Unsupported nested detail silently normalized | Retain exact artifact bytes and emit `SARIF_DETAIL_NOT_NORMALIZED` warnings |
| Fabricated fingerprint stability | Prefer declared full/partial fingerprints; label fallback explicitly as ForgeGate-derived SHA-256 |
| Suppressed result treated as active | Preserve suppression records and mark accepted suppressions explicitly |

## Addressed in the Phase 1 Benchmark slice

| Threat | Current control |
|---|---|
| Ambiguous producer-specific benchmark shape | Exact `forgegate.benchmark.v1` schema version and strict field allowlists |
| Empty benchmark represented as successful evidence | Reject empty metric arrays; complete collections always contain metrics |
| Duplicate metric overwrites or double counting | Reject duplicate `(scope, name)` identities |
| NaN, Infinity, overflow, or underflow distortion | Decimal JSON parsing plus finite/range and conversion checks |
| Tolerance interpreted without comparison point | Any tolerance requires an explicit baseline |
| Percent versus absolute tolerance ambiguity | Required `mode` enum with `absolute` and `percent` only |
| Pathological JSON shape or volume | Artifact byte, JSON node/depth, and metric-count limits |
| Unknown fields silently ignored | Unknown root, tool, metric, and tolerance fields reject collection |

## Addressed in the Phase 2 policy-engine slice

| Threat | Current control |
|---|---|
| Wall-clock-dependent or irreproducible decision | Caller-supplied timezone-aware evaluation timestamp |
| Evaluation predates its evidence bundle | Reject evaluation time before bundle generation |
| NaN or Infinity creates non-standard input identity | Canonical JSON fingerprinting rejects non-finite values |
| Enum text accidentally used as assurance ordering | Explicit trust and verification rank tables |
| Missing evidence silently treated as a zero or empty all-set | Kind-level presence gate and no vacuous `all` evaluation |
| Stale or future evidence accepted | Future rejection plus optional inclusive maximum age |
| Conflicting producers collapsed into one value | Canonical distinct-value detection and REVIEW |
| Weakly typed comparisons produce surprising PASS | Strict numeric, equality, containment, and existence semantics |
| Optional failure accidentally blocks release | Mandatory-only overall decision with optional outcomes retained |
| Fail/review/error precedence changes by rule order | Explicit ERROR > FAIL > REVIEW > PASS rank table |
| Decision detached from evaluated inputs | Policy/evidence SHA-256 fingerprints and timestamp-bound evaluation ID |
| Unhandled expression failure becomes PASS | Per-rule defensive ERROR boundary and exit code 3 |

## Addressed in the Phase 2 candidate-lifecycle slice

| Threat | Current control |
|---|---|
| Candidate skips or reverses lifecycle state | Explicit one-way transition table and exact state revisions |
| Terminal candidate is silently reopened | Terminal states have no outgoing transitions |
| Transition event time rewrites history | Timezone-aware timestamps cannot precede current `updated_at` |
| PASS manufactured without policy evaluation | PASS/FAIL/REVIEW require a matching evaluation ID, commit, decision, and time |
| System error cannot be represented safely | ERROR permits a fail-closed transition without a policy result |
| Transition content changes under the same ID | Model recomputes content-bound transition SHA-256 |
| Event points to a different candidate result | Result envelope checks ID, state, time, evaluation, and result fingerprint |
| CLI preview mistaken for durable state | Documentation and output boundary explicitly state no persistence or locking |

## Addressed in the Phase 2 SQLite candidate-store slice

| Threat | Current control |
|---|---|
| Two writers advance the same revision | `BEGIN IMMEDIATE`, caller `expected_revision`, and SQL compare-and-swap |
| Retried request duplicates an event | Immutable idempotency key with canonical request fingerprint and stored response |
| Idempotency key reused for different input | Stable `STORE_IDEMPOTENCY_CONFLICT` failure |
| Mid-transaction failure leaves partial state | Snapshot, event, pointer, and idempotency row share one rollback boundary |
| Audit event or snapshot is edited/deleted | SQLite append-only update/delete triggers plus read-time chain validation |
| Candidate identity or revision pointer is rewritten | Candidate trigger freezes identity and requires a unit revision increment |
| Wrong or future database schema is opened | ForgeGate application ID, exact `user_version`, metadata, and object checks |
| Foreign-key or canonical JSON corruption is ignored | Every read validates foreign keys, strict models, canonical JSON, and fingerprints |
| Writer contention silently loses work | Bounded busy timeout and stable `STORE_BUSY` failure; no automatic unsafe retry |

## Addressed in the Phase 2 attestation slice

| Threat | Current control |
|---|---|
| Attestation embeds a different candidate or partial history | Require the terminal candidate and exactly four linked transition events; recompute all candidate/event associations |
| Evaluation is detached or internally inconsistent | Recompute evaluation identity, fingerprint, mandatory decision precedence, unique rule IDs, and evidence-reference union |
| Attestation content changes under the same ID | Recompute a SHA-256 identity over every field except schema version and the ID itself |
| Human-readable summary diverges from machine record | Render Markdown deterministically from the validated JSON model and revalidate stored bytes on read |
| Existing output is silently overwritten | Content-addressed directory, create-only staging files, atomic rename, exact-replay verification, and conflict failure |
| Symlink or irregular output target redirects publication | Reject symlink roots/targets and require exactly two safe regular files for replay |
| Mid-publication failure is mistaken for data loss | Store attestation transaction first; exact rerun publishes the same durable document or reports a conflict |
| Local record is mistaken for signed authority | Required `assurance: unsigned_local` plus explicit JSON/Markdown documentation boundary |
| Legacy migration fabricates a missing evaluation | Explicit v1/v2-to-v3 migration leaves it absent; exact matching evaluation import is required before attestation |

## Addressed in the Phase 3 Analog Validation compatibility slice

| Threat | Current control |
|---|---|
| Upstream runtime code crosses the product boundary | Consume only a versioned JSON artifact; no Studio import, subprocess, serial, or device path |
| Synthetic/replay evidence is promoted to hardware proof | Fixed source-to-verification mapping derived from the artifact |
| A `BENCH_*` label is mistaken for calibrated physical proof | Cap at `system_observed` and emit a warning because v1 lacks mandatory instrument/calibration provenance |
| Upstream PASS becomes an automatic release decision | Preserve it as observed `analog-validation.run`/criterion status; policy evaluation remains separate |
| Result fields or lineage are silently dropped or contradicted | Exact field allowlists plus TestRun/point/raw-record/source/criteria invariant checks |
| Future or malformed result schema is accepted | Exact version, enum, type, duplicate-key, finite-number, UTF-8, and unknown-field rejection |
| Pathological result JSON exhausts resources | Upstream 2,000,000-byte limit plus configured node/depth limits |
| Claimed producer commit is confused with byte integrity | Separate caller execution context/trust from registry-owned artifact SHA-256 |

## Addressed in the Phase 4 evidence-assembly slice

| Threat | Current control |
|---|---|
| Malformed collection-result JSON crosses the collector boundary | Strict UTF-8, duplicate-key, finite-number, schema, node, and depth validation |
| Collection result escapes the declared workspace | Root-confined regular-file registration with stable byte reads |
| Original artifact changes after collection | Re-register every referenced artifact and require exact path, media type, size, and SHA-256 equality |
| Same collection is silently counted twice | Reject duplicate raw source paths and duplicate normalized-result fingerprints |
| Evidence is mixed across candidate commits | Nested `EvidenceBundle` requires every record commit to equal the candidate commit |
| Receipt provenance is detached from bundle evidence | Require exact ordered evidence-ID coverage and receipt-owned artifact identity |
| Same artifact path names conflicting bytes | Reject path collisions with different media type, size, or SHA-256 |
| Collector warning disappears during aggregation | Reject by default; explicit retention preserves the complete warning records |
| Assembly content changes under the same identity | Recompute `assembly_id` over the nested bundle and all receipts |
| Byte integrity is mistaken for producer authenticity | Document SHA-256 as local identity only; no signature or CI identity claim |

## Addressed in the Phase 4 candidate-evidence-binding slice

| Threat | Current control |
|---|---|
| Candidate reaches `READY` without durable audited evidence | New v3 candidates require one binding before the `COLLECTING -> READY` transition |
| Assembly is bound to another candidate or commit | Embed the revision-one candidate and require its commit to equal the nested bundle commit |
| Binding content is changed under the same identity | Recompute candidate, assembly, and whole-binding SHA-256 fingerprints on every load |
| Binding is replaced after lifecycle advancement | One-row association, foreign key, append-only update/delete triggers, and read-time chain validation |
| Terminal decision evaluates different evidence | Require policy-evaluation `evidence_fingerprint` to equal the bound nested bundle fingerprint |
| Lifecycle chronology predates evidence acceptance | Binding cannot predate candidate/assembly; `READY` cannot predate binding |
| Retry key is reused to smuggle different input | Canonical request fingerprint, immutable response, exact replay, and conflict rejection |
| Migration invents assurance that did not exist | Legacy v1/v2 candidates retain an immutable no-binding-required marker; no binding is fabricated |
| Binding hash is mistaken for authenticated provenance | Explicit unsigned-local boundary; no producer, operator, CI, clock, or commit authentication claim |

## Addressed in the Phase 5 local REST API baseline

| Threat | Current control |
|---|---|
| Unauthenticated service is exposed to another host | `serve` accepts only `localhost`, IPv4 loopback, or IPv6 loopback addresses |
| CLI and HTTP apply different candidate rules | Shared `CandidateApplication` delegates both transports to the same domain and repository methods |
| Retried HTTP create duplicates a candidate | Required `Idempotency-Key` reaches the existing durable request-fingerprint and exact-replay control |
| Unknown or weakly typed JSON reaches the domain | Strict Pydantic request model rejects unknown fields and invalid types before the application service |
| Internal exception details leak through HTTP | Catch-all handler returns a fixed fail-closed message and correlation ID without exception text |
| Error response shape changes by failure source | Structured `ApiErrorResponse` covers request, domain, store, and unexpected failures |
| Requests cannot be correlated during local diagnosis | Valid caller `X-Request-ID` is echoed; otherwise a safe unpredictable identifier is generated |
| Malicious correlation value reaches logs or headers | Eight-to-128-character allowlist rejects spaces, control characters, and unsafe punctuation |
| OpenAPI silently diverges from the implementation | Deterministic export, committed byte-for-byte drift gate, and installed-wheel comparison |
| Local transport is mistaken for authenticated authority | Documentation explicitly states no identity, authorization, TLS, or non-loopback deployment claim |

## Addressed in the Phase 6 local REST command workflow

| Threat | Current control |
|---|---|
| HTTP and CLI mutate candidates through different policy paths | Shared application commands delegate both transports to the same SQLite repository and domain lifecycle |
| Concurrent HTTP writers silently overwrite a candidate | Every transition/evaluation supplies `expected_revision`; SQLite performs transactional compare-and-swap |
| Retried transition, binding, or evaluation duplicates state | Caller idempotency key plus canonical request fingerprint and stored exact response |
| HTTP policy evaluates evidence different from the persisted binding | Application loads the immutable binding and passes its nested bundle directly to the policy engine |
| Weaker unrelated policy is used for a release track | Phase 10 additionally requires exact material authorized by the candidate's frozen profile; name equality remains a legacy/stateless check |
| Evaluation result and terminal state diverge | Application derives the target state from the policy decision and stores both in one repository transaction |
| API reads or publishes arbitrary local paths | No loader/output path is accepted; nested assembly path metadata is not dereferenced, and file publication remains CLI-only |
| Attestation request races mutable candidate state | Store accepts only a terminal immutable revision-four candidate and exact deterministic replay |
| DNS rebinding or forged HTTP Host bypasses bind intent | Middleware requires the request Host itself to be localhost or a loopback IP |
| Declared oversized JSON exhausts ordinary local use | Requests declaring more than 4 MiB in `Content-Length` reject before validation |
| Local command endpoint is mistaken for operator authentication | Authority remains the local OS process/account boundary; no ForgeGate user identity is claimed |

## Addressed in the Phase 7 project registry and audit-query slice

| Threat | Current control |
|---|---|
| Project registration is silently replaced | One immutable row per project ID plus update/delete triggers and canonical readback validation |
| Retried registration duplicates state | Caller idempotency key binds the canonical registration request and exact response |
| Candidate write commits without its audit event | Domain write and audit append share the same SQLite transaction and rollback boundary |
| Exact replay duplicates audit history | Replay returns before event insertion; one durable state change yields one event |
| Audit row metadata diverges from its document | Every query revalidates canonical JSON, event identity, cursor, type, association, and subject fingerprint metadata |
| Unbounded audit query exhausts local resources | Strict 1-200 page limit, increasing integer cursor, and indexed project/candidate filters |
| Migration invents a project or actor | v1/v2/v3 migration projects only existing immutable candidate documents and never creates project profiles or identity claims |
| Audit hash is mistaken for an authenticated log | Documentation states local integrity/ordering only; no signature, trusted clock, retention, or administrator-resistant guarantee |
| Rejected input is assumed to be durably audited | Contract explicitly limits v4 events to successful state changes; rejected-request ingestion is deferred |

## Addressed in the Phase 8 project authority and discovery slice

| Threat | Current control |
|---|---|
| Candidate is created for an unknown project | Product-surface application, CLI, and API creation resolve the immutable project row inside the write transaction |
| Candidate uses a release track absent from the project profile | Exactly one configured track key must normalize to the requested canonical hyphen identity |
| Underscore compatibility creates two apparent authorities | Profiles containing ambiguous underscore/hyphen keys that normalize to the same track fail closed |
| Authority check races candidate persistence | Project and track validation share the same `BEGIN IMMEDIATE` transaction as candidate and audit insertion |
| Discovery crosses project boundaries | Candidate listing requires a registered project and filters by exact project ID before cursor pagination |
| Unbounded list request exhausts local resources | Strict page contracts enforce a one-to-200 limit and exclusive stable slug cursors |
| Legacy candidate becomes unreadable after the authority gate | Existing direct candidate/history reads remain available; only new product-surface writes require registration |
| Project configuration is mistaken for operator authorization | Documentation explicitly separates profile authority from absent caller identity/authentication |
| Mutable profile silently changes historical candidate meaning | Phase 9 uses append-only revisions and exact candidate-profile binding; no historical profile is rewritten |

## Addressed in the Phase 9 project-profile revision slice

| Threat | Current control |
|---|---|
| Concurrent profile writers overwrite one another | Caller expected version and one-step SQLite head CAS reject stale writers |
| Revision rewrites or deletes prior authority | Full replacement documents append to a guarded ledger; profile and binding update/delete triggers fail closed |
| Revision chain points to unrelated content | Content identity includes the immediate previous profile ID, complete config, version, and effective time; every read validates the contiguous chain |
| Project identity changes through a revision | Request and model require the replacement config project ID to equal the immutable registered project ID |
| Effective authority moves backward in time | Revision and candidate creation reject time before the governing current profile |
| Idempotency retry is reinterpreted under a later profile | Candidate and revision replay resolves the exact durable response before applying current authority |
| Track removal alters historical candidate meaning | Candidate v2 identity and immutable binding row retain the exact profile ID/version used at creation |
| Migration invents a historical candidate/profile link | v5-to-v6 migration backfills version-one registrations only; legacy v1 candidates have no binding row |
| Binding metadata is deleted or detached | Every candidate read validates snapshot identity, binding row, referenced profile, and chronology; corruption fails closed |
| Profile path is mistaken for exact policy authority | Phase 10 materializes and retains exact root-confined bytes before terminal evaluation |

## Addressed in the Phase 10 profile-authorized policy-material slice

| Threat | Current control |
|---|---|
| Policy name equality substitutes for frozen-profile authority | New product candidates require material project/profile/version/track fields to equal the immutable candidate binding |
| Profile authorizes one path but another file is evaluated | Store resolves the exact frozen track and requires the retained normalized artifact path to equal its configured policy path |
| Policy bytes change without changing parsed semantics | Material identity includes exact base64 bytes, size, media type, and artifact SHA-256; semantically equal byte variants have different IDs |
| Embedded policy differs from retained bytes | Validation reparses exact UTF-8 YAML/JSON with duplicate-key rejection and compares the strict model plus fingerprint |
| Evaluation is detached from its material | Evaluation v2 identity and store checks bind material ID, artifact SHA-256, profile ID/version, evidence fingerprint, and time |
| Partial terminal write retains material without a decision | Material, evaluation, transition, audit events, pointer, and idempotency response share one rollback boundary |
| HTTP caller selects a server filesystem path | REST accepts a complete validated material document and exposes no materialization/path-dereference route |
| Migration invents historical policy bytes | v1-v6 candidates receive `policy_material_required = 0`; no material row or authenticity claim is synthesized |
| Policy hash is mistaken for approval or producer identity | Contract and output documentation state unsigned-local byte association only |

## Deferred risks

- archive and compressed-input bombs in future collectors;
- stronger filesystem race resistance than the current open-handle metadata
  stability check;
- malicious plugins and subprocess isolation;
- CI identity verification, secret redaction, signing, revocation, trusted
  timestamping, and key
  management;
- database authorization, API authentication, audit retention, backup, repair,
  encryption at rest, and administrator-resistant tamper evidence.
- portable attestation bundling of the complete retained policy material;
- an exact streaming request-body limiter for unknown-length/chunked HTTP
  bodies; the current 4 MiB gate covers declared `Content-Length` only.
