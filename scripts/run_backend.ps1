$ErrorActionPreference = 'Stop'

$RootDir = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $RootDir

if (-not (Test-Path (Join-Path $RootDir '.venv'))) {
    throw 'Missing .venv. Run .\scripts\setup_local.ps1 first.'
}

$uvicornExe = Join-Path $RootDir '.venv\Scripts\uvicorn.exe'
if (-not (Test-Path $uvicornExe)) {
    throw 'uvicorn was not found in .venv. Re-run setup script.'
}

& $uvicornExe app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
