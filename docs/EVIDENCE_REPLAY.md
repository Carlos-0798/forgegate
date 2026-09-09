# Private source evidence and offline replay

Phase 51 adds a separate, bounded **original-report replay archive**. The existing
three-file assurance ZIP remains unchanged: it references reports but does not
embed their bytes. Use this new archive when a reviewer needs to reparse those
reports and reproduce the retained policy decision without a database.

## What is checked

The exporter and verifier check the exact original collection-result JSON and raw
report hashes/sizes, rerun the built-in parsers, compare all normalized results
and warnings, reconstruct the bound assembly, and recompute the embedded policy
at its original evaluation time. The verifier also checks the canonical ZIP and
an independently supplied expected candidate commit.

**VALID is not PASS.** CLI verification exits 0 for an internally valid replay,
including a correctly reproduced FAIL, REVIEW or ERROR decision. Read `decision`
as well as `status`. Invalid or mismatched input exits 3; command usage errors
follow the CLI's normal usage handling.

This is report parsing and policy replay, not re-execution of producer tests,
benchmarks, scanners, report-generation/mapping tools or hardware. Hashes and
declared commit association do not authenticate a report producer. No signature,
trusted time, remote publication or release approval is added.

## CLI

Run from the ForgeGate environment; replace the uppercase placeholders:

```powershell
forgegate evidence-replay export DATABASE CANDIDATE_ID --source-root ORIGINAL_ROOT --destination NEW_DIRECTORY
forgegate evidence-replay verify REPLAY_ARCHIVE.zip --expected-commit COMMIT_SHA
```

Export requires an attested candidate and retained originals. `ORIGINAL_ROOT`
must resolve the relative artifact references already recorded in its assembly,
including each collection-result JSON, not just the XML/SARIF/benchmark reports.
Use the original collection handoff directory; filenames alone cannot repair
different bytes. No missing report is synthesized and no candidate is changed.

The destination must not already exist or traverse a symlink/junction. Export
validates before creating it and never overwrites. A filesystem write failure
can leave a new partial destination: keep it for diagnosis and choose another
new directory after correcting the cause. This is not an atomic directory
transaction or a defense against a hostile local filesystem administrator.

The recipient needs ForgeGate with the same version and compatible parser
behavior; the verifier rejects a version or replay mismatch. Preserve the exact
tested ForgeGate checkout/wheel for long-term reproduction: the Alpha version
string alone does not uniquely identify every development working tree.

## Dashboard

From a completed [Quick assessment](QUICK_ASSESSMENT.md), Phase 55 also offers
**Save originals for offline replay** with the report/receipt files already
prepared. Review their hashes and privacy before download; save before closing
that dialog. The steps below remain the separate retained-candidate path.

1. Activate an **operator** session scoped to the candidate's project.
2. Open the candidate's **Assurance** page and choose **Export original evidence**.
3. Select the complete original reports and collection-result JSON files. File
   matching uses SHA-256, not their selected filenames. With the current native
   multi-select picker, put byte-preserving copies in one private folder if the
   originals are spread across directories; alternatively use the CLI.
4. Choose **Review selected originals**. A missing, extra, changed, duplicate or
   oversized selection is refused before export and can be selected again.
5. Read and acknowledge the source-data privacy boundary, then choose
   **Confirm private replay download**. The server reparses the supplied bytes
   and recomputes policy before returning a ZIP. The browser checks the response
   identity and full archive hash before offering the download.
6. Run the displayed offline verification command against the downloaded file.
   Confirm its commit and decision against an independent handoff record.

The POST endpoint is
`/app/api/candidates/{candidate_id}/evidence-replay-export`. It uses the existing
same-origin, CSRF, operator and project authorization. Revision/bundle mismatch
returns 409; invalid source replay returns 400, invalid request shape 422, and
the existing request/rate limits remain applicable. There is no automatic retry.
Selected bytes are handled in memory, not added to the candidate store or logs;
download still creates a private file on the user's computer.

## Version 1 boundary

- Built-in JUnit, Cobertura coverage XML, LCOV, SARIF 2.1.0 and benchmark JSON;
  one raw artifact per collection, complete results only, no external plugins.
- Up to 16 collections / 4,096 evidence records; at most 32 distinct report/result
  files, 1 MiB each and 2 MiB total. The original result JSON counts toward limits.
  Assurance document: 16 MiB; complete replay archive: 20 MiB.
- Parser requests are reconstructed from retained evidence metadata, not an
  independently stored invocation. Benchmark metrics use their embedded scopes
  and the default repository fallback. Non-default fallback/custom parser
  configurations that do not reproduce exactly are rejected, not approximated.
- The rootless deterministic ZIP contains `manifest.json`,
  `assurance-bundle.json` and `blobs/<sha256>`. It uses no compression or encryption.
  Verification is in memory without extraction, commands, network, plugins or
  database writes; extra/missing/duplicate members, altered bytes and noncanonical
  ZIP structure are rejected.
- Originals may contain private paths, source snippets or test data. There is
  **no automatic redaction or encryption**. Keep the archive private. Editing a
  report to redact it changes its hash and is not the original retained evidence.
  Share a separately reviewed summary instead when disclosure is inappropriate.

See [Phase 51 acceptance](../reports/PHASE_51_SOURCE_REPLAY_ACCEPTANCE.md) for the
real AVS four-report replay and browser download evidence. Phase 50's upstream
golden-manifest failure and static-review findings are not fixed by this feature.
