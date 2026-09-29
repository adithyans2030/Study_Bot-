# Creates the StudyBot virtualenv OUTSIDE OneDrive and installs dependencies.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo "backend"
$sbHome = if ($env:STUDYBOT_HOME) { $env:STUDYBOT_HOME } else { Join-Path $env:LOCALAPPDATA "StudyBot" }

if ($sbHome -match "OneDrive") {
    throw "STUDYBOT_HOME ($sbHome) is inside OneDrive. Choose a path outside OneDrive."
}

$version = (python --version) -replace "Python ", ""
if ([version]$version -lt [version]"3.11") {
    throw "Python 3.11+ required, found $version"
}

$venv = Join-Path $sbHome "venv"
$python = Join-Path $venv "Scripts\python.exe"
New-Item -ItemType Directory -Force -Path $sbHome | Out-Null

if (-not (Test-Path $python)) {
    Write-Host "Creating virtualenv at $venv (Python $version)"
    python -m venv $venv
}

& $python -m pip install --upgrade pip --quiet

$lock = Join-Path $backend "requirements.lock"
$reqs = if (Test-Path $lock) { $lock } else { Join-Path $backend "requirements-dev.txt" }
Write-Host "Installing from $reqs"
& $python -m pip install -r $reqs

Write-Host "Done. Run tests: scripts\test.ps1   Run server: scripts\run_dev.ps1"
