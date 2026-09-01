# Phase 17 Plugin SDK discovery acceptance report

- Date: 2026-09-01
- Version: `0.1.0.dev24`
- Stage: implemented, privately synchronized, and cross-platform verified
- Evidence class: local-host and private CI software tests over synthetic
  distribution metadata and a standalone generic fixture

## Accepted scope

Phase 17 adds a safe metadata foundation before external plugin execution:

1. strict content-derived `forgegate.plugin-manifest.v1` declarations;
2. import-free enumeration of the `forgegate.plugins.v1` entry-point group;
3. exact Plugin API v1 compatibility checks;
4. deterministic `COMPATIBLE`, `INCOMPATIBLE`, `INVALID`, and `CONFLICT`
   reporting through `forgegate.plugin-discovery.v1`;
5. `forgegate plugins list` without loading plugin code;
6. a standalone import-hostile generic plugin distribution used for
   install/discover/uninstall clean-wheel smoke.

## Security and independence result

- Manifest reads use exact distribution-listed paths, regular stable bytes, a
  64 KiB limit, strict UTF-8 JSON, duplicate/non-finite rejection, and bounded
  node/depth validation.
- Entry-point values are validated but never loaded; reports explicitly retain
  `execution=NOT_LOADED`.
- Malformed, incompatible, duplicate, missing, oversized, or mismatched plugin
  metadata is isolated to a stable discovery entry and cannot become an
  executable plugin.
- Requested permissions are declarations, not grants.
- The generic fixture imports no ForgeGate runtime and ForgeGate imports no AFE
  or MSP430 package. Core discovery works with the fixture absent.

## Local verification evidence

- pytest: 696 passed, 3 skipped
- branch coverage: 97.55%
- measured source: 6,955 statements and 1,844 branches
- Phase 17 focus: 30 passed, 1 skipped; plugin package 99.27% branch-aware
  coverage
- Ruff, format check, strict mypy, dependency check, committed Schema drift,
  and regenerated OpenAPI metadata drift: PASS
- `python tools/release_smoke.py`: PASS, including core wheel/sdist, standalone
  plugin wheel, zero-plugin discovery, import-free compatible discovery,
  versioned report validation, uninstall, and zero-plugin recovery

All three local skips require Windows symlink creation, which this host does not
permit. The Phase 17 skipped case directly exercises manifest-symlink rejection;
missing, external, oversized, unlisted, malformed, depth/node, and other unsafe
metadata paths passed locally. Private CI executed all 699 tests without skips
on each supported runner, so the local host limitation remains recorded without
being generalized to the cross-platform result.

## Explicit limitations

- No external plugin callable is imported or executed.
- No subprocess sandbox, timeout, resource quota, secret broker, permission
  enforcement, publisher signature, or durable plugin-run audit exists.
- `COMPATIBLE` means only that strict installed metadata targets Plugin API v1;
  it does not approve code safety, publisher identity, or execution.
- The standalone fixture is maintained inside this private development
  repository for reproducibility; no second remote repository is created.
- No MSP430 access, AFE runtime import, physical device operation, target/HIL/
  bench validation, production deployment, public release, or License change
  occurred.

## Cross-platform evidence

- Implementation commit:
  `7290efd9f42ab37ce06d7cef4a32c9c18e6e5551`
- Private GitHub Actions run:
  `33561999025`
- Windows, Ubuntu, and macOS each passed all 699 tests in `verify.py` and the
  complete `release_smoke.py` workflow, including clean ForgeGate install plus
  standalone sample-plugin install, import-free discovery, report validation,
  uninstall, and zero-plugin recovery.
- The dependent generic-fixture composite Action smoke job also passed.
