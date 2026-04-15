$ErrorActionPreference = 'Stop'

$RootDir = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $RootDir

$EnvPath = Join-Path $RootDir '.env'
if (Test-Path $EnvPath) {
    foreach ($rawLine in Get-Content $EnvPath) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith('#')) {
            continue
        }
        $parts = $line -split '=', 2
        if ($parts.Count -ne 2) {
            continue
        }
        $name = $parts[0].Trim()
        if ($name.StartsWith('export ')) {
            $name = $name.Substring(7).Trim()
        }
        if (-not $name) {
            continue
        }
        $value = $parts[1].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -Path "Env:$name" -Value $value
    }
}

if (-not (Test-Path (Join-Path $RootDir '.venv'))) {
    throw 'Missing .venv. Run .\scripts\setup_local.ps1 first.'
}

$uvicornExe = Join-Path $RootDir '.venv\Scripts\uvicorn.exe'
if (-not (Test-Path $uvicornExe)) {
    throw 'uvicorn was not found in .venv. Re-run setup script.'
}

& $uvicornExe app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
