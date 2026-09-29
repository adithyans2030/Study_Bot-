# Copies the live database into %LOCALAPPDATA%\StudyBot\backups (or $STUDYBOT_HOME\backups),
# keeping the 14 most recent. Safe to run while the server is up. This is what the nightly
# scheduled task calls; run it by hand any time with:
#   powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$sbHome = if ($env:STUDYBOT_HOME) { $env:STUDYBOT_HOME } else { Join-Path $env:LOCALAPPDATA "StudyBot" }
$python = Join-Path $sbHome "venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Virtualenv missing. Run scripts\setup.ps1 first." }

Set-Location (Join-Path $repo "backend")
& $python -m app.cli backup
