# Plugin SDK discovery foundation

## Scope

Phase 17 freezes a declarative, import-free plugin discovery boundary. ForgeGate
enumerates only the `forgegate.plugins.v1` entry-point group, locates a fixed
`forgegate-plugin.json` file listed in each distribution, validates the bounded
manifest, and reports compatibility with Plugin API v1.

Discovery does not call `EntryPoint.load`, import a module, instantiate a
plugin, execute a subprocess, grant a permission, read a candidate database, or
collect/evaluate/export evidence. The public contracts are:

- `forgegate.plugin-manifest.v1` for content-derived plugin declarations;
- `forgegate.plugin-discovery.v1` for deterministic discovery results;
- `forgegate plugins list` for installed-environment inspection.

## Manifest placement and identity

An entry point uses a normal `package.module:attribute` value. Its top-level
package must contain a distribution-listed `forgegate-plugin.json` file:

```toml
[project.entry-points."forgegate.plugins.v1"]
"example.sample-collector" = "sample_plugin.runtime:plugin"
```

```text
sample_plugin/
  forgegate-plugin.json
  runtime.py
```

The manifest declares the plugin ID/version, target ForgeGate API version,
capabilities, versioned input schemas, requested permissions, and output
evidence kinds. Its `manifest_id` is the SHA-256 fingerprint of normalized
manifest content. The entry-point name must exactly equal the manifest plugin
ID.

Requested permissions are declarations only. Phase 17 does not grant, enforce,
or exercise artifact, filesystem, network, notification, secret, or subprocess
authority.

## Compatibility and isolation

Every discovered entry is classified without loading code:

| Status | Meaning |
|---|---|
| `COMPATIBLE` | strict manifest is valid and targets Plugin API v1 |
| `INCOMPATIBLE` | strict manifest is valid but targets another API version |
| `INVALID` | entry-point or manifest metadata failed a bounded contract check |
| `CONFLICT` | more than one installed distribution declares the same plugin ID |

Invalid, incompatible, and conflicting entries remain visible with stable
issue codes but are not loaded. The discovery report always states
`execution=NOT_LOADED`; a compatible status is not an execution approval.

Discovery is limited to 4,096 installed distributions, 1,024 plugin entries,
and 10,000 listed files per distribution. Manifests are limited to 64 KiB,
strict UTF-8 JSON, 2,048 nodes, and depth 16.
Duplicate keys, non-finite numbers, NUL bytes, unsafe symlinks, missing or
unlisted files, changed bytes, identity mismatches, and ambiguous IDs fail
closed. Reports contain distribution/package identifiers but no installation
path.

## Standalone fixture and independence

`examples/plugin-sdk/sample-collector-plugin` is a separately buildable Python
distribution. Its package deliberately raises if imported. Clean-wheel smoke
tests establish this sequence:

1. ForgeGate works with zero plugins;
2. install the standalone fixture wheel;
3. discover one compatible manifest without importing its package;
4. validate the versioned discovery report;
5. uninstall the fixture and confirm ForgeGate still works with zero plugins.

The fixture is generic and metadata-only. It is not an AFE or MSP430 plugin and
does not represent a source artifact, physical measurement, or production run.

## Deferred execution boundary

Plugin callable loading, collection requests/results, subprocess isolation,
resource limits, timeouts, secret handling, permission enforcement, signatures,
publisher trust, durable `plugin_runs` audit, and failure-to-ERROR mapping are
not implemented. Those controls must be designed and adversarially verified
before ForgeGate executes any external plugin code.
