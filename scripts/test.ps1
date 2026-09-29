# Runs the StudyBot backend test suite. Extra args are passed to pytest.
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$sbHome = if ($env:STUDYBOT_HOME) { $env:STUDYBOT_HOME } else { Join-Path $env:LOCALAPPDATA "StudyBot" }
$python = Join-Path $sbHome "venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Virtualenv missing. Run scripts\setup.ps1 first." }

Set-Location (Join-Path $repo "backend")
& $python -m pytest @args
exit $LASTEXITCODE
