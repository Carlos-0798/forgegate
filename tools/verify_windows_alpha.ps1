[CmdletBinding()]
param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [string]$Podman = "C:\Program Files\RedHat\Podman\podman.exe",
    [string]$SandboxEvidence = "reports\PHASE_19_WINDOWS_SANDBOX_LIVE_EVIDENCE.json",
    [string]$LiveOutput = "reports\PHASE_22_WINDOWS_ALPHA_LIVE_EVIDENCE.json"
)

$ErrorActionPreference = "Stop"

foreach ($required in @($Python, $Podman, $SandboxEvidence)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required Windows Alpha input is unavailable: $required"
    }
}

& $Python tools\verify.py
if ($LASTEXITCODE -ne 0) {
    throw "ForgeGate development verification failed with exit code $LASTEXITCODE"
}

& $Python tools\release_smoke.py `
    --windows-live-broker `
    --sandbox-evidence $SandboxEvidence `
    --podman $Podman `
    --live-output $LiveOutput
if ($LASTEXITCODE -ne 0) {
    throw "ForgeGate Windows Alpha clean-wheel verification failed with exit code $LASTEXITCODE"
}

Write-Host "ForgeGate Windows Alpha verification: PASS"
