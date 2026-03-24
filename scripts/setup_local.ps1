$ErrorActionPreference = 'Stop'

$RootDir = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $RootDir

if (Get-Command python3.12 -ErrorAction SilentlyContinue) {
    & python3.12 -m venv .venv
    Write-Host 'Created virtual environment with python3.12'
} elseif (Get-Command python3.11 -ErrorAction SilentlyContinue) {
    & python3.11 -m venv .venv
    Write-Host 'Created virtual environment with python3.11'
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv .venv
    Write-Host 'Created virtual environment with python'
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $created = $false
    foreach ($ver in @('3.12', '3.11', '3')) {
        try {
            & py -$ver -m venv .venv
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Created virtual environment with py -$ver"
                $created = $true
                break
            }
        } catch {
        }
    }
    if (-not $created) {
        throw 'Unable to create virtual environment with py launcher (tried 3.12, 3.11, 3). Install Python 3.12 and retry.'
    }
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
