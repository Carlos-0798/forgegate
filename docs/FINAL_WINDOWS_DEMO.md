# Final Windows Alpha demonstration

For the current independently runnable Dashboard, use
[Local workspace quickstart](LOCAL_WORKSPACE_QUICKSTART.md). The instructions
below preserve the Phase 61 frozen-wheel demonstration. Its Dashboard section
requires the owner's existing private development workspace; it was **not** a
fresh-recipient GUI startup path. Phase 61's fresh-recipient check covered CLI
fixtures only. Do not apply the new workspace command to the older frozen wheel.

This is the frozen `0.1.0a1` reviewer path. It uses committed generic fixtures
and the exact Phase 59 wheel. It does not run a producer project, authenticate
report origin, access hardware, publish a release or approve deployment.

## Five-minute CLI demonstration

Use a short local extraction path such as `C:\forgegate-demo`. The delivery ZIP
contains the wheel, this guide, generic inputs, retained browser images and
path-free acceptance evidence. From PowerShell in the extracted directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install `
  .\forgegate-0.1.0a1-py3-none-any.whl
.\.venv\Scripts\python.exe -m forgegate validate-config `
  .\examples\sample-python-api\forgegate.yaml
```

The ZIP contains ForgeGate, not a complete offline dependency mirror. The pip
step therefore needs the required packages in the local cache or access to the
configured package index.

Expected validation output begins with:

```text
VALID forgegate.project.v1:
```

Run the positive decision:

```powershell
.\.venv\Scripts\python.exe -m forgegate evaluate-policy `
  .\examples\sample-python-api\policies\pull-request.yaml `
  .\examples\sample-python-api\evidence\pass-bundle.json `
  --evaluated-at 2026-08-30T21:00:00Z
```

Expected: JSON decision `PASS` and process exit `0`.

Run the negative control:

```powershell
.\.venv\Scripts\python.exe -m forgegate evaluate-policy `
  .\examples\sample-python-api\policies\pull-request.yaml `
  .\examples\sample-python-api\evidence\fail-bundle.json `
  --evaluated-at 2026-08-30T21:00:00Z
```

Expected: JSON decision `FAIL`, failed rule `tests-pass`, and process exit `1`.
The nonzero exit is the intended release-gate behavior, not a crashed demo.

## Authenticated Dashboard demonstration

The Dashboard intentionally requires a user-owned candidate database, public
identity/trust document and matching local Ed25519 private key. These files are
not included in the shareable ZIP. Never commit or paste the key into a browser.

From the repository, launch one existing private demo workspace with the frozen
installed interpreter:

```powershell
.\tools\start_dashboard.ps1 `
  -Python .\work\phase59-closeout\installed\.venv\Scripts\python.exe `
  -Database .\work\phase61-final-demo\forgegate.db `
  -TrustStore .\work\phase61-final-demo\trust-store.json `
  -Port 8161
```

Keep the foreground terminal open and visit `http://127.0.0.1:8161/app/`.
Choose **Start local activation**, then approve the displayed code in a second
PowerShell window:

```powershell
.\work\phase59-closeout\installed\.venv\Scripts\python.exe `
  -m forgegate dashboard-activate FG-ABCDE-FGHJK `
  --server http://127.0.0.1:8161 `
  --identity .\work\phase61-final-demo\identity.json `
  --private-key .\work\phase61-final-demo\operator-key.pem `
  --role operator --project sample-api
```

Replace the one-time code with the current page value. Expected reviewer path:

1. **Overview** — Healthy, `0.1.0a1`, API v1, schema v9 and explicit limits.
2. **Candidates** — compare `phase58-installed-quick` (`PASS`) with
   `junit-fail-fixture` (`FAIL`).
3. **Evidence** — the PASS example contains four collections and nine records.
4. **Decision** — six exact PASS rules; the negative example explains
   `security-clean` with actual `1` against expected `0`.
5. **Assurance** — unsigned-local attestation, portable bundle identity,
   immutable transitions and `not_embedded` source bytes.
6. **Devices** — without an explicit serial option, displays
   `No live monitor configured`; no hardware operation is implied.

If the browser shows `ERR_CONNECTION_REFUSED`, the foreground service is not
running. Restart it; refreshing a bookmark cannot start a local process.

## Real-project evidence references

- AVS: Phase 60 reproduces the retained four-collection, 130-record, 12-rule
  `VALID / FAIL` handoff. Preserving the producer failure is correct behavior.
- MSP430: Phase 60 collects 17 `system_observed` records from the retained
  historical artifact and preserves both HIL/review-correction warnings.
- These references are artifact-consumer acceptance. They are not current
  upstream execution, producer authentication or a new physical observation.

## Screenshot gallery

The delivery ZIP contains the six Phase 58 installed-wheel captures under
`screenshots/`: Quick Assessment preview/PASS, replay download, restored-rule
comparison, changed-policy incompatibility and assurance download. Phase 59
proved all 109 runtime package members byte-equal to that browser-accepted wheel,
so Phase 61 reuses those images instead of presenting duplicate captures as new
evidence. The full repository gallery remains in
[Portfolio evidence](PORTFOLIO_EVIDENCE.md).

## Stop and clean up

Press `Ctrl+C` in the foreground service terminal. The private database and key
remain under ignored `work/`; remove them only through your normal private-data
retention process. Closing the browser alone does not stop ForgeGate.
