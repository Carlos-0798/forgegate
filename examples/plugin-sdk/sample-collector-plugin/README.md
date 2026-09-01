# ForgeGate sample collector plugin

This is a standalone, metadata-only fixture for the ForgeGate Plugin SDK
discovery boundary. Its package deliberately raises if imported: successful
`forgegate plugins list` execution therefore demonstrates that discovery read
the installed manifest without importing or executing plugin code.

The manifest declares a generic sample input and output. It does not collect
real evidence, access a network or device, or provide AFE/MSP430 integration.
Runtime loading and execution are intentionally not implemented in Phase 17.
