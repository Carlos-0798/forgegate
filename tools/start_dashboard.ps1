# Explicit foreground lifecycle. No service registration, process killing or migration.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Database,
    [Parameter(Mandatory = $true)][string]$TrustStore,
    [string]$Python,
    [string]$JobStore,
    [switch]$ExistingPair,
    [ValidateRange(1, 65535)][int]$Port = 8131,
    [ValidateRange(60, 3600)][int]$SessionTtlSeconds = 900,
    [string]$Msp430Port
)
$ErrorActionPreference = 'Stop'
$failureMessage = 'A required database, trust-store or Python file is missing or inaccessible.'
try {
    if (-not $Python) {
        $Python = Join-Path $PSScriptRoot '../.venv/Scripts/python.exe'
    }
    if ($ExistingPair -and ((-not $JobStore) -or $Msp430Port)) {
        $failureMessage = 'ExistingPair requires JobStore and does not allow Msp430Port.'
        throw 'Invalid existing-pair options.'
    }
    $jobPath = $null
    if ($JobStore) {
        if (-not (Test-Path -LiteralPath $JobStore -PathType Leaf)) {
            throw 'The job store is missing.'
        }
        # Preserve the original path for Python reparse/alias validation.
        $jobPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($JobStore)
    }
    # Literal paths and argument arrays preserve spaces and do not evaluate input as code.
    foreach ($entry in @($Database, $TrustStore, $Python)) {
        if (-not (Test-Path -LiteralPath $entry -PathType Leaf)) {
            throw 'A required database, trust-store or Python file is missing. Nothing was started.'
        }
    }
    $databasePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Database)
    $trustPath = (Resolve-Path -LiteralPath $TrustStore).ProviderPath
    $pythonPath = (Resolve-Path -LiteralPath $Python).ProviderPath
    $failureMessage = 'The database file is empty. Initialize a new workspace explicitly, not through recovery.'
    if ((Get-Item -LiteralPath $databasePath).Length -eq 0) {
        throw 'Empty database rejected.'
    }
    $failureMessage = 'The requested loopback port cannot be reserved. No process was stopped.'
    # Advisory exclusive-bind probe, not an ownership check or permanent reservation.
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    $listener.ExclusiveAddressUse = $true
    try {
        $listener.Start()
    }
    catch {
        throw 'The requested loopback port cannot be reserved. Inspect the listener; no process was stopped.'
    }
    finally {
        $listener.Stop()
    }
    $failureMessage = 'Python could not start. Check the selected environment and local terminal output.'
    $arguments = @('-m', 'forgegate', 'dashboard', '--database', $databasePath,
        '--trust-store', $trustPath, '--host', '127.0.0.1', '--port', "$Port",
        '--session-ttl-seconds', "$SessionTtlSeconds")
    if ($Msp430Port) {
        $arguments += @('--msp430-port', $Msp430Port)
    }
    if ($jobPath) {
        $arguments += @('--job-store', $jobPath)
    }
    if ($ExistingPair) {
        $arguments += '--existing-pair'
    }
    Write-Host 'Starting the foreground Dashboard. Keep this terminal open; Ctrl+C stops it.'
    Write-Host "In another terminal, run: python -m forgegate dashboard-check --port $Port"
    Write-Host 'A startup message is not a readiness confirmation. No automatic restart or login is enabled.'
    & $pythonPath @arguments
    exit $LASTEXITCODE
}
catch {
    # Emit one stable stderr line. Write-Error adds invocation formatting and
    # terminal-width wrapping, making the documented recovery message unstable.
    [Console]::Error.WriteLine("Dashboard startup did not complete. $failureMessage")
    exit 3
}
