# Dashboard recovery rehearsal receipt review

Phase 45 adds an operator-only, read-only review surface for the strict
`forgegate.recovery-rehearsal.v1` receipt produced by
`workspace rehearse-recovery`. It makes a completed restored-copy observation
visible without turning the browser into a restore console.

## Workflow

1. Complete the owner-operated CLI rehearsal described in
   [Recovery rehearsal](RECOVERY_REHEARSAL.md).
2. Activate the loopback Dashboard with an operator identity and open Recovery.
3. Select the exact `REHEARSAL.json` file. The browser rejects empty, malformed,
   non-UTF-8, wrong-schema or over-1,048,576-byte input and hashes the exact bytes.
4. The same-origin endpoint rechecks the supplied SHA-256, bounded JSON shape,
   duplicate keys, non-finite values and strict receipt coherence.
5. Review restored task/event totals, archive dependency totals, database hashes,
   the inspection fingerprint and the content-derived receipt/review identities.

Selecting a different file clears the prior result and restores the explicit
review action. A completed request is not retried automatically after HTTP
409, 413, 429 or 500 responses.

## Authority and evidence boundary

`POST /app/api/recovery-rehearsal-review` is loopback, same-origin, authenticated,
CSRF-protected and operator-only. It accepts exact JSON text and the expected
SHA-256 only. It does not accept or dereference a local path, backup ZIP,
database, recovery destination, trust store or private key. A successful review
does not alter candidate, job or audit records.

`VERIFIED_RESTORED_COPY` means the imported completion receipt is internally
coherent and content-addressed. It does not repeat the restore, re-open the
restored stores, establish continuing availability, rehydrate archived result
payloads, switch the live workspace, run queued tasks, authenticate producers,
control hardware or approve production use. Re-run the CLI checks when a fresh
operational statement is required.

## Verified

Python tests cover exact-byte success, unauthenticated and unauthorized access,
origin/CSRF enforcement, read-only behavior, hash/schema/duplicate/non-finite/
empty/oversize rejection and content-derived identity forgery. Production-
TypeScript tests cover successful rendering, exact endpoint/CSRF use, selection
recovery, browser-side malformed/oversize refusal, 409/413/429/500 presentation,
inconsistent response rejection and stale-response isolation.

Native Microsoft Edge accepted the actual Phase 44 receipt twice in an isolated
local workspace. It displayed 27 restored tasks, 43 events, one archived task
and one verified external result. Different-name reselection cleared the old
result and enabled a fresh explicit review. The browser console contained no
warnings or errors. See the [Phase 45 acceptance report](../reports/PHASE_45_RECOVERY_REHEARSAL_REVIEW_ACCEPTANCE.md)
and [retained screenshot](assets/phase45-recovery-rehearsal-review.png).
