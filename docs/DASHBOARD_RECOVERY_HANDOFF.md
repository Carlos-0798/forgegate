# Dashboard recovery handoff

Phase 43 adds an operator-only review surface between the offline readiness CLI
and a future explicit recovery rehearsal. It is a document handoff, not a restore
button or live backup monitor.

## Workflow

1. Run `workspace recovery-check ... --output recovery-readiness.json` against
   the exact root and original backups intended for recovery.
2. Activate the loopback Dashboard with an operator identity and open Recovery.
3. Select the generated JSON. The browser rejects empty or over-262,144-byte
   files, decodes strict UTF-8, checks the schema marker and calculates SHA-256.
4. The same-origin service rechecks the exact hash, JSON bounds, duplicate keys,
   non-finite values, strict model coherence and operator/CSRF authority.
5. Review READY FOR REHEARSAL or BLOCKED, the root/report/handoff identities,
   each dependency outcome and the explicit evidence boundaries.
6. Optionally download the reviewed `forgegate.recovery-readiness-handoff.v1`
   JSON. The download changes no retained candidate or job state.

## Security and evidence boundary

The browser sends only the path-free readiness JSON. It never sends the backup
ZIP, local filename/path, private key, API token or recovery destination. The
endpoint is loopback, same-origin, authenticated, CSRF-protected and restricted
to operators. Producer sessions cannot submit a document.

`READY_FOR_REHEARSAL` means the imported report was coherent and said READY for
the exact bytes observed at its historical `checked_at` timestamp. It does not
prove those ZIPs still exist, perform another hash check, authenticate a producer,
verify external trust/identity files, reserve disk, restore data, start a service,
touch hardware or publish anything. Rerun the CLI immediately before an actual
rehearsal.

## Verified

Local host tests cover READY/BLOCKED, exact hashes, malformed/duplicate/non-finite
JSON, model forgery, size limits, origin/CSRF/role enforcement, HTTP error
presentation, sequential reselection and stale-response isolation. Native Edge
READY and INCOMPLETE selection passed, rendering `READY_FOR_REHEARSAL` and
`BLOCKED` respectively. Both downloaded handoffs matched the SHA-256 displayed
by the browser and passed strict model validation. The manual pass also found and
fixed exact-byte trailing-newline normalization and post-success reselection.
Interactive screenshots were captured but are not claimed as repository-retained
because browser policy blocked transferring their captured bytes through a local
`file://` bridge.
