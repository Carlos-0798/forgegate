# Phase 12 authenticated identity foundation acceptance report

- Date: 2026-08-31
- Version: 0.1.0.dev19
- Scope: portable-assurance signer identity and offline trust verification
- Evidence level: local host test
- Hardware/device evidence: none; no device access performed

## Accepted capability

ForgeGate can derive a public `forgegate.signing-identity.v1` from an existing
Ed25519 private key, authorize that exact identity for explicit projects and
producer/operator roles in an external `forgegate.trust-store.v1`, sign the
canonical Phase 11 assurance-bundle bytes, and verify the resulting
`forgegate.assurance-signature.v1` against that trust root without a database,
project tree, network service, AFE runtime, MSP430 runtime, or device.

The signature statement is domain-separated and binds bundle ID, exact
canonical bundle SHA-256, complete public signer document, role, and
timezone-aware caller-supplied signing time. Signature files publish under a
content-derived filename with exact replay and conflict rejection.

## Fail-closed evidence

Tests cover wrong private keys, detached bundles, altered signatures, unknown
identities, metadata mismatch, revoked identities, unauthorized roles and
projects, malformed/noncanonical base64, naive time, duplicate keys, non-finite
JSON, invalid encoding/schema/root/size, unstable file reads, output conflicts,
and concurrent exact replay. The installed-wheel smoke creates only an
ephemeral temporary key, derives identity/trust documents, signs twice, verifies
trust, and validates all three new document contracts.

## Local acceptance

- `pip check`: PASS
- Ruff and Ruff format: PASS
- strict mypy: PASS across 55 source/tool files
- pytest: 624 passed, 1 skipped because Windows symlink creation was unavailable
- branch-aware coverage: 98.13% across 5,733 statements and 1,526 branches
- Phase 12 identity focus: 22 passed; identity package 96.48%
- 25 canonical document Schemas plus two artifact Schemas: generated and parsed
- OpenAPI: drift-checked; no authenticated or non-loopback route was added
- source distribution, wheel, clean-install identity/sign/replay/verify smoke:
  PASS
- GitHub Actions: PASS on Windows, Ubuntu, and macOS; each platform completed
  `verify.py` and `release_smoke.py` in run 33455212296 for implementation
  commit `85586a0`

## Explicit limitations

The trust store is an externally protected local trust anchor; its content ID
does not establish authority by itself. The signed time is not a trusted
timestamp. Revocation is a static local record. ForgeGate does not generate or
retain long-term keys, validate host ACLs, support encrypted keys, rotate keys,
use HSM/TPM/KMS custody, federate CI identity, authenticate source-artifact
producers, or authenticate/authorize the REST API. The API remains loopback-only.

The underlying assurance bundle remains `unsigned_local`, and no software test,
CI result, signature, or replay was described as hardware, bench, field, or
production verification. No AFE or MSP430 code was imported and no hardware was
accessed.
