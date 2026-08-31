# Trust and evidence semantics

ForgeGate keeps two independent dimensions.

`EvidenceTrust` describes confidence in producer identity, from an unsigned
local claim through a future signed attestation. `VerificationLevel` describes
what engineering observation occurred, such as simulation, replay, host tests,
target build, CI validation, system observation, or physical verification.

Neither dimension automatically implies the other. A cryptographically signed
simulation is still simulation. A physically measured value in an unsigned
local file may be real, but ForgeGate cannot authenticate its producer.

Phase 0 records these values and permits policies to declare minimums. Ranking
and enforcement belong to the future deterministic policy evaluator and must
use an explicit compatibility table, not lexical enum ordering.

Artifact SHA-256 proves that the bytes evaluated later are the same bytes that
were registered. Candidate commit matching proves declared association. Neither
proves that the producer ran the stated tool honestly.
