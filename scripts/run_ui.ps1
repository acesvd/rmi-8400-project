$ErrorActionPreference = 'Stop'

$RootDir = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $RootDir

if (-not (Test-Path (Join-Path $RootDir '.venv'))) {
    throw 'Missing .venv. Run .\scripts\setup_local.ps1 first.'
}

$streamlitExe = Join-Path $RootDir '.venv\Scripts\streamlit.exe'
if (-not (Test-Path $streamlitExe)) {
    throw 'streamlit was not found in .venv. Re-run setup script.'
}

& $streamlitExe run (Join-Path $RootDir 'ui\app.py') --server.port 8501 --server.address 0.0.0.0
