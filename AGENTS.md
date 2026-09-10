# ForgeGate repository instructions

These instructions apply to the entire repository.

## Read first

Before changing implementation or claims, read `README.md`,
`docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, and
`docs/VERIFICATION_MATRIX.md`.

## Current product scope

After completing the finite Alpha gates, the owner authorized an independent
runtime, interaction and feature reassessment on 2026-09-09. The earlier feature
freeze is lifted. Prioritize complete user tasks and demonstrated correctness
or usability gaps, rather than adding disconnected platform subsystems.
Preserve existing accepted evidence; repeat checks for changed artifacts,
failures or specifically unresolved acceptance conditions. External publication,
privacy and hardware boundaries below remain in effect.

## Product and evidence boundaries

- Keep ForgeGate Core domain-neutral. Do not import code from Analog Validation
  Studio or the MSP430 Equipment Health & Safety Controller.
- Integrations consume versioned public artifacts through optional collectors or
  packs. Upstream tests and measurements never become ForgeGate-owned evidence.
- Do not describe planned, simulated, replayed, host-tested, target-built,
  system-observed, or physically verified work as equivalent evidence.
- Artifact hashes and claimed commit metadata establish integrity/association,
  not producer authenticity.
- The canonical generic example and all core tests must work with every embedded
  compatibility component absent.

## Development gates

- Use Python 3.12 and the repository `.venv`.
- Run `python tools/verify.py` before accepting a change.
- Run `python tools/release_smoke.py` for packaging or dependency changes.
- Regenerate and commit JSON Schemas with model changes; schema drift is a test
  failure.
- Complete and document a vertical slice before adding another collector or
  external plugin surface.

## External and physical actions

- Do not create a remote, push, publish, change visibility, select a license, or
  make resume/LinkedIn claims without explicit owner approval.
- ForgeGate development does not authorize opening serial ports, flashing a
  board, sending device commands, changing FRAM, or controlling external loads.

## Repository privacy and presentation

- Keep the GitHub repository private unless the owner explicitly authorizes a
  visibility change. A push does not authorize a public release, License,
  GitHub Release, or LinkedIn publication.
- Use the repository-configured `Carlos-0798` identity and the account-specific
  GitHub noreply address for every author and committer record. Never record a
  personal email address in commits, documentation, screenshots, logs, or
  reports.
- Do not commit machine-specific absolute paths, credentials, generated local
  databases, build outputs, or private artifacts.
- Prefer Conventional Commit prefixes such as `feat:`, `fix:`, `test:`, and
  `docs:` for new commits.
- Keep README, status, roadmap, verification evidence, and known limitations
  aligned at meaningful checkpoints. CI claims must describe only the commands
  that the workflow actually executed.
