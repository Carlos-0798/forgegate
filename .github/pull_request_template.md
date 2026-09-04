## Summary

Describe the problem, the implemented change, and the resulting behavior.

## Scope

- In scope:
- Out of scope:
- Compatibility impact: none / Analog Validation artifact / future MSP430 artifact

## Acceptance criteria

- [ ] The intended behavior is observable and bounded.
- [ ] Failure, replay, malformed-input, and trust-boundary behavior is covered where applicable.
- [ ] Schemas/OpenAPI and their drift checks are updated where applicable.
- [ ] README, status, roadmap, limitations, and evidence claims remain aligned.

## Verification evidence

| Command or review | Result | Evidence level |
|---|---|---|
| `python tools/verify.py` |  | Local host / hosted CI |
| `python tools/release_smoke.py` |  | Local host / hosted CI / not applicable |
| Focused test or live fixture |  | State exact boundary |

Record skips and failures; do not replace them with a general “all checks pass”
statement. Hosted CI does not prove local Podman/WSL2, hardware, or production
behavior.

## Security, privacy, and publication

- [ ] No credential, token, private key, personal email, private artifact, or machine-specific absolute path is included.
- [ ] New inputs, outputs, filesystem paths, subprocesses, network access, and authorization surfaces were threat-reviewed where applicable.
- [ ] AFE/MSP430 evidence retains its producer-owned evidence level.
- [ ] No hardware action or production/publication claim is implied without separate evidence and approval.
- [ ] The commit uses the repository-configured noreply identity.

## Reviewer notes

List remaining limitations, follow-up work, or decisions requiring owner action.
