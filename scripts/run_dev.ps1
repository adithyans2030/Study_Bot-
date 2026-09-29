# Starts the StudyBot API in dev mode (auto-reload) on 127.0.0.1.
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$sbHome = if ($env:STUDYBOT_HOME) { $env:STUDYBOT_HOME } else { Join-Path $env:LOCALAPPDATA "StudyBot" }
$python = Join-Path $sbHome "venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Virtualenv missing. Run scripts\setup.ps1 first." }

$port = if ($env:STUDYBOT_PORT) { $env:STUDYBOT_PORT } else { "8000" }
Set-Location (Join-Path $repo "backend")
& $python -m uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port $port
