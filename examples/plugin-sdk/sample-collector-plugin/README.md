# ForgeGate sample collector plugin

This is a standalone generic fixture for both the import-free ForgeGate Plugin
SDK discovery boundary and the production Windows broker test. Discovery reads
its manifest without importing the package. The broker later copies the exact
installed package into a disposable Podman sandbox; ForgeGate Core never imports
the entry point.

The callable consumes one synthetic JSON input and attempts fixed filesystem,
host-path, network, subprocess, and environment probes. It reports only
`unsigned_local` / `declared` fixture evidence and never accesses a device or
provides AFE/MSP430 integration.
