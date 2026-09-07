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

## Verified and open

Local host tests cover READY/BLOCKED, exact hashes, malformed/duplicate/non-finite
JSON, model forgery, size limits, origin/CSRF/role enforcement, HTTP error
presentation and stale-response isolation. Production TypeScript navigation was
observed in Edge. Native Edge file selection remains a manual acceptance gate on
this workstation because the browser-control extension currently lacks file-URL
access; no successful browser screenshot is claimed until that permission is
owner-enabled and the exact generated file is selected.
