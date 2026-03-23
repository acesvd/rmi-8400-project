$ErrorActionPreference = 'Stop'

$RootDir = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $RootDir

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m venv .venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv .venv
} else {
    throw 'Python 3 was not found. Install Python 3.11+ and retry.'
}

$pythonExe = Join-Path $RootDir '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    throw 'Virtual environment creation failed (.venv\Scripts\python.exe not found).'
}
& $pythonExe -m pip install --upgrade pip setuptools wheel
& $pythonExe -m pip install -r (Join-Path $RootDir 'backend\requirements.txt') -r (Join-Path $RootDir 'ui\requirements.txt')

Write-Host ''
Write-Host 'Local setup complete.'
Write-Host 'Run backend: .\scripts\run_backend.ps1'
Write-Host 'Run UI: .\scripts\run_ui.ps1'
