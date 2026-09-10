# Dashboard activation recovery — 2026-09-06

## Scope and result

Phase 28 follow-up on base commit `8f1ea08d059fe7b97af27dd66d903d7e5d50e0ae`.
The Dashboard now includes its current loopback origin in the companion CLI
command. This fixes a real port mismatch: the page used port 8131 while the
previous command silently selected the CLI default of 8000.

The private-key, role, project, one-time-code, Origin/CSRF, and session contracts
are unchanged. No new API endpoint, authentication bypass, persistent session,
hardware write, or automatic command execution is introduced.

## Corrections

1. Include `--server` with the page's exact origin, including IPv6 brackets and
   non-default ports. Explain local environment and placeholder replacement.
2. Provide a working manual retry after failed activation creation or polling.
3. Explain one-time-code expiry and replace the stale expiry notice when a new
   code is successfully issued.
4. Disable retry for a server-supplied Retry-After interval without submitting
   automatically when the timer ends.
5. Discard creation/poll responses belonging to a superseded activation screen.
6. Update the stale demo/UX documentation that still described pre-Phase-28
   functionality or omitted the activation server address.

## Verification

| Check | Result | Boundary |
|---|---|---|
| TypeScript check and Vite build | PASS | Local build |
| Production-TypeScript interaction regressions | 13/13 PASS | Minimal DOM, controlled HTTP and clock; not a real browser |
| Full Python gate | 882 passed, 3 skipped; 95.21% branch-aware coverage | Host tests; skips require Windows symlink privilege |
| CLI/API interaction smoke | 33/33 PASS | Host fixture; no hardware |
| Schema/OpenAPI/asset inventory | PASS | Existing contracts unchanged |
| Clean-wheel release smoke | PASS | Package/install/workflow/uninstall; not deployment |
| Browser activation on port 8131 | PASS | Real Codex in-app browser and companion CLI |
| Browser logout, real 60-second code expiry, fresh-code activation | PASS | Real local service, no injected HTTP errors |
| Browser activation while service is stopped, then manual retry after restart | PASS | Actual connection failure; no candidate write |
| Chrome/Edge retest | NOT RUN this follow-up | Current browser-control surface did not expose Chrome |
| High contrast, spoken Narrator, Remote Desktop | NOT RUN | Previously open environmental checks remain open |

Run the frontend regressions with Node 24.19.0 (the pinned CI runtime):

```powershell
pnpm run check:dashboard
pnpm run test:dashboard
pnpm run build:dashboard
.\.venv\Scripts\python.exe tools/dashboard_assets.py --write
.\.venv\Scripts\python.exe tools/verify.py
.\.venv\Scripts\python.exe tools/release_smoke.py
```

The host harness executes the production TypeScript using Node's experimental
type-stripping API; its experimental warning is retained, not hidden. An initial
harness attempt used the TypeScript compiler JS API, which is unavailable in
the installed TypeScript 7 package. The corrected harness uses only Node built-ins
and adds no package dependency. Its tests are separately wired into CI and are
not included in the Python coverage percentage.

The 13 cases cover four loopback origins (IPv4 port 8131, localhost port 8000,
IPv6 port 8131, and IPv4 implicit HTTP port), network and 500 creation
failures, 429 retry delay, three expiry/unknown statuses, polling network failure,
late creation, and late polling. Negative HTTP status outcomes are host fixtures,
not claims that 429/500 were reproduced in the live browser. A separate real
service stop/start did reproduce the browser's network-failure retry path.

The initial browser cycle completed CLI authorization at 05:25:13 UTC and
displayed the operator `sample-api` workspace. After logout, a new code expired
at 05:26:28 UTC; the page removed the command and offered a fresh activation.
Reactivation completed at 05:26:51 UTC. That cycle exposed a stale expiry notice
beside the new code; the notice was corrected and its replacement was added to
all three expiry regression cases.

## Retained portfolio captures

The following unedited 1043 × 1272 PNG screenshots are from the real in-app
browser. The code shown in the first image was used and its session explicitly
ended before publication; it is no longer usable. Paths in the command are
placeholders, not owner paths. No private key or Bearer/cookie value is shown.

| File under `docs/assets/` | SHA-256 |
|---|---|
| `forgegate-dashboard-activation-server.png` | `4d771f4017e8716ebf8b8cfb0005d34fe6b9eb633c6b12b725b9ed021b1b9a0c` |
| `forgegate-dashboard-activation-expired.png` | `7530cbd2d4be3329722db19ba3d62bcfbc2ada572e3ba1b455c0bc9dd1c73309` |
| `forgegate-dashboard-activation-retry.png` | `b1cfeaf21a4874d6f439b05c0c602bbc4ce5e7cdd08d2671bbfc989a01e16de2` |

Captures show origin-aware activation and actual expiry, not software-release
approval, producer authenticity, physical measurement validation, or complete
accessibility acceptance. The input-only MSP430 monitor may run alongside the
service; it does not turn these interaction results into device evidence.

## GitHub gate

At inspection, post-merge run
[34001577886](https://github.com/Carlos-0798/forgegate/actions/runs/34001577886)
was still attempt 1 and failed overall. Its three OS verification/package jobs
passed; the final generic Action fixture job never started because GitHub
reported an account payment/spending-limit restriction. This is an owner-account
blocker, not evidence of a failing test. Do not mark current main fully green or
bypass checks to merge this follow-up. No payment or budget setting was changed.
