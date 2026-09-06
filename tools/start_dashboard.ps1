# Explicit foreground lifecycle. No service registration, process killing or migration.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Database,
    [Parameter(Mandatory = $true)][string]$TrustStore,
    [string]$Python,
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
    # Literal paths and argument arrays preserve spaces and do not evaluate input as code.
    foreach ($entry in @($Database, $TrustStore, $Python)) {
        if (-not (Test-Path -LiteralPath $entry -PathType Leaf)) {
            throw 'A required database, trust-store or Python file is missing. Nothing was started.'
        }
    }
    $databasePath = (Resolve-Path -LiteralPath $Database).ProviderPath
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
    Write-Host 'Starting the foreground Dashboard. Keep this terminal open; Ctrl+C stops it.'
    Write-Host "In another terminal, run: python -m forgegate dashboard-check --port $Port"
    Write-Host 'A startup message is not a readiness confirmation. No automatic restart or login is enabled.'
    & $pythonPath @arguments
    exit $LASTEXITCODE
}
catch {
    # Fixed explanation; PowerShell itself may add local invocation context.
    Write-Error "Dashboard startup did not complete. $failureMessage" -ErrorAction Continue
    exit 3
}
