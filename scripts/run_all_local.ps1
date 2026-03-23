$ErrorActionPreference = 'Stop'

$RootDir = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $RootDir

if (-not (Test-Path (Join-Path $RootDir '.venv'))) {
    throw 'Missing .venv. Run .\scripts\setup_local.ps1 first.'
}

$uvicornExe = Join-Path $RootDir '.venv\Scripts\uvicorn.exe'
$streamlitExe = Join-Path $RootDir '.venv\Scripts\streamlit.exe'

if (-not (Test-Path $uvicornExe)) {
    throw 'uvicorn was not found in .venv. Re-run setup script.'
}
if (-not (Test-Path $streamlitExe)) {
    throw 'streamlit was not found in .venv. Re-run setup script.'
}

$backendLog = Join-Path $env:TEMP 'appeals_backend.log'
$backendJob = Start-Job -ScriptBlock {
    param($RootDir, $UvicornExe, $BackendLog)
    Set-Location $RootDir
    & $UvicornExe app.main:app --app-dir backend --host 0.0.0.0 --port 8000 *> $BackendLog
} -ArgumentList $RootDir, $uvicornExe, $backendLog

Write-Host "Backend started in background job $($backendJob.Id). Logs: $backendLog"
Write-Host 'Starting Streamlit UI...'

try {
    & $streamlitExe run (Join-Path $RootDir 'ui\app.py') --server.port 8501 --server.address 0.0.0.0
} finally {
    Stop-Job -Job $backendJob -ErrorAction SilentlyContinue | Out-Null
    Remove-Job -Job $backendJob -ErrorAction SilentlyContinue | Out-Null
}
