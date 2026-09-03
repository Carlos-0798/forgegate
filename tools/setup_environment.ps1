$ErrorActionPreference = "Stop"

$forgegateRoot = Split-Path -Parent $PSScriptRoot
$forgegatePython = Join-Path $forgegateRoot ".venv\Scripts\python.exe"
$forgegateConstraints = Join-Path $forgegateRoot "requirements\dev-constraints.txt"

Push-Location $forgegateRoot
try {
    if (-not (Test-Path -LiteralPath $forgegatePython)) {
        py -3.12 -m venv .venv
    }
    & $forgegatePython -m pip install --disable-pip-version-check --upgrade `
        -c $forgegateConstraints pip
    & $forgegatePython -m pip install --disable-pip-version-check `
        -c $forgegateConstraints -e ".[dev]"
    & $forgegatePython tools\verify.py
}
finally {
    Pop-Location
}
