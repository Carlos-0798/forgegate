# ForgeGate release attestation

> This is an unsigned local ForgeGate record. It establishes content
> consistency and association, not producer identity or authorization.

## Release decision

| Field | Value |
|---|---|
| Decision | PASS |
| Project | sample-api |
| Version | 1.2.0 |
| Commit | aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa |
| Branch | main |
| Release track | pull-request |
| Candidate ID | cand-dab25eb0be1a0107b3996080 |
| Candidate fingerprint | sha256:a30c5d60b52ac16696723750f2dfbc7392ff2a8000e6ff0d45d674fb393242cf |
| Evaluation ID | sha256:bea1da21514953043911d4001967d0107e687086acc09957e56e056ef3d682b8 |
| Terminal time | 2026-08-30T21:00:00Z |
| Issued at | 2026-08-31T01:00:00Z |
| Attestation ID | sha256:11ed4fb82e75cfa055dde1894dda0e069fe0a5e2a9409a6407990fe24fcb7fa3 |
| Assurance | unsigned_local |

## Candidate transition chain

| Revision | Transition | State | Occurred at |
|---:|---|---|---|
| 1 | sha256:cdb66d8cc66e6e79937f693b332cbe140b0a6d6227b249a33233773958794bd2 | COLLECTING | 2026-08-30T12:01:00Z |
| 2 | sha256:69d70fcb96d6eb2b6c958055192348e281c004d2b80b7698f7bcbe1d688247af | READY | 2026-08-30T12:02:00Z |
| 3 | sha256:ab3b07ac4eb7fe28d84a9d7b855ebbc717cd324f3c7fd1886d2481ecd3c1b02d | EVALUATING | 2026-08-30T12:03:00Z |
| 4 | sha256:3a398c5d4aee8273c404650da1c56b460c679e8d7ac029c9647c89e6386534d9 | PASS | 2026-08-30T21:00:00Z |

Transition-chain fingerprint: sha256:5f5ba7998fe2c4e5d52c76b9c4c6e164906c5747e546dccf2596417f23d1ce93

## Policy evaluation

Policy: pull-request

Evaluation fingerprint: sha256:8fde8215df96164ad8a5426f046a4bceb7fd0c2016e3d91f0d7b8ad1e3408c78

| Rule | Decision | Mandatory | Reason |
|---|---|---|---|
| rule-01 | PASS | true | RULE_RESULT |

Evaluated evidence IDs:

- evidence-01

## Generator

ForgeGate version: 0.1.0.dev8
