# Authenticated assurance identity

## Scope

Phase 12 authenticates the signer of one exact Phase 11 portable assurance
bundle. It does not change the bundle contract, reopen its content-addressed
directory, or claim that referenced source artifacts were produced by that
signer. The local REST service remains unauthenticated and loopback-only.

Three domain-neutral documents define the boundary:

- `forgegate.signing-identity.v1` contains a display name, Ed25519 public key,
  and identity ID derived only from the algorithm and canonical public-key bytes;
- `forgegate.trust-store.v1` lists exact identities, their authorized
  `producer` and/or `operator` roles, explicit project IDs, and active/revoked
  state under one content-derived store ID;
- `forgegate.assurance-signature.v1` binds the bundle ID, SHA-256 of canonical
  bundle JSON, signer identity, claimed role, and caller-supplied signing time.

The trust store is deliberately external to the assurance bundle. Embedding it
beside attacker-controlled content would provide no independent trust anchor.

## Signing and verification

The signed bytes are:

```text
"ForgeGate assurance signature v1\0" || canonical-json(statement)
```

The NUL-terminated prefix domain-separates ForgeGate assurance signatures from
other Ed25519 uses. The statement contains the complete public signer document,
role, bundle ID, canonical bundle-file SHA-256, and timezone-aware signing time.
Ed25519 signing is deterministic for those exact inputs.

Verification first reruns every Phase 11 member, canonical-byte, manifest,
identity, and cross-document association check. It then:

1. recomputes the canonical bundle-file SHA-256;
2. verifies the Ed25519 signature against the embedded public key;
3. finds exactly that key-derived identity in the external trust store;
4. requires exact signer metadata, active status, the claimed role, and the
   bundled project ID to be authorized;
5. returns a bounded authenticated-signer summary.

Unknown, mismatched, revoked, wrong-role, wrong-project, detached-bundle, or
cryptographically invalid inputs fail closed.

## Filesystem and parser boundary

Identity inputs accept only bounded regular non-symlink files containing strict
UTF-8 JSON. Duplicate keys, non-finite numbers, unsupported schema versions,
unknown fields, invalid canonical base64, wrong key/signature lengths, and
unstable reads reject. Signature publication writes one canonical
`assurance-signature-<sha256>.json` through a flushed staging file. An exact
rerun reuses existing bytes; conflicts and unsafe roots fail closed.

The CLI derives a public identity from an existing unencrypted PKCS8 Ed25519
PEM, but never prints, copies, generates, or persists private-key bytes.

## Trust and compatibility boundary

Authentication here means: at verification time, an external trust store says
that this exact Ed25519 key is active for this role and project, and that key
signed these exact canonical assurance bytes. The trust-store file must itself
be distributed and protected out of band. Its SHA-256 ID detects content change
but does not make an untrusted trust store authoritative.

The caller-supplied `signed_at` value is signed but is not a trusted timestamp.
Revocation is a local trust-store snapshot, not an online status protocol. The
current CLI does not validate Windows ACLs or POSIX ownership/mode, support
encrypted private keys, integrate an HSM/TPM/KMS, rotate keys, federate CI
workload identity, or authenticate an HTTP session.

The embedded bundle remains `unsigned_local` because its evidence records and
source artifacts are unchanged. A signer authorized as `producer` attests only
to the bundle statement; ForgeGate does not infer that every nested JUnit,
coverage, SARIF, benchmark, AFE, future MSP430, hardware, bench, field, or
production fact originated from that signer. Optional AFE/MSP collectors remain
separate versioned artifact boundaries with no runtime or device dependency.
