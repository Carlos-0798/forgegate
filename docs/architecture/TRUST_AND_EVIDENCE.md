# Trust and evidence semantics

ForgeGate keeps two independent dimensions.

`EvidenceTrust` describes confidence in producer identity, from an unsigned
local claim through a future signed attestation. `VerificationLevel` describes
what engineering observation occurred, such as simulation, replay, host tests,
target build, CI validation, system observation, or physical verification.

Neither dimension automatically implies the other. A cryptographically signed
simulation is still simulation. A physically measured value in an unsigned
local file may be real, but ForgeGate cannot authenticate its producer.

Policies declare minimums, and the Phase 2 evaluator enforces them using
explicit compatibility tables rather than lexical enum ordering. Evidence
below either minimum produces REVIEW when no eligible record remains; it is
not treated as absent or accepted by accident.

Artifact SHA-256 proves that the bytes evaluated later are the same bytes that
were registered. Candidate commit matching proves declared association. Neither
proves that the producer ran the stated tool honestly.

Evaluation does not upgrade either dimension. In particular, host-tested
software evidence remains host-tested software evidence and never becomes
target, system-observed, or physically verified evidence through policy PASS.
